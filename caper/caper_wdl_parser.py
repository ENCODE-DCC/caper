import logging

from .wdl_parser import WDLParser

logger = logging.getLogger(__name__)


class CaperWDLParser(WDLParser):
    """WDL parser for Caper.
    """

    RE_WDL_COMMENT_DOCKER = r'^\s*\#\s*CAPER\s+docker\s(.+)'
    RE_WDL_COMMENT_SINGULARITY = r'^\s*\#\s*CAPER\s+singularity\s(.+)'
    WDL_WORKFLOW_META_DOCKER = ('default_docker', 'caper_docker')
    WDL_WORKFLOW_META_SINGULARITY = ('default_singularity', 'caper_singularity')
    WDL_WORKFLOW_META_CONDA = (
        'default_conda',
        'default_conda_env',
        'caper_conda',
        'caper_conda_env',
    )

    def __init__(self, wdl):
        super().__init__(wdl)

    @property
    def caper_docker(self):
        """Find a default Docker image in WDL for Caper.

        Backward compatibililty:
            Keep using old regex method
            if WDL_WORKFLOW_META_DOCKER doesn't exist in workflow's meta
        """
        if self.workflow_meta:
            for docker_key in CaperWDLParser.WDL_WORKFLOW_META_DOCKER:
                if docker_key in self.workflow_meta:
                    return self.workflow_meta[docker_key]

        ret = self._find_val_of_matched_lines(CaperWDLParser.RE_WDL_COMMENT_DOCKER)
        if ret:
            return ret[0].strip('"\'')

    @property
    def caper_singularity(self):
        """Find a default Singularity image in WDL for Caper.

        Backward compatibililty:
            Keep using old regex method
            if WDL_WORKFLOW_META_SINGULARITY doesn't exist in workflow's meta
        """
        if self.workflow_meta:
            for singularity_key in CaperWDLParser.WDL_WORKFLOW_META_SINGULARITY:
                if singularity_key in self.workflow_meta:
                    return self.workflow_meta[singularity_key]

        ret = self._find_val_of_matched_lines(CaperWDLParser.RE_WDL_COMMENT_SINGULARITY)
        if ret:
            return ret[0].strip('"\'')

    @property
    def caper_conda(self):
        """Find a default Conda environment name in WDL for Caper.
        """
        if self.workflow_meta:
            for conda_key in CaperWDLParser.WDL_WORKFLOW_META_CONDA:
                if conda_key in self.workflow_meta:
                    return self.workflow_meta[conda_key]
