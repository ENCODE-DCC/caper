import copy
import json
import logging
import os

from autouri import GCSURI, AutoURI

from .caper_wdl_parser import CaperWDLParser
from .cromwell_backend import (
    BACKEND_AWS,
    BACKEND_GCP,
    ENVIRONMENT_CONDA,
    ENVIRONMENT_DOCKER,
    ENVIRONMENT_SINGULARITY,
)
from .dict_tool import merge_dict
from .singularity import find_bindpath

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
        lsf_queue=None,
        lsf_extra_param=None,
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
            lsf_queue:
                For lsf backend only.
                LSF queue to submit tasks to.
            lsf_extra_param:
                For lsf backend only.
                Extra parameters for LSF.
                This will be appended to "bsub" command line.
        """
        self._template = {CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES: dict()}
        default_runtime_attributes = self._template[
            CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES
        ]

        if gcp_zones and not use_google_cloud_life_sciences:
            default_runtime_attributes['zones'] = ' '.join(gcp_zones)

        if slurm_partition:
            default_runtime_attributes['slurm_partition'] = slurm_partition
        if slurm_account:
            default_runtime_attributes['slurm_account'] = slurm_account
        if slurm_extra_param:
            default_runtime_attributes['slurm_extra_param'] = slurm_extra_param

        if sge_pe:
            default_runtime_attributes['sge_pe'] = sge_pe
        if sge_queue:
            default_runtime_attributes['sge_queue'] = sge_queue
        if sge_extra_param:
            default_runtime_attributes['sge_extra_param'] = sge_extra_param

        if pbs_queue:
            default_runtime_attributes['pbs_queue'] = pbs_queue
        if pbs_extra_param:
            default_runtime_attributes['pbs_extra_param'] = pbs_extra_param

        if lsf_queue:
            default_runtime_attributes['lsf_queue'] = lsf_queue
        if lsf_extra_param:
            default_runtime_attributes['lsf_extra_param'] = lsf_extra_param

    def create_file(
        self,
        directory,
        wdl,
        backend=None,
        inputs=None,
        custom_options=None,
        docker=None,
        singularity=None,
        conda=None,
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
            conda:
                Default Conda environemnt name to run a workflow.
            docker:
                Default Docker image to run a workflow on.
            singularity:
                Default Singularity image to run a workflow on.
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
        default_runtime_attributes = template[
            CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES
        ]

        if backend:
            template['backend'] = backend

        wdl_parser = CaperWDLParser(wdl)

        # sanity check for environment flags
        defined_env_flags = [env for env in (docker, singularity, conda) if env]
        if len(defined_env_flags) > 1:
            raise ValueError(
                'docker, singularity and conda are mutually exclusive. '
                'Define nothing or only one environment.'
            )

        if docker is not None:
            environment = ENVIRONMENT_DOCKER
        elif singularity is not None:
            environment = ENVIRONMENT_SINGULARITY
        elif conda is not None:
            environment = ENVIRONMENT_CONDA
        else:
            environment = None

        if environment:
            default_runtime_attributes['environment'] = environment

        if docker == '' or backend in (BACKEND_GCP, BACKEND_AWS) and not docker:
            # if used as a flag or cloud backend is chosen
            # try to find "default_docker" from WDL's workflow.meta or "#CAPER docker" from comments
            docker = wdl_parser.default_docker
            if docker:
                logger.info(
                    'Docker image found in WDL metadata. wdl={wdl}, d={d}'.format(
                        wdl=wdl, d=docker
                    )
                )
            else:
                logger.info(
                    "Docker image not found in WDL metadata. wdl={wdl}".format(wdl=wdl)
                )

        if docker:
            default_runtime_attributes['docker'] = docker

        if singularity == '':
            # if used as a flag
            if backend in (BACKEND_GCP, BACKEND_AWS):
                raise ValueError(
                    'Singularity cannot be used for cloud backend (e.g. aws, gcp).'
                )

            singularity = wdl_parser.default_singularity
            if singularity:
                logger.info(
                    'Singularity image found in WDL metadata. wdl={wdl}, s={s}'.format(
                        wdl=wdl, s=singularity
                    )
                )
            else:
                logger.info(
                    'Singularity image not found in WDL metadata. wdl={wdl}.'.format(
                        wdl=wdl
                    )
                )

        if singularity:
            default_runtime_attributes['singularity'] = singularity
            if inputs:
                default_runtime_attributes['singularity_bindpath'] = find_bindpath(
                    inputs
                )

        if conda == '':
            # if used as a flag
            if backend in (BACKEND_GCP, BACKEND_AWS):
                raise ValueError(
                    'Conda cannot be used for cloud backend (e.g. aws, gcp).'
                )
            conda = wdl_parser.default_conda
            if conda:
                logger.info(
                    'Conda environment name found in WDL metadata. wdl={wdl}, s={s}'.format(
                        wdl=wdl, s=conda
                    )
                )
            else:
                logger.info(
                    'Conda environment name not found in WDL metadata. wdl={wdl}'.format(
                        wdl=wdl
                    )
                )

        if conda:
            default_runtime_attributes['conda'] = conda

        if max_retries is not None:
            default_runtime_attributes['maxRetries'] = max_retries
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
