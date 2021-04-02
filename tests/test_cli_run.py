"""This does not cover all CLI parameters defined in caper/caper_args.py.
Google Cloud Platform is tested in test_cli_server_client.py.
However, other cloud (aws) and HPCs (slurm/sge/pbs) are not tested.

In this testing module, 'caper run' is tested with a local backend.

See test_cli_server_client.py for 'caper server/submit/...'.
We will use gcp (Google Cloud Platform) backend to test server-client
functions.
"""
import json
import os

import pytest
from autouri import GCSURI

from caper.cli import main as cli_main
from caper.cromwell_metadata import CromwellMetadata
from caper.wdl_parser import WDLParser

from .example_wdl import make_directory_with_wdls


def test_wrong_subcmd():
    cmd = ['wrong_subcmd']
    with pytest.raises(SystemExit):
        cli_main(cmd)


@pytest.mark.parametrize(
    'cmd',
    [
        ['--docker', '--singularity'],
        ['--docker', 'ubuntu:latest', '--singularity'],
        ['--docker', '--singularity', 'docker://ubuntu:latest'],
        ['--docker', 'ubuntu:latest', '--singularity', 'docker://ubuntu:latest'],
        ['--docker', '--soft-glob-output'],
        ['--docker', 'ubuntu:latest', '--soft-glob-output'],
    ],
)
def test_mutually_exclusive_params(tmp_path, cmd):
    make_directory_with_wdls(str(tmp_path))

    cmd = ['run', str(tmp_path / 'main.wdl')] + cmd
    with pytest.raises(ValueError):
        cli_main(cmd)


@pytest.mark.integration
def test_run(tmp_path, cromwell, womtool, debug_caper):
    """Will test most local parameters (run only) here.
    """
    make_directory_with_wdls(str(tmp_path))
    wdl = tmp_path / 'main.wdl'
    inputs = tmp_path / 'inputs.json'
    p = WDLParser(str(wdl))
    imports = p.zip_subworkflows(str(tmp_path / 'imports.zip'))

    cmd = ['run']
    cmd += [str(wdl)]
    cmd += ['--tmp-dir', str(tmp_path / 'tmp_dir')]
    # local (instead of correct Local with capital L) should work.
    cmd += ['--backend', 'local']
    cmd += ['--cromwell-stdout', str(tmp_path / 'cromwell_stdout.o')]
    cmd += ['--db', 'file']
    cmd += ['--db-timeout', '500000']
    cmd += ['--file-db', str(tmp_path / 'file_db_prefix')]
    cmd += ['--max-concurrent-tasks', '2']
    cmd += ['--max-concurrent-workflows', '2']
    cmd += ['--disable-call-caching']
    cmd += ['--soft-glob-output']
    cmd += ['--local-hash-strat', 'path']
    cmd += ['--local-out-dir', str(tmp_path / 'out_dir')]
    cmd += ['--inputs', str(inputs)]
    cmd += ['--imports', str(imports)]
    cmd += ['--ignore-womtool']
    cmd += ['--cromwell', cromwell]
    cmd += ['--womtool', womtool]
    cmd += ['--java-heap-womtool', '2G']
    cmd += ['--java-heap-run', '2G']
    cmd += ['--max-retries', '1']
    cmd += ['--metadata-output', str(tmp_path / 'metadata.json')]
    if debug_caper:
        cmd += ['--debug']

    cli_main(cmd)

    assert (tmp_path / 'tmp_dir').exists()
    assert (tmp_path / 'file_db_prefix.lobs').exists()
    assert (tmp_path / 'metadata.json').exists()
    assert (tmp_path / 'cromwell_stdout.o').exists()

    # test cleanup() on local storage
    cm = CromwellMetadata(str(tmp_path / 'metadata.json'))
    # check if metadata JSON and workflowRoot dir exists
    root_out_dir = cm.data['workflowRoot']
    assert os.path.exists(root_out_dir) and os.path.isdir(root_out_dir)

    # dry-run should not delete anything
    cm.cleanup(dry_run=True)
    assert os.path.exists(root_out_dir)

    cm.cleanup(dry_run=False)
    assert not os.path.exists(root_out_dir)


