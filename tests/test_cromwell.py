import json
import os
import sys
import time

from caper.cromwell import Cromwell
from caper.cromwell_rest_api import CromwellRestAPI
from caper.wdl_parser import WDLParser

from .example_wdl import WRONG_WDL, make_directory_with_wdls

BACKEND_CONF_CONTENTS = """
backend {{
  providers {{
    Local {{
      config {{
        root = {root}
      }}
    }}
  }}
}}
"""

TIMEOUT_SERVER_SPIN_UP = 200
TIMEOUT_SERVER_RUN_WORKFLOW = 960


def test_validate(tmp_path, cromwell, womtool):
    c = Cromwell(cromwell=cromwell, womtool=womtool)

    wdl = tmp_path / 'wrong.wdl'
    wdl.write_text(WRONG_WDL)
    assert not c.validate(str(wdl))

    make_directory_with_wdls(str(tmp_path / 'successful'))
    wdl = tmp_path / 'successful' / 'main.wdl'
    inputs = tmp_path / 'successful' / 'inputs.json'
    assert c.validate(str(wdl), str(inputs))

    # zip subworkflows for later use
    p = WDLParser(str(wdl))
    imports = p.zip_subworkflows(str(tmp_path / 'imports.zip'))

    # test with imports.zip
    make_directory_with_wdls(str(tmp_path / 'wo_sub_wdls'), no_sub_wdl=True)
    wdl = tmp_path / 'wo_sub_wdls' / 'main.wdl'
    inputs = tmp_path / 'wo_sub_wdls' / 'inputs.json'
    assert c.validate(str(wdl), str(inputs), imports)


def test_run(tmp_path, cromwell, womtool):
    fileobj_stdout = sys.stdout

    c = Cromwell(cromwell=cromwell, womtool=womtool)

    make_directory_with_wdls(str(tmp_path))

    o_dir = tmp_path / 'output'
    o_dir.mkdir()
    work_dir = tmp_path / 'work_dir'
    work_dir.mkdir()

    backend_conf = tmp_path / 'backend.conf'
    backend_conf.write_text(BACKEND_CONF_CONTENTS.format(root=o_dir))

    try:
        th = c.run(
            backend_conf=str(backend_conf),
            wdl=str(tmp_path / 'main.wdl'),
            inputs=str(tmp_path / 'inputs.json'),
            metadata=str(tmp_path / 'metadata.json'),
            fileobj_stdout=fileobj_stdout,
            work_dir=work_dir,
            cwd=str(tmp_path),
        )
    finally:
        th.join()
    assert th.returncode == 0

    # check if metadata.json is written on both specified location
    # (tmp_path/metadata.json) and workflow's root directory
    metadata_dict = th.returnvalue
    root_dir = metadata_dict['workflowRoot']

    with open(os.path.join(root_dir, 'metadata.json')) as fp:
        metadata_contents_on_root = fp.read()
    metadata_dict_on_root = json.loads(metadata_contents_on_root)

    assert metadata_dict == metadata_dict_on_root
    # check if backend_conf's change of root directory worked
    assert root_dir.startswith(str(o_dir))

    # zip subworkflows for later use
    p = WDLParser(str(tmp_path / 'main.wdl'))
    imports = p.zip_subworkflows(str(tmp_path / 'imports.zip'))

    # test without sub WDLs but with imports.zip
    # test run without work_dir
    make_directory_with_wdls(str(tmp_path / 'wo_sub_wdls'), no_sub_wdl=True)

    try:
        th = c.run(
            wdl=str(tmp_path / 'wo_sub_wdls' / 'main.wdl'),
            inputs=str(tmp_path / 'wo_sub_wdls' / 'inputs.json'),
            imports=imports,
            fileobj_stdout=fileobj_stdout,
            cwd=str(tmp_path / 'wo_sub_wdls'),
        )
    finally:
        th.join()
    assert th.returncode == 0


def test_server(tmp_path, cromwell, womtool):
    """Test Cromwell.server() method, which returns a Thread object.
    """
    server_port = 8005
    fileobj_stdout = sys.stdout

    c = Cromwell(cromwell=cromwell, womtool=womtool)

    o_dir = tmp_path / 'output'
    o_dir.mkdir()

    backend_conf = tmp_path / 'backend.conf'
    backend_conf.write_text(BACKEND_CONF_CONTENTS.format(root=o_dir))

    is_server_started = False

    def on_server_start():
        nonlocal is_server_started
        is_server_started = True

    workflow_id = None
    is_workflow_done = False

    def on_status_change(metadata):
        nonlocal workflow_id
        nonlocal is_workflow_done

        if metadata:
            if metadata['id'] == workflow_id:
                if metadata['status'] in ('Succeeded', 'Failed'):
                    is_workflow_done = True

    # also tests two callback functions
    try:
        th = c.server(
            server_port=server_port,
            backend_conf=str(backend_conf),
            embed_subworkflow=True,
            fileobj_stdout=fileobj_stdout,
            on_server_start=on_server_start,
            on_status_change=on_status_change,
            cwd=str(tmp_path),
        )
        assert th.status is None

        # wait until server is ready to take submissions
        t_start = time.time()
        while not is_server_started:
            time.sleep(1)
            if time.time() - t_start > TIMEOUT_SERVER_SPIN_UP:
                raise TimeoutError('Timed out waiting for Cromwell server spin-up.')

        # another way of checking server is started
        assert th.status

        # make WDLs and imports
        wdl = tmp_path / 'main.wdl'
        make_directory_with_wdls(str(tmp_path))
        # zip subworkflows for later use
        p = WDLParser(str(wdl))
        imports = p.zip_subworkflows(str(tmp_path / 'imports.zip'))

        cra = CromwellRestAPI(hostname='localhost', port=server_port)
        r = cra.submit(
            source=str(wdl), dependencies=imports, inputs=str(tmp_path / 'inputs.json')
        )
        workflow_id = r['id']

        t_start = time.time()
        while not is_workflow_done:
            time.sleep(1)
            print('polling: ', workflow_id, is_workflow_done)
            if time.time() - t_start > TIMEOUT_SERVER_RUN_WORKFLOW:
                raise TimeoutError('Timed out waiting for workflow being done.')

        metadata = cra.get_metadata([workflow_id], embed_subworkflow=True)[0]

        # check if metadata JSON is written on workflow's root directory.
        root_dir = metadata['workflowRoot']
        metadata_file = os.path.join(root_dir, 'metadata.json')
        assert os.path.exists(metadata_file)

        # check if subworkflow is embedded.
        with open(metadata_file) as fp:
            metadata_from_file = json.loads(fp.read())
        assert metadata == metadata_from_file

    finally:
        th.stop()
        th.join()
