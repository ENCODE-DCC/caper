#!/usr/bin/env python3
"""Caper: Cromwell/WDL wrapper python script
for multiple backends (local, gc, aws)

(Optional)
Add the following comments to your WDL script to specify container images
that Caper will use for your WDL. You still need to add
"--use-docker" or "--use-singularity" to command line arguments.

Example:
#CAPER docker quay.io/encode-dcc/atac-seq-pipeline:v1.1.7.2
#CAPER singularity docker://quay.io/encode-dcc/atac-seq-pipeline:v1.1.7.2

Author:
    Jin Lee (leepc12@gmail.com) at ENCODE-DCC
"""

from pyhocon import ConfigFactory, HOCONConverter
import os
import sys
import logging
import pwd
import json
import re
import time
import socket
from threading import Thread
import shutil
from subprocess import Popen, check_call, PIPE, CalledProcessError
from datetime import datetime
from autouri import AutoURI, AbsPath, GCSURI, S3URI, URIBase
from autouri import logger as autouri_logger
from autouri.loc_aux import recurse_json
from tempfile import TemporaryDirectory
from .dict_tool import merge_dict
from .caper_args import parse_caper_arguments
from .caper_init import init_caper_conf, install_cromwell_jar, install_womtool_jar

from .caper_wdl_parser import CaperWDLParser
from .caper_check import check_caper_conf
from .cromwell_rest_api import CromwellRestAPI
from .caper_backend import BACKEND_GCP, BACKEND_AWS, BACKEND_LOCAL, \
    CaperBackendCommon, CaperBackendDatabase, CaperBackendGCP, \
    CaperBackendAWS, CaperBackendLocal, CaperBackendSLURM, \
    CaperBackendSGE, CaperBackendPBS
from .caper_backend import CaperBackendBase, CaperBackendBaseLocal


logging.basicConfig(level=logging.INFO, format='%(asctime)s|%(name)s|%(levelname)s| %(message)s')
logger = logging.getLogger('caper')


