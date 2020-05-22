import copy
import json
import logging
import os
import re
from autouri import AutoURI
from .caper_backend import CromwellBackendGCP, BACKEND_GCP, BACKEND_AWS
from .caper_wdl_parser import CaperWDLParser



logger = logging.getLogger(__name__)


class CaperWorkflowOpts:
    DEFAULT_RUNTIME_ATTRIBUTES = 'default_runtime_attributes'
    BASENAME_WORKFLOW_OPTS_JSON = 'workflow_opts.json'
    DEFAULT_MAX_RETRIES = 1

    def __init__(
            self,
            gcp_zones=None,
            slurm_partition=None,
            slurm_account=None,
            slurm_extra_param=None,
            sge_pe=None,
            sge_queue=None,
            sge_extra_param=None,
            pbs_queue=None,
            pbs_extra_param=None):
        """Template for a workflows options JSON file.

        Args:
            gcp_zones:
            slurm_partition:
            slurm_account:
            slurm_extra_param:
            sge_pe:
            sge_queue:
            sge_extra_param:
            pbs_queue:
            pbs_extra_param:
        """
        self._template = {
            CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES: dict()
        }
        dra = self._template[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]

        if gcp_zones:
            zones = ' '.join(
                re.split(
                    CromwellBackendGCP.REGEX_DELIMITER_GCP_ZONES,
                    gcp_zones))
            dra['zones'] = zones

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
            inputs=None,
            custom_options=None,
            docker=None,
            singularity=None,
            singularity_cachedir=None,
            no_build_singularity=False,
            backend=None,
            max_retries=DEFAULT_MAX_RETRIES,
            basename=BASENAME_WORKFLOW_OPTS_JSON):
        """Creates Cromwell's workflow options JSON file.
            directory:
            wdl:
            inputs:
                Input JSON file. It is required to find SINGULARITY_BINDPATH,
                which is a common root for all files in input JSON.
            custom_options:
                User's custom workflow options JSON file.
            docker:
                Docker image to run a workflow on.
            singularity:
                Singularity image to run a workflow on.
            singularity_cachedir:
            no_build_singularity:
            backend:
                Backend to run a workflow on.
            max_retries:
            basename:
        """
        template = copy.deepcopy(self._template)
        dra = template[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]

        if backend:
            template['backend'] = backend

        wdl_parser = CaperWDLParser(wdl)
        if docker == '' or backend in (BACKEND_GCP, BACKEND_AWS) and not docker:
            # find "caper-docker" from WDL's workflow.meta
            # or "#CAPER docker" from comments
            docker = wdl_parser.find_docker()
            if docker:
                logger.info('Docker image found in WDL. wdl={wdl}, d={d}'.format(
                    wdl=wdl, d=docker))
            else:
                raise ValueError('Docker image not found in WDL: wdl={wdl}.'.format(
                    wdl=wdl))
        if docker:
            dra['docker'] = docker

        if singularity == '':
            singularity = wdl_parser.find_singularity()
            if singularity:
                logger.info('Singularity image found in WDL. wdl={wdl}, s={s}'.format(
                    wdl=wdl, s=singularity))
            else:
                raise ValueError('Singularity image not found in WDL: wdl={wdl}.'.format(
                    wdl=wdl))
        if singularity:
            dra['singularity'] = singularity
            if singularity_cachedir:
                dra['singularity_cachedir'] = singularity_cachedir

            s = Singularity(singularity, singularity_cachedir)
            dra['singularity_bindpath'] = s.find_singularity_bindpath(inputs)
            if not no_build_singularity:
                s.build_singularity_image()

        if max_retries is not None:
            dra['maxRetries'] = max_retries

        if custom_options:
            s = AutoURI(custom_options).read()
            d = json.loads(fp.read())
            merge_dict(template, d)

        final_options_file = os.path.join(directory, basename)
        AutoURI(final_options_file).write(
            json.dumps(template, indent=4) + '\n')

        return final_options_file
