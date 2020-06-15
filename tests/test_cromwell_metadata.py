import json
import os
from io import StringIO

from autouri import AutoURI

from caper.cromwell import Cromwell
from caper.cromwell_metadata import CromwellMetadata

from .example_wdl import make_directory_with_failing_wdls, make_directory_with_wdls


def test_all(tmp_path, cromwell, womtool):
    make_directory_with_wdls(str(tmp_path / 'successful'))

    # Run Cromwell to get metadata.json
    cromwell_stdout = StringIO()
    c = Cromwell(cromwell=cromwell, womtool=womtool)
    rc, m_file = c.run(
        wdl=str(tmp_path / 'successful' / 'main.wdl'), fileobj_stdout=cromwell_stdout
    )
    print(rc, m_file)
    if rc:
        print(cromwell_stdout.read())

    cm = CromwellMetadata(m_file)
    m_dict = json.loads(AutoURI(m_file).read())

    # test all properties
    assert cm.data == m_dict
    assert cm.metadata == m_dict
    assert CromwellMetadata(m_dict).data == m_dict
    assert cm.workflow_id == m_dict['id']
    assert cm.workflow_status == m_dict['status']
    assert cm.failures == m_dict['failures']
    assert cm.calls == m_dict['calls']

    # test recurse_calls(): test with a simple function

    # test write_on_workflow_root()
    cm.write_on_workflow_root()
    m_file_on_root = os.path.join(cm.metadata['workflowRoot'], 'metadata.json')
    assert os.path.exists(m_file_on_root)
    assert CromwellMetadata(m_file_on_root).metadata == cm.metadata

    make_directory_with_failing_wdls(str(tmp_path / 'failed'))

    # Run Cromwell to get failed metadata.json
    # to test troubleshoot()
    cromwell_stdout = StringIO()
    rc, failed_m_file = c.run(
        wdl=str(tmp_path / 'failed' / 'main.wdl'), fileobj_stdout=cromwell_stdout
    )
    if rc:
        print(cromwell_stdout.read())

    failed_cm = CromwellMetadata(failed_m_file)

    # test troubleshoot()
    fileobj = StringIO()
    failed_cm.troubleshoot()

    fileobj.seek(0)
    s = fileobj.read()
    assert '* Found failures JSON object' in s
    assert '==== NAME=' in s
