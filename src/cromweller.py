#!/usr/bin/env python3
"""Cromweller: Cromwell/WDL wrapper python script
for multiple backends (local, gc, aws)

(Optional)
Add the following comments to your WDL script to specify container images
that Cromweller will use for your WDL. You still need to use them by adding
"--use-docker" or "--use-singularity" to command line arguments.

Example:
#CROMWELLER docker quay.io/encode-dcc/atac-seq-pipeline:v1.1.7.2
#CROMWELLER singularity docker://quay.io/encode-dcc/atac-seq-pipeline:v1.1.7.2

Author:
    Jin Lee (leepc12@gmail.com) at ENCODE-DCC
"""

import argparse
from configparser import ConfigParser
from pyhocon import ConfigFactory, HOCONConverter
import os
import sys
import json
import re
import time
from subprocess import Popen, PIPE, CalledProcessError
from datetime import datetime

from cromwell_rest_api import CromwellRestAPI
from cromweller_uri import URI_S3, URI_GCS, URI_LOCAL, \
    init_cromweller_uri, CromwellerURI
from cromweller_backend import BACKEND_GCP, BACKEND_AWS, BACKEND_LOCAL, \
    CromwellerBackendCommon, CromwellerBackendMySQL, CromwellerBackendGCP, \
    CromwellerBackendAWS, CromwellerBackendLocal, CromwellerBackendSLURM, \
    CromwellerBackendSGE, CromwellerBackendPBS

__version__ = "v0.1.0"

DEFAULT_CROMWELLER_CONF = '~/.cromweller/default.conf'
DEFAULT_CROMWELL_JAR = 'https://github.com/broadinstitute/cromwell/releases/download/38/cromwell-38.jar'
DEFAULT_MYSQL_DB_IP = 'localhost'
DEFAULT_MYSQL_DB_PORT = 3306
DEFAULT_MAX_CONCURRENT_WORKFLOWS = 40
DEFAULT_MAX_CONCURRENT_TASKS = 1000
DEFAULT_PORT = 8000
DEFAULT_IP = 'localhost'
DEFAULT_FORMAT = 'id,status,name,str_label,submission'
DEFAULT_DEEPCOPY_EXT = 'json,tsv'


