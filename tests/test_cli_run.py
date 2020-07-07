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

from caper.cli import main as cli_main
from caper.wdl_parser import WDLParser

from .example_wdl import make_directory_with_wdls


def test_wrong_subcmd():
    cmd = ['wrong_subcmd']
    with pytest.raises(SystemExit):
        cli_main(cmd)


def test_mutually_exclusive_params(tmp_path):
    make_directory_with_wdls(str(tmp_path))

    # mutually exclusive params
    cmd = ['run', str(tmp_path / 'main.wdl'), '--docker', '--singularity']
    with pytest.raises(ValueError):
        cli_main(cmd)
    cmd = ['run', str(tmp_path / 'main.wdl'), '--docker', '--soft-glob-output']
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
    cmd += ['--gcp-memory-retry-error-keys', 'Killed']
    cmd += ['--gcp-memory-retry-multiplier', '1.5']
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
