#!/usr/bin/env python3
"""Cromweller: Cromwell/WDL wrapper python script
for multiple backends (local, gc, aws)

(Optional)
Add the following comments to your WDL script to specify container images
that Cromweller will use for your WDL.

Example:
#CROMWELLER docker quay.io/encode-dcc/atac-seq-pipeline:v1.1.7.2
#CROMWELLER singularity docker://quay.io/encode-dcc/atac-seq-pipeline:v1.1.7.2
"""

import argparse
import configparser
import os
import sys
import json
import subprocess
import re
import time
from datetime import datetime

import cromweller_backend as cb
import cromweller_uri as cu
from pyhocon import ConfigFactory, HOCONConverter


DEFAULT_CROMWELLER_CONF = '~/.cromweller/default.conf'
DEFAULT_CROMWELL_JAR = 'https://github.com/broadinstitute/cromwell/releases/download/38/cromwell-38.jar'
DEFAULT_MYSQL_DB_IP = 'localhost'
DEFAULT_MYSQL_DB_PORT = 3306
DEFAULT_NUM_CONCURRENT_WORKFLOWS = 40
DEFAULT_NUM_CONCURRENT_TASKS = 1000
DEFAULT_SERVER_PORT = 8000
DEFAULT_SERVER_IP = 'localhost'

