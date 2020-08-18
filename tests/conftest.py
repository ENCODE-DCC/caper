#!/usr/bin/env python3
"""
"""
import pytest

from caper.cromwell import Cromwell


def pytest_addoption(parser):
    parser.addoption(
        '--ci-prefix', default='default_ci_prefix', help='Prefix for CI test.'
    )
    parser.addoption(
        '--gcs-root',
        default='gs://encode-test-caper',
        help='GCS root path for CI test. '
        'This GCS bucket must be publicly accessible '
        '(read access for everyone is enough for testing).',
    )
    parser.addoption(
        '--gcs-metadata-files-for-res-analysis',
        nargs='+',
        default=[
            'gs://encode-test-caper/res_analysis/caper_out/atac/',
            'gs://encode-test-caper/res_analysis/caper_out/atac/',
        ],
        help='GCS paths of metadata.json files for pipelines. '
        'Resource data will be collected for them and used for testing '
        'class ResourceAnalysis.',
    )
    parser.addoption(
        '--cromwell',
        default=Cromwell.DEFAULT_CROMWELL,
        help='URI for Cromwell JAR. Local path is recommended.',
    )
    parser.addoption(
        '--womtool',
        default=Cromwell.DEFAULT_WOMTOOL,
        help='URI for Womtool JAR. Local path is recommended.',
    )
    parser.addoption(
        '--gcp-prj', default='encode-dcc-1016', help='Project on Google Cloud Platform.'
    )
    parser.addoption(
        '--gcp-service-account-key-json', help='JSON key file for GCP service account.'
    )
    parser.addoption(
        '--debug-caper', action='store_true', help='Debug-level logging for CLI tests.'
    )


@pytest.fixture(scope='session')
def ci_prefix(request):
    return request.config.getoption('--ci-prefix').rstrip('/')


@pytest.fixture(scope='session')
def gcs_root(request):
    """GCS root to generate test GCS URIs on.
    """
    return request.config.getoption('--gcs-root').rstrip('/')


@pytest.fixture(scope='session')
def cromwell(request):
    return request.config.getoption('--cromwell')


@pytest.fixture(scope='session')
def womtool(request):
    return request.config.getoption('--womtool')


@pytest.fixture(scope='session')
def gcp_prj(request):
    return request.config.getoption('--gcp-prj')


@pytest.fixture(scope='session')
def gcp_service_account_key_json(request):
    return request.config.getoption('--gcp-service-account-key-json')


@pytest.fixture(scope='session')
def debug_caper(request):
    return request.config.getoption('--debug-caper')


@pytest.fixture(scope='session')
def gcs_metadata_files_for_res_analysis(request):
    return request.config.getoption('--gcs-metadata-files-for-res-analysis')