def parse_cromweller_arguments():
    """Argument parser for Cromweller
    """
    conf_parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    conf_parser.add_argument('-c', '--conf', help='Specify config file',
                             metavar='FILE',
                             default=DEFAULT_CROMWELLER_CONF)
    known_args, remaining_argv = conf_parser.parse_known_args()

    # read conf file if it exists
    defaults = {}

    if known_args.conf is not None:
        # resolve tilde (~) in conf path
        known_args.conf = os.path.expanduser(known_args.conf)
        if os.path.exists(known_args.conf):
            config = ConfigParser()
            config.read([known_args.conf])
            defaults.update(dict(config.items("defaults")))

    parser = argparse.ArgumentParser(parents=[conf_parser])
    subparser = parser.add_subparsers(dest='action')

    # run, server, submit
    parent_backend = argparse.ArgumentParser(add_help=False)
    parent_backend.add_argument(
        '-b', '--backend', help='Backend to run a workflow')

    # run, server
    parent_host = argparse.ArgumentParser(add_help=False)

    group_mysql = parent_host.add_argument_group(
        title='MySQL arguments')
    group_mysql.add_argument(
        '--mysql-db-ip', default=DEFAULT_MYSQL_DB_IP,
        help='MySQL Database IP address (e.g. localhost)')
    group_mysql.add_argument(
        '--mysql-db-port', default=DEFAULT_MYSQL_DB_PORT,
        help='MySQL Database TCP/IP port (e.g. 3306)')
    group_mysql.add_argument(
        '--mysql-db-user', help='MySQL Database username')
    group_mysql.add_argument(
        '--mysql-db-password', help='MySQL Database password')

    group_cromwell = parent_host.add_argument_group(
        title='Cromwell settings')
    group_cromwell.add_argument(
        '--cromwell', default=DEFAULT_CROMWELL_JAR,
        help='Path or URL for Cromwell JAR file')
    group_cromwell.add_argument(
        '--max-concurrent-tasks', default=DEFAULT_MAX_CONCURRENT_TASKS,
        help='Number of concurrent tasks. '
             '"config.concurrent-job-limit" in Cromwell backend configuration '
             'for each backend')
    group_cromwell.add_argument(
        '--max-concurrent-workflows', default=DEFAULT_MAX_CONCURRENT_WORKFLOWS,
        help='Number of concurrent workflows. '
             '"system.max-concurrent-workflows" in backend configuration')
    group_cromwell.add_argument(
        '--use-call-caching', action='store_true',
        help='Use Cromwell\'s call caching, which re-uses outputs from '
             'previous workflows. Make sure to configure MySQL correctly to '
             'use this feature')
    group_cromwell.add_argument(
        '--backend-file',
        help='Custom Cromwell backend configuration file to override all')
    # group_cromwell.add_argument(
    #     '--keep-temp-backend-file', action='store_true',
    #     help='Keep backend.conf file in a temporary directory. '
    #     '(SECURITY WARNING) MySQL database username/password will be '
    #     'exposed in the temporary backend.conf file')

    group_local = parent_host.add_argument_group(
        title='local backend arguments')
    group_local.add_argument(
        '--out-dir', default='.', help='Output directory for local backend')
    group_local.add_argument(
        '--tmp-dir', help='Temporary directory for local backend')

    group_gc = parent_host.add_argument_group(
        title='GC backend arguments')
    group_gc.add_argument('--gc-project', help='GC project')
    group_gc.add_argument(
        '--out-gcs-bucket', help='Output GCS bucket for GC backend')
    group_gc.add_argument(
        '--tmp-gcs-bucket', help='Temporary GCS bucket for GC backend')

    group_aws = parent_host.add_argument_group(
        title='AWS backend arguments')
    group_aws.add_argument('--aws-batch-arn', help='ARN for AWS Batch')
    group_aws.add_argument('--aws-region', help='AWS region (e.g. us-west-1)')
    group_aws.add_argument(
        '--out-s3-bucket', help='Output S3 bucket for AWS backend')
    group_aws.add_argument(
        '--tmp-s3-bucket', help='Temporary S3 bucket for AWS backend')
    group_aws.add_argument(
        '--use-gsutil-over-aws-s3', action='store_true',
        help='Use gsutil instead of aws s3 CLI even for S3 buckets.')

    group_http = parent_host.add_argument_group(
        title='HTTP/HTTPS authentication arguments')
    group_http.add_argument(
        '--http-user',
        help='Username to directly download data from URLs')
    group_http.add_argument(
        '--http-password',
        help='Password to directly download data from URLs')

    # run, submit
    parent_submit = argparse.ArgumentParser(add_help=False)

    parent_submit.add_argument('wdl', help='Path or URL for WDL script')
    parent_submit.add_argument(
        '-i', '--inputs', help='Workflow inputs JSON file')
    parent_submit.add_argument(
        '-o', '--options', help='Workflow options JSON file')
    parent_submit.add_argument(
        '-l', '--label',
        help='String label to identify a workflow submitted to '
             'Cromwell server. This is not Cromwell\'s JSON labels file. '
             'This label is written to Cromwell\'s JSON labels file as '
             'one of the values in it and then later used to find '
             'matching workflows for subcommands "list", "metadata" and '
             '"abort". '
             'DO NOT USE IRREGULAR CHARACTERS. USE LETTERS, NUMBERS, '
             'DASHES AND UNDERSCORES ONLY (^[A-Za-z0-9\\-\\_]+$) '
             'since this label is used to compose a path for '
             'workflow\'s temporary directory (tmp_dir/label/timestamp/)')

    parent_submit.add_argument(
        '--deepcopy', action='store_true',
        help='Deepcopy for JSON (.json), TSV (.tsv) and CSV (.csv) '
             'files specified in an input JSON file (--inputs). '
             'Find all path/URI string values in an input JSON file '
             'and make copies of files on a local/remote storage '
             'for a target backend. Make sure that you have installed '
             'gsutil for GCS and aws for S3.')
    parent_submit.add_argument(
        '--deepcopy-ext', default=DEFAULT_DEEPCOPY_EXT,
        help='Comma-separated list of file extensions to be deepcopied')

    group_dep = parent_submit.add_argument_group(
        title='dependency resolver for all backends',
        description=''
        'Cloud-based backends (gc and aws) will only use Docker '
        'so that "--docker URI_FOR_DOCKER_IMG" must be specified '
        'in the command line argument or as a comment "#CROMWELLER '
        'docker URI_FOR_DOCKER_IMG" in a WDL file')
    group_dep.add_argument(
        '--docker', help='URI for Docker image (e.g. ubuntu:latest). '
        'Defining it automatically turn on flag "--use-docker"')
    group_dep.add_argument(
        '--use-docker', action='store_true',
        help='Use Singularity to resolve dependency for local backend.')
    group_dep_local = parent_submit.add_argument_group(
        title='dependency resolver for local backend',
        description=''
        'Singularity is for local backend only. Other backends '
        '(gcp and aws) will use Docker only. '
        'Local backend defaults to not use any container-based methods. '
        'Activate "--use-singularity" or "--use-docker" to use containers')
    group_dep_local.add_argument(
        '--singularity',
        help='URI or path for Singularity image '
             '(e.g. ~/.singularity/ubuntu-latest.simg, '
             'docker://ubuntu:latest, shub://vsoch/hello-world). '
             'Defining it automatically turn on flag "--use-singularity"')
    group_dep_local.add_argument(
        '--use-singularity', action='store_true',
        help='Use Singularity to resolve dependency for local backend.')

    group_slurm = parent_submit.add_argument_group('SLURM arguments')
    group_slurm.add_argument('--slurm-partition', help='SLURM partition')
    group_slurm.add_argument('--slurm-account', help='SLURM account')
    group_slurm.add_argument(
        '--slurm-extra-param',
        help='SLURM extra parameters. Must be double-quoted')

    group_sge = parent_submit.add_argument_group('SGE arguments')
    group_sge.add_argument(
        '--sge-pe', help='SGE parallel environment. Check with "qconf -spl"')
    group_sge.add_argument(
        '--sge-queue', help='SGE queue. Check with "qconf -sql"')
    group_sge.add_argument(
        '--sge-extra-param',
        help='SGE extra parameters. Must be double-quoted')

    group_pbs = parent_submit.add_argument_group('PBS arguments')
    group_pbs.add_argument(
        '--pbs-queue', help='PBS queue')
    group_pbs.add_argument(
        '--pbs-extra-param',
        help='PBS extra parameters. Must be double-quoted')

    # list, metadata, abort
    parent_search_wf = argparse.ArgumentParser(add_help=False)
    parent_search_wf.add_argument(
        'wf_id_or_label', nargs='*',
        help='List of workflow IDs to find matching workflows to '
             'commit a specified action (list, metadata and abort). '
             'Wildcards (* and ?) are allowed.')

    parent_server_client = argparse.ArgumentParser(add_help=False)
    parent_server_client.add_argument(
        '-p', '--port', default=DEFAULT_PORT,
        help='Port for Cromweller server')
    parent_client = argparse.ArgumentParser(add_help=False)
    parent_client.add_argument(
        '--ip', default=DEFAULT_IP,
        help='IP address for Cromweller server')
    parent_client.add_argument(
        '--user',
        help='Username for HTTP auth to connect to Cromwell server')
    parent_client.add_argument(
        '--password',
        help='Password for HTTP auth to connect to Cromwell server')
    parent_list = argparse.ArgumentParser(add_help=False)
    parent_list.add_argument(
        '-f', '--format', default=DEFAULT_FORMAT,
        help='Comma-separated list of items to be shown for "list" '
        'subcommand. Any key name in workflow JSON from Cromwell '
        'server\'s response is allowed. '
        'Available keys are "id" (workflow ID), "status", "str_label", '
        '"name" (WDL/CWL name), "submission" (date/time), "start", "end". '
        '"str_label" is a special key for Cromweller. See help context '
        'of "--label" for details')

    p_run = subparser.add_parser(
        'run', help='Run a single workflow without server',
        parents=[parent_submit, parent_host, parent_backend])
    p_server = subparser.add_parser(
        'server', help='Run a Cromwell server',
        parents=[parent_server_client, parent_host, parent_backend])
    p_submit = subparser.add_parser(
        'submit', help='Submit a workflow to a Cromwell server',
        parents=[parent_server_client, parent_client, parent_submit,
                 parent_backend])
    p_abort = subparser.add_parser(
        'abort', help='Abort running/pending workflows on a Cromwell server',
        parents=[parent_server_client, parent_client, parent_search_wf])
    p_list = subparser.add_parser(
        'list', help='List running/pending workflows on a Cromwell server',
        parents=[parent_server_client, parent_client, parent_search_wf,
                 parent_list])
    p_metadata = subparser.add_parser(
        'metadata',
        help='Retrieve metadata JSON for workflows from a Cromwell server',
        parents=[parent_server_client, parent_client, parent_search_wf])

    for p in [p_run, p_server, p_submit, p_abort, p_list, p_metadata]:
        p.set_defaults(**defaults)

    if len(sys.argv[1:]) == 0:
        parser.print_help()
        parser.exit()
    # parse all args
    args = parser.parse_args(remaining_argv)

    # convert to dict
    args_d = vars(args)

    # init some important path variables
    if args_d.get('out_dir') is None:
        args_d['out_dir'] = os.getcwd()

    if args_d.get('tmp_dir') is None:
        args_d['tmp_dir'] = os.path.join(args_d['out_dir'], 'cromweller_tmp')

    if args_d.get('tmp_s3_bucket') is None:
        if args_d.get('out_s3_bucket'):
            args_d['tmp_s3_bucket'] = os.path.join(args_d['out_s3_bucket'],
                                                   'cromweller_tmp')

    if args_d.get('tmp_gcs_bucket') is None:
        if args_d.get('out_gcs_bucket'):
            args_d['tmp_gcs_bucket'] = os.path.join(args_d['out_gcs_bucket'],
                                                    'cromweller_tmp')
    return args_d