def parse_cromweller_arguments():
    """Argument parser for Cromweller
    """
    conf_parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    conf_parser.add_argument('-c', '--conf',
        help='Specify config file',
        metavar='FILE',
        default=DEFAULT_CROMWELLER_CONF)
    known_args, remaining_argv = conf_parser.parse_known_args()

    # read conf file if it exists
    defaults = {}
    if known_args.conf and os.path.exists(known_args.conf):
        config = configparser.ConfigParser()
        config.read([known_args.conf])
        defaults.update(dict(config.items("defaults")))

    parser = argparse.ArgumentParser(parents=[conf_parser])
    subparser = parser.add_subparsers(dest='action')

    # run, server, submit 
    parent_backend = argparse.ArgumentParser(add_help=False)
    parent_backend.add_argument('-b', '--backend',
        help='Backend to run a workflow')

    # run, server
    parent_host = argparse.ArgumentParser(add_help=False)

    group_mysql = parent_host.add_argument_group(
        title='MySQL arguments')
    group_mysql.add_argument('--mysql-db-ip',
        default=DEFAULT_MYSQL_DB_IP,
        help='MySQL Database IP address (e.g. localhost)')
    group_mysql.add_argument('--mysql-db-port',
        default=DEFAULT_MYSQL_DB_PORT,
        help='MySQL Database TCP/IP port (e.g. 3306)')
    group_mysql.add_argument('--mysql-db-user',
        help='MySQL Database username')
    group_mysql.add_argument('--mysql-db-password',
        help='MySQL Database password')

    group_cromwell = parent_host.add_argument_group(
        title='Cromwell settings')
    group_cromwell.add_argument('--cromwell',
        default=DEFAULT_CROMWELL_JAR,
        help='Path or URL for Cromwell JAR file')
    group_cromwell.add_argument('--num-concurrent-tasks',
        default=DEFAULT_NUM_CONCURRENT_TASKS,
        help='Number of concurrent tasks. '
            '"config.concurrent-job-limit" in Cromwell backend configuration '
            'for each backend')
    group_cromwell.add_argument('--num-concurrent-workflows',
        default=DEFAULT_NUM_CONCURRENT_WORKFLOWS,
        help='Number of concurrent workflows. '
            '"system.max-concurrent-workflows" in backend configuration')
    group_cromwell.add_argument('--use-call-caching',
        action='store_true',
        help='Use Cromwell\'s call caching, which re-uses outputs from previous workflows. '
            'Make sure to configure MySQL correctly to use this feature')
    group_cromwell.add_argument('--backend-conf',
        help='Custom Cromwell backend configuration file to override all')

    group_local = parent_host.add_argument_group(
        title='local backend arguments')
    group_local.add_argument('--out-dir',
        default='.',
        help='Output directory for local backend')
    group_local.add_argument('--tmp-dir',
        help='Temporary directory for local backend')

    group_gc = parent_host.add_argument_group(
        title='GC backend arguments')
    group_gc.add_argument('--gc-project',
        help='GC project')
    group_gc.add_argument('--out-gcs-bucket',
        help='Output GCS bucket for GC backend')
    group_gc.add_argument('--tmp-gcs-bucket',
        help='Temporary GCS bucket for GC backend')

    group_aws = parent_host.add_argument_group(
        title='AWS backend arguments')
    group_aws.add_argument('--aws-batch-arn',
        help='ARN for AWS Batch')
    group_aws.add_argument('--aws-region',
        help='AWS region (e.g. us-west-1)')
    group_aws.add_argument('--out-s3-bucket',
        help='Output S3 bucket for AWS backend')
    group_aws.add_argument('--tmp-s3-bucket',
        help='Temporary S3 bucket for AWS backend')
    group_aws.add_argument('--use-gsutil-over-aws-s3',
        action='store_true',
        help='Use gsutil instead of aws s3 CLI even for S3 buckets.')

    # run, submit
    parent_submit = argparse.ArgumentParser(add_help=False)

    parent_submit.add_argument('wdl',
        help='Path or URL for WDL script')
    parent_submit.add_argument('-i', '--inputs',
        help='Workflow inputs JSON file')
    parent_submit.add_argument('-o', '--options',
        help='Workflow options JSON file')
    parent_submit.add_argument('--deep-copy',
        help='Deep-copy for JSON (.json), TSV (.tsv) and CSV (.csv) '
            'files specified in an input JSON file (--inputs). '
            'Find all string values in an input JSON file '
            'and make copies of files on a local/remote storage '
            'for a target backend. Make sure that you have installed '
            'gsutil for GCS and aws for S3.')

    group_dep = parent_submit.add_argument_group(
        title='dependency resolver for all backends',
        description='Cloud-based backends (gc and aws) will only use Docker '
            'so that "--docker URI_FOR_DOCKER_IMG" must be specified '
            'in the command line argument or as a comment "#CROMWELLER '
            'docker URI_FOR_DOCKER_IMG" in a WDL file')
    group_dep.add_argument('--docker',
        help='URI for Docker image (e.g. ubuntu:latest)')

    group_dep_local = parent_submit.add_argument_group(
        title='dependency resolver for local backend',
        description='Singularity is for local backend only. Other backends '
            '(gc and aws) will use Docker. '
            'Local backend defaults not to use any container-based methods. '
            'Activate --use-singularity or --use-docker to use one of them')
    group_dep_local.add_argument('--singularity',
        help='URI or path for Singularity image '
            '(e.g. ~/.singularity/ubuntu-latest.simg, '
            'docker://ubuntu:latest, shub://vsoch/hello-world)')
    group_dep_local.add_argument('--use-singularity',
        help='Use Singularity to resolve dependency for local backend.',
        action='store_true')
    group_dep_local.add_argument('--use-docker',
        help='Use Singularity to resolve dependency for local backend.',
        action='store_true')

    group_slurm = parent_submit.add_argument_group('SLURM arguments')
    group_slurm.add_argument('--slurm-partition',
        help='SLURM partition')
    group_slurm.add_argument('--slurm-account',
        help='SLURM account')
    group_slurm.add_argument('--slurm-extra-param',
        help='SLURM extra parameters. Must be double-quoted')

    group_sge = parent_submit.add_argument_group('SGE arguments')
    group_sge.add_argument('--sge-pe',
        help='SGE parallel environment. Check with "qconf -spl"')
    group_sge.add_argument('--sge-queue',
        help='SGE queue. Check with "qconf -sql"')
    group_sge.add_argument('--sge-extra-param',
        help='SGE extra parameters. Must be double-quoted')

    group_pbs = parent_submit.add_argument_group('PBS arguments')
    group_pbs.add_argument('--pbs-queue',
        help='PBS queue')
    group_pbs.add_argument('--pbs-extra-param',
        help='PBS extra parameters. Must be double-quoted')

    # list, cancel
    parent_wf_id = argparse.ArgumentParser(add_help=False)
    parent_wf_id.add_argument('-w', '--workflow-ids',
        nargs='+',
        help='Workflow IDs')

    # submit, list, cancel
    parent_label = argparse.ArgumentParser(add_help=False)
    parent_label.add_argument('-l', '--labels',
        nargs='+',
        help='Labels')

    parent_server_client = argparse.ArgumentParser(add_help=False)
    parent_server_client.add_argument('--server-port',
        default=DEFAULT_SERVER_PORT,
        help='Port for Cromweller server')
    parent_client = argparse.ArgumentParser(add_help=False)
    parent_client.add_argument('--server-ip',
        default=DEFAULT_SERVER_IP,
        help='IP address for Cromweller server')

    p_run = subparser.add_parser('run',
        help='Run a single workflow without server',
        parents=[parent_submit, parent_host, parent_backend])
    p_server = subparser.add_parser('server',
        help='Run a Cromwell server',
        parents=[parent_server_client, parent_host, parent_backend])
    p_submit = subparser.add_parser('submit',
        help='Submit a workflow to a Cromwell server',
        parents=[parent_server_client, parent_client, parent_submit, parent_label,
            parent_backend])
    p_cancel = subparser.add_parser('cancel',
        help='Cancel a workflow running on a Cromwell server',
        parents=[parent_server_client, parent_client, parent_wf_id, parent_label])
    p_list = subparser.add_parser('list',
        help='List workflows running on a Cromwell server',
        parents=[parent_server_client, parent_client, parent_wf_id, parent_label])

    for p in [p_run, p_server, p_submit, p_cancel, p_list]:
        p.set_defaults(**defaults)

    if len(sys.argv[1:])==0:
        parser.print_help()        
        parser.exit()
    # parse all args
    args = parser.parse_args(remaining_argv)

    # convert to dict
    args_d = vars(args)

    # init some important path variables
    if args_d.get('tmp_dir') is None:
        args_d['tmp_dir'] = os.path.join(
            args_d['out_dir'],
            'cromweller_tmp_dir')

    if args_d.get('tmp_s3_bucket') is None:
        if args_d.get('out_s3_bucket'):
            args_d['tmp_s3_bucket'] = os.path.join(
                args_d['out_s3_bucket'],
                'cromweller_tmp_dir')

    if args_d.get('tmp_gcs_bucket') is None:
        if args_d.get('out_gcs_bucket'):
            args_d['tmp_gcs_bucket'] = os.path.join(
                args_d['out_gcs_bucket'],
                'cromweller_tmp_dir')
    
    return args_d


