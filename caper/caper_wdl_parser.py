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
    RE_PATTERN_WDL_IMPORT = r'^\s*import\s+[\"\'](.+)[\"\']\s+as\s+'    
    RE_PATTERN_WDL_COMMENT_DOCKER = r'^\s*\#\s*CAPER\s+docker\s(.+)'
    RE_PATTERN_WDL_COMMENT_SINGULARITY = r'^\s*\#\s*CAPER\s+singularity\s(.+)'

    def __init__(self, wdl):
        self._wdl = AbsPath.get_abspath_if_exists(wdl)

    def find_val(self, regex_val):
        u = AutoURI(self._wdl)
        if not u.exists:
            raise ValueError('WDL does not exist: {f}='.format(f=self._wdl))
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
            u_main_wdl = AutoURI(self._wdl)
            # sub WDLs should physically exist 
            # with a directory structure as they imported
            sub_exist = self.__recurse_subworkflow(root_zip_dir=tmp_d)
            if sub_exist:
                shutil.make_archive(AutoURI(zip_file).uri_wo_ext, 'zip', tmp_d)
            return sub_exist

    def __recurse_subworkflow(
        self, parent_rel_to_root_zip_dir='', root_zip_dir=None, files_to_zip=tuple()):
        """Recurse imported subworkflows in WDL.
        For subworkflows with relative path only.
        Recursion is meaningless for subworkflows with URL or absolute path.
        """
        parent_wdl_dirname = AutoURI(self._wdl).dirname
        imports = self.find_imports()
        sub_exist = False
        for sub_rel_to_parent in imports:
            u = AutoURI(sub_rel_to_parent)
            if not isinstance(u, (HTTPURL, AbsPath)):
                # sub_rel is relative path to parent WDL
                sub_abs = os.path.join(parent_wdl_dirname, sub_rel_to_parent)
                dest = os.path.join(root_zip_dir, parent_rel_to_root_zip_dir, sub_rel_to_parent)
                u = AutoURI(sub_abs)
                if not u.exists:
                    raise FileNotFoundError(
                        'Subworkflow WDL does not exist: main={main}, sub={sub}'.format(
                            main=self._wdl, sub=sub_abs))
                u.cp(dest)
                sub_exist = True

                CaperWDLParser(sub_abs).__recurse_subworkflow(
                    parent_rel_to_root_zip_dir=os.path.dirname(sub_rel_to_parent),
                    root_zip_dir=root_zip_dir)
        return sub_exist
