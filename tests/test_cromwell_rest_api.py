import sys
import time

import pytest

from caper.caper_labels import CaperLabels
from caper.cromwell import Cromwell
from caper.cromwell_rest_api import CromwellRestAPI, has_wildcard, is_valid_uuid
from caper.wdl_parser import WDLParser

from .example_wdl import make_directory_with_wdls


@pytest.mark.parametrize(
    'test_input,expected',
    [
        ('asldkhjlkasdf289jisdl;sladkjasdflksd', False),
        ('cromwell-f9c26f2e-f550-4748-a650-5d0d4cab9f3a', False),
        ('f9c26f2e-f550-4748-a650-5d0d4c', False),
        ('f9c26f2e-f550-4748-a650-5d0d4cab9f3a', True),
        ('F9C26f2e-F550-4748-A650-5D0D4cab9f3a', False),
        ('f9c26f2e', False),
        ([], False),
        (tuple(), False),
        (None, False),
    ],
)
def test_is_valid_uuid(test_input, expected):
    assert is_valid_uuid(test_input) == expected


@pytest.mark.parametrize(
    'test_input,expected',
    [
        ('?????', True),
        (('lskadfj', 'sdkfjaslf'), False),
        ('*', True),
        ('?', True),
        (':', False),
        (('*', '?'), True),
        (('_', '-', 'asdfjkljklasdfjklasdf'), False),
        ([], False),
        (tuple(), False),
        (None, False),
    ],
)
def test_has_wildcard(test_input, expected):
    assert has_wildcard(test_input) == expected


def test_all(tmp_path, cromwell, womtool):
    """Test Cromwell.server() method, which returns a Thread object.
    """
    server_port = 8010
    fileobj_stdout = sys.stdout
    test_label = 'test_label'

    c = Cromwell(cromwell=cromwell, womtool=womtool)

    o_dir = tmp_path / 'output'
    o_dir.mkdir()

    labels_file = CaperLabels().create_file(
        directory=str(tmp_path), str_label=test_label
    )

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
            if time.time() - t_start > 60:
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
        # no workflow
        assert not cra.find(workflow_ids=['*'])

        # put a hold on a workflow when submitting
        r = cra.submit(
            source=str(wdl),
            dependencies=imports,
            inputs=str(tmp_path / 'inputs.json'),
            labels=labels_file,
            on_hold=True,
        )
        workflow_id = r['id']
        time.sleep(10)
        # find by workflow ID
        workflow_by_id = cra.find(workflow_ids=[workflow_id])[0]
        # find by label
        workflow_by_label = cra.find(labels=[('caper-str-label', test_label)])[0]
        # find by workflow ID with wildcard *
        workflow_by_id_with_wildcard = cra.find(workflow_ids=[workflow_id[:-10] + '*'])[
            0
        ]
        # find by label with wildcard ?
        workflow_by_label_with_wildcard = cra.find(
            labels=[('caper-str-label', test_label[:-1] + '?')]
        )[0]

        assert workflow_by_label['id'] == workflow_id
        assert workflow_by_id['id'] == workflow_id
        assert workflow_by_id_with_wildcard['id'] == workflow_id
        assert workflow_by_label_with_wildcard['id'] == workflow_id
        assert workflow_by_id['status'] == 'On Hold'

        cra.release_hold([workflow_id])
        time.sleep(3)

        assert cra.get_label(workflow_id, 'caper-str-label') == test_label
        assert cra.get_labels(workflow_id)['caper-str-label'] == test_label

        # abort it
        assert cra.find([workflow_id])[0]['status'] in ('Submitted', 'On Hold')
        cra.abort([workflow_id])
        time.sleep(5)
        assert cra.find([workflow_id])[0]['status'] == 'Aborted'

        # submit another workflow
        r = cra.submit(
            source=str(wdl),
            dependencies=imports,
            inputs=str(tmp_path / 'inputs.json'),
            on_hold=False,
        )
        is_workflow_done = False
        workflow_id = r['id']
        time.sleep(5)

        t_start = time.time()
        while not is_workflow_done:
            time.sleep(1)
            print('polling: ', workflow_id, is_workflow_done)
            if time.time() - t_start > 120:
                raise TimeoutError('Timed out waiting for workflow being done.')

        metadata = cra.get_metadata([workflow_id], embed_subworkflow=True)[0]
        metadata_wo_sub = cra.get_metadata([workflow_id], embed_subworkflow=False)[0]

        assert 'subWorkflowMetadata' not in metadata_wo_sub['calls']['main.sub'][0]
        subworkflow = metadata['calls']['main.sub'][0]
        assert 'subWorkflowMetadata' in subworkflow
        assert (
            'subWorkflowMetadata'
            in subworkflow['subWorkflowMetadata']['calls']['sub.sub_sub'][0]
        )

        # check server's properties before closing it
        assert cra.get_default_backend() == 'Local'
        assert cra.get_backends()['supportedBackends'] == ['Local']

    finally:
        th.stop()
        th.join()
