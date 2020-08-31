"""Test GCP memory-retry.

Default return codes for memory-retry: [0, 137]
    137
        - General SIGKILL (including OOM kill).
    0
        - Success

If there is memory-retry-keyword in STDERR,
Cromwell does memory-retry even with return code 0, which means success.

It's currently (Cromwell-52) not possible to control such behavior for 0 return code.
So it's important to carefully parse STDERR to catch OOM for 137 cases only.

Cromwell's default memory-retry-keyword is ['OutOfMemoryError', 'Killed']
    OutOfMemoryError
        - It's Java OOM message, which is actually `java.lang.OutOfMemoryError: DESC, STACKTRACE`
    Killed
        - Default SIGKILL message format of `sh`.
        - This will catch all `Killed` in STDERR. So use regex `^Killed$` instead of it.

Cromwell is based on bash. So in order to precisely catch killed message.
Use the following.
    PID Killed CMDLINE
        - Default SIGKILL message format of `bash`.
        - Use [0-9]+ Killed
"""
import json
import os

import pytest

from caper.cli import main as cli_main

from .example_wdl import MEM_RETRY_WDL


@pytest.mark.google_cloud
@pytest.mark.integration
def test_gcp_memory_retry(
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
    # Temporarily disabled until memory-retry issue is fixed on Cromwell's side:
    #   https://github.com/broadinstitute/cromwell/issues/5815
    return

    out_gcs_bucket = os.path.join(gcs_root, 'caper_out', ci_prefix)
    tmp_gcs_bucket = os.path.join(gcs_root, 'caper_tmp')

    # prepare WDLs and input JSON, imports to be submitted
    wdl = tmp_path / 'mem_retry.wdl'
    wdl.write_text(MEM_RETRY_WDL)
    metadata = tmp_path / 'metadata.json'

    cmd = ['run', str(wdl)]
    cmd += ['-m', str(metadata)]
    if gcp_service_account_key_json:
        cmd += ['--gcp-service-account-key-json', gcp_service_account_key_json]
    cmd += ['--use-google-cloud-life-sciences']
    cmd += ['--gcp-region', 'us-central1']
    cmd += ['--gcp-zones', 'us-west1-a,us-west1-b']
    cmd += ['--gcp-prj', gcp_prj]
    cmd += ['--tmp-dir', str(tmp_path / 'tmp_dir')]
    cmd += ['--backend', 'gcp']
    cmd += ['--gcp-out-dir', out_gcs_bucket]
    cmd += ['--gcp-loc-dir', tmp_gcs_bucket]
    cmd += ['--cromwell-stdout', str(tmp_path / 'cromwell_stdout.o')]
    cmd += ['--db', 'in-memory']
    cmd += ['--cromwell', cromwell]
    cmd += ['--womtool', womtool]
    cmd += ['--java-heap-run', '4G']
    cmd += ['--docker', 'ubuntu:latest']
    if debug_caper:
        cmd += ['--debug']
    print(' '.join(cmd))

    cli_main(cmd)
    json.loads(metadata.read_text())
