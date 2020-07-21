import logging

from .wdl_parser import WDLParser

logger = logging.getLogger(__name__)


class CaperWDLParser(WDLParser):
    """WDL parser for Caper.
    """

    RE_WDL_COMMENT_DOCKER = r'^\s*\#\s*CAPER\s+docker\s(.+)'
    RE_WDL_COMMENT_SINGULARITY = r'^\s*\#\s*CAPER\s+singularity\s(.+)'
    WDL_WORKFLOW_META_DOCKER = 'caper_docker'
    WDL_WORKFLOW_META_SINGULARITY = 'caper_singularity'

    def __init__(self, wdl):
        super().__init__(wdl)

    @property
    def caper_docker(self):
        """Find a Docker image in WDL for Caper.

        Backward compatibililty:
            Keep using old regex method
            if WDL_WORKFLOW_META_DOCKER doesn't exist in workflow's meta
        """
        if self.workflow_meta:
            if CaperWDLParser.WDL_WORKFLOW_META_DOCKER in self.workflow_meta:
                return self.workflow_meta[CaperWDLParser.WDL_WORKFLOW_META_DOCKER]

        ret = self._find_val_of_matched_lines(CaperWDLParser.RE_WDL_COMMENT_DOCKER)
        if ret:
            return ret[0].strip('"\'')

    @property
    def caper_singularity(self):
        """Find a Singularity image in WDL for Caper.

        Backward compatibililty:
            Keep using old regex method
            if WDL_WORKFLOW_META_SINGULARITY doesn't exist in workflow's meta
        """
        if self.workflow_meta:
            if CaperWDLParser.WDL_WORKFLOW_META_SINGULARITY in self.workflow_meta:
                return self.workflow_meta[CaperWDLParser.WDL_WORKFLOW_META_SINGULARITY]

        ret = self._find_val_of_matched_lines(CaperWDLParser.RE_WDL_COMMENT_SINGULARITY)
        if ret:
            return ret[0].strip('"\'')