class Cromweller(object):
    """Cromwell/WDL wrapper
    """

    BACKEND_CONF_HEADER = 'include required(classpath("application"))\n'
    DEFAULT_BACKEND = cb.BACKEND_LOCAL
    RE_PATTERN_BACKEND_CONF_HEADER = r'^[\s]*include\s'
    RE_PATTERN_WDL_COMMENT_DOCKER = r'^\s*\#\s*CROMWELLER\s+docker\s(.+)'
    RE_PATTERN_WDL_COMMENT_SINGULARITY = r'^\s*\#\s*CROMWELLER\s+singularity\s(.+)'
    RE_PATTERN_WORKFLOW_ID = r'started WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)'
    DEEPCOPY_EXTS_IN_INPUT_JSON = ('.json', '.tsv', '.csv')

    def __init__(self, args):
        """Initializes from args dict
        """
        self._num_concurrent_tasks = args.get('num_concurrent_tasks')
        self._tmp_dir = args.get('tmp_dir')
        self._out_dir = args.get('out_dir')
        self._gc_project = args.get('gc_project')
        self._out_gcs_bucket = args.get('out_gcs_bucket')
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
        self._backend_conf = args.get('backend_conf')
        self._use_singularity = args.get('use_singularity')
        self._use_docker = args.get('use_docker')
        self._wdl = args.get('wdl')
        self._inputs = args.get('inputs')
        self._cromwell = args.get('cromwell')
        self._backend = args.get('backend')
        self._deepcopy = args.get('deepcopy')
        
        if self._backend is None:
            self._backend = Cromweller.DEFAULT_BACKEND

    def run(self):
        """Run a workflow using Cromwell run mode
        """
        # compose label for workflow
        #   label = WDL filename + timestamp
        label = self.__generate_workflow_label()

        # make temp directory to store inputs
        tmp_dir = self.__mkdir_tmp_dir(label)

        # all input files
        backend_file = self.__create_backend_conf_file(tmp_dir)
        input_file = self.__get_input_json_file(tmp_dir)
        workflow_opts_file = self.__create_workflow_opts_json_file(tmp_dir)
        
        # metadata JSON file is an output from Cromwell
        #   place it on the tmp dir
        metadata_file = self.__get_metadata_json_file(tmp_dir)

        cmd = ['java', '-jar',
            '-Dconfig.file={}'.format(backend_file),
            cu.CromwellerURI(self._cromwell).get_local_file(),
            'run',
            cu.CromwellerURI(self._wdl).get_local_file(),
            '-i', input_file,
            '-o', workflow_opts_file,
            '-m', metadata_file]
        print('RUN: ',cmd)

        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
            workflow_id = None
            rc = None
            while p.poll() is None:
                stdout = p.stdout.readline().strip()
                if workflow_id is None:
                    workflow_id = Cromweller.__get_workflow_id_from_cromwell_stdout(
                                    stdout)
                print(stdout)
            rc = p.poll()
        except subprocess.CalledProcessError as e:
            rc = e.returncode
        except KeyboardInterrupt:
            while p.poll() is None:
                stdout = p.stdout.readline().strip()
                print(stdout)
        print("RC: ", rc)
        print("WORKFLOW_ID: ", workflow_id)

        # move metadata_file to backend's output storage
        with open(metadata_file, 'r') as fp:
            # read metadata contents first locally
            metadata = fp.read()
            target_metadata_file = self.__write_metadata_json_file(
                metadata, workflow_id)
        
            # delete original metadata file
            os.remove(metadata_file)
        print("CROMWELL_METADATA_JSON_FILE: ", target_metadata_file)

    def __write_metadata_json_file(self, metadata, workflow_id):
        """Write metadata.json (Cromwell's final output) to
        corresponding output storage for a workflow
        """
        # get absolute path on target storage
        target_metadata_file = os.path.join(
            self.__get_workflow_output_dir(workflow_id),
            'metadata.json')
        # write on target storage (possible remote buckets)
        return cu.CromwellerURI(target_metadata_file).write_file(
            metadata)

    def server(self):
        """Run a Cromwell server
        """
        tmp_dir = self.__mkdir_tmp_dir()
        backend_file = self.__create_backend_conf_file(tmp_dir)

        cmd = ['java', '-jar',
            '-Dconfig.file={}'.format(backend_file),
            cu.CromwellerURI(self._cromwell).get_local_file(),
            'server']
        print('SERVER: ',cmd)

        workflow_ids = set()
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                universal_newlines=True)
            rc = None
            while p.poll() is None:
                stdout = p.stdout.readline().strip()
                workflow_id = Cromweller.__get_workflow_id_from_cromwell_stdout(
                                stdout)
                if workflow_id is not None and not workflow_id in workflow_ids:
                    workflow_ids.add(workflow_id)
                print(stdout)

        except subprocess.CalledProcessError as e:
            rc = e.returncode
        except KeyboardInterrupt:
            while p.poll() is None:
                stdout = p.stdout.readline().strip()
                print(stdout)
        print("RC: ", rc)
        print("WORKFLOWS: ", workflow_ids)

    def __query_cromwell_server(self):
        try:
            pass
        except:
            pass
        return

    def submit(self):
        """Submit a workflow to Cromwell server
        """
        raise NotImplemented

    def cancel(self):
        """Send Cromwell server a request to Cancel running/pending
        workflows
        """
        raise NotImplemented

    def list(self):
        """Get list of running/pending workflows from Cromwell server
        """
        raise NotImplemented
        
    def __create_backend_conf_file(self, directory,
        fname='backend.conf'):
        """Creates Cromwell's backend conf file
        """
        backend_str = self.__get_backend_conf_str()
        backend_file = os.path.join(directory, fname)
        with open(backend_file, 'w') as fp:
            fp.write(backend_str)
        return backend_file

    def __get_metadata_json_file(self, directory,
        fname='metadata.json'):
        metadata_file = os.path.join(directory, fname)
        return metadata_file       

    def __get_input_json_file(self, directory,
        fname='inputs.json'):
        """Make a copy of input JSON file.
        Deepcopy to specified storage if required.
        """
        if self._inputs is not None:
            # init parameters for deepcopying
            if self._backend == cb.BACKEND_GCP:
                uri_type = cu.URI_GCS
            elif self._backend == cb.BACKEND_AWS:
                uri_type = cu.URI_S3
            else:
                uri_type = cu.URI_LOCAL

            # deepcopy to backend if required
            if self._deepcopy:
                uri_exts = Cromweller.DEEPCOPY_EXTS_IN_INPUT_JSON
            else:
                uri_exts = ()

            return cu.CromwellerURI(self._inputs).get_local_file(
                deepcopy_uri_type=uri_type,
                deepcopy_uri_exts=uri_exts)
        else:            
            input_file = os.path.join(directory, fname)
            with open(input_file, 'w') as fp:
                fp.write('{}')
            return input_file

    def __create_workflow_opts_json_file(self, directory,
        fname='workflow_opts.json'):
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
            'default_runtime_attributes' : {}
        }

        if self._backend is not None:
            template['default_runtime_attributes']['backend'] = \
                self._backend

        # find docker/singularity from WDL or command line args
        if self._use_docker:
            if self._docker is None:
                docker = self.__find_docker_from_wdl()
            else:
                docker = self._docker
            if docker is not None:
                template['default_runtime_attributes']['docker'] = \
                    docker
                
        elif self._use_singularity:
            if self._singularity is None:
                singularity = self.__find_singularity_from_wdl()
            else:
                singularity = self._singularity
            if singularity is not None:            
                template['default_runtime_attributes']['singularity'] = \
                    singularity

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
            template['default-runtime-attributes']['sge_queue'] = \
            self._sge_queue
        if self._sge_extra_param is not None:
            template['default_runtime_attributes']['sge_extra_param'] = \
            self._sge_extra_param

        # write it
        workflow_opts_file = os.path.join(directory, fname)        
        with open(workflow_opts_file, 'w') as fp:
            fp.write(json.dumps(template, indent=4))

        return workflow_opts_file

    def __find_docker_from_wdl(self):
        return self.__find_var_from_wdl(
            Cromweller.RE_PATTERN_WDL_COMMENT_DOCKER)

    def __find_singularity_from_wdl(self):
        return self.__find_var_from_wdl(
            Cromweller.RE_PATTERN_WDL_COMMENT_SINGULARITY)

    def __find_var_from_wdl(self, regex_var):
        if self._wdl is not None:
            with open(cu.CromwellerURI(self._wdl).get_local_file(),'r') as fp:
                for line in fp.readlines():
                    r = re.findall(regex_var, line)
                    if len(r)>0:
                        ret = r[0].strip()
                        if len(ret)>0:
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

        def merge_dict(a, b, path=None):
            """Merge b into a recursively. This mutates a and overwrites
            items in b on a for conflicts.            

            Ref: https://stackoverflow.com/questions/7204805/dictionaries-of-dictionaries-merge/7205107#7205107                
            """
            if path is None: path = []
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

        # init backend dict
        backend_dict = {}

        # local backend
        merge_dict(backend_dict, cb.CromwellerBackendLocal(
            out_dir=self._out_dir,
            concurrent_job_limit=self._num_concurrent_tasks))

        # GC
        if self._gc_project is not None:
            merge_dict(backend_dict, cb.CromwellerBackendGC(
                gc_project=self._gc_project,
                out_gcs_bucket=self._out_gcs_bucket,
                concurrent_job_limit=self._num_concurrent_tasks))

        # AWS
        if self._aws_batch_arn is not None and self._aws_region is not None:
            merge_dict(backend_dict, cb.CromwellerBackendAWS(
                aws_batch_arn=self._aws_batch_arn,
                aws_region=self._aws_region,
                concurrent_job_limit=self._num_concurrent_tasks))

        # SLURM
        merge_dict(backend_dict, cb.CromwellerBackendSLURM(
            partition=self._slurm_partition,
            account=self._slurm_account,
            extra_param=self._slurm_extra_param,
            concurrent_job_limit=self._num_concurrent_tasks))

        # SGE
        merge_dict(backend_dict, cb.CromwellerBackendSGE(
            pe=self._sge_pe,
            queue=self._sge_queue,
            extra_param=self._sge_extra_param,
            concurrent_job_limit=self._num_concurrent_tasks))

        # PBS
        merge_dict(backend_dict, cb.CromwellerBackendPBS(
            queue=self._pbs_queue,
            extra_param=self._pbs_extra_param,
            concurrent_job_limit=self._num_concurrent_tasks))

        # MySQL is optional
        if self._mysql_db_user is not None and self._mysql_db_password is not None:
            merge_dict(backend_dict, cb.CromwellerBackendMySQL(
                ip=self._mysql_db_ip,
                port=self._mysql_db_port,
                user=self._mysql_db_user,
                password=self._mysql_db_password))

        # set header for conf ("include ...")
        assert(Cromweller.BACKEND_CONF_HEADER.endswith('\n'))
        lines_header = [Cromweller.BACKEND_CONF_HEADER]

        # override with user-specified backend.conf if exists
        if self._backend_conf is not None:
            lines_wo_header = []

            with open(cu.CromwellerURI(self._backend_conf).get_local_file(), 'r') as fp:
                for line in fp.readlines():
                    # find header and exclude
                    if re.findall(Cromweller.RE_PATTERN_BACKEND_CONF_HEADER, line):
                        if not line in lines_header:
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

    def __mkdir_tmp_dir(self, label=''):
        """Create a temporary directory (self._tmp_dir/label)
        """
        tmp_dir = os.path.join(self._tmp_dir, label)
        os.makedirs(tmp_dir, exist_ok=True)
        return tmp_dir

    def __get_workflow_output_dir(self, workflow_id=''):
        wdl = self.__get_wdl_basename()
        if self._backend==cb.BACKEND_GCP:
            out_dir = self._out_gcs_bucket
        if self._backend==cb.BACKEND_AWS:
            out_dir = self._out_aws_bucket
        else:
            out_dir = self._out_dir
        if wdl is None:
            return os.path.join(out_dir,
                workflow_id)
        else:
            return os.path.join(out_dir,
                os.path.basename(wdl),
                workflow_id)

    def __generate_workflow_label(self):
        """Random label for workflow, which is used for a label
        specified by --labels in Cromwell's command line. With this
        Cromweller will be able to distinguish between workflows.

        This is different from UUID (a.k.a workflow ID) generated
        from Cromwell itself.

        We cannot use Cromwell's UUID as a label since UUID can only
        be known after communicating with Cromwell.

        We use a milliseconded timestamp instead of Cromwell's UUID.
        """
        timestamp = Cromweller.__get_time_str()
        wdl = self.__get_wdl_basename()
        if wdl is not None:
            return wdl + '_' + timestamp
        else:
            return timestamp

    def __get_wdl_basename(self):
        if self._wdl is not None:
            wdl, _ = os.path.splitext(self._wdl)
            return os.path.basename(wdl)
        else:
            return None

    @staticmethod
    def __get_workflow_id_from_cromwell_stdout(stdout):
        for line in stdout.split('\n'):
            r = re.findall(Cromweller.RE_PATTERN_WORKFLOW_ID, line)
            if len(r)>0:
                return r[0].strip()
        return None

    @staticmethod
    def __get_time_str():
        return datetime.now().strftime('%Y%m%d_%H%M%S_%f')


