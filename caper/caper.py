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
import pwd
import json
import re
import time
import shutil
from subprocess import Popen, check_call, PIPE, CalledProcessError
from datetime import datetime

from .caper_args import parse_caper_arguments
from .cromwell_rest_api import CromwellRestAPI
from .caper_uri import URI_S3, URI_GCS, URI_LOCAL, \
    init_caper_uri, CaperURI
from .caper_backend import BACKEND_GCP, BACKEND_AWS, BACKEND_LOCAL, \
    CaperBackendCommon, CaperBackendDatabase, CaperBackendGCP, \
    CaperBackendAWS, CaperBackendLocal, CaperBackendSLURM, \
    CaperBackendSGE, CaperBackendPBS


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


class Caper(object):
    """Cromwell/WDL wrapper
    """

    CROMWELL_JAR_DIR = '~/.caper/cromwell_jar'
    BACKEND_CONF_HEADER = 'include required(classpath("application"))\n'
    DEFAULT_BACKEND = BACKEND_LOCAL
    RE_PATTERN_BACKEND_CONF_HEADER = r'^\s*include\s'
    RE_PATTERN_WDL_COMMENT_DOCKER = r'^\s*\#\s*CAPER\s+docker\s(.+)'
    RE_PATTERN_WDL_COMMENT_SINGULARITY = \
        r'^\s*\#\s*CAPER\s+singularity\s(.+)'
    RE_PATTERN_STARTED_WORKFLOW_ID = \
        r'started WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)'
    RE_PATTERN_FINISHED_WORKFLOW_ID = \
        r'WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b) is in a terminal state'
    RE_PATTERN_WORKFLOW_ID = \
        r'\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b'
    RE_PATTERN_WDL_IMPORT = r'^\s*import\s+[\"\'](.+)[\"\']\s+as\s+'
    RE_PATTERN_DELIMITER_GCP_ZONES = r',| '
    USER_INTERRUPT_WARNING = '\n********** DO NOT CTRL+C MULTIPLE TIMES **********\n'

    SEC_INTERVAL_UPDATE_METADATA = 240.0
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
        # init REST API
        self._port = args.get('port')
        self._ip = args.get('ip')
        self._cromwell_rest_api = CromwellRestAPI(
            ip=self._ip, port=self._port, verbose=False)

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

        self._backend_file = args.get('backend_file')
        self._wdl = args.get('wdl')
        self._inputs = args.get('inputs')
        self._cromwell = args.get('cromwell')
        self._workflow_opts = args.get('options')
        self._str_label = args.get('str_label')
        self._labels = args.get('labels')
        self._imports = args.get('imports')
        self._metadata_output = args.get('metadata_output')
        self._singularity_cachedir = args.get('singularity_cachedir')

        # file DB
        self._file_db = args.get('file_db')
        self._no_file_db = args.get('no_file_db')

        # MySQL DB
        self._mysql_db_ip = args.get('mysql_db_ip')
        self._mysql_db_port = args.get('mysql_db_port')
        self._mysql_db_user = args.get('mysql_db_user')
        self._mysql_db_password = args.get('mysql_db_password')

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
        self._deepcopy = args.get('deepcopy')
        self._deepcopy_ext = args.get('deepcopy_ext')
        if self._deepcopy_ext is not None:
            self._deepcopy_ext = [
                '.'+ext for ext in self._deepcopy_ext.split(',')]

        # containers
        self._use_singularity = args.get('use_singularity')
        self._no_build_singularity = args.get('no_build_singularity')
        self._use_docker = args.get('use_docker')
        self._singularity = args.get('singularity')
        self._docker = args.get('docker')
        if self._singularity is not None:
            self._use_singularity = True
        if self._docker is not None:
            self._use_docker = True

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
        imports_file = self.__create_imports_zip_file_from_wdl(tmp_dir)

        # metadata JSON file is an output from Cromwell
        #   place it on the tmp dir
        metadata_file = os.path.join(
            tmp_dir, Caper.TMP_FILE_BASENAME_METADATA_JSON)

        java_heap = '-Xmx{}'.format(self._java_heap_run)
        # LOG_LEVEL must be >=INFO to catch workflow ID from STDOUT
        cmd = ['java', java_heap, '-XX:ParallelGCThreads=1', '-DLOG_LEVEL=INFO',
               '-jar', '-Dconfig.file={}'.format(backend_file),
               self.__download_cromwell_jar(), 'run',
               CaperURI(self._wdl).get_local_file(),
               '-i', input_file,
               '-o', workflow_opts_file,
               '-l', labels_file,
               '-m', metadata_file]
        if imports_file is not None:
            cmd += ['-p', imports_file]
        print('[Caper] cmd: ', cmd)

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
            print(Caper.USER_INTERRUPT_WARNING)
            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')
                print(stdout)

        # move metadata file to a workflow output directory
        if metadata_file is not None and workflow_id is not None:
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
                CaperURI(metadata_uri).get_local_file(),
                self._show_completed_task)

        print('[Caper] run: ', rc, workflow_id, metadata_uri)
        return workflow_id

    def server(self):
        """Run a Cromwell server
        """
        tmp_dir = self.__mkdir_tmp_dir()
        backend_file = self.__create_backend_conf_file(tmp_dir)

        java_heap = '-Xmx{}'.format(self._java_heap_server)
        # LOG_LEVEL must be >=INFO to catch workflow ID from STDOUT
        cmd = ['java', java_heap, '-XX:ParallelGCThreads=1', '-DLOG_LEVEL=INFO',
               '-jar', '-Dconfig.file={}'.format(backend_file),
               self.__download_cromwell_jar(), 'server']
        print('[Caper] cmd: ', cmd)

        # pending/running workflows
        started_wf_ids = set()
        # completed, aborted or terminated workflows
        finished_wf_ids = set()
        try:
            p = Popen(cmd, stdout=PIPE, universal_newlines=True)
            rc = None
            t0 = time.perf_counter()  # tickcount

            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')
                if stdout != '':
                    print(stdout)

                # find workflow id from Cromwell server's STDOUT
                wf_ids_with_status = \
                    Caper.__get_workflow_ids_from_cromwell_stdout(stdout)
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
            print(Caper.USER_INTERRUPT_WARNING)
            while p.poll() is None:
                stdout = p.stdout.readline().strip('\n')
                print(stdout)
        print('[Caper] server: ', rc, started_wf_ids, finished_wf_ids)
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
        imports_file = self.__create_imports_zip_file_from_wdl(tmp_dir)
        workflow_opts_file = self.__create_workflow_opts_json_file(
            input_file, tmp_dir)
        labels_file = self.__create_labels_json_file(tmp_dir)
        on_hold = self._hold if self._hold is not None else False

        r = self._cromwell_rest_api.submit(
            source=CaperURI(self._wdl).get_local_file(),
            dependencies=imports_file,
            inputs_file=input_file,
            options_file=workflow_opts_file,
            labels_file=labels_file,
            on_hold=on_hold)
        print("[Caper] submit: ", r)
        return r

    def abort(self):
        """Abort running/pending workflows on a Cromwell server
        """
        r = self._cromwell_rest_api.abort(
                self._wf_id_or_label,
                [(Caper.KEY_CAPER_STR_LABEL, v)
                 for v in self._wf_id_or_label])
        print("[Caper] abort: ", r)
        return r

    def unhold(self):
        """Release hold of workflows on a Cromwell server
        """
        r = self._cromwell_rest_api.release_hold(
                self._wf_id_or_label,
                [(Caper.KEY_CAPER_STR_LABEL, v)
                 for v in self._wf_id_or_label])
        print("[Caper] unhold: ", r)
        return r

    def metadata(self, no_print=False):
        """Retrieve metadata for workflows from a Cromwell server
        """
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
            submission = w['submission']

            if self._hide_result_before is not None:
                if submission <= self._hide_result_before:
                    continue
            for f in formats:
                if f == 'workflow_id':
                    row.append(str(workflow_id))
                elif f == 'str_label':
                    lbl = self._cromwell_rest_api.get_label(
                        workflow_id,
                        Caper.KEY_CAPER_STR_LABEL)
                    row.append(str(lbl))
                elif f == 'user':
                    lbl = self._cromwell_rest_api.get_label(
                        workflow_id,
                        Caper.KEY_CAPER_USER)
                    row.append(str(lbl))
                else:
                    row.append(str(w[f] if f in w else None))
            print('\t'.join(row))
        return workflows

    def troubleshoot(self):
        """Troubleshoot errors based on information from Cromwell's metadata
        """
        if self._wf_id_or_label is None or len(self._wf_id_or_label) == 0:
            return
        # if it's a file
        wf_id_or_label = []
        metadatas = []
        for f in self._wf_id_or_label:
            cu = CaperURI(f)
            if cu.file_exists():
                metadatas.append(cu.get_local_file())
            else:
                wf_id_or_label.append(f)

        if len(wf_id_or_label) > 0:
            self._wf_id_or_label = wf_id_or_label
            metadatas.extend(self.metadata(no_print=True))

        for metadata in metadatas:
            Caper.__troubleshoot(metadata, self._show_completed_task)

    def __download_cromwell_jar(self):
        """Download cromwell-X.jar
        """
        cu = CaperURI(self._cromwell)
        if cu.uri_type == URI_LOCAL:
            return cu.get_uri()

        path = os.path.join(
            os.path.expanduser(Caper.CROMWELL_JAR_DIR),
            os.path.basename(self._cromwell))
        return cu.copy(target_uri=path)

    def __write_metadata_jsons(self, workflow_ids):
        try:
            for wf_id in workflow_ids:
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
            return True
        except Exception as e:
            print('[Caper] Exception caught while retrieving '
                  'metadata from Cromwell server. Keeping running... ',
                  str(e), workflow_ids)
        return False

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

        return CaperURI(metadata_uri).write_str_to_file(
            json.dumps(metadata_json, indent=4)).get_uri()

    def __create_input_json_file(
            self, directory, fname='inputs.json'):
        """Make a copy of input JSON file.
        Deepcopy to a specified storage if required.
        """
        if self._inputs is not None:
            c = CaperURI(self._inputs)
            if self._deepcopy and self._deepcopy_ext:
                # deepcopy all files in JSON/TSV/CSV
                #   to the target backend
                if self._backend == BACKEND_GCP:
                    uri_type = URI_GCS
                elif self._backend == BACKEND_AWS:
                    uri_type = URI_S3
                else:
                    uri_type = URI_LOCAL
                c = c.deepcopy(uri_type=uri_type,
                               uri_exts=self._deepcopy_ext)
            return c.get_local_file()
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
            s = CaperURI(self._labels).get_file_contents()
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
                # find docker/singularity from WDL or command line args
                docker = self.__find_docker_from_wdl()
            else:
                docker = self._docker
            if docker is None:
                raise Exception('Docker image URI must be specified either in '
                      'cmd line/conf file (--docker) or in WDL (#CAPER docker) '
                      'for cloud backends (gcp, aws)')
            template['default_runtime_attributes']['docker'] = docker

        if self._use_singularity:
            if self._singularity is None:
                singularity = self.__find_singularity_from_wdl()
            else:
                singularity = self._singularity
            assert(singularity is not None)
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
            f = CaperURI(self._workflow_opts).get_local_file()
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
        if self._imports is not None:
            return CaperURI(self._imports).get_local_file()

        imports = self.__find_val_from_wdl(Caper.RE_PATTERN_WDL_IMPORT)
        if imports is None:
            return None

        zip_tmp_dir = os.path.join(directory, 'imports_zip_tmp_dir')

        files_to_zip = []
        for imp in imports:
            # ignore imports as HTTP URL or absolute PATH
            if CaperURI(imp).uri_type == URI_LOCAL \
                    or not os.path.isabs(imp):
                # download imports relative to WDL (which can exists remotely)
                wdl_dirname = os.path.dirname(self._wdl)
                c_imp_ = CaperURI(os.path.join(wdl_dirname, imp))
                # download file to tmp_dir
                f = c_imp_.get_local_file()
                target_f = os.path.join(zip_tmp_dir, imp)
                target_dirname = os.path.dirname(target_f)
                os.makedirs(target_dirname, exist_ok=True)
                shutil.copyfile(f, target_f)

        if len(files_to_zip) == 0:
            return None

        imports_file = os.path.join(directory, fname)
        imports_file_wo_ext, ext = os.path.splitext(imports_file)
        shutil.make_archive(imports_file_wo_ext, 'zip', zip_tmp_dir)
        shutil.rmtree(zip_tmp_dir)
        return imports_file

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

        # local backend
        merge_dict(
            backend_dict,
            CaperBackendLocal(
                out_dir=self._out_dir,
                concurrent_job_limit=self._max_concurrent_tasks))
        # GC
        if self._gcp_prj is not None and self._out_gcs_bucket is not None:
            merge_dict(
                backend_dict,
                CaperBackendGCP(
                    gcp_prj=self._gcp_prj,
                    out_gcs_bucket=self._out_gcs_bucket,
                    concurrent_job_limit=self._max_concurrent_tasks))
        # AWS
        if self._aws_batch_arn is not None and self._aws_region is not None \
                and self._out_s3_bucket is not None:
            merge_dict(
                backend_dict,
                CaperBackendAWS(
                    aws_batch_arn=self._aws_batch_arn,
                    aws_region=self._aws_region,
                    out_s3_bucket=self._out_s3_bucket,
                    concurrent_job_limit=self._max_concurrent_tasks))
        # SLURM
        merge_dict(
            backend_dict,
            CaperBackendSLURM(
                out_dir=self._out_dir,
                partition=self._slurm_partition,
                account=self._slurm_account,
                extra_param=self._slurm_extra_param,
                concurrent_job_limit=self._max_concurrent_tasks))
        # SGE
        merge_dict(
            backend_dict,
            CaperBackendSGE(
                out_dir=self._out_dir,
                pe=self._sge_pe,
                queue=self._sge_queue,
                extra_param=self._sge_extra_param,
                concurrent_job_limit=self._max_concurrent_tasks))

        # PBS
        merge_dict(
            backend_dict,
            CaperBackendPBS(
                out_dir=self._out_dir,
                queue=self._pbs_queue,
                extra_param=self._pbs_extra_param,
                concurrent_job_limit=self._max_concurrent_tasks))

        # Database
        if self._no_file_db is not None and self._no_file_db:
            file_db = None
        else:
            file_db = self._file_db
        merge_dict(
            backend_dict,
            CaperBackendDatabase(
                file_db=file_db,
                mysql_ip=self._mysql_db_ip,
                mysql_port=self._mysql_db_port,
                mysql_user=self._mysql_db_user,
                mysql_password=self._mysql_db_password))

        # set header for conf ("include ...")
        assert(Caper.BACKEND_CONF_HEADER.endswith('\n'))
        lines_header = [Caper.BACKEND_CONF_HEADER]

        # override with user-specified backend.conf if exists
        if self._backend_file is not None:
            lines_wo_header = []

            with open(CaperURI(self._backend_file).get_local_file(),
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

    def __find_docker_from_wdl(self):
        r = self.__find_val_from_wdl(
            Caper.RE_PATTERN_WDL_COMMENT_DOCKER)
        return r[0] if len(r) > 0 else None

    def __find_singularity_from_wdl(self):
        r = self.__find_val_from_wdl(
            Caper.RE_PATTERN_WDL_COMMENT_SINGULARITY)
        return r[0] if len(r) > 0 else None

    def __find_val_from_wdl(self, regex_val):
        result = []
        if self._wdl is not None:
            with open(CaperURI(self._wdl).get_local_file(), 'r') as fp:
                for line in fp.readlines():
                    r = re.findall(regex_val, line)
                    if len(r) > 0:
                        ret = r[0].strip()
                        if len(ret) > 0:
                            result.append(ret)
        return result

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
            print('[Caper] building local singularity image: ',
                  singularity)
            cmd = ['singularity', 'exec', singularity,
                   'echo', '[Caper] building done.']
            if self._singularity_cachedir is not None \
                    and 'SINGULARITY_CACHEDIR' not in os.environ:
                env = {'SINGULARITY_CACHEDIR': self._singularity_cachedir}
            else:
                env = None
            return check_call(cmd, env=env)

        print('[Caper] skip building local singularity image.')
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
    def __get_time_str():
        return datetime.now().strftime('%Y%m%d_%H%M%S_%f')

    @staticmethod
    def __troubleshoot(metadata_json, show_completed_task=False):
        """Troubleshoot from metadata JSON obj/file
        """
        if isinstance(metadata_json, dict):
            metadata = metadata_json
        else:
            f = CaperURI(metadata_json).get_local_file()
            with open(f, 'r') as fp:
                metadata = json.loads(fp.read())
        if isinstance(metadata, list):
            metadata = metadata[0]

        workflow_id = metadata['id']
        workflow_status = metadata['status']
        print('[Caper] troubleshooting {} ...'.format(workflow_id))
        if not show_completed_task and workflow_status == 'Succeeded':
            print('This workflow ran successfully. '
                  'There is nothing to troubleshoot')
            return

        def recurse_calls(calls, failures=None, show_completed_task=False):
            if failures is not None:
                s = json.dumps(failures, indent=4)
                print('Found failures:\n{}'.format(s))
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
                    if 'executionEvents' in call:
                        for ev in call['executionEvents']:
                            if ev['description'].startswith('Running'):
                                run_start = ev['startTime']
                                run_end = ev['endTime']
                                break
                    else:
                        run_start = None
                        run_end = None

                    if not show_completed_task and \
                            task_status in ('Done', 'Succeeded'):
                        continue
                    print('\n{} {}. SHARD_IDX={}, RC={}, JOB_ID={}, '
                          'RUN_START={}, RUN_END={}, '
                          'STDOUT={}, STDERR={}'.format(
                            task_name, task_status, shard_index, rc, job_id,
                            run_start, run_end, stdout, stderr))

                    if stderr is not None:
                        cu = CaperURI(stderr)
                        if cu.file_exists():
                            local_stderr_f = cu.get_local_file()
                            with open(local_stderr_f, 'r') as fp:
                                stderr_contents = fp.read()
                            print('STDERR_CONTENTS=\n{}'.format(
                                stderr_contents))

        calls = metadata['calls']
        failures = metadata['failures'] if 'failures' in metadata else None
        recurse_calls(calls, failures, show_completed_task)

    @staticmethod
    def __find_singularity_bindpath(input_json_file):
        """Read input JSON file and find paths to be bound for singularity
        by finding common roots for all files in input JSON file
        """
        with open(input_json_file, 'r') as fp:
            input_json = json.loads(fp.read())

        # find dirname of all files
        def recurse_dict(d, d_parent=None, d_parent_key=None,
                         lst=None, lst_idx=None):
            result = set()
            if isinstance(d, dict):
                for k, v in d.items():
                    result |= recurse_dict(v, d_parent=d,
                                           d_parent_key=k)
            elif isinstance(d, list):
                for i, v in enumerate(d):
                    result |= recurse_dict(v, lst=d,
                                           lst_idx=i)
            elif type(d) == str:
                assert(d_parent is not None or lst is not None)
                c = CaperURI(d)
                # local absolute path only
                if c.uri_type == URI_LOCAL and c.is_valid_uri():
                    dirname, basename = os.path.split(c.get_uri())
                    result.add(dirname)

            return result

        all_dirnames = recurse_dict(input_json)
        # add all (but not too high level<4) parent directories
        # to all_dirnames. start from self
        # e.g. /a/b/c/d/e/f/g/h with COMMON_ROOT_SEARCH_LEVEL = 5
        # add all the followings:
        # /a/b/c/d/e/f/g/h (self)
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

    # init caper uri to transfer files across various storages
    #   e.g. gs:// to s3://, http:// to local, ...
    init_caper_uri(
        tmp_dir=args.get('tmp_dir'),
        tmp_s3_bucket=args.get('tmp_s3_bucket'),
        tmp_gcs_bucket=args.get('tmp_gcs_bucket'),
        http_user=args.get('http_user'),
        http_password=args.get('http_password'),
        use_netrc=args.get('use_netrc'),
        use_gsutil_over_aws_s3=args.get('use_gsutil_over_aws_s3'),
        verbose=True)

    # init caper: taking all args at init step
    c = Caper(args)

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
    elif action == 'unhold':
        c.unhold()
    elif action == 'troubleshoot':
        c.troubleshoot()

    else:
        raise Exception('Unsupported or unspecified action.')
    return 0


if __name__ == '__main__':
    main()
