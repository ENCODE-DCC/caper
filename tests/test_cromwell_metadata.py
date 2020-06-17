import os
from io import StringIO

from autouri import AutoURI

from caper.cromwell import Cromwell
from caper.cromwell_metadata import CromwellMetadata

from .example_wdl import make_directory_with_wdls


def test_all(tmp_path, cromwell, womtool):
    make_directory_with_wdls(str(tmp_path / 'successful'))

    # Run Cromwell to get metadata JSON
    cromwell_stdout = StringIO()
    c = Cromwell(cromwell=cromwell, womtool=womtool)
    th = c.run(
        wdl=str(tmp_path / 'successful' / 'main.wdl'), fileobj_stdout=cromwell_stdout
    )
    th.join()

    metadata = th.ret
    print(type(metadata))
    cm = CromwellMetadata(metadata)

    # test all properties
    assert cm.data == metadata
    assert cm.metadata == metadata
    assert CromwellMetadata(metadata).data == metadata
    assert cm.workflow_id == metadata['id']
    assert cm.workflow_status == metadata['status']
    assert cm.failures == metadata['failures']
    assert cm.calls == metadata['calls']

    # test recurse_calls(): test with a simple function

    # test write_on_workflow_root()
    m_file_on_root = os.path.join(cm.metadata['workflowRoot'], 'metadata.json')
    u = AutoURI(m_file_on_root)
    u.rm()
    assert not u.exists

    cm.write_on_workflow_root()
    assert os.path.exists(m_file_on_root)
    assert CromwellMetadata(m_file_on_root).metadata == cm.metadata

    # make_directory_with_failing_wdls(str(tmp_path / 'failed'))

    # # Run Cromwell to get failed metadata.json
    # # to test troubleshoot()
    # cromwell_stdout = StringIO()
    # th_failed = c.run(
    #     wdl=str(tmp_path / 'failed' / 'main.wdl'), fileobj_stdout=cromwell_stdout
    # )
    # th_failed.join()

    # failed_metadata = th_failed.ret
    # failed_cm = CromwellMetadata(failed_metadata)

    # # test troubleshoot()
    # fileobj = StringIO()
    # failed_cm.troubleshoot()

    # fileobj.seek(0)
    # s = fileobj.read()
    # assert '* Found failures JSON object' in s
    # assert '==== NAME=' in s