def merge_dict(a, b, path=None):
    """Merge b into a recursively. This mutates a and overwrites
    items in b on a for conflicts.

    Ref: https://stackoverflow.com/questions/7204805/dictionaries
    -of-dictionaries-merge/7205107#7205107
    """
    if path is None:
        path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_dict(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]


class Cromweller(object):
    """Cromwell/WDL wrapper
    """

    BACKEND_CONF_HEADER = 'include required(classpath("application"))\n'
    DEFAULT_BACKEND = BACKEND_LOCAL
    RE_PATTERN_BACKEND_CONF_HEADER = r'^[\s]*include\s'
    RE_PATTERN_WDL_COMMENT_DOCKER = r'^\s*\#\s*CROMWELLER\s+docker\s(.+)'
    RE_PATTERN_WDL_COMMENT_SINGULARITY = r'^\s*\#\s*CROMWELLER\s+singularity\s(.+)'
    RE_PATTERN_WORKFLOW_ID = r'started WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)'
    RE_PATTERN_FINISHED_WORKFLOW_ID = r'WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b) is in a terminal state'
    RE_PATTERN_VALID_LABEL = r'^[A-Za-z0-9\-\_]+$'
    SEC_INTERVAL_CHK_WORKFLOW_DONE = 60.0

    def __init__(self, args):
        """Initializes from args dict
        """
        # init REST API
        self._port = args.get('port')
        self._cromwell_rest_api = CromwellRestAPI(
            ip=args.get('ip'), port=self._port, verbose=False)

        # init others
        # self._keep_temp_backend_file = args.get('keep_temp_backend_file')
        self._format = args.get('format')
        self._use_call_caching = args.get('use_call_caching')
        self._max_concurrent_workflows = args.get('max_concurrent_workflows')
        self._max_concurrent_tasks = args.get('max_concurrent_tasks')
        self._tmp_dir = args.get('tmp_dir')
        self._out_dir = args.get('out_dir')
        self._gc_project = args.get('gc_project')
        self._out_gcs_bucket = args.get('out_gcs_bucket')
        self._out_s3_bucket = args.get('out_s3_bucket')
        self._aws_batch_arn = args.get('aws_batch_arn')
        self._aws_region = args.get('aws_region')
        self._slurm_partition = args.get('slurm_partition')
        self._slurm_account = args.get('slurm_account')
        self._slurm_extra_param = args.get('slurm_extra_param')
        self._sge_pe = args.get('sge_pe')
        self._sge_queue = args.get('sge_queue')
        self._sge_extra_param = args.get('sge_extra_param')
        self._pbs_queue = args.get('pbs_queue')
        self._pbs_extra_param = args.get('pbs_extra_param')
        self._mysql_db_ip = args.get('mysql_db_ip')
        self._mysql_db_port = args.get('mysql_db_port')
        self._mysql_db_user = args.get('mysql_db_user')
        self._mysql_db_password = args.get('mysql_db_password')
        self._backend_file = args.get('backend_file')
        self._wdl = args.get('wdl')
        self._inputs = args.get('inputs')
        self._cromwell = args.get('cromwell')
        self._backend = args.get('backend')
        if self._backend is not None and self._backend == 'local':
            self._backend = BACKEND_LOCAL  # Local (capital L)
        self._workflow_opts = args.get('options')
        self._label = args.get('label')

        # deepcopy
        self._deepcopy = args.get('deepcopy')
        self._deepcopy_ext = args.get('deepcopy_ext')
        if self._deepcopy_ext is not None:
            self._deepcopy_ext = [
                '.'+ext for ext in self._deepcopy_ext.split(',')]

        # containers
        self._use_singularity = args.get('use_singularity')
        self._use_docker = args.get('use_docker')
        self._singularity = args.get('singularity')
        self._docker = args.get('docker')
        if self._singularity is not None:
            self._use_singularity = True
        if self._docker is not None:
            self._use_docker = True

        # list of values
        self._wf_id_or_label = args.get('wf_id_or_label')

        if self._backend is None:
            self._backend = Cromweller.DEFAULT_BACKEND

    def run(self):
        """Run a workflow using Cromwell run mode
        """
        timestamp = Cromweller.__get_time_str()
        if self._label is not None:
            # check if label is valid
            r = re.findall(Cromweller.RE_PATTERN_VALID_LABEL, self._label)
            if len(r) != 1:
                raise ValueError('Invalid label.')
            suffix = os.path.join(
                self._label, timestamp)
        else:
            # otherwise, use WDL basename
            suffix = os.path.join(
                self.__get_wdl_basename(), timestamp)
        tmp_dir = self.__mkdir_tmp_dir(suffix)

        # all input files
        backend_file = self.__create_backend_conf_file(tmp_dir)
        input_file = self.__get_input_json_file(tmp_dir)
        workflow_opts_file = self.__create_workflow_opts_json_file(tmp_dir)

        # metadata JSON file is an output from Cromwell
        #   place it on the tmp dir
        metadata_file = os.path.join(tmp_dir, 'metadata.json')

        # LOG_LEVEL must be >=INFO to catch workflow ID from STDOUT
        cmd = ['java', '-DLOG_LEVEL=INFO', '-jar',
               '-Dconfig.file={}'.format(backend_file),
               CromwellerURI(self._cromwell).get_local_file(), 'run',
               CromwellerURI(self._wdl).get_local_file(), '-i', input_file,
               '-o', workflow_opts_file, '-m', metadata_file]
        print('[Cromweller] cmd: ', cmd)

        if self._label is not None:
            # create labels JSON file
            labels_file = os.path.join(tmp_dir, 'labels.json')
            with open(labels_file, 'w') as fp:
                fp.write('{{ "{key}":"{val}" }}'.format(
                    key=CromwellRestAPI.KEY_LABEL,
                    val=self._label))
            cmd += ['-l', labels_file]

        try:
            p = Popen(cmd, stdout=PIPE, universal_newlines=True, cwd=tmp_dir)
            workflow_id = None
            rc = None
            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')
                # find workflow id from STDOUT
                if workflow_id is None:
                    wf_ids_with_status = \
                        Cromweller.__get_workflow_ids_from_cromwell_stdout(
                            stdout)
                    for wf_id, status in wf_ids_with_status:
                        if status == 'submitted' or status == 'finished':
                            workflow_id = wf_id
                            break
                # else:
                #     # remove temp backend_file for security
                #     #    (MySQL database password in it)
                #     if os.path.exists(backend_file) \
                #         and (self._keep_temp_backend_file is None \
                #             or not self._keep_temp_backend_file):
                #         os.remove(backend_file)

                print(stdout)
            rc = p.poll()
        except CalledProcessError as e:
            rc = e.returncode
        except KeyboardInterrupt:
            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')
                print(stdout)

        # move metadata Json file to workflow's output directory
        if workflow_id is not None and os.path.exists(metadata_file):
            metadata_uri = os.path.join(
                self.__get_workflow_output_dir(workflow_id),
                'metadata.json')
            with open(metadata_file, 'r') as fp:
                CromwellerURI(metadata_uri).write_str_to_file(fp.read())
            os.remove(metadata_file)
        else:
            metadata_uri = None

        print('[Cromweller] run: ', rc, workflow_id, metadata_uri)
        return workflow_id

    def server(self):
        """Run a Cromwell server
        """
        tmp_dir = self.__mkdir_tmp_dir()
        backend_file = self.__create_backend_conf_file(tmp_dir)
        # LOG_LEVEL must be >=INFO to catch workflow ID from STDOUT
        cmd = ['java', '-DLOG_LEVEL=INFO', '-jar',
               '-Dconfig.file={}'.format(backend_file),
               CromwellerURI(self._cromwell).get_local_file(), 'server']
        print('[Cromweller] cmd: ', cmd)

        # pending/running workflows
        workflow_ids = set()
        # completed, aborted or terminated workflows
        finished_workflow_ids = set()
        try:
            p = Popen(cmd, stdout=PIPE, universal_newlines=True, cwd=tmp_dir)
            rc = None
            # tickcount
            t0 = time.perf_counter()

            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')

                # find workflow id from STDOUT
                wf_ids_with_status = \
                    Cromweller.__get_workflow_ids_from_cromwell_stdout(stdout)
                for wf_id, status in wf_ids_with_status:
                    if status == 'submitted':
                        workflow_ids.add(wf_id)
                    elif status == 'finished':
                        finished_workflow_ids.add(wf_id)
                print(stdout)

                # # write metadata.json for running/just-finished workflows
                # t1 = time.perf_counter()
                # if (t1 - t0) > \
                #     Cromweller.SEC_INTERVAL_CHK_WORKFLOW_DONE:
                #     t0 = t1
                #     # check if any submitted workflow finished
                #     wfs_to_req_metadata = set()
                #     for wf_id in finished_workflow_ids:
                #         if wf_id in workflow_ids:
                #             wfs_to_req_metadata.add(wf_id)
                #             workflow_ids.remove(wf_id)
                #     for wf_id in workflow_ids:
                #         wfs_to_req_metadata.add(wf_id)
                #     # get metadata for running/just-finished workflows
                #     metadata = self._cromwell_rest_api.get_metadata(wfs_to_req_metadata)
                #     # for m in metadata:
                #     #     wf_id = m['id']
                #     # move metadata Json file
                #     if workflow_id is not None and os.path.exists(metadata_file):
                #         metadata_uri = os.path.join(
                #             self.__get_workflow_output_dir(workflow_id),
                #             'metadata.json')
                #         with open(metadata_file, 'r') as fp:
                #             CromwellerURI(uri).write_str_to_file(fp.read())
                #         os.remove(metadata_file)
                #     else:
                #         metadata_uri = None

        except CalledProcessError as e:
            rc = e.returncode
        except KeyboardInterrupt:
            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')
                print(stdout)
        print('[Cromweller] server: ', rc, workflow_ids, finished_workflow_ids)
        return rc

    def submit(self):
        """Submit a workflow to Cromwell server
        """
        timestamp = Cromweller.__get_time_str()
        if self._label is not None:
            # check if label is valid
            r = re.findall(Cromweller.RE_PATTERN_VALID_LABEL, self._label)
            if len(r) != 1:
                raise ValueError('Invalid label.')
            suffix = os.path.join(
                self._label, timestamp)
        else:
            # otherwise, use WDL basename
            suffix = os.path.join(
                self.__get_wdl_basename(), timestamp)
        tmp_dir = self.__mkdir_tmp_dir(suffix)

        # all input files
        input_file = self.__get_input_json_file(tmp_dir)
        workflow_opts_file = self.__create_workflow_opts_json_file(tmp_dir)

        r = self._cromwell_rest_api.submit(
            source=CromwellerURI(self._wdl).get_local_file(),
            dependencies=None,
            inputs_file=input_file,
            options_file=workflow_opts_file,
            str_label=self._label)
        print("[Cromweller] submit: ", r)
        return r

    def abort(self):
        """Abort running/pending workflows on a Cromwell server
        """
        r = self._cromwell_rest_api.abort(self._wf_id_or_label,
                                          self._wf_id_or_label)
        print("[Cromweller] abort: ", r)
        return r

    def metadata(self):
        """Retrieve metadata for workflows from a Cromwell server
        """
        m = self._cromwell_rest_api.get_metadata(self._wf_id_or_label,
                                                 self._wf_id_or_label)
        print(json.dumps(m, indent=4))
        return m

    def list(self):
        """Get list of running/pending workflows from a Cromwell server
        """
        # if not argument, list all workflows using wildcard (*)
        if self._wf_id_or_label is None or len(self._wf_id_or_label) == 0:
            workflow_ids = ['*']
            str_labels = ['*']
        else:
            workflow_ids = self._wf_id_or_label
            str_labels = self._wf_id_or_label
        workflows = self._cromwell_rest_api.find(
            workflow_ids=workflow_ids,
            str_labels=str_labels)
        formats = self._format.split(',')
        print('\t'.join(formats))

        if workflows is None:
            return None
        for w in workflows:
            row = []
            workflow_id = w['id'] if 'id' in w else None
            for f in formats:
                if f == 'workflow_id':
                    row.append(str(workflow_id))
                elif f == 'str_label':
                    lbl = self._cromwell_rest_api.get_str_label(workflow_id)
                    row.append(str(lbl))
                else:
                    row.append(str(w[f] if f in w else None))
            print('\t'.join(row))
        return workflows

    def __create_backend_conf_file(self, directory, fname='backend.conf'):
        """Creates Cromwell's backend conf file
        """
        backend_str = self.__get_backend_conf_str()
        backend_file = os.path.join(directory, fname)
        with open(backend_file, 'w') as fp:
            fp.write(backend_str)
        return backend_file

    def __get_input_json_file(
            self, directory, fname='inputs.json'):
        """Make a copy of input JSON file.
        Deepcopy to a specified storage if required.
        """
        if self._inputs is not None:
            c = CromwellerURI(self._inputs)
            if self._deepcopy and self._deepcopy_ext:
                # deepcopy all files in JSON/TSV/CSV
                #   to the target backend
                if self._backend == BACKEND_GCP:
                    uri_type = URI_GCS
                elif self._backend == BACKEND_AWS:
                    uri_type = URI_S3
                else:
                    uri_type = URI_LOCAL
                c = c.deepcopy(uri_type=uri_type, uri_exts=self._deepcopy_ext)
            return c.get_local_file()
        else:
            input_file = os.path.join(directory, fname)
            with open(input_file, 'w') as fp:
                fp.write('{}')
            return input_file

    def __create_workflow_opts_json_file(
            self, directory, fname='workflow_opts.json'):
        """Creates Cromwell's workflow options JSON file

        Items written to workflow options JSON file:
            * very important backend
            backend: a backend to run workflows on

            * important dep resolver
            docker: docker image URI (e.g. ubuntu:latest)
            singularity: singularity image URI (docker://, shub://)

            * SLURM params (can also be defined in backend conf file)
            slurm_partition
            slurm_account
            slurm_extra_param

            * SGE params (can also be defined in backend conf file)
            sge_pe
            sge_queue
            sge_extra_param

            * PBS params (can also be defined in backend conf file)
            pbs_queue
            pbs_extra_param
        """
        template = {
            'default_runtime_attributes': {}
        }

        if self._backend is not None:
            template['backend'] = \
                self._backend

        # find docker/singularity from WDL or command line args
        docker_from_wdl = self.__find_docker_from_wdl()
        # automatically add docker_from_wdl for cloud backend
        if docker_from_wdl is not None \
                and self._backend in (BACKEND_GCP, BACKEND_AWS):
            template['default_runtime_attributes']['docker'] = docker_from_wdl
        elif self._use_docker:
            if self._docker is None:
                docker = docker_from_wdl
            else:
                docker = self._docker
            assert(docker is not None)
            template['default_runtime_attributes']['docker'] = docker

        singularity_from_wdl = self.__find_singularity_from_wdl()
        if self._use_singularity:
            if self._singularity is None:
                singularity = singularity_from_wdl
            else:
                singularity = self._singularity
            assert(singularity is not None)
            template['default_runtime_attributes']['singularity'] = singularity

        if self._slurm_partition is not None:
            template['default_runtime_attributes']['slurm_partition'] = \
                self._slurm_partition
        if self._slurm_account is not None:
            template['default_runtime_attributes']['slurm_account'] = \
                self._slurm_account
        if self._slurm_extra_param is not None:
            template['default_runtime_attributes']['slurm_extra_param'] = \
                self._slurm_extra_param

        if self._pbs_queue is not None:
            template['default_runtime_attributes']['pbs_queue'] = \
                self._pbs_queue
        if self._pbs_extra_param is not None:
            template['default_runtime_attributes']['pbs_extra_param'] = \
                self._pbs_extra_param

        if self._sge_pe is not None:
            template['default_runtime_attributes']['sge_pe'] = \
                self._sge_pe
        if self._sge_queue is not None:
            template['default_runtime_attributes']['sge_queue'] = \
                self._sge_queue
        if self._sge_extra_param is not None:
            template['default_runtime_attributes']['sge_extra_param'] = \
                self._sge_extra_param

        # if workflow opts file is given by a user, merge it to template
        if self._workflow_opts is not None:
            f = CromwellerURI(self._workflow_opts).get_local_file()
            with open(f, 'r') as fp:
                d = json.loads(fp.read())
                merge_dict(template, d)

        # write it
        workflow_opts_file = os.path.join(directory, fname)
        with open(workflow_opts_file, 'w') as fp:
            fp.write(json.dumps(template, indent=4))
            fp.write('\n')

        return workflow_opts_file

    def __find_docker_from_wdl(self):
        return self.__find_var_from_wdl(
            Cromweller.RE_PATTERN_WDL_COMMENT_DOCKER)

    def __find_singularity_from_wdl(self):
        return self.__find_var_from_wdl(
            Cromweller.RE_PATTERN_WDL_COMMENT_SINGULARITY)

    def __find_var_from_wdl(self, regex_var):
        if self._wdl is not None:
            with open(CromwellerURI(self._wdl).get_local_file(), 'r') as fp:
                for line in fp.readlines():
                    r = re.findall(regex_var, line)
                    if len(r) > 0:
                        ret = r[0].strip()
                        if len(ret) > 0:
                            return ret
        return None

    def __get_backend_conf_str(self):
        """
        Initializes the following backend stanzas,
        which are defined in "backend" {} in a Cromwell's backend
        configuration file:
            1) local: local backend
            2) gc: Google Cloud backend (optional)
            3) aws: AWS backend (optional)
            4) slurm: SLURM (optional)
            5) sge: SGE (optional)
            6) pbs: PBS (optional)

        Also, initializes the following common non-"backend" stanzas:
            a) common: base stanzas
            b) mysql: connect to MySQL (optional)

        Then converts it to a HOCON string
        """
        # init backend dict
        backend_dict = {}

        # common stanza for backend conf file
        merge_dict(
            backend_dict,
            CromwellerBackendCommon(
                port=self._port,
                use_call_caching=self._use_call_caching,
                max_concurrent_workflows=self._max_concurrent_workflows))

        # local backend
        merge_dict(
            backend_dict,
            CromwellerBackendLocal(
                out_dir=self._out_dir,
                concurrent_job_limit=self._max_concurrent_tasks))
        # GC
        if self._gc_project is not None and self._out_gcs_bucket is not None:
            merge_dict(
                backend_dict,
                CromwellerBackendGCP(
                    gc_project=self._gc_project,
                    out_gcs_bucket=self._out_gcs_bucket,
                    concurrent_job_limit=self._max_concurrent_tasks))
        # AWS
        if self._aws_batch_arn is not None and self._aws_region is not None \
                and self._out_s3_bucket is not None:
            merge_dict(
                backend_dict,
                CromwellerBackendAWS(
                    aws_batch_arn=self._aws_batch_arn,
                    aws_region=self._aws_region,
                    out_s3_bucket=self._out_s3_bucket,
                    concurrent_job_limit=self._max_concurrent_tasks))
        # SLURM
        merge_dict(
            backend_dict,
            CromwellerBackendSLURM(
                partition=self._slurm_partition,
                account=self._slurm_account,
                extra_param=self._slurm_extra_param,
                concurrent_job_limit=self._max_concurrent_tasks))
        # SGE
        merge_dict(
            backend_dict,
            CromwellerBackendSGE(
                pe=self._sge_pe,
                queue=self._sge_queue,
                extra_param=self._sge_extra_param,
                concurrent_job_limit=self._max_concurrent_tasks))

        # PBS
        merge_dict(
            backend_dict,
            CromwellerBackendPBS(
                queue=self._pbs_queue,
                extra_param=self._pbs_extra_param,
                concurrent_job_limit=self._max_concurrent_tasks))

        # MySQL is optional
        if self._mysql_db_user is not None \
                and self._mysql_db_password is not None:
            merge_dict(
                backend_dict,
                CromwellerBackendMySQL(
                    ip=self._mysql_db_ip,
                    port=self._mysql_db_port,
                    user=self._mysql_db_user,
                    password=self._mysql_db_password))

        # set header for conf ("include ...")
        assert(Cromweller.BACKEND_CONF_HEADER.endswith('\n'))
        lines_header = [Cromweller.BACKEND_CONF_HEADER]

        # override with user-specified backend.conf if exists
        if self._backend_file is not None:
            lines_wo_header = []

            with open(CromwellerURI(self._backend_file).get_local_file(),
                      'r') as fp:
                for line in fp.readlines():
                    # find header and exclude
                    if re.findall(Cromweller.RE_PATTERN_BACKEND_CONF_HEADER,
                                  line):
                        if line not in lines_header:
                            lines_header.append(line)
                    else:
                        lines_wo_header.append(line)

            # parse HOCON to JSON to dict
            c = ConfigFactory.parse_string(''.join(lines_wo_header))
            j = HOCONConverter.to_json(c)
            d = json.loads(j)
            # apply to backend conf
            merge_dict(backend_dict, d)

        # use default backend (local) if not specified
        if self._backend is not None:
            backend_dict['backend']['default'] = self._backend
        else:
            backend_dict['backend']['default'] = Cromweller.DEFAULT_BACKEND

        # dict to HOCON (excluding header)
        backend_hocon = ConfigFactory.from_dict(backend_dict)
        # write header to HOCON string
        backend_str = ''.join(lines_header)
        # convert HOCON to string
        backend_str += HOCONConverter.to_hocon(backend_hocon)

        return backend_str

    def __mkdir_tmp_dir(self, suffix=''):
        """Create a temporary directory (self._tmp_dir/suffix)
        """
        tmp_dir = os.path.join(self._tmp_dir, suffix)
        os.makedirs(tmp_dir, exist_ok=True)
        return tmp_dir

    def __get_workflow_output_dir(self, workflow_id=''):
        if self._backend == BACKEND_GCP:
            out_dir = self._out_gcs_bucket
        elif self._backend == BACKEND_AWS:
            out_dir = self._out_aws_bucket
        else:
            out_dir = self._out_dir

        wdl = self.__get_wdl_basename()
        if wdl is None:
            path = os.path.join(out_dir, workflow_id)
        else:
            path = os.path.join(out_dir, os.path.basename(wdl), workflow_id)

        if self._backend not in (BACKEND_GCP, BACKEND_AWS):
            os.makedirs(path, exist_ok=True)
        return path

    def __get_wdl_basename(self):
        if self._wdl is not None:
            wdl, _ = os.path.splitext(self._wdl)
            return os.path.basename(wdl)
        else:
            return None

    @staticmethod
    def __get_workflow_ids_from_cromwell_stdout(stdout):
        result = []
        for line in stdout.split('\n'):
            r1 = re.findall(Cromweller.RE_PATTERN_WORKFLOW_ID, line)
            if len(r1) > 0:
                result.append((r1[0].strip(), 'submitted'))
            r2 = re.findall(Cromweller.RE_PATTERN_FINISHED_WORKFLOW_ID, line)
            if len(r2) > 0:
                result.append((r2[0].strip(), 'finished'))
        return result

    @staticmethod
    def __get_time_str():
        return datetime.now().strftime('%Y%m%d_%H%M%S_%f')


def main():
    # parse arguments
    #   note that args is a dict
    args = parse_cromweller_arguments()

    # init cromweller uri to transfer files across various storages
    #   e.g. gs:// to s3://, http:// to local, ...
    init_cromweller_uri(
        tmp_dir=args.get('tmp_dir'),
        tmp_s3_bucket=args.get('tmp_s3_bucket'),
        tmp_gcs_bucket=args.get('tmp_gcs_bucket'),
        http_user=args.get('http_user'),
        http_password=args.get('http_password'),
        use_gsutil_over_aws_s3=args.get('use_gsutil_over_aws_s3'),
        verbose=True)

    # init cromweller: taking all args at init step
    c = Cromweller(args)

    action = args['action']
    if action == 'run':
        c.run()
    elif action == 'server':
        c.server()
    elif action == 'submit':
        c.submit()
    elif action == 'abort':
        c.abort()
    elif action == 'list':
        c.list()
    elif action == 'metadata':
        c.metadata()
    else:
        raise Exception('Unsupported or unspecified action.')
    return 0


if __name__ == '__main__':
    main()
