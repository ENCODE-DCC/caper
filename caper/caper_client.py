import logging

from autouri import AutoURI

from .caper_base import CaperBase
from .caper_labels import CaperLabels
from .caper_wdl_parser import CaperWDLParser
from .caper_workflow_opts import CaperWorkflowOpts
from .cromwell import Cromwell
from .cromwell_rest_api import CromwellRestAPI, has_wildcard, is_valid_uuid
from .singularity import Singularity

logger = logging.getLogger(__name__)


class CaperClient(CaperBase):
    def __init__(
        self,
        local_loc_dir=None,
        gcp_loc_dir=None,
        aws_loc_dir=None,
        gcp_service_account_key_json=None,
        server_hostname=CromwellRestAPI.DEFAULT_HOSTNAME,
        server_port=CromwellRestAPI.DEFAULT_PORT,
        server_heartbeat=None,
    ):
        """Initializes for Caper's client functions.

        Args:
            server_hostname:
                Server hostname.
                Used only if heartbeat file is not available or timed out.
            server_port:
                Server port.
                Used only if heartbeat file is not available or timed out.
            server_heartbeat:
                ServerHeartbeat object in which a heartbeat file is defined.
                This object is to read hostname/port pair from it.
        """
        super().__init__(
            local_loc_dir=local_loc_dir,
            gcp_loc_dir=gcp_loc_dir,
            aws_loc_dir=aws_loc_dir,
            gcp_service_account_key_json=gcp_service_account_key_json,
        )

        if server_heartbeat:
            res = server_heartbeat.read()
            if res:
                server_hostname, server_port = res

        if not server_hostname or not server_port:
            raise ValueError(
                'Server hostname/port must be defined '
                'if server heartbeat is not available or timed out.'
            )

        self._cromwell_rest_api = CromwellRestAPI(server_hostname, server_port)

    def abort(self, wf_ids_or_labels):
        """Abort running/pending workflows on a Cromwell server.

        Args:
            wf_ids_or_labels:
                List of workflows IDs or string labels (Caper's string label)
                Wild cards (*, ?) are allowed.
        """
        workflow_ids, labels = self._split_workflow_ids_and_labels(wf_ids_or_labels)

        r = self._cromwell_rest_api.abort(workflow_ids, labels)
        logger.info('abort: {r}'.format(r=r))
        return r

    def unhold(self, wf_ids_or_labels):
        """Release hold of workflows on a Cromwell server.

        Args:
            wf_ids_or_labels:
                List of workflows IDs or string labels (Caper's string label)
                Wild cards (*, ?) are allowed.
        """
        workflow_ids, labels = self._split_workflow_ids_and_labels(wf_ids_or_labels)

        r = self._cromwell_rest_api.release_hold(workflow_ids, labels)
        logger.info('unhold: {r}'.format(r=r))
        return r

    def list(self, wf_ids_or_labels=None, exclude_subworkflow=True):
        """Retrieves list of running/pending workflows from a Cromwell server

        Args:
            wf_ids_or_labels:
                List of workflows IDs or string labels (Caper's string label)
                Wild cards (*, ?) are allowed.
            exclude_subworkflow:
                Exclude subworkflows
        Returns:
            List of workflows found. Each workflow object will be in a form of
            Cromwell's metadata JSON file but with limited amount of information.
            e.g. workflow ID, status, labels.
        """
        if wf_ids_or_labels:
            workflow_ids, labels = self._split_workflow_ids_and_labels(wf_ids_or_labels)
        else:
            workflow_ids, labels = ['*'], None

        return self._cromwell_rest_api.find(
            workflow_ids, labels, exclude_subworkflow=exclude_subworkflow
        )

    def metadata(self, wf_ids_or_labels, embed_subworkflow=False):
        """Retrieves metadata for workflows from a Cromwell server.

        Args:
            wf_ids_or_labels:
                List of workflows IDs or string labels (Caper's string label)
                Wild cards (*, ?) are allowed.
            embed_subworkflow:
                Recursively embed subworkflow's metadata JSON object
                in parent workflow's metadata JSON.
                This is to mimic behavior of Cromwell's run mode paramteter -m.
        Returns:
            List of metadata JSONs of matched worflows.
        """
        workflow_ids, labels = self._split_workflow_ids_and_labels(wf_ids_or_labels)

        return self._cromwell_rest_api.get_metadata(
            workflow_ids, labels, embed_subworkflow=embed_subworkflow
        )

    def _split_workflow_ids_and_labels(self, workflow_ids_or_labels):
        workflow_ids = []
        labels = []

        if workflow_ids_or_labels:
            for query in workflow_ids_or_labels:
                if is_valid_uuid(query):
                    workflow_ids.append(query)
                else:
                    labels.append((CaperLabels.KEY_CAPER_STR_LABEL, query))
                    if has_wildcard(query):
                        workflow_ids.append(query)

        return workflow_ids, labels


