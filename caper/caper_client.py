import logging
import os
from autouri import AutoURI
from datetime import datetime
from .caper_base import CaperBase
from .caper_wdl_parser import CaperWDLParser
from .caper_workflow_opts import CaperWorkflowOpts
from .caper_labels import CaperLabels
from .cromwell import Cromwell
from .cromwell_rest_api import CromwellRestAPI
from .server_heartbeat import ServerHeartbeat
from .singularity import Singularity


logger = logging.getLogger(__name__)


class CaperClient(CaperBase):
    def __init__(
            self,
            tmp_dir,
            tmp_gcs_bucket=None,
            tmp_s3_bucket=None,        
            server_heartbeat_file=CaperBase.DEFAULT_SERVER_HEARTBEAT_FILE,
            server_heartbeat_timeout=ServerHeartbeat.DEFAULT_HEARTBEAT_TIMEOUT_MS,
            server_hostname=CromwellRestAPI.DEFAULT_HOSTNAME,
            server_port=CromwellRestAPI.DEFAULT_PORT):
        """Initializes CaperClient.

        Args:
            server_hostname:
                Use this hostname if server_heartbeat_file is not available.
            server_port:
                Use this port if server_heartbeat_file is not available.
        """
        super().__init__(
            tmp_dir=tmp_dir,
            tmp_gcs_bucket=tmp_gcs_bucket,
            tmp_s3_bucket=tmp_s3_bucket,
            server_heartbeat_file=server_heartbeat_file,
            server_heartbeat_timeout=server_heartbeat_timeout)

        self._server_hostname = server_hostname
        self._server_port = server_port

        self._server_hostname, self._server_port = self._get_hostname_port()

    def abort(self, wf_ids_or_labels):
        """Abort running/pending workflows on a Cromwell server.
        """
        r = self._get_cromwell_rest_api().abort(
                wf_ids_or_labels,
                [(CaperLabels.KEY_CAPER_STR_LABEL, v) for v in wf_ids_or_labels])
        logger.info('abort: {r}'.format(r=r))
        return r

    def unhold(self, wf_ids_or_labels):
        """Release hold of workflows on a Cromwell server.
        """
        r = self._get_cromwell_rest_api().release_hold(
                wf_ids_or_labels,
                [(CaperLabels.KEY_CAPER_STR_LABEL, v) for v in wf_ids_or_labels])
        logger.info('unhold: {r}'.format(r=r))
        return r

    def list(self, wf_ids_or_labels=None):
        """Retrieves list of running/pending workflows from a Cromwell server

        Args:
            wf_ids_or_labels:
                List of Workflow IDs or Caper's string labels.
                Wild cards (*, ?) allowed.
        """
        if wf_ids_or_labels:
            workflow_ids = wf_ids_or_labels
            labels = [(CaperLabels.KEY_CAPER_STR_LABEL, v) for v in wf_ids_or_labels]
        else:
            workflow_ids = ['*']
            labels = [(CaperLabels.KEY_CAPER_STR_LABEL, '*')]

        return self._get_cromwell_rest_api().find(workflow_ids, labels)

    def metadata(self, wf_ids_or_labels, embed_subworkflow=False):
        """Retrieves metadata for workflows from a Cromwell server.

        Args:
            wf_ids_or_labels:
                List of Workflow IDs or Caper's string labels.
                Wild cards (*, ?) allowed.
            embed_subworkflow:
                Recursively embed subworkflow's metadata JSON object
                in parent workflow's metadata JSON.
        Returns:
            List of metadata JSONs of matched worflows.
        """
        return self._get_cromwell_rest_api().get_metadata(
            wf_ids_or_labels,
            [(CaperLabels.KEY_CAPER_STR_LABEL, v) for v in wf_ids_or_labels],
            embed_subworkflow=embed_subworkflow)

    def _get_hostname_port(self):
        if self._server_heartbeat:
            res = self._server_heartbeat.read_from_file()
            if res:
                return res
        return self._server_hostname, self._server_port

    def _get_cromwell_rest_api(self):
        res = self._get_hostname_port()
        if res:
            return CromwellRestAPI(res[0], res[1])
        return None


