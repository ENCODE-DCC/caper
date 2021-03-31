import copy
import json
import logging
import os

from autouri import GCSURI, AutoURI

from .caper_wdl_parser import CaperWDLParser
from .cromwell_backend import BACKEND_AWS, BACKEND_GCP
from .dict_tool import merge_dict
from .singularity import Singularity

logger = logging.getLogger(__name__)


class CaperWorkflowOpts:
    DEFAULT_RUNTIME_ATTRIBUTES = 'default_runtime_attributes'
    BASENAME_WORKFLOW_OPTS_JSON = 'workflow_opts.json'
    DEFAULT_MAX_RETRIES = 1
    DEFAULT_MEMORY_RETRY_MULTIPLIER = 1.2
    DEFAULT_GCP_MONITORING_SCRIPT = (
        'gs://caper-data/scripts/resource_monitor/resource_monitor.sh'
    )

    def __init__(
        self,
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
        """Template for a workflows options JSON file.
        All parameters are optional.

        Args:
            use_google_cloud_life_sciences:
                Use Google Cloud Life Sciences API instead of Genomics API
                which has beed deprecated.
                If this flag is on gcp_zones is ignored.
            gcp_zones:
                For gcp backend only.
                List of GCP zones to run workflows on.
            slurm_partition:
                For slurm backend only.
                SLURM partition to submit tasks to.
                Caper will submit tasks with "sbatch --partition".
            slurm_account:
                For slurm backend only.
                SLURM account to submit tasks to.
                Caper will submit tasks with "sbatch --account".
            slurm_extra_param:
                For slurm backend only.
                Extra parameters for SLURM.
                This will be appended to "sbatch" command line.
            sge_pe:
                For sge backend only.
                Name of parallel environment (PE) of SGE cluster.
                If it does not exist ask your admin to add one.
            sge_queue:
                For sge backend only.
                SGE queue to submit tasks to.
            sge_extra_param:
                For sge backend only.
                Extra parameters for SGE.
                This will be appended to "qsub" command line.
            pbs_queue:
                For pbs backend only.
                PBS queue to submit tasks to.
            pbs_extra_param:
                For pbs backend only.
                Extra parameters for PBS.
                This will be appended to "qsub" command line.
        """
        self._template = {CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES: dict()}
        dra = self._template[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]

        if gcp_zones and not use_google_cloud_life_sciences:
            dra['zones'] = ' '.join(gcp_zones)

        if slurm_partition:
            dra['slurm_partition'] = slurm_partition
        if slurm_account:
            dra['slurm_account'] = slurm_account
        if slurm_extra_param:
            dra['slurm_extra_param'] = slurm_extra_param

        if sge_pe:
            dra['sge_pe'] = sge_pe
        if sge_queue:
            dra['sge_queue'] = sge_queue
        if sge_extra_param:
            dra['sge_extra_param'] = sge_extra_param

        if pbs_queue:
            dra['pbs_queue'] = pbs_queue
        if pbs_extra_param:
            dra['pbs_extra_param'] = pbs_extra_param

    def create_file(
        self,
        directory,
        wdl,
        backend=None,
        inputs=None,
        custom_options=None,
        docker=None,
        singularity=None,
        singularity_cachedir=None,
        no_build_singularity=False,
        max_retries=DEFAULT_MAX_RETRIES,
        memory_retry_multiplier=DEFAULT_MEMORY_RETRY_MULTIPLIER,
        gcp_monitoring_script=DEFAULT_GCP_MONITORING_SCRIPT,
        basename=BASENAME_WORKFLOW_OPTS_JSON,
    ):
        """Creates Cromwell's workflow options JSON file.
        Workflow options JSON file sets default values for attributes
        defined in runtime {} section of WDL's task.
        For example, docker attribute can be defined here instead of directory
        defining in task's runtime { docker: "" }.

        Args:
            directory:
                Directory to make workflow options JSON file.
            wdl:
                WDL file.
            backend:
                Backend to run a workflow on. If not defined, server's default or
                runner's Local backend will be used.
            inputs:
                Input JSON file to define input files/parameters for WDL.
                This will be overriden by environment variable SINGULARITY_BINDPATH.
                For Singularity, it is required to find SINGULARITY_BINDPATH,
                which is a comma-separated list of common root directories
                for all files defined in input JSON.
                Unlike Docker, Singularity binds directories instead of mounting them.
                Therefore, Caper will try to find an optimal SINGULARITY_BINDPATH
                by looking at all files paths and find common parent directories for them.
            custom_options:
                User's custom workflow options JSON file.
                This will be merged at the end of this function.
                Therefore, users can override on Caper's auto-generated
                workflow options JSON file.
            docker:
                Docker image to run a workflow on.
            singularity:
                Singularity image to run a workflow on.
            singularity_cachedir:
                Singularity cache directory to build local images on.
                This will be overriden by environment variable SINGULARITY_CACHEDIR.
            no_build_singularity:
                Caper run "singularity exec IMAGE" to build a local Singularity image
                before submitting/running a workflow.
                With this flag on, Caper does not pre-build a local Singularity container.
                Therefore, Singularity container will be built inside each task,
                which will result in multiple redundant local image building.
                Also, trying to build on the same Singularity image file can
                lead to corruption of the image file.
            max_retries:
                Maximum number of retirals for each task. 1 means 1 retrial.
            memory_retry_multiplier:
                Multiplier for the memory retry feature.
                See https://cromwell.readthedocs.io/en/develop/cromwell_features/RetryWithMoreMemory/
                for details.
            gcp_monitoring_script:
                Monitoring script for GCP backend only.
                Useful to monitor resources on an instance.
            basename:
                Basename for a temporary workflow options JSON file.
        """
        if singularity and docker:
            raise ValueError('Cannot use both Singularity and Docker.')

        template = copy.deepcopy(self._template)
        dra = template[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]

        if backend:
            template['backend'] = backend

        wdl_parser = CaperWDLParser(wdl)
        if docker == '' or backend in (BACKEND_GCP, BACKEND_AWS) and not docker:
            # find "caper-docker" from WDL's workflow.meta
            # or "#CAPER docker" from comments
            docker = wdl_parser.caper_docker
            if docker:
                logger.info(
                    'Docker image found in WDL\'s metadata. wdl={wdl}, d={d}'.format(
                        wdl=wdl, d=docker
                    )
                )
            else:
                logger.warning(
                    "Docker image not found in WDL's metadata, which means that "
                    "docker is not defined either as comment (#CAPER docker) or "
                    "in workflow's meta section (under key caper_docker) in WDL. "
                    "If your WDL already has docker defined "
                    "in each task's runtime "
                    "then it should be okay. wdl={wdl}".format(wdl=wdl)
                )
        if docker:
            dra['docker'] = docker

        if singularity == '':
            if backend in (BACKEND_GCP, BACKEND_AWS):
                raise ValueError(
                    'Singularity cannot be used for cloud backend (e.g. aws, gcp).'
                )

            singularity = wdl_parser.caper_singularity
            if singularity:
                logger.info(
                    'Singularity image found in WDL\'s metadata. wdl={wdl}, s={s}'.format(
                        wdl=wdl, s=singularity
                    )
                )
            else:
                raise ValueError(
                    'Singularity image not found in WDL. wdl={wdl}'.format(wdl=wdl)
                )
        if singularity:
            dra['singularity'] = singularity
            if singularity_cachedir:
                dra['singularity_cachedir'] = singularity_cachedir

            s = Singularity(singularity, singularity_cachedir)
            if inputs:
                dra['singularity_bindpath'] = s.find_bindpath(inputs)
            if not no_build_singularity:
                s.build_local_image()

        if max_retries is not None:
            dra['maxRetries'] = max_retries
        # Cromwell's bug in memory-retry feature.
        # Disabled until it's fixed on Cromwell's side.
        # if memory_retry_multiplier is not None:
        #     template['memory_retry_multiplier'] = memory_retry_multiplier

        if gcp_monitoring_script and backend == BACKEND_GCP:
            if not GCSURI(gcp_monitoring_script).is_valid:
                raise ValueError(
                    'gcp_monitoring_script is not a valid URI. {uri}'.format(
                        uri=gcp_monitoring_script
                    )
                )
            template['monitoring_script'] = gcp_monitoring_script

        if custom_options:
            s = AutoURI(custom_options).read()
            d = json.loads(s)
            merge_dict(template, d)

        final_options_file = os.path.join(directory, basename)
        AutoURI(final_options_file).write(json.dumps(template, indent=4) + '\n')

        return final_options_file