class Caper(object):
    """Cromwell/WDL wrapper
    """

    BACKEND_CONF_HEADER = 'include required(classpath("application"))\n'
    DEFAULT_BACKEND = BACKEND_LOCAL
    RE_PATTERN_BACKEND_CONF_HEADER = r'^\s*include\s'
    RE_PATTERN_STARTED_WORKFLOW_ID = \
        r'started WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)'
    RE_PATTERN_FINISHED_WORKFLOW_ID = \
        r'WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b) is in a terminal state'
    RE_PATTERN_STARTED_CROMWELL_SERVER = \
        r'Cromwell \d+ service started on'
    RE_PATTERN_WORKFLOW_ID = \
        r'\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b'
    RE_PATTERN_DELIMITER_GCP_ZONES = r',| '
    USER_INTERRUPT_WARNING = '\n********** DO NOT CTRL+C MULTIPLE TIMES **********\n'

    MAX_RETRY_UPDATING_METADATA = 3
    SEC_INTERVAL_UPDATE_METADATA = 1200.0
    SEC_INTERVAL_UPDATE_SERVER_HEARTBEAT = 60.0
    SEC_INTERVAL_RETRY_UPDATING_METADATA = 10.0

    # added to cromwell labels file
    KEY_CAPER_STR_LABEL = 'caper-str-label'
    KEY_CAPER_USER = 'caper-user'
    KEY_CAPER_BACKEND = 'caper-backend'
    TMP_FILE_BASENAME_METADATA_JSON = 'metadata.json'
    TMP_FILE_BASENAME_WORKFLOW_OPTS_JSON = 'workflow_opts.json'
    TMP_FILE_BASENAME_BACKEND_CONF = 'backend.conf'
    TMP_FILE_BASENAME_LABELS_JSON = 'labels.json'
    TMP_FILE_BASENAME_IMPORTS_ZIP = 'imports.zip'
    COMMON_ROOT_SEARCH_LEVEL = 5  # to find common roots of files for singularity_bindpath

    def __init__(self, args):
        """Initializes from args dict
        """
        self._dry_run = args.get('dry_run')

        # init REST API
        self.__init_cromwell_rest_api(
            action=args.get('action'),
            ip=args.get('ip'),
            port=args.get('port'),
            no_server_hearbeat=args.get('no_server_heartbeat'),
            server_hearbeat_file=args.get('server_heartbeat_file'),
            server_hearbeat_timeout=args.get('server_heartbeat_timeout'))

        # java heap size
        self._java_heap_server = args.get('java_heap_server')
        self._java_heap_run = args.get('java_heap_run')

        # init others
        # self._keep_temp_backend_file = args.get('keep_temp_backend_file')
        self._hold = args.get('hold')
        self._format = args.get('format')
        self._hide_result_before = args.get('hide_result_before')
        self._disable_call_caching = args.get('disable_call_caching')
        self._max_concurrent_workflows = args.get('max_concurrent_workflows')
        self._max_concurrent_tasks = args.get('max_concurrent_tasks')
        self._max_retries = args.get('max_retries')
        self._tmp_dir = args.get('tmp_dir')
        self._out_dir = args.get('out_dir')
        if self._out_dir is not None:
            self._out_dir = os.path.abspath(self._out_dir)
        if self._tmp_dir is not None:
            self._tmp_dir = os.path.abspath(self._tmp_dir)
        self._gcp_prj = args.get('gcp_prj')
        self._gcp_zones = args.get('gcp_zones')
        self._gcp_call_caching_dup_strat = args.get('gcp_call_caching_dup_strat')
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

        self._backend_file = AbsPath.get_abspath_if_exists(
            args.get('backend_file'))
        self._soft_glob_output = args.get('soft_glob_output')
        self._wdl = AbsPath.get_abspath_if_exists(
            args.get('wdl'))
        self._inputs = AbsPath.get_abspath_if_exists(
            args.get('inputs'))
        self._cromwell = AbsPath.get_abspath_if_exists(
            args.get('cromwell'))
        self._workflow_opts = AbsPath.get_abspath_if_exists(
            args.get('options'))
        self._str_label = args.get('str_label')
        self._labels = AbsPath.get_abspath_if_exists(
            args.get('labels'))
        self._imports = AbsPath.get_abspath_if_exists(
            args.get('imports'))
        self._singularity_cachedir = args.get('singularity_cachedir')
        self._ignore_womtool = args.get('ignore_womtool')
        self._womtool = AbsPath.get_abspath_if_exists(
            args.get('womtool'))

        self._metadata_output = args.get('metadata_output')
        if self._metadata_output is not None and not AutoURI(self._metadata_output).is_valid:
            # metadata output doesn't exist at this moment since it's an output
            # so cannot use AbsPath.get_abspath_if_exists() here
            # make it abspath if it's given as local relative path ($CWD/relpath)
            self._metadata_output = os.path.abspath(self._metadata_output)

        # DB
        self._db = args.get('db')
        self._db_timeout = args.get('db_timeout')
        self._file_db = args.get('file_db')
        self._mysql_db_ip = args.get('mysql_db_ip')
        self._mysql_db_port = args.get('mysql_db_port')
        self._mysql_db_user = args.get('mysql_db_user')
        self._mysql_db_password = args.get('mysql_db_password')
        self._mysql_db_name = args.get('mysql_db_name')
        self._postgresql_db_ip = args.get('postgresql_db_ip')
        self._postgresql_db_port = args.get('postgresql_db_port')
        self._postgresql_db_user = args.get('postgresql_db_user')
        self._postgresql_db_password = args.get('postgresql_db_password')
        self._postgresql_db_name = args.get('postgresql_db_name')

        # troubleshoot
        self._show_completed_task = args.get('show_completed_task')

        # backend and default backend
        self._backend = args.get('backend')
        if self._backend is None:
            if args.get('action') == 'submit':
                self._backend = self._cromwell_rest_api.get_default_backend()
            else:
                self._backend = Caper.DEFAULT_BACKEND
        if self._backend == 'local':
            self._backend = BACKEND_LOCAL  # Local (capital L)

        # deepcopy
        self._no_deepcopy = args.get('no_deepcopy')

        # containers
        self._no_build_singularity = args.get('no_build_singularity')
        self._use_docker = args.get('use_docker')
        self._use_singularity = args.get('use_singularity')
        self._singularity = args.get('singularity')
        self._docker = args.get('docker')

        # list of values
        self._wf_id_or_label = args.get('wf_id_or_label')

    def run(self):
        """Run a workflow using Cromwell run mode
        """

        timestamp = Caper.__get_time_str()
        # otherwise, use WDL basename
        suffix = os.path.join(
            self.__get_wdl_basename_wo_ext(), timestamp)
        tmp_dir = self.__mkdir_tmp_dir(suffix)

        # all input files
        backend_file = self.__create_backend_conf_file(tmp_dir)
        input_file = self.__create_input_json_file(tmp_dir)
        workflow_opts_file = self.__create_workflow_opts_json_file(
            input_file, tmp_dir)
        labels_file = self.__create_labels_json_file(tmp_dir)

        if self._imports is not None:
            imports_file = AbsPath.localize(self._imports)
        else:
            imports_file = None
        wdl = AbsPath.localize(self._wdl)

        # metadata JSON file is an output from Cromwell
        #   place it on the tmp dir
        metadata_file = os.path.join(
            tmp_dir, Caper.TMP_FILE_BASENAME_METADATA_JSON)

        java_heap = '-Xmx{}'.format(self._java_heap_run)
        # LOG_LEVEL must be >=INFO to catch workflow ID from STDOUT
        cmd = ['java', java_heap, '-XX:ParallelGCThreads=1', '-DLOG_LEVEL=INFO',
               '-DLOG_MODE=standard',
               '-jar', '-Dconfig.file={}'.format(backend_file),
               install_cromwell_jar(self._cromwell), 'run',
               wdl,
               '-i', input_file,
               '-o', workflow_opts_file,
               '-l', labels_file,
               '-m', metadata_file]
        if imports_file is not None:
            cmd += ['-p', imports_file]

        self.__validate_with_womtool(wdl, input_file, imports_file)

        logger.info('cmd: {cmd}'.format(cmd=cmd))
        if self._dry_run:
            return -1
        try:
            p = Popen(cmd, stdout=PIPE, universal_newlines=True)
            workflow_id = None
            rc = None
            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')

                # find workflow id from STDOUT
                if workflow_id is None:
                    wf_ids_with_status = \
                        Caper.__get_workflow_ids_from_cromwell_stdout(
                            stdout)
                    for wf_id, status in wf_ids_with_status:
                        if status == 'started' or status == 'finished':
                            workflow_id = wf_id
                            break
                if stdout != '':
                    print(stdout)
            # get final RC
            rc = p.poll()
        except CalledProcessError as e:
            rc = e.returncode
        except KeyboardInterrupt:
            logger.error(Caper.USER_INTERRUPT_WARNING)
            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')
                print(stdout)

        # move metadata file to a workflow output directory
        if metadata_file is not None and workflow_id is not None and \
                os.path.exists(metadata_file):
            with open(metadata_file, 'r') as fp:
                metadata_uri = self.__write_metadata_json(
                    workflow_id,
                    json.loads(fp.read()))
            # remove original one
            os.remove(metadata_file)
        else:
            metadata_uri = None

        # troubleshoot if metadata is available
        if metadata_uri is not None:
            Caper.__troubleshoot(
                AbsPath.localize(metadata_uri),
                self._show_completed_task)

        logger.info(
            'run: {rc}, {wf_id}, {m}'.format(
                rc=rc, wf_id=workflow_id, m=metadata_uri))
        return workflow_id

    def server(self):
        """Run a Cromwell server
        """
        tmp_dir = self.__mkdir_tmp_dir()
        backend_file = self.__create_backend_conf_file(tmp_dir)

        # check if port is open
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((self._ip, self._port))
        if result == 0:
            err = '[Caper] Error: server port {} is already taken. '\
                  'Try with a different --port'.format(self._port)
            raise Exception(err)

        java_heap = '-Xmx{}'.format(self._java_heap_server)
        # LOG_LEVEL must be >=INFO to catch workflow ID from STDOUT
        cmd = ['java', java_heap, '-XX:ParallelGCThreads=1', '-DLOG_LEVEL=INFO',
               '-DLOG_MODE=standard',
               '-jar', '-Dconfig.file={}'.format(backend_file),
               install_cromwell_jar(self._cromwell), 'server']
        logger.info('cmd: {cmd}'.format(cmd=cmd))

        # pending/running workflows
        started_wf_ids = set()
        # completed, aborted or terminated workflows
        finished_wf_ids = set()

        self._stop_heartbeat_thread = False
        t_heartbeat = Thread(
            target=self.__write_heartbeat_file)
        if self._dry_run:
            return -1
        try:
            p = Popen(cmd, stdout=PIPE, universal_newlines=True)
            rc = None
            t0 = time.perf_counter()  # tickcount
            server_is_ready = False

            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')
                if stdout != '':
                    print(stdout)

                # find workflow id from Cromwell server's STDOUT
                wf_ids_with_status = \
                    Caper.__get_workflow_ids_from_cromwell_stdout(stdout)
                if not server_is_ready:
                    server_is_ready = \
                        Caper.__check_cromwell_server_start_from_stdout(stdout)
                    if server_is_ready:
                        t_heartbeat.start()

                for wf_id, status in wf_ids_with_status:
                    if status in 'started':
                        started_wf_ids.add(wf_id)
                    elif status == 'finished':
                        finished_wf_ids.add(wf_id)

                for wf_id in finished_wf_ids:
                    started_wf_ids.remove(wf_id)

                # write metadata.json for finished workflows
                self.__write_metadata_jsons(finished_wf_ids)
                # flush finished workflow IDs
                #   so that their metadata don't get updated any longer
                finished_wf_ids.clear()

                # write metadata.json for running workflows
                #   every SEC_INTERVAL_UPDATE_METADATA
                t1 = time.perf_counter()
                if (t1 - t0) > Caper.SEC_INTERVAL_UPDATE_METADATA:
                    t0 = t1
                    self.__write_metadata_jsons(started_wf_ids)

        except CalledProcessError as e:
            rc = e.returncode
        except KeyboardInterrupt:
            logger.error(Caper.USER_INTERRUPT_WARNING)
            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')
                print(stdout)
        time.sleep(1)
        self._stop_heartbeat_thread = True
        t_heartbeat.join()
        logger.info(
            'server: {rc}, {s_wf_ids}, {f_wf_ids}'.format(
                rc=rc, s_wf_ids=started_wf_ids, f_wf_ids=finished_wf_ids))
        return rc

    def submit(self):
        """Submit a workflow to Cromwell server
        """
        timestamp = Caper.__get_time_str()
        # otherwise, use WDL basename
        suffix = os.path.join(
            self.__get_wdl_basename_wo_ext(), timestamp)
        tmp_dir = self.__mkdir_tmp_dir(suffix)

        # all input files
        input_file = self.__create_input_json_file(tmp_dir)
        if self._imports is not None:
            imports_file = AbsPath.localize(self._imports)
        else:
            imports_file = self.__create_imports_zip_file_from_wdl(tmp_dir)
        workflow_opts_file = self.__create_workflow_opts_json_file(
            input_file, tmp_dir)
        labels_file = self.__create_labels_json_file(tmp_dir)
        on_hold = self._hold if self._hold is not None else False
        wdl = AbsPath.localize(self._wdl)

        logger.debug(
            'submit params: wdl={w}, imports_f={imp}, input_f={i}, '
            'opt_f={o}, labels_f={l}, on_hold={on_hold}'.format(
                w=wdl,
                imp=imports_file,
                i=input_file,
                o=workflow_opts_file,
                l=labels_file,
                on_hold=on_hold))

        self.__validate_with_womtool(wdl, input_file, imports_file)

        if self._dry_run:
            return -1
        r = self._cromwell_rest_api.submit(
            source=wdl,
            dependencies=imports_file,
            inputs_file=input_file,
            options_file=workflow_opts_file,
            labels_file=labels_file,
            on_hold=on_hold)
        logger.info('submit: {r}'.format(r=r))
        return r

    def abort(self):
        """Abort running/pending workflows on a Cromwell server
        """
        if self._dry_run:
            return -1
        r = self._cromwell_rest_api.abort(
                self._wf_id_or_label,
                [(Caper.KEY_CAPER_STR_LABEL, v)
                 for v in self._wf_id_or_label])
        logger.info('abort: {r}'.format(r=r))
        return r

    def unhold(self):
        """Release hold of workflows on a Cromwell server
        """
        if self._dry_run:
            return -1
        r = self._cromwell_rest_api.release_hold(
                self._wf_id_or_label,
                [(Caper.KEY_CAPER_STR_LABEL, v)
                 for v in self._wf_id_or_label])
        logger.info('unhold: {r}'.format(r=r))
        return r

    def metadata(self, no_print=False):
        """Retrieve metadata for workflows from a Cromwell server
        """
        if self._dry_run:
            return -1
        m = self._cromwell_rest_api.get_metadata(
                self._wf_id_or_label,
                [(Caper.KEY_CAPER_STR_LABEL, v)
                 for v in self._wf_id_or_label])
        if not no_print:
            if len(m) == 1:
                m_ = m[0]
            else:
                m_ = m
            print(json.dumps(m_, indent=4))
        return m

    def list(self):
        """Get list of running/pending workflows from a Cromwell server
        """
        if self._dry_run:
            return -1
        # if not argument, list all workflows using wildcard (*)
        if self._wf_id_or_label is None or len(self._wf_id_or_label) == 0:
            workflow_ids = ['*']
            labels = [(Caper.KEY_CAPER_STR_LABEL, '*')]
        else:
            workflow_ids = self._wf_id_or_label
            labels = [(Caper.KEY_CAPER_STR_LABEL, v)
                      for v in self._wf_id_or_label]

        workflows = self._cromwell_rest_api.find(
            workflow_ids, labels)
        formats = self._format.split(',')
        print('\t'.join(formats))

        if workflows is None:
            return None
        for w in workflows:
            row = []
            workflow_id = w['id'] if 'id' in w else None

            if self._hide_result_before is not None:
                if 'submission' in w and w['submission'] <= self._hide_result_before:
                    continue
            for f in formats:
                if f == 'workflow_id':
                    row.append(str(workflow_id))
                elif f == 'str_label':
                    if 'labels' in w and Caper.KEY_CAPER_STR_LABEL in w['labels']:
                        lbl = w['labels'][Caper.KEY_CAPER_STR_LABEL]
                    else:
                        lbl = None
                    row.append(str(lbl))
                elif f == 'user':
                    if 'labels' in w and Caper.KEY_CAPER_USER in w['labels']:
                        lbl = w['labels'][Caper.KEY_CAPER_USER]
                    else:
                        lbl = None
                    row.append(str(lbl))
                else:
                    row.append(str(w[f] if f in w else None))
            print('\t'.join(row))
        return workflows

    def troubleshoot(self):
        """Troubleshoot errors based on information from Cromwell's metadata
        """
        if self._dry_run:
            return -1
        if self._wf_id_or_label is None or len(self._wf_id_or_label) == 0:
            return
        # if it's a file
        wf_id_or_label = []
        metadatas = []
        for f in self._wf_id_or_label:
            u = AutoURI(f)
            if u.is_valid and u.exists:
                metadatas.append(AbsPath.localize(u))
            else:
                wf_id_or_label.append(f)

        if len(wf_id_or_label) > 0:
            self._wf_id_or_label = wf_id_or_label
            metadatas.extend(self.metadata(no_print=True))

        for metadata in metadatas:
            Caper.__troubleshoot(metadata, self._show_completed_task)

    def __validate_with_womtool(self, wdl, input_file, imports):
        if not self._ignore_womtool:
            with TemporaryDirectory() as tmp_d:
                if imports:
                    # copy WDL to temp dir and unpack imports.zip (sub WDLs) if exists
                    wdl_copy = os.path.join(tmp_d, AutoURI(self._wdl).basename)
                    AutoURI(wdl).cp(wdl_copy)
                    shutil.unpack_archive(imports, tmp_d)
                else:
                    wdl_copy = wdl
                cmd_womtool = ['java', '-Xmx512M', '-jar', '-DLOG_LEVEL=INFO',
                               install_womtool_jar(self._womtool),
                               'validate', wdl_copy,
                               '-i', input_file]
                try:
                    logger.info('Validating WDL/input JSON with womtool...')
                    check_call(cmd_womtool)
                except CalledProcessError as e:
                    logger.error('Womtool: WDL or input JSON is invalid '
                                 'or input JSON doesn\'t exist.')
                    rc = e.returncode
                    sys.exit(rc)

    def __init_cromwell_rest_api(self, action, ip, port,
                                 no_server_hearbeat,
                                 server_hearbeat_file,
                                 server_hearbeat_timeout):
        self._no_server_hearbeat = no_server_hearbeat
        self._server_hearbeat_file = server_hearbeat_file
        self._ip, self._port = \
            self.__read_heartbeat_file(action, ip, port, server_hearbeat_timeout)

        self._cromwell_rest_api = CromwellRestAPI(
            ip=self._ip, port=self._port, verbose=False)

    def __read_heartbeat_file(self, action, ip, port, server_hearbeat_timeout):
        if not self._no_server_hearbeat and self._server_hearbeat_file is not None:
            self._server_hearbeat_file = os.path.expanduser(
                self._server_hearbeat_file)
            if action != 'server':
                try:
                    if os.path.exists(self._server_hearbeat_file):
                        f_time = os.path.getmtime(self._server_hearbeat_file)
                        if (time.time() - f_time) * 1000.0 < server_hearbeat_timeout:
                            with open(self._server_hearbeat_file, 'r') as fp:
                                ip, port = fp.read().strip('\n').split(':')
                except:
                    logger.warning(
                        'Failed to read server_heartbeat_file: {f}'.format(
                            f=self._server_hearbeat_file))
        return ip, port

    def __write_heartbeat_file(self):
        if not self._no_server_hearbeat and self._server_hearbeat_file is not None:
            while True:
                try:
                    logger.info(
                        'Writing heartbeat: {ip}, {port}'.format(
                            ip=socket.gethostname(), port=self._port))
                    with open(self._server_hearbeat_file, 'w') as fp:
                        fp.write('{}:{}'.format(
                            socket.gethostname(),
                            self._port))
                except Exception as e:
                    logger.warning('Failed to write a heartbeat_file')
                cnt = 0
                while cnt < Caper.SEC_INTERVAL_UPDATE_SERVER_HEARTBEAT:
                    cnt += 1
                    if self._stop_heartbeat_thread:
                        break
                    time.sleep(1)
                if self._stop_heartbeat_thread:
                    break

    def __write_metadata_jsons(self, workflow_ids):
        for wf_id in workflow_ids.copy():
            for trial in range(Caper.MAX_RETRY_UPDATING_METADATA + 1):
                try:
                    time.sleep(Caper.SEC_INTERVAL_RETRY_UPDATING_METADATA)
                    # get metadata for wf_id
                    m = self._cromwell_rest_api.get_metadata([wf_id])
                    assert(len(m) == 1)
                    metadata = m[0]
                    if 'labels' in metadata and \
                            'caper-backend' in metadata['labels']:
                        backend = \
                            metadata['labels']['caper-backend']
                    else:
                        backend = None

                    if backend is not None:
                        self.__write_metadata_json(
                            wf_id, metadata,
                            backend=backend,
                            wdl=metadata['workflowName'])
                except Exception as e:
                    logger.warning(
                        '[Caper] Exception caught while retrieving '
                        'metadata from Cromwell server. '
                        'trial: {t}, wf_id: {wf_id}, e: {e}'.format(
                            t=trial, wf_id=wf_id, e=str(e)))
                break

    def __write_metadata_json(self, workflow_id, metadata_json,
                              backend=None, wdl=None):
        if backend is None:
            backend = self._backend
        if backend is None:
            return None

        if backend == BACKEND_GCP:
            out_dir = self._out_gcs_bucket
        elif backend == BACKEND_AWS:
            out_dir = self._out_s3_bucket
        else:
            out_dir = self._out_dir

        if wdl is None:
            wdl = self.__get_wdl_basename_wo_ext()
        if wdl is None:
            path = os.path.join(out_dir, workflow_id)
        else:
            path = os.path.join(out_dir, os.path.basename(wdl), workflow_id)

        if self._metadata_output is not None:
            metadata_uri = self._metadata_output
        else:
            metadata_uri = os.path.join(
                path, Caper.TMP_FILE_BASENAME_METADATA_JSON)

        return AutoURI(metadata_uri).write(
            json.dumps(metadata_json, indent=4))

    def __create_input_json_file(
            self, directory, fname='inputs.json'):
        """Make a copy of input JSON file.
        Deepcopy to a specified storage if required.
        """
        if self._inputs is not None:
            if not self._no_deepcopy:
                # deepcopy all files in JSON/TSV/CSV
                #   to the target backend
                if self._backend == BACKEND_GCP:
                    uri_cls = GCSURI
                elif self._backend == BACKEND_AWS:
                    uri_cls = S3URI
                else:
                    uri_cls = AbsPath

                new_uri = uri_cls.localize(
                    self._inputs,
                    recursive=True,
                    make_md5_file=True)
            else:
                new_uri = self._inputs
            # localize again on local
            return AbsPath.localize(new_uri)
        else:
            input_file = os.path.join(directory, fname)
            with open(input_file, 'w') as fp:
                fp.write('{}')
            return input_file

    def __create_labels_json_file(
            self, directory, fname=TMP_FILE_BASENAME_LABELS_JSON):
        """Create labels JSON file
        """
        if self._labels is not None:
            s = AutoURI(self._labels).read()
            labels_dict = json.loads(s)
        else:
            labels_dict = {}

        labels_dict[Caper.KEY_CAPER_BACKEND] = self._backend
        if self._str_label is not None:
            labels_dict[Caper.KEY_CAPER_STR_LABEL] = \
                self._str_label
        username = pwd.getpwuid(os.getuid())[0]
        labels_dict[Caper.KEY_CAPER_USER] = username

        labels_file = os.path.join(directory, fname)
        with open(labels_file, 'w') as fp:
            fp.write(json.dumps(labels_dict, indent=4))
        return labels_file

    def __create_workflow_opts_json_file(
            self, input_json_file,
            directory, fname=TMP_FILE_BASENAME_WORKFLOW_OPTS_JSON,):
        """Creates Cromwell's workflow options JSON file

        input_json_file is required to find singularity_bindpath,
        which is a common root for all data input JSON.

        Items written to workflow options JSON file:
            * very important backend
            backend: a backend to run workflows on

            * important dep resolver
            docker:
                docker image URI (e.g. ubuntu:latest)
            singularity:
                singularity image URI (docker://, shub://)
                singularity_bindpath (calculate common root of
                                      files in input JSON)
                singularity_cachedir

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

        # automatically add docker_from_wdl for cloud backend
        if self._use_docker or self._backend in (BACKEND_GCP, BACKEND_AWS):
            if self._docker is None:
                # find docker from WDL or command line args
                docker = CaperWDLParser(self._wdl).find_docker()
            else:
                docker = self._docker
            if docker is None:
                logger.warning('No docker image specified with --docker.')
            else:
                template['default_runtime_attributes']['docker'] = docker

        if self._use_singularity:
            if self._singularity is None:
                # find singularity from WDL or command line args
                singularity = CaperWDLParser(self._wdl).find_singularity()
            else:
                singularity = self._singularity
            if singularity is None:
                raise ValueError('Singularity image is not defined either '
                                 'in WDL nor in --singularity.')
            # build singularity image before running a pipeline
            self.__build_singularity_image(singularity)

            # important singularity settings (cachedir, bindpath)
            template['default_runtime_attributes']['singularity'] = singularity
            if self._singularity_cachedir is not None:
                template['default_runtime_attributes']['singularity_cachedir'] = \
                        self._singularity_cachedir
            # calculate bindpath from all file paths in input JSON file
            template['default_runtime_attributes']['singularity_bindpath'] = \
                Caper.__find_singularity_bindpath(input_json_file)

        if self._gcp_zones is not None:
            # delimiters: comma or whitespace
            zones = ' '.join(re.split(Caper.RE_PATTERN_DELIMITER_GCP_ZONES,
                                      self._gcp_zones))
            template['default_runtime_attributes']['zones'] = zones

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

        if self._max_retries is not None:
            template['default_runtime_attributes']['maxRetries'] = \
                self._max_retries

        # if workflow opts file is given by a user, merge it to template
        if self._workflow_opts is not None:
            f = AbsPath.localize(self._workflow_opts)
            with open(f, 'r') as fp:
                d = json.loads(fp.read())
                merge_dict(template, d)

        # write it
        workflow_opts_file = os.path.join(directory, fname)
        with open(workflow_opts_file, 'w') as fp:
            fp.write(json.dumps(template, indent=4))
            fp.write('\n')

        return workflow_opts_file

    def __create_imports_zip_file_from_wdl(
            self, directory, fname=TMP_FILE_BASENAME_IMPORTS_ZIP):
        zip_file = os.path.join(directory, fname)
        if CaperWDLParser(self._wdl).zip_subworkflows(zip_file):
            return zip_file
        return None

    def __create_backend_conf_file(
            self, directory, fname=TMP_FILE_BASENAME_BACKEND_CONF):
        """Creates Cromwell's backend conf file
        """
        backend_str = self.__get_backend_conf_str()
        backend_file = os.path.join(directory, fname)
        with open(backend_file, 'w') as fp:
            fp.write(backend_str)
        return backend_file

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
            CaperBackendCommon(
                port=self._port,
                disable_call_caching=self._disable_call_caching,
                max_concurrent_workflows=self._max_concurrent_workflows))

        # common settings for all backends
        if self._max_concurrent_tasks is not None:
            CaperBackendBase.CONCURRENT_JOB_LIMIT = self._max_concurrent_tasks

        # common settings for local-based backends
        if self._soft_glob_output is not None:
            CaperBackendBaseLocal.USE_SOFT_GLOB_OUTPUT = self._soft_glob_output
        if self._out_dir is not None:
            CaperBackendBaseLocal.OUT_DIR = self._out_dir

        # local backend
        merge_dict(
            backend_dict,
            CaperBackendLocal())

        # GC
        if self._gcp_prj is not None and self._out_gcs_bucket is not None:
            merge_dict(
                backend_dict,
                CaperBackendGCP(
                    gcp_prj=self._gcp_prj,
                    out_gcs_bucket=self._out_gcs_bucket,
                    call_caching_dup_strat=self._gcp_call_caching_dup_strat))

        # AWS
        if self._aws_batch_arn is not None and self._aws_region is not None \
                and self._out_s3_bucket is not None:
            merge_dict(
                backend_dict,
                CaperBackendAWS(
                    aws_batch_arn=self._aws_batch_arn,
                    aws_region=self._aws_region,
                    out_s3_bucket=self._out_s3_bucket))

        # SLURM
        merge_dict(
            backend_dict,
            CaperBackendSLURM(
                partition=self._slurm_partition,
                account=self._slurm_account,
                extra_param=self._slurm_extra_param))

        # SGE
        merge_dict(
            backend_dict,
            CaperBackendSGE(
                pe=self._sge_pe,
                queue=self._sge_queue,
                extra_param=self._sge_extra_param))

        # PBS
        merge_dict(
            backend_dict,
            CaperBackendPBS(
                queue=self._pbs_queue,
                extra_param=self._pbs_extra_param))

        # Database
        merge_dict(
            backend_dict,
            CaperBackendDatabase(
                db_type=self._db,
                db_timeout=self._db_timeout,
                file_db=self._file_db,
                mysql_ip=self._mysql_db_ip,
                mysql_port=self._mysql_db_port,
                mysql_user=self._mysql_db_user,
                mysql_password=self._mysql_db_password,
                mysql_name=self._mysql_db_name,
                postgresql_ip=self._postgresql_db_ip,
                postgresql_port=self._postgresql_db_port,
                postgresql_user=self._postgresql_db_user,
                postgresql_password=self._postgresql_db_password,
                postgresql_name=self._postgresql_db_name))

        # set header for conf ("include ...")
        assert(Caper.BACKEND_CONF_HEADER.endswith('\n'))
        lines_header = [Caper.BACKEND_CONF_HEADER]

        # override with user-specified backend.conf if exists
        if self._backend_file is not None:
            lines_wo_header = []

            with open(AbsPath.localize(self._backend_file),
                      'r') as fp:
                for line in fp.readlines():
                    # find header and exclude
                    if re.findall(Caper.RE_PATTERN_BACKEND_CONF_HEADER,
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
            backend_dict['backend']['default'] = Caper.DEFAULT_BACKEND

        # dict to HOCON (excluding header)
        backend_hocon = ConfigFactory.from_dict(backend_dict)
        # write header to HOCON string
        backend_str = ''.join(lines_header)
        # convert HOCON to string
        backend_str += HOCONConverter.to_hocon(backend_hocon)

        return backend_str

    def __get_wdl_basename_wo_ext(self):
        if self._wdl is not None:
            wdl, _ = os.path.splitext(self._wdl)
            return os.path.basename(wdl)
        else:
            return None

    def __mkdir_tmp_dir(self, suffix=''):
        """Create a temporary directory (self._tmp_dir/suffix)
        """
        tmp_dir = os.path.join(self._tmp_dir, suffix)
        os.makedirs(tmp_dir, exist_ok=True)
        return tmp_dir

    def __build_singularity_image(self, singularity):
        if self._no_build_singularity is not None \
                and self._no_build_singularity:
            pass

        elif self._backend is not None \
                and self._backend not in (BACKEND_AWS, BACKEND_GCP):
            logger.info(
                'Building local singularity image: {img}'.format(
                    img=singularity))
            cmd = ['singularity', 'exec', singularity,
                   'echo', '[Caper] building done.']
            env = os.environ.copy()
            if self._singularity_cachedir is not None \
                    and 'SINGULARITY_CACHEDIR' not in env:
                env['SINGULARITY_CACHEDIR'] = self._singularity_cachedir
            return check_call(cmd, env=env)

        logger.info('Skipped building local singularity image.')
        return None

    @staticmethod
    def __get_workflow_ids_from_cromwell_stdout(stdout):
        result = []
        for line in stdout.split('\n'):
            r1 = re.findall(Caper.RE_PATTERN_STARTED_WORKFLOW_ID, line)
            if len(r1) > 0:
                result.append((r1[0].strip(), 'started'))
            r2 = re.findall(Caper.RE_PATTERN_FINISHED_WORKFLOW_ID, line)
            if len(r2) > 0:
                result.append((r2[0].strip(), 'finished'))
        return result

    @staticmethod
    def __check_cromwell_server_start_from_stdout(stdout):
        for line in stdout.split('\n'):
            r1 = re.findall(Caper.RE_PATTERN_STARTED_CROMWELL_SERVER, line)
            if len(r1) > 0:
                return True
        return False

    @staticmethod
    def __get_time_str():
        return datetime.now().strftime('%Y%m%d_%H%M%S_%f')

    @staticmethod
    def __troubleshoot(metadata_json, show_completed_task=False):
        """Troubleshoot from metadata JSON obj/file
        """
        if isinstance(metadata_json, dict):
            metadata = metadata_json
        else:
            f = AbsPath.localize(metadata_json)
            with open(f, 'r') as fp:
                metadata = json.loads(fp.read())
        if isinstance(metadata, list):
            metadata = metadata[0]

        workflow_id = metadata['id']
        workflow_status = metadata['status']
        logger.info('Troubleshooting {wf_id} ...'.format(wf_id=workflow_id))
        if not show_completed_task and workflow_status == 'Succeeded':
            logger.info(
                'This workflow ran successfully. There is nothing to troubleshoot')
            return

        def recurse_calls(calls, failures=None, show_completed_task=False):
            if failures is not None:
                s = json.dumps(failures, indent=4)
                logger.info('Found failures:\n{s}'.format(s=s))
            for task_name, call_ in calls.items():
                for call in call_:
                    # if it is a subworkflow, then recursively dive into it
                    if 'subWorkflowMetadata' in call:
                        subworkflow = call['subWorkflowMetadata']
                        recurse_calls(
                            subworkflow['calls'],
                            subworkflow['failures']
                            if 'failures' in subworkflow else None,
                            show_completed_task)
                        continue
                    task_status = call['executionStatus']
                    shard_index = call['shardIndex']
                    rc = call['returnCode'] if 'returnCode' in call else None
                    job_id = call['jobId'] if 'jobId' in call else None
                    stdout = call['stdout'] if 'stdout' in call else None
                    stderr = call['stderr'] if 'stderr' in call else None
                    run_start = None
                    run_end = None
                    if 'executionEvents' in call:
                        for ev in call['executionEvents']:
                            if ev['description'].startswith('Running'):
                                run_start = ev['startTime']
                                run_end = ev['endTime']
                                break

                    if not show_completed_task and \
                            task_status in ('Done', 'Succeeded'):
                        continue
                    print(
                        '\n{tn} {ts}. SHARD_IDX={shard_id}, RC={rc}, JOB_ID={job_id}, '
                        'RUN_START={start}, RUN_END={end}, '
                        'STDOUT={stdout}, STDERR={stderr}'.format(
                            tn=task_name, ts=task_status,
                            shard_id=shard_index, rc=rc, job_id=job_id,
                            start=run_start, end=run_end,
                            stdout=stdout, stderr=stderr))

                    if stderr is not None:
                        u = AutoURI(stderr)
                        if u.is_valid and u.exists:
                            local_stderr_f = AbsPath.localize(u)
                            with open(local_stderr_f, 'r') as fp:
                                stderr_contents = fp.read()
                            print('STDERR_CONTENTS=\n{}'.format(
                                stderr_contents))

        calls = metadata['calls']
        failures = metadata['failures'] if 'failures' in metadata else None
        recurse_calls(calls, failures, show_completed_task)

    @staticmethod
    def __find_singularity_bindpath(input_json_file):
        """Find paths to be bound for singularity
        by finding common roots for all files in input JSON file.
        This function will recursively visit all values in input JSON and
        also JSON, TSV, CSV files in the input JSON itself.

        This function visit all files in input JSON.
        Files with some extensions (defined by Autouri's URIBase.LOC_RECURSE_EXT_AND_FNC)
        are recursively visited.

        Args:
            input_json_file:
                localized input JSON file so that all files in it are already
                recursively localized
        """
        with open(input_json_file, 'r') as fp:
            input_json_contents = fp.read()

        all_dirnames = []
        def find_dirname(s):
            u = AbsPath(s)
            if u.is_valid:
                for ext, recurse_fnc_for_ext in URIBase.LOC_RECURSE_EXT_AND_FNC.items():
                    if u.ext == ext:
                        _, _ = recurse_fnc_for_ext(u.read(), find_dirname)
                # file can be a soft-link
                # singularity will want to have access to both soft-link and real one
                # so add dirnames of both soft-link and realpath
                all_dirnames.append(u.dirname)
                all_dirnames.append(os.path.dirname(os.path.realpath(u.uri)))
            return None, False
        _, _ = recurse_json(input_json_contents, find_dirname)

        # add all (but not too high level<4) parent directories
        # to all_dirnames. start from original
        # e.g. /a/b/c/d/e/f/g/h with COMMON_ROOT_SEARCH_LEVEL = 5
        # add all the followings:
        # /a/b/c/d/e/f/g/h (org)
        # /a/b/c/d/e/f/g
        # /a/b/c/d/e/f
        # /a/b/c/d/e
        # /a/b/c/d (minimum level = COMMON_ROOT_SEARCH_LEVEL-1)
        all_dnames_incl_parents = set(all_dirnames)
        for d in all_dirnames:
            dir_arr = d.split(os.sep)
            for i, _ in enumerate(
                    dir_arr[Caper.COMMON_ROOT_SEARCH_LEVEL:]):
                d_child = os.sep.join(
                    dir_arr[:i + Caper.COMMON_ROOT_SEARCH_LEVEL])
                all_dnames_incl_parents.add(d_child)

        bindpaths = set()
        # remove overlapping directories
        for i, d1 in enumerate(sorted(all_dnames_incl_parents,
                                      reverse=True)):
            overlap_found = False
            for j, d2 in enumerate(sorted(all_dnames_incl_parents,
                                          reverse=True)):
                if i >= j:
                    continue
                if d1.startswith(d2):
                    overlap_found = True
                    break
            if not overlap_found:
                bindpaths.add(d1)

        return ','.join(bindpaths)


def main():
    # parse arguments
    #   note that args is a dict
    args = parse_caper_arguments()
    action = args['action']
    if action == 'init':
        init_caper_conf(args)
        sys.exit(0)
    args = check_caper_conf(args)

    # init Autouri classes to transfer files across various storages
    #   e.g. gs:// to s3://, http:// to local, ...
    # loc_prefix means prefix (root directory)
    # for localizing files of different storages
    AbsPath.init_abspath(
        loc_prefix=args.get('tmp_dir')
    )
    GCSURI.init_gcsuri(
        loc_prefix=args.get('tmp_gcs_bucket'),
        use_gsutil_for_s3=args.get('use_gsutil_for_s3')
    )
    S3URI.init_s3uri(
        loc_prefix=args.get('tmp_s3_bucket')
    )
    # init both loggers of Autouri and Caper
    if args.get('verbose'):
        autouri_logger.setLevel('INFO')
        logger.setLevel('INFO')
    elif args.get('debug'):
        autouri_logger.setLevel('DEBUG')
        logger.setLevel('DEBUG')

    # initialize caper: taking all args at init step
    c = Caper(args)

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
    elif action == 'unhold':
        c.unhold()
    elif action in ['troubleshoot', 'debug']:
        c.troubleshoot()

    else:
        raise Exception('Unsupported or unspecified action.')
    return 0


if __name__ == '__main__':
    main()