def main():
    # parse arguments
    #   note that args is a dict
    args = parse_cromweller_arguments()

    # init cromweller uri to transfer files across various storages
    #   e.g. gs:// to s3://, http:// to local, ...
    cu.init_cromweller_uri(
        tmp_dir=args.get('tmp_dir'),
        tmp_s3_bucket=args.get('tmp_s3_bucket'),
        tmp_gcs_bucket=args.get('tmp_gcs_bucket'),
        http_user=args.get('http_user'),
        http_password=args.get('http_password'),
        use_gsutil_over_aws_s3=args.get('use_gsutil_over_aws_s3'))

    # init cromweller: taking all args at init step
    c = Cromweller(args)

    action = args['action']
    if action=='run':
        c.run()
    elif action=='server':
        c.server()
    elif action=='submit':
        c.submit()
    elif action=='cancel':
        c.cancel()
    elif action=='list':
        c.list()
    else:
        raise Exception('Unsupported or unspecified action.')

if __name__ == '__main__':
    main()




"""
DEV NOTE
cromwell is desinged to monitor rc (return code) file, which is generated/controlled
in ${script}, so if singularity does not run it due to some problems in singuarlity's
internal settings then rc file is not generated.
this can result in hanging of a cromwell process.
setting the below parameter enables monitoring by 'check-alive'.
it will take about 'exit-code-timeout-seconds' x 3 time to detect failure.

        # cromwell responds only to non-zero exit code from 'check-alive',
        # but 'squeue -j [JOB_ID]' returns zero exit code even when job is not found
        # workaround to exit with 1 (like SGE's qstat -j [JOB_ID] does) for such cases.

exit-code-timeout-seconds = 180

'export PYTHONNOUSERSITE='
'unset PYTHONPATH'
"""