class CaperClientSubmit(CaperClient):
    def __init__(
            self,
            tmp_dir,
            tmp_gcs_bucket=None,
            tmp_s3_bucket=None,        
            server_hostname=CromwellRestAPI.DEFAULT_HOSTNAME,
            server_port=CromwellRestAPI.DEFAULT_PORT,
            server_heartbeat_file=CaperBase.DEFAULT_SERVER_HEARTBEAT_FILE,
            server_heartbeat_timeout=ServerHeartbeat.DEFAULT_HEARTBEAT_TIMEOUT_MS,
            womtool=Cromwell.DEFAULT_WOMTOOL,
            java_heap_womtool=Cromwell.DEFAULT_JAVA_HEAP_WOMTOOL,            
            gcp_zones=None,
            slurm_partition=None,
            slurm_account=None,
            slurm_extra_param=None,
            sge_pe=None,
            sge_queue=None,
            sge_extra_param=None,
            pbs_queue=None,
            pbs_extra_param=None):
        """
        Args:
            womtool:
                Womtool JAR file.
            java_heap_run:
                Java heap for Womtool valididation.            
        """
        super().__init__(            
            tmp_dir=tmp_dir,
            tmp_gcs_bucket=tmp_gcs_bucket,
            tmp_s3_bucket=tmp_s3_bucket,        
            server_hostname=server_hostname,
            server_port=server_port,
            server_heartbeat_file=server_heartbeat_file,            
            server_heartbeat_timeout=server_heartbeat_timeout)

        self._womtool = womtool
        self._java_heap_womtool = java_heap_womtool

        self._caper_workflow_opts = CaperWorkflowOpts(
            gcp_zones=gcp_zones,
            slurm_partition=slurm_partition,
            slurm_account=slurm_account,
            slurm_extra_param=slurm_extra_param,
            sge_pe=sge_pe,
            sge_queue=sge_queue,
            sge_extra_param=sge_extra_param,
            pbs_queue=pbs_queue,
            pbs_extra_param=pbs_extra_param)

        self._caper_labels = CaperLabels()

    def submit(
            self, wdl,
            inputs=None,
            options=None,
            labels=None,
            imports=None,
            str_label=None,
            user=None,
            docker=None,
            singularity=None,
            singularity_cachedir=Singularity.DEFAULT_SINGULARITY_CACHEDIR,
            no_build_singularity=False,            
            backend=None,
            max_retries=CaperWorkflowOpts.DEFAULT_MAX_RETRIES,            
            tmp_dir=None,
            ignore_womtool=False,
            no_deepcopy=False,
            hold=False,
            dry_run=False):
        """Submit a workflow to Cromwell server.

        Args:
            wdl:
                WDL file.
            inputs:
                Input JSON file.
            options:
                Workflow options JSON file.
            labels:
                Labels JSON file.
            imports:
                imports ZIP file.
            str_label:
                Caper's string label, which will be written to labels JSON file.
                If user's custom labels file is given then two will be merged.
            user:
                Username. If not defined, find a username from system.
            docker:
                Docker image to run a workflow on.
                This will add "docker" attribute to runtime {} section
                of all tasks in WDL.
                This will be overriden by existing "docker" attr defined in 
                WDL's task's "runtime {} section.
            singularity:
                Singularity image to run a workflow on.
                To use this, do not define "docker" attribute in 
                WDL's task's "runtime {} section.
            singularity_cachedir:
                Cache directory for local Singularity images.
                If there is a shell environment variable SINGULARITY_CACHEDIR
                define then this parameter will be ignored.
            no_build_singularity:
                Do not build local singularity image.
                However, a local singularity image will be eventually built on
                env var SINGULARITY_CACHEDIR.
                Therefore, use this flag if you have already built it.                
            backend:
                Choose among Caper's built-in backends.
                (aws, gcp, Local, slurm, sge, pbs).
                Or use a backend defined in your custom backend config file
                (above "backend_conf" file).
            tmp_dir:
                Local temporary directory to store all temporary files.
                Temporary files mean intermediate files used for running Cromwell.
                For example, workflow options file, imports zip file.
                Localized (recursively) data files defined in input JSON
                will NOT be stored here.
                They will be localized on self._tmp_dir instead.
                If this is not defined, then cache directory self._tmp_dir will be used.
            ignore_womtool:
                Disable Womtool validation for WDL/input JSON/imports.
            no_deepcopy:
                Disable recursive localization of files defined in input JSON.
                Input JSON file itself will still be localized.
            hold:
                Put a workflow on hold when submitted. This workflow will be on hold until
                it's released. See self.unhold() for details.
            dry_run:
                Stop before running Java command line for Cromwell.
        """
        u_wdl = AutoURI(wdl)
        if not u_wdl.exists:
            raise FileNotFound(
                'WDL does not exists. {wdl}'.format(wdl=wdl))

        if tmp_dir is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            suffix = os.path.join(u_wdl.basename_wo_ext, timestamp)
            tmp_dir = os.path.join(self._tmp_dir, suffix)
        os.makedirs(tmp_dir, exist_ok=True)

        wdl = u_wdl.localize_on(tmp_dir)

        cromwell_rest_api = self._get_cromwell_rest_api()
        if backend is None:
            backend = cromwell_rest_api.get_default_backend()

        if inputs:
            maybe_remote_file = self.localize_on_backend(
                inputs,
                backend=backend,
                recursive=not no_deepcopy,
                make_md5_file=True)
            inputs = AutoURI(maybe_remote_file).localize_on(tmp_dir)

        options = self._caper_workflow_opts.create_file(
            directory=tmp_dir,
            wdl=wdl,
            inputs=inputs,
            custom_options=options,
            docker=docker,
            singularity=singularity,
            singularity_cachedir=singularity_cachedir,
            no_build_singularity=no_build_singularity,
            backend=backend,
            max_retries=max_retries)

        labels = self._caper_labels.create_file(
            directory=tmp_dir,
            backend=backend,
            custom_labels=labels,
            str_label=str_label,
            user=user)

        wdl_parser = CaperWDLParser(wdl)
        if imports:
            imports = AutoURI(imports).localize_on(tmp_dir)
        else:
            imports = wdl_parser.create_imports_file(tmp_dir)

        logger.debug(
            'submit params: wdl={w}, imports={imp}, inputs={i}, '
            'options={o}, labels={l}, hold={hold}'.format(
                w=wdl,
                imp=imports,
                i=inputs,
                o=options,
                l=labels,
                hold=hold))

        if not ignore_womtool:
            cromwell = Cromwell(
                womtool=self._womtool,
                java_heap_womtool=self._java_heap_womtool)
            cromwell.validate(
                wdl=wdl,
                inputs=inputs,
                imports=imports)

        if dry_run:
            return None

        r = cromwell_rest_api.submit(
            source=wdl,
            dependencies=imports,
            inputs=inputs,
            options=options,
            labels=labels,
            on_hold=hold)
        logger.info('submit: {r}'.format(r=r))
        return r
