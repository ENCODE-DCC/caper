import sys
import time

from caper.caper_labels import CaperLabels
from caper.cromwell import Cromwell
from caper.cromwell_rest_api import CromwellRestAPI
from caper.wdl_parser import WDLParser

from .example_wdl import make_directory_with_wdls


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
        time.sleep(5)
        # find by label (not by workflow id)
        workflow_by_id = cra.find(workflow_ids=[workflow_id])[0]
        workflow_by_label = cra.find(labels=[('caper-str-label', test_label)])[0]

        assert workflow_by_label['id'] == workflow_id
        assert workflow_by_id['id'] == workflow_id
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
            if time.time() - t_start > 60:
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