@pytest.mark.google_cloud
@pytest.mark.integration
def test_run_gcp_with_life_sciences_api(
    tmp_path,
    gcs_root,
    ci_prefix,
    cromwell,
    womtool,
    gcp_prj,
    gcp_service_account_key_json,
    debug_caper,
):
    """Test run with Google Cloud Life Sciences API
    """
    out_gcs_bucket = os.path.join(gcs_root, 'caper_out', ci_prefix)
    tmp_gcs_bucket = os.path.join(gcs_root, 'caper_tmp')

    # prepare WDLs and input JSON, imports to be submitted
    make_directory_with_wdls(str(tmp_path))
    wdl = tmp_path / 'main.wdl'
    inputs = tmp_path / 'inputs.json'
    metadata = tmp_path / 'metadata.json'

    cmd = ['run', str(wdl)]
    cmd += ['--inputs', str(inputs)]
    cmd += ['-m', str(metadata)]
    if gcp_service_account_key_json:
        cmd += ['--gcp-service-account-key-json', gcp_service_account_key_json]
    cmd += ['--use-google-cloud-life-sciences']
    cmd += ['--gcp-region', 'us-central1']
    # --gcp-zones should be ignored
    cmd += ['--gcp-zones', 'us-west1-a,us-west1-b']
    cmd += ['--gcp-prj', gcp_prj]
    cmd += ['--memory-retry-error-keys', 'Killed']
    cmd += ['--memory-retry-multiplier', '1.5']
    cmd += ['--tmp-dir', str(tmp_path / 'tmp_dir')]
    cmd += ['--backend', 'gcp']
    cmd += ['--gcp-out-dir', out_gcs_bucket]
    cmd += ['--gcp-loc-dir', tmp_gcs_bucket]
    cmd += ['--cromwell-stdout', str(tmp_path / 'cromwell_stdout.o')]
    # test with file type DB
    cmd += ['--db', 'file']
    cmd += ['--db-timeout', '500000']
    cmd += ['--file-db', str(tmp_path / 'file_db_prefix')]
    cmd += ['--max-concurrent-tasks', '2']
    cmd += ['--max-concurrent-workflows', '2']
    cmd += ['--disable-call-caching']
    cmd += ['--cromwell', cromwell]
    cmd += ['--womtool', womtool]
    cmd += ['--java-heap-run', '4G']
    cmd += ['--docker', 'ubuntu:latest']
    if debug_caper:
        cmd += ['--debug']
    print(' '.join(cmd))

    cli_main(cmd)
    m_dict = json.loads(metadata.read_text())

    assert m_dict['status'] == 'Succeeded'

    # test CromwellMetadata.gcp_monitor() here
    # since it's for gcp only and this function is one of the two
    # test functions ran on a gcp backend.
    # task main.t1 has sleep 10 so that monitoring_script has time to
    # write monitoring data to `monitoringLog` file
    cm = CromwellMetadata(m_dict)
    monitor_data = cm.gcp_monitor()
    for data in monitor_data:
        instance_cpu = data['instance']['cpu']
        instance_mem = data['instance']['mem']
        instance_disk = data['instance']['disk']
        assert instance_cpu >= 1
        assert instance_mem >= 1024 * 1024 * 1024
        assert instance_disk >= 10 * 1024 * 1024 * 1024

        max_cpu_percent = data['stats']['max']['cpu_pct']
        max_mem = data['stats']['max']['mem']
        max_disk = data['stats']['max']['disk']
        if max_cpu_percent or data['task_name'] == 'main.t1':
            assert max_cpu_percent <= 100.0
        if max_mem or data['task_name'] == 'main.t1':
            assert max_mem <= instance_mem
        if max_disk or data['task_name'] == 'main.t1':
            assert max_disk <= instance_disk

    # test cleanup on gcp backend (gs://)
    root_out_dir = cm.data['workflowRoot']

    # remote metadata JSON file on workflow's root output dir.
    remote_metadata_json_file = os.path.join(root_out_dir, 'metadata.json')
    assert GCSURI(remote_metadata_json_file).exists

    # dry-run should not delete anything
    cm.cleanup(dry_run=True)
    assert GCSURI(remote_metadata_json_file).exists

    cm.cleanup(dry_run=False)
    assert not GCSURI(remote_metadata_json_file).exists
