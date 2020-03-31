import os
import re
import shutil
from autouri import AutoURI, AbsPath, HTTPURL
from tempfile import TemporaryDirectory


class CaperWDLParser(object):
    """WDL parser for Caper.
    Find special comments for Caper in WDL.
    For example,
        #CAPER docker ubuntu:latest
    Find subworkflows and zip it.
    """
    RE_PATTERN_WDL_IMPORT = r'^\s*import\s+[\"\'](.+)[\"\']\s*'
    RE_PATTERN_WDL_COMMENT_DOCKER = r'^\s*\#\s*CAPER\s+docker\s(.+)'
    RE_PATTERN_WDL_COMMENT_SINGULARITY = r'^\s*\#\s*CAPER\s+singularity\s(.+)'
    RECURSION_DEPTH_LIMIT = 20

    def __init__(self, wdl):
        self._wdl = AbsPath.get_abspath_if_exists(wdl)

    def find_val(self, regex_val):
        u = AutoURI(self._wdl)
        if not u.exists:
            raise ValueError('WDL does not exist: wdl={wdl}'.format(wdl=self._wdl))
        result = []
        for line in u.read().split('\n'):
            r = re.findall(regex_val, line)
            if len(r) > 0:
                ret = r[0].strip()
                if len(ret) > 0:
                    result.append(ret)
        return result

    def find_imports(self):
        r = self.find_val(
            CaperWDLParser.RE_PATTERN_WDL_IMPORT)
        return r

    def find_docker(self):
        r = self.find_val(
            CaperWDLParser.RE_PATTERN_WDL_COMMENT_DOCKER)
        return r[0] if len(r) > 0 else None

    def find_singularity(self):
        r = self.find_val(
            CaperWDLParser.RE_PATTERN_WDL_COMMENT_SINGULARITY)
        return r[0] if len(r) > 0 else None

    def zip_subworkflows(self, zip_file):
        """Zip imported subworkflow WDLs (with relative paths only).
        For this (main) workflow, any URI is allowed.
        However, only subworkflows with relative path will be zipped.
        """
        with TemporaryDirectory() as tmp_d:
            main_wdl = AbsPath.localize(self._wdl)
            u = AutoURI(main_wdl)
            # with a directory structure as they imported
            num_sub_wf_packed = self.__recurse_subworkflow(
                root_wdl_dir=u.dirname,
                root_zip_dir=tmp_d)
            if num_sub_wf_packed:
                shutil.make_archive(AutoURI(zip_file).uri_wo_ext, 'zip', tmp_d)
            return num_sub_wf_packed

    def __recurse_subworkflow(
        self,
        root_zip_dir=None,
        root_wdl_dir=None,
        imported_as_url=False,
        depth=0):
        """Recurse imported sub-WDLs in main-WDL.

        Unlike Cromwell, Womtool does not take imports.zip while validating WDLs.
        All sub-WDLs should be in a correct directory structure relative to the 
        root WDL.
        For Womtool, we should make a temporary directory and unpack imports.zip there and
        need to make a copy of root WDL on it. Then run Womtool to validate them.
        This function is to make such imports.zip.

        Sub-WDLs imported as relative path simply inherit parent's directory.
        Sub-WDLs imported as URL does not inherit parent's directory but root 
        WDL's directory.
        Sub-WDLs imported as absolute path are not allowed. This can work with "caper run"
        but not with "caper submit" (or Cromwell submit).

        Args:
            depth: Recursion depth
        Returns:
            Total number of subworkflows:
                Sub WDL files "recursively" localized on "root_zip_dir".
        """
        if depth > CaperWDLParser.RECURSION_DEPTH_LIMIT:
            raise ValueError(
                'Reached recursion depth limit while zipping subworkflows recursively. '
                'Possible clyclic import or self-refencing in WDLs? wdl={wdl}'.format(
                    wdl=self._wdl))

        if imported_as_url:
            main_wdl_dir = root_wdl_dir
        else:
            main_wdl_dir = AbsPath(self._wdl).dirname

        num_sub_wf_packed = 0
        imports = self.find_imports()
        for sub_rel_to_parent in imports:
            u_sub = AutoURI(sub_rel_to_parent)

            if isinstance(u_sub, HTTPURL):
                sub_abs = u_sub.uri
                imported_as_url_sub = True
            elif isinstance(u_sub, AbsPath):
                raise ValueError(
                    'For sub WDL zipping, absolute path is not allowed for sub WDL. '
                    'main={main}, sub={sub}'.format(
                        main=self._wdl, sub=sub_rel_to_parent))
            else:
                sub_abs = os.path.realpath(
                    os.path.join(main_wdl_dir, sub_rel_to_parent))
                u_sub_abs = AbsPath(sub_abs)
                if not u_sub_abs.exists:
                    raise FileNotFoundError(
                        'Sub WDL does not exist. Did you import main WDL '
                        'as a URL but sub WDL references a local file? '
                        'main={main}, sub={sub}, imported_as_url={i}'.format(
                            main=self._wdl, sub=sub_rel_to_parent, i=imported_as_url))
                if not sub_abs.startswith(root_wdl_dir):
                    raise ValueError(
                        'Sub WDL exists but it is out of root WDL directory. '
                        'Too many "../" in your sub WDL? '
                        'Or main WDL is imported as an URL but sub WDL '
                        'has "../"? '
                        'main={main}, sub={sub}, imported_as_url={i}'.format(
                            main=self._wdl, sub=sub_rel_to_parent, i=imported_as_url))

                # make a copy on zip_dir
                rel_path = os.path.relpath(sub_abs, root_wdl_dir)
                cp_dest = os.path.join(root_zip_dir, rel_path)

                u_sub_abs.cp(cp_dest)
                num_sub_wf_packed += 1
                imported_as_url_sub = False

            num_sub_wf_packed += CaperWDLParser(sub_abs).__recurse_subworkflow(
                root_zip_dir=root_zip_dir,
                root_wdl_dir=root_wdl_dir,
                imported_as_url=imported_as_url_sub,
                depth=depth + 1)
        return num_sub_wf_packed
