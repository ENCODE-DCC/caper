"""WDLs used for testing.

To test many functions recursively working with subworkflows
these WDLs have the following structure:

    main.wdl (imports sub.wdl)
        sub/
            sub.wdl (imports sub_sub.wdl)
            sub/
                sub_sub.wdl (imports nothing)
        inputs.json (inputs JSON file)
"""
import json
import os
from textwrap import dedent

from autouri import AutoURI

WRONG_WDL = dedent(
    """\
    version 1.0

    workflwwwwwwwwwowwwww main {
    }
"""
)

MAIN_WDL = dedent(
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
            Int input_i = 1
        }

        call t1
        call sub.sub

        output {
            File out1 = t1.out
            File out_sub = sub.out
        }
    }

    task t1 {
        command {
            echo 1 > out.txt
            sleep 10
        }
        output {
            File out = 'out.txt'
        }
    }
"""
)

MAIN_INPUTS = {'main.input_s': 'a'}

MAIN_WDL_META_DICT = {'key1': 'val1', 'key2': 'val2'}


MAIN_WDL_PARAMETER_META_DICT = {
    'input_s': {'key1': 'val1'},
    'input_i': {'key1': 'val1'},
}

SUB_WDL = dedent(
    """\
    version 1.0
    import "sub/sub_sub.wdl" as sub_sub

    workflow sub {
        call t2
        call sub_sub.sub_sub

        output {
            File out = t2.out
            File out_sub = sub_sub.out
        }
    }

    task t2 {
        command {
            echo 2 > out2.txt
        }
        output {
            File out = 'out2.txt'
        }
    }
"""
)

SUB_WDL_TO_FAIL = dedent(
    """\
    version 1.0
    import "sub/sub_sub.wdl" as sub_sub

    workflow sub {
        call t2_failing
        call sub_sub.sub_sub

        output {
            File out = t2_failing.out
            File out_sub = sub_sub.out
        }
    }

    task t2_failing {
        command {
            echo 2 > out2.txt
            INTENTED_ERROR
        }
        output {
            File out = 'out2.txt'
        }
    }
"""
)

SUB_SUB_WDL = dedent(
    """\
    version 1.0

    workflow sub_sub {
        call t3
        output {
            File out = t3.out
        }
    }

    task t3 {
        command {
            echo 3 > out3.txt
        }
        output {
            File out = 'out3.txt'
        }
    }
"""
)


def make_directory_with_wdls(directory, no_sub_wdl=False):
    """
    Run Cromwell with WDLs:
    main + 1 sub + 1 sub's sub.

    Returns:
        Created root directory
    """
    main_inputs = os.path.join(directory, 'inputs.json')
    AutoURI(main_inputs).write(json.dumps(MAIN_INPUTS, indent=4))

    main_wdl = os.path.join(directory, 'main.wdl')
    AutoURI(main_wdl).write(MAIN_WDL)

    if not no_sub_wdl:
        sub_wdl = os.path.join(directory, 'sub', 'sub.wdl')
        AutoURI(sub_wdl).write(SUB_WDL)

        sub_sub_wdl = os.path.join(directory, 'sub', 'sub', 'sub_sub.wdl')
        AutoURI(sub_sub_wdl).write(SUB_SUB_WDL)


def make_directory_with_failing_wdls(directory, no_sub_wdl=False):
    """
    Run Cromwell with WDLs:
    main + 1 sub (supposed to fail) + 1 sub's sub.

    Returns:
        Created root directory
    """
    main_inputs = os.path.join(directory, 'inputs.json')
    AutoURI(main_inputs).write(json.dumps(MAIN_INPUTS, indent=4))

    main_wdl = os.path.join(directory, 'main.wdl')
    AutoURI(main_wdl).write(MAIN_WDL)

    if not no_sub_wdl:
        sub_wdl = os.path.join(directory, 'sub', 'sub.wdl')
        AutoURI(sub_wdl).write(SUB_WDL_TO_FAIL)

        sub_sub_wdl = os.path.join(directory, 'sub', 'sub', 'sub_sub.wdl')
        AutoURI(sub_sub_wdl).write(SUB_SUB_WDL)
