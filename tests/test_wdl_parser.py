"""
There are three WDL 1.0 files to test subworkflow zipping.
main.wdl (imports sub/sub.wdl)
    sub/
        sub.wdl (imports sub/sub_sub.wdl)
        sub/
            sub_sub.wdl
There is another trivial WDL 1.0 file with empty workflow.
"""

import os
import shutil

from caper.wdl_parser import WDLParser

from .example_wdl import (
    MAIN_WDL,
    MAIN_WDL_META_DICT,
    MAIN_WDL_PARAMETER_META_DICT,
    make_directory_with_wdls,
)


def test_properties(tmp_path):
    """Test the following properties.
        - contents
        - workflow_meta
        - workflow_parameter_meta
        - imports
    """
    wdl = tmp_path / 'main.wdl'
    wdl.write_text(MAIN_WDL)

    wp = WDLParser(str(wdl))
    assert wp.contents == MAIN_WDL
    assert wp.workflow_meta == MAIN_WDL_META_DICT
    assert wp.workflow_parameter_meta == MAIN_WDL_PARAMETER_META_DICT
    assert wp.imports == ['sub/sub.wdl']


def test_zip_subworkflows(tmp_path):
    """This actually tests create_imports_file since
    create_imports_file's merely a wrapper for zip_subworkflows.
    """
    # make tmp directory to store WDLs
    make_directory_with_wdls(str(tmp_path))

    # we now have all WDL files
    # main.wdl, sub/sub.wdl, sub/sub/sub_sub.wdl

    main_wdl = tmp_path / 'main.wdl'
    sub_sub_wdl = tmp_path / 'sub' / 'sub' / 'sub_sub.wdl'

    main = WDLParser(str(main_wdl))

    # simple WDL without any imports
    simple = WDLParser(str(sub_sub_wdl))

    # make working directory
    d = tmp_path / 'imports'
    d.mkdir(parents=True)

    simple_zip_file = simple.create_imports_file(str(d), 'test_trivial_imports.zip')
    assert simple_zip_file is None

    main_zip_file = main.create_imports_file(str(d), 'test_imports.zip')
    assert os.path.basename(main_zip_file) == 'test_imports.zip'

    shutil.unpack_archive(main_zip_file, extract_dir=str(d))
    assert os.path.exists(str(d / 'sub' / 'sub.wdl'))
    assert os.path.exists(str(d / 'sub' / 'sub' / 'sub_sub.wdl'))
