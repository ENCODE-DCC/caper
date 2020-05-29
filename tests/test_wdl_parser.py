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
from textwrap import dedent

from caper.wdl_parser import WDLParser

MAIN_WDL_CONTENTS = dedent(
    """\
    version 1.0
    import "sub/sub.wdl" as sub

    workflow main {
        meta {
            key1: "val1"
            key2: "val2"
        }
        parameter_meta {
            input_s: {
                key1: "val1"
            }
            input_i: {
                key1: "val1"
            }
        }
        input {
            String input_s
            Int input_i
        }
    }
"""
)


MAIN_WDL_META_DICT = {'key1': 'val1', 'key2': 'val2'}


MAIN_WDL_PARAMETER_META_DICT = {
    'input_s': {'key1': 'val1'},
    'input_i': {'key1': 'val1'},
}

TRIVIAL_WDL_CONTENTS = dedent(
    """\
    version 1.0

    workflow trivial {
    }
"""
)

SUB_WDL_CONTENTS = dedent(
    """\
    version 1.0
    import "sub/sub_sub.wdl" as sub_sub

    workflow sub {
    }
"""
)

SUB_SUB_WDL_CONTENTS = dedent(
    """\
    version 1.0

    workflow sub {
    }
"""
)


def test_properties(tmp_path):
    """Test the following properties.
        - contents
        - workflow_meta
        - workflow_parameter_meta
        - imports
    """
    d = tmp_path / 'test_wdl_parser' / 'test_properties'
    d.mkdir(parents=True)
    wdl = d / 'main.wdl'
    wdl.write_text(MAIN_WDL_CONTENTS)

    wp = WDLParser(str(wdl))
    assert wp.contents == MAIN_WDL_CONTENTS
    assert wp.workflow_meta == MAIN_WDL_META_DICT
    assert wp.workflow_parameter_meta == MAIN_WDL_PARAMETER_META_DICT
    assert wp.imports == ['sub/sub.wdl']


def test_zip_subworkflows(tmp_path):
    """This actually tests create_imports_file since
    create_imports_file's merely a wrapper for zip_subworkflows.
    """
    # make tmp directory to store WDLs
    d_main = tmp_path / 'test_wdl_parser' / 'test_create_imports_file' / 'wdls'
    d_main.mkdir(parents=True)
    main_wdl = d_main / 'main.wdl'
    main_wdl.write_text(MAIN_WDL_CONTENTS)
    trivial_wdl = d_main / 'trivial.wdl'
    trivial_wdl.write_text(TRIVIAL_WDL_CONTENTS)

    d_sub = d_main / 'sub'
    d_sub.mkdir(parents=True)
    sub_wdl = d_sub / 'sub.wdl'
    sub_wdl.write_text(SUB_WDL_CONTENTS)

    d_sub_sub = d_main / 'sub' / 'sub'
    d_sub_sub.mkdir(parents=True)
    sub_sub_wdl = d_sub_sub / 'sub_sub.wdl'
    sub_sub_wdl.write_text(SUB_SUB_WDL_CONTENTS)

    main = WDLParser(str(main_wdl))
    trivial = WDLParser(str(trivial_wdl))

    # make working directory
    d = tmp_path / 'test_wdl_parser' / 'test_create_imports_file' / 'imports'
    d.mkdir(parents=True)

    trivial_zip_file = trivial.create_imports_file(str(d), 'test_trivial_imports.zip')
    assert trivial_zip_file is None

    main_zip_file = main.create_imports_file(str(d), 'test_imports.zip')
    assert os.path.basename(main_zip_file) == 'test_imports.zip'

    shutil.unpack_archive(main_zip_file, extract_dir=str(d))
    assert os.path.exists(str(d / 'sub' / 'sub.wdl'))
    assert os.path.exists(str(d / 'sub' / 'sub' / 'sub_sub.wdl'))