class CaperClientSubmit(CaperClient):
    def __init__(
        self,
        local_loc_dir=None,
        gcp_loc_dir=None,
        aws_loc_dir=None,
        gcp_service_account_key_json=None,
        server_hostname=CromwellRestAPI.DEFAULT_HOSTNAME,
        server_port=CromwellRestAPI.DEFAULT_PORT,
        server_heartbeat=None,
        womtool=Cromwell.DEFAULT_WOMTOOL,
        use_google_cloud_life_sciences=False,
        gcp_zones=None,
        slurm_partition=None,
        slurm_account=None,
        slurm_extra_param=None,
        sge_pe=None,
        sge_queue=None,
        sge_extra_param=None,
        pbs_queue=None,
        pbs_extra_param=None,
    ):
        """Submit subcommand needs much more parameters than other client subcommands.

        Args:
            womtool:
                Womtool JAR file.
            use_google_cloud_life_sciences:
                Use Google Cloud Life Sciences API.
                gcp_zones will be ignored since it's already configured with in
                server side backend.conf.
            gcp_zones:
                GCP zones. Used for gcp backend only.
            slurm_partition:
                SLURM partition if required to sbatch jobs.
            slurm_account:
                SLURM account if required to sbatch jobs.
            slurm_extra_param:
                SLURM extra parameter to be appended to sbatch command line.
            sge_pe:
                SGE parallel environment (required to run with multiple cpus).
            sge_queue:
                SGE queue.
            sge_extra_param:
                SGE extra parameter to be appended to qsub command line.
            pbs_queue:
                PBS queue.
            pbs_extra_param:
                PBS extra parameter to be appended to qsub command line.
        """
        super().__init__(
            local_loc_dir=local_loc_dir,
            gcp_loc_dir=gcp_loc_dir,
            aws_loc_dir=aws_loc_dir,
            gcp_service_account_key_json=gcp_service_account_key_json,
            server_hostname=server_hostname,
            server_port=server_port,
            server_heartbeat=server_heartbeat,
        )

        self._cromwell = Cromwell(womtool=womtool)

        self._caper_workflow_opts = CaperWorkflowOpts(
            use_google_cloud_life_sciences=use_google_cloud_life_sciences,
            gcp_zones=gcp_zones,
            slurm_partition=slurm_partition,
            slurm_account=slurm_account,
            slurm_extra_param=slurm_extra_param,
            sge_pe=sge_pe,
            sge_queue=sge_queue,
            sge_extra_param=sge_extra_param,
            pbs_queue=pbs_queue,
            pbs_extra_param=pbs_extra_param,
        )

        self._caper_labels = CaperLabels()

    def submit(
        self,
        wdl,
        backend=None,
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
        max_retries=CaperWorkflowOpts.DEFAULT_MAX_RETRIES,
        memory_retry_multiplier=CaperWorkflowOpts.DEFAULT_MEMORY_RETRY_MULTIPLIER,
        gcp_monitoring_script=CaperWorkflowOpts.DEFAULT_GCP_MONITORING_SCRIPT,
        ignore_womtool=False,
        no_deepcopy=False,
        hold=False,
        java_heap_womtool=Cromwell.DEFAULT_JAVA_HEAP_WOMTOOL,
        dry_run=False,
        work_dir=None,
    ):
        """Submit a workflow to Cromwell server.

        Args:
            wdl:
                WDL file.
            backend:
                Backend to run a workflow on.
                Choose among Caper's built-in or user's custom backends.
                (aws, gcp, Local, slurm, sge, pbs, ...).
                If not defined then server's default backend will be used.
            inputs:
                Input JSON file.
            options:
                Workflow options JSON file.
            labels:
                Labels JSON file.
            imports:
                imports ZIP file.
            str_label:
                Caper's string label for a workflow,
                which will be written to labels JSON file.
            user:
                Username. If not defined, find a username from system.
                This will be written to to Cromwell' labels JSON file and will not
                be used elsewhere.
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
            max_retries:
                Max retrial for a failed task. 0 or None means no trial.
            memory_retry_multiplier:
                Multiplier for the memory retry feature.
                See https://cromwell.readthedocs.io/en/develop/cromwell_features/RetryWithMoreMemory/
                for details.
            ignore_womtool:
                Disable Womtool validation for WDL/input JSON/imports.
            no_deepcopy:
                Disable recursive localization of files defined in input JSON.
                Input JSON file itself will still be localized.
            hold:
                Put a workflow on hold when submitted. This workflow will be on hold until
                it's released. See self.unhold() for details.
            java_heap_womtool:
                Java heap (java -Xmx) for Womtool.
            dry_run:
                Stop before running Java command line for Cromwell.
            work_dir:
                Local temporary directory to store all temporary files.
                Temporary files mean intermediate files used for running Cromwell.
                For example, workflow options file, imports zip file.
                Localized (recursively) data files defined in input JSON
                will NOT be stored here.
                They will be localized on self._local_loc_dir instead.
                If this is not defined, then cache directory self._local_loc_dir will be used.
        """
        wdl_file = AutoURI(wdl)
        if not wdl_file.exists:
            raise FileNotFoundError('WDL does not exists. {wdl}'.format(wdl=wdl))

        if str_label is None and inputs:
            str_label = AutoURI(inputs).basename_wo_ext

        if work_dir is None:
            work_dir = self.create_timestamped_work_dir(prefix=wdl_file.basename_wo_ext)

        wdl = wdl_file.localize_on(work_dir)

        if backend is None:
            backend = self._cromwell_rest_api.get_default_backend()

        if inputs:
            # inputs should be localized on corresponding
            # backend's localization directory.
            # check if such loc_dir is defined.
            if self.get_loc_dir(backend) is None:
                raise ValueError(
                    'loc_dir is not defined for your backend. {b}'.format(b=backend)
                )

            maybe_remote_file = self.localize_on_backend_if_modified(
                inputs, backend=backend, recursive=not no_deepcopy, make_md5_file=True
            )
            inputs = AutoURI(maybe_remote_file).localize_on(work_dir)

        options = self._caper_workflow_opts.create_file(
            directory=work_dir,
            wdl=wdl,
            backend=backend,
            inputs=inputs,
            custom_options=options,
            docker=docker,
            singularity=singularity,
            singularity_cachedir=singularity_cachedir,
            no_build_singularity=no_build_singularity,
            max_retries=max_retries,
            memory_retry_multiplier=memory_retry_multiplier,
            gcp_monitoring_script=gcp_monitoring_script,
        )

        labels = self._caper_labels.create_file(
            directory=work_dir,
            backend=backend,
            custom_labels=labels,
            str_label=str_label,
            user=user,
        )

        wdl_parser = CaperWDLParser(wdl)
        if imports:
            imports = AutoURI(imports).localize_on(work_dir)
        else:
            imports = wdl_parser.create_imports_file(work_dir)

        logger.debug(
            'submit params: wdl={wdl}, imports={imp}, inputs={inp}, '
            'options={opt}, labels={lbl}, hold={hold}'.format(
                wdl=wdl, imp=imports, inp=inputs, opt=options, lbl=labels, hold=hold
            )
        )

        if not ignore_womtool:
            if not self._cromwell.validate(
                wdl=wdl,
                inputs=inputs,
                imports=imports,
                java_heap_womtool=java_heap_womtool,
            ):
                return

        if dry_run:
            return

        r = self._cromwell_rest_api.submit(
            source=wdl,
            dependencies=imports,
            inputs=inputs,
            options=options,
            labels=labels,
            on_hold=hold,
        )
        logger.info('submit: {r}'.format(r=r))
        return r
