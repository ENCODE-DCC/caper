import json
import os
import sys
import time
from threading import Thread

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


def test_validate(tmp_path, cromwell, womtool):
    c = Cromwell(cromwell=cromwell, womtool=womtool)

    wdl = tmp_path / 'wrong.wdl'
    wdl.write_text(WRONG_WDL)
    rc = c.validate(str(wdl))
    assert rc

    make_directory_with_wdls(str(tmp_path / 'successful'))
    wdl = tmp_path / 'successful' / 'main.wdl'
    inputs = tmp_path / 'successful' / 'inputs.json'
    rc = c.validate(str(wdl), str(inputs))
    assert rc == 0

    # zip subworkflows for later use
    p = WDLParser(str(wdl))
    imports = p.zip_subworkflows(str(tmp_path / 'imports.zip'))

    # test with imports.zip
    make_directory_with_wdls(str(tmp_path / 'wo_sub_wdls'), no_sub_wdl=True)
    wdl = tmp_path / 'wo_sub_wdls' / 'main.wdl'
    inputs = tmp_path / 'wo_sub_wdls' / 'inputs.json'
    rc = c.validate(str(wdl), str(inputs), imports)
    assert rc == 0


def test_run(tmp_path, cromwell, womtool):
    # fileobj_stdout = None
    fileobj_stdout = sys.stdout

    c = Cromwell(cromwell=cromwell, womtool=womtool)

    make_directory_with_wdls(str(tmp_path))

    o_dir = tmp_path / 'output'
    o_dir.mkdir()
    work_dir = tmp_path / 'work_dir'
    work_dir.mkdir()

    backend_conf = tmp_path / 'backend.conf'
    backend_conf.write_text(BACKEND_CONF_CONTENTS.format(root=o_dir))

    rc, metadata_file = c.run(
        backend_conf=str(backend_conf),
        wdl=str(tmp_path / 'main.wdl'),
        inputs=str(tmp_path / 'inputs.json'),
        metadata=str(tmp_path / 'metadata.json'),
        fileobj_stdout=fileobj_stdout,
        work_dir=work_dir,
    )
    assert rc == 0
    # check if metadata.json is written on both specified location
    # (tmp_path/metadata.json) and workflow's root directory
    with open(str(tmp_path / 'metadata.json')) as fp:
        metadata_contents = fp.read()
    metadata_dict = json.loads(metadata_contents)
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
    make_directory_with_wdls(str(tmp_path / 'wo_sub_wdls'), no_sub_wdl=True)
    rc, metadata_file = c.run(
        wdl=str(tmp_path / 'wo_sub_wdls' / 'main.wdl'),
        inputs=str(tmp_path / 'wo_sub_wdls' / 'inputs.json'),
        imports=imports,
        fileobj_stdout=fileobj_stdout,
    )
    assert rc == 0


def xx():
    i = 0
    while True:
        i += 1
        time.sleep(1)
        print(i)


def test_server(tmp_path, cromwell, womtool):
    server_port = 8005

    # fileobj_stdout = None
    fileobj_stdout = sys.stdout

    c = Cromwell(cromwell=cromwell, womtool=womtool)

    o_dir = tmp_path / 'output'
    o_dir.mkdir()
    work_dir = tmp_path / 'work_dir'
    work_dir.mkdir()

    make_directory_with_wdls(str(tmp_path))

    backend_conf = tmp_path / 'backend.conf'
    backend_conf.write_text(BACKEND_CONF_CONTENTS.format(root=o_dir))

    try:
        # th = Thread(target=xx)
        th = Thread(
            target=c.server,
            kwargs={
                'server_port': server_port,
                'backend_conf': str(backend_conf),
                'embed_subworkflow': True,
                'work_dir': str(work_dir),
                'fileobj_stdout': fileobj_stdout,
            },
        )
        th.start()

        t_start = time.time()
        while True:
            time.sleep(1)
            if time.time() - t_start > 30:
                raise TimeoutError
            print(time.time() - t_start)
            if c.is_listening():
                break

        cra = CromwellRestAPI(hostname='localhost', port=server_port)
        r = cra.submit(
            source=str(tmp_path / 'main.wdl'), inputs=str(tmp_path / 'inputs.json')
        )
        workflow_id = r['id']

        t_start = time.time()
        while True:
            time.sleep(5)
            if time.time() - t_start > 60:
                raise TimeoutError
            ret = cra.get_metadata([workflow_id], embed_subworkflow=True)
            if ret and 'status' in ret[0]:
                if ret[0]['status'] == 'Succeeded':
                    break
                elif ret[0]['status'] == 'Failed':
                    raise RuntimeError

        metadata = ret[0]
        # check if subworkflow is embedded.
        root_dir = metadata['workflowRoot']
        assert os.path.exists(os.path.join(root_dir, 'metadata.json'))
    finally:
        th.join()
