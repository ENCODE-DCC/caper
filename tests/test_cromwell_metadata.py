import os
import sys
from io import StringIO

from autouri import AutoURI

from caper.cromwell import Cromwell
from caper.cromwell_metadata import CromwellMetadata

from .example_wdl import make_directory_with_failing_wdls, make_directory_with_wdls


def test_on_successful_workflow(tmp_path, cromwell, womtool):
    fileobj_stdout = sys.stdout

    make_directory_with_wdls(str(tmp_path / 'successful'))

    # Run Cromwell to get metadata JSON
    c = Cromwell(cromwell=cromwell, womtool=womtool)
    th = c.run(
        wdl=str(tmp_path / 'successful' / 'main.wdl'),
        inputs=str(tmp_path / 'successful' / 'inputs.json'),
        fileobj_stdout=fileobj_stdout,
        cwd=str(tmp_path / 'successful'),
    )
    th.join()
    metadata = th.returnvalue
    assert metadata

    cm = CromwellMetadata(metadata)
    # test all properties
    assert cm.data == metadata
    assert cm.metadata == metadata
    assert CromwellMetadata(metadata).data == metadata
    assert cm.workflow_id == metadata['id']
    assert cm.workflow_status == metadata['status']
    # no failures for successful workflow's metadata
    assert cm.failures is None
    assert cm.calls == metadata['calls']

    # test recurse_calls(): test with a simple function
    def fnc(call_name, call, parent_call_names):
        assert call_name in ('main.t1', 'sub.t2', 'sub_sub.t3')
        assert call['executionStatus'] == 'Done'
        if call_name == 'main.t1':
            assert not parent_call_names
        elif call_name == 'sub.t2':
            assert parent_call_names == ('main.sub',)
        elif call_name == 'sub_sub.t3':
            assert parent_call_names == ('main.sub', 'sub.sub_sub')
        else:
            raise ValueError('Wrong call_name: {name}'.format(name=call_name))

    cm.recurse_calls(fnc)

    # test write_on_workflow_root()
    m_file_on_root = os.path.join(cm.metadata['workflowRoot'], 'metadata.json')
    u = AutoURI(m_file_on_root)
    u.rm()
    assert not u.exists

    cm.write_on_workflow_root()
    assert os.path.exists(m_file_on_root)
    assert CromwellMetadata(m_file_on_root).metadata == cm.metadata


def test_on_failed_workflow(tmp_path, cromwell, womtool):
    fileobj_stdout = sys.stdout

    make_directory_with_failing_wdls(str(tmp_path / 'failed'))

    # Run Cromwell to get metadata JSON
    # designed to fail in a subworkflow
    c = Cromwell(cromwell=cromwell, womtool=womtool)
    th = c.run(
        wdl=str(tmp_path / 'failed' / 'main.wdl'),
        inputs=str(tmp_path / 'failed' / 'inputs.json'),
        fileobj_stdout=fileobj_stdout,
        cwd=str(tmp_path / 'failed'),
    )
    th.join()

    # check failed
    assert th.returncode
    metadata = th.returnvalue
    assert metadata
    cm = CromwellMetadata(metadata)

    assert cm.failures == metadata['failures']
    assert cm.calls == metadata['calls']

    # test troubleshoot()
    fileobj = StringIO()
    cm.troubleshoot(fileobj=fileobj)

    fileobj.seek(0)
    s = fileobj.read()
    assert '* Found failures JSON object' in s
    assert 'NAME=sub.t2_failing' in s
    assert 'INTENTED_ERROR: command not found'
