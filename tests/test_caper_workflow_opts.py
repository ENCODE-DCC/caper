import json
import os
from textwrap import dedent

import pytest

from caper.caper_workflow_opts import CaperWorkflowOpts
from caper.cromwell_backend import BACKEND_AWS, BACKEND_GCP


def test_create_file(tmp_path):
    """Test without docker/singularity.
    """
    use_google_cloud_life_sciences = False
    gcp_zones = ['us-west-1', 'us-west-2']
    slurm_partition = 'my_partition'
    slurm_account = 'my_account'
    slurm_extra_param = 'my_extra_param'
    sge_pe = 'my_pe'
    sge_queue = 'my_queue'
    sge_extra_param = 'my_extra_param'
    pbs_queue = 'my_queue'
    pbs_extra_param = 'my_extra_param'

    co = CaperWorkflowOpts(
        use_google_cloud_life_sciences=use_google_cloud_life_sciences,
        gcp_zones=gcp_zones,
        slurm_partition=slurm_partition,
        slurm_account=slurm_account,
        slurm_extra_param=slurm_extra_param,
        sge_pe=sge_pe,
        sge_queue=sge_queue,
        sge_extra_param=sge_extra_param,
        pbs_queue=pbs_queue,
        pbs_extra_param=pbs_extra_param,
    )

    wdl = tmp_path / 'test.wdl'
    wdl.write_text('')

    inputs = None

    # check if backend and slurm_partition is replaced with
    # that of this custom options file.
    custom_options = tmp_path / 'my_custom_options.json'
    custom_options_dict = {
        'backend': 'world',
        CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES: {
            'slurm_partition': 'not_my_partition'
        },
    }
    custom_options.write_text(json.dumps(custom_options_dict, indent=4))

    backend = 'my_backend'
    max_retries = 999
    memory_retry_multiplier = 1.3
    gcp_monitoring_script = 'gs://dummy/gcp_monitoring_script.sh'
    basename = 'my_basename.json'

    f = co.create_file(
        directory=str(tmp_path),
        wdl=str(wdl),
        inputs=inputs,
        custom_options=str(custom_options),
        docker=None,
        singularity=None,
        singularity_cachedir=None,
        no_build_singularity=False,
        backend=backend,
        max_retries=max_retries,
        memory_retry_multiplier=memory_retry_multiplier,
        gcp_monitoring_script=gcp_monitoring_script,
        basename=basename,
    )

    with open(f) as fp:
        d = json.loads(fp.read())

    dra = d[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]
    assert dra['zones'] == ' '.join(gcp_zones)
    assert dra['slurm_partition'] == 'not_my_partition'
    assert dra['slurm_account'] == slurm_account
    assert dra['slurm_extra_param'] == slurm_extra_param
    assert dra['sge_pe'] == sge_pe
    assert dra['sge_queue'] == sge_queue
    assert dra['sge_extra_param'] == sge_extra_param
    assert dra['pbs_queue'] == pbs_queue
    assert dra['pbs_extra_param'] == pbs_extra_param

    assert d['backend'] == 'world'
    assert dra['maxRetries'] == max_retries
    # assert d['memory_retry_multiplier'] == memory_retry_multiplier
    # this should be ignored for non-gcp backends
    assert 'monitoring_script' not in d
    assert os.path.basename(f) == basename
    assert os.path.dirname(f) == str(tmp_path)

    # test for gcp backend
    f = co.create_file(
        directory=str(tmp_path),
        wdl=str(wdl),
        backend='gcp',
        docker='ubuntu:latest',
        max_retries=max_retries,
        gcp_monitoring_script=gcp_monitoring_script,
        basename=basename,
    )
    with open(f) as fp:
        d = json.loads(fp.read())
    assert d['monitoring_script'] == gcp_monitoring_script


def test_create_file_with_google_cloud_life_sciences(tmp_path):
    """Test with use_google_cloud_life_sciences flag.
    zones should not be written to dra.
    """
    gcp_zones = ['us-west-1', 'us-west-2']

    co = CaperWorkflowOpts(use_google_cloud_life_sciences=True, gcp_zones=gcp_zones)

    wdl = tmp_path / 'test.wdl'
    wdl.write_text('')

    f = co.create_file(directory=str(tmp_path), wdl=str(wdl))

    with open(f) as fp:
        d = json.loads(fp.read())

    dra = d[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]
    assert 'zones' not in dra


def test_create_file_docker(tmp_path):
    """Test with docker and docker defined in WDL.
    """
    wdl_contents = dedent(
        """\
        version 1.0
        workflow test_docker {
            meta {
                caper_docker: "ubuntu:latest"
            }
        }
    """
    )

    wdl = tmp_path / 'docker.wdl'
    wdl.write_text(wdl_contents)

    co = CaperWorkflowOpts()

    # cloud backend gcp should try to find docker in WDL
    f_gcp = co.create_file(
        directory=str(tmp_path),
        wdl=str(wdl),
        backend=BACKEND_GCP,
        basename='opts_gcp.json',
    )
    with open(f_gcp) as fp:
        d_gcp = json.loads(fp.read())
        dra_gcp = d_gcp[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]
    assert dra_gcp['docker'] == 'ubuntu:latest'

    # cloud backend aws should try to find docker in WDL
    f_aws = co.create_file(
        directory=str(tmp_path),
        wdl=str(wdl),
        backend=BACKEND_AWS,
        basename='opts_aws.json',
    )
    with open(f_aws) as fp:
        d_aws = json.loads(fp.read())
        dra_aws = d_aws[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]
    assert dra_aws['docker'] == 'ubuntu:latest'

    # local backend should not try to find docker in WDL
    # if docker is not defined
    f_local = co.create_file(
        directory=str(tmp_path),
        wdl=str(wdl),
        backend='my_backend',
        basename='opts_local.json',
    )
    with open(f_local) as fp:
        d_local = json.loads(fp.read())
        dra_local = d_local[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]
    assert 'docker' not in dra_local

    # local backend should use docker if docker is explicitly defined
    f_local2 = co.create_file(
        directory=str(tmp_path),
        wdl=str(wdl),
        docker='ubuntu:16',
        backend='my_backend',
        basename='opts_local2.json',
    )
    with open(f_local2) as fp:
        d_local2 = json.loads(fp.read())
        dra_local2 = d_local2[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]
    assert dra_local2['docker'] == 'ubuntu:16'


def test_create_file_singularity(tmp_path):
    """Test with singularity and singularity defined in WDL.
    """
    wdl_contents = dedent(
        """\
        version 1.0
        workflow test_singularity {
            meta {
                caper_docker: "ubuntu:latest"
                caper_singularity: "docker://ubuntu:latest"
            }
        }
    """
    )

    wdl = tmp_path / 'singularity.wdl'
    wdl.write_text(wdl_contents)

    co = CaperWorkflowOpts()

    # cloud backend gcp should not try to find singularity in WDL
    f_gcp = co.create_file(
        directory=str(tmp_path),
        wdl=str(wdl),
        backend=BACKEND_GCP,
        basename='opts_gcp.json',
    )
    with open(f_gcp) as fp:
        d_gcp = json.loads(fp.read())
        dra_gcp = d_gcp[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]
    assert 'singularity' not in dra_gcp

    # cloud backend aws should not try to find singularity in WDL
    f_aws = co.create_file(
        directory=str(tmp_path),
        wdl=str(wdl),
        backend=BACKEND_AWS,
        basename='opts_aws.json',
    )
    with open(f_aws) as fp:
        d_aws = json.loads(fp.read())
        dra_aws = d_aws[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]
    assert 'singularity' not in dra_aws

    # cloud backend aws/gcp should not work with singularity
    with pytest.raises(ValueError):
        co.create_file(
            directory=str(tmp_path),
            wdl=str(wdl),
            backend=BACKEND_GCP,
            singularity='',
            basename='opts_gcp2.json',
        )
    with pytest.raises(ValueError):
        co.create_file(
            directory=str(tmp_path),
            wdl=str(wdl),
            backend=BACKEND_AWS,
            singularity='',
            basename='opts_aws2.json',
        )

    # local backend should not try to find singularity in WDL
    # if singularity is not defined
    f_local = co.create_file(
        directory=str(tmp_path),
        wdl=str(wdl),
        backend='my_backend',
        basename='opts_local.json',
    )
    with open(f_local) as fp:
        d_local = json.loads(fp.read())
        dra_local = d_local[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]
    assert 'singularity' not in dra_local

    # input JSON to test singularity bindpath
    # this will be test thoroughly in other testing module (test_singularity)
    inputs = tmp_path / 'inputs.json'
    inputs_dict = {
        'test.input': '/a/b/c/d.txt',
        'test.input2': '/a/b/e.txt',
        'test.input3': '/f/g/h.txt',
    }
    inputs.write_text(json.dumps(inputs_dict, indent=4))

    # local backend should use singularity if singularity is explicitly defined
    # also, singularity_bindpath should be input JSON.
    f_local2 = co.create_file(
        directory=str(tmp_path),
        wdl=str(wdl),
        inputs=str(inputs),
        singularity='ubuntu:16',
        singularity_cachedir='/tmp',
        no_build_singularity=True,
        backend='my_backend',
        basename='opts_local2.json',
    )
    with open(f_local2) as fp:
        d_local2 = json.loads(fp.read())
        dra_local2 = d_local2[CaperWorkflowOpts.DEFAULT_RUNTIME_ATTRIBUTES]
    assert dra_local2['singularity'] == 'ubuntu:16'
    assert dra_local2['singularity_cachedir'] == '/tmp'
    assert sorted(dra_local2['singularity_bindpath'].split(',')) == ['/a/b', '/f/g']
