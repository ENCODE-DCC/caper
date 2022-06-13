import os

from .cromwell import Cromwell
from .cromwell_backend import (
    BACKEND_ALIAS_LOCAL,
    BACKEND_AWS,
    BACKEND_GCP,
    BACKEND_LOCAL,
    BACKEND_LSF,
    BACKEND_PBS,
    BACKEND_SGE,
    BACKEND_SLURM,
    CromwellBackendLsf,
    CromwellBackendPbs,
    CromwellBackendSge,
    CromwellBackendSlurm,
)

from .hpc import (
    SlurmWrapper,
    SgeWrapper,
    PbsWrapper,
    LsfWrapper,
)


CONF_CONTENTS_TMP_DIR = """
# Local directory for localized files and Cromwell's intermediate files.
# If not defined then Caper will make .caper_tmp/ on CWD or `local-out-dir`.
# /tmp is not recommended since Caper store localized data files here.
local-loc-dir=
"""

CONF_CONTENTS_COMMON_RESOURCE_PARAM_HELP = """
# This parameter defines resource parameters for submitting WDL task to job engine.
# It is for HPC backends only (slurm, sge, pbs and lsf).
# It is not recommended to change it unless your cluster has custom resource settings.
# See https://github.com/ENCODE-DCC/caper/blob/master/docs/resource_param.md for details."""

CONF_CONTENTS_SLURM_PARAM = """
# This parameter defines resource parameters for Caper's leader job only.
slurm-leader-job-resource-param={slurm_leader_job_resource_param}
{help_context}
slurm-resource-param={slurm_resource_param}
""".format(
    help_context=CONF_CONTENTS_COMMON_RESOURCE_PARAM_HELP,
    slurm_resource_param=CromwellBackendSlurm.DEFAULT_SLURM_RESOURCE_PARAM,
    slurm_leader_job_resource_param=' '.join(SlurmWrapper.DEFAULT_LEADER_JOB_RESOURCE_PARAM),
)

CONF_CONTENTS_SGE_PARAM = """
# This parameter defines resource parameters for Caper's leader job only.
sge-leader-job-resource-param={sge_leader_job_resource_param}

# Parallel environment of SGE:
# Find one with `$ qconf -spl` or ask you admin to add one if not exists.
# If your cluster works without PE then edit the below sge-resource-param
sge-pe=
{help_context}
sge-resource-param={sge_resource_param}
""".format(
    help_context=CONF_CONTENTS_COMMON_RESOURCE_PARAM_HELP,
    sge_resource_param=CromwellBackendSge.DEFAULT_SGE_RESOURCE_PARAM,
    sge_leader_job_resource_param=' '.join(SgeWrapper.DEFAULT_LEADER_JOB_RESOURCE_PARAM),
)

CONF_CONTENTS_PBS_PARAM = """
# This parameter defines resource parameters for Caper's leader job only.
pbs-leader-job-resource-param={pbs_leader_job_resource_param}
{help_context}
pbs-resource-param={pbs_resource_param}
""".format(
    help_context=CONF_CONTENTS_COMMON_RESOURCE_PARAM_HELP,
    pbs_resource_param=CromwellBackendPbs.DEFAULT_PBS_RESOURCE_PARAM,
    pbs_leader_job_resource_param=' '.join(PbsWrapper.DEFAULT_LEADER_JOB_RESOURCE_PARAM),
)

CONF_CONTENTS_LSF_PARAM = """
# This parameter defines resource parameters for Caper's leader job only.
lsf-leader-job-resource-param={lsf_leader_job_resource_param}
{help_context}
lsf-resource-param={lsf_resource_param}
""".format(
    help_context=CONF_CONTENTS_COMMON_RESOURCE_PARAM_HELP,
    lsf_resource_param=CromwellBackendLsf.DEFAULT_LSF_RESOURCE_PARAM,
    lsf_leader_job_resource_param=' '.join(LsfWrapper.DEFAULT_LEADER_JOB_RESOURCE_PARAM),
)

DEFAULT_CONF_CONTENTS_LOCAL = (
    """backend=local
"""
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_SLURM = (
    """backend=slurm

# SLURM partition. DEFINE ONLY IF REQUIRED BY YOUR CLUSTER'S POLICY.
# You must define it for Stanford Sherlock.
slurm-partition=

# SLURM account. DEFINE ONLY IF REQUIRED BY YOUR CLUSTER'S POLICY.
# You must define it for Stanford SCG.
slurm-account=
"""
    + CONF_CONTENTS_TMP_DIR
    + CONF_CONTENTS_SLURM_PARAM
)

DEFAULT_CONF_CONTENTS_SGE = (
    """backend=sge

# Parallel environement is required, ask your administrator to create one
# If your cluster doesn't support PE then edit 'sge-resource-param'
# to fit your cluster's configuration.
"""
    + CONF_CONTENTS_TMP_DIR
    + CONF_CONTENTS_SGE_PARAM
)

DEFAULT_CONF_CONTENTS_PBS = (
    """backend=pbs
"""
    + CONF_CONTENTS_TMP_DIR
    + CONF_CONTENTS_PBS_PARAM
)

DEFAULT_CONF_CONTENTS_LSF = (
    """backend=lsf
"""
    + CONF_CONTENTS_TMP_DIR
    + CONF_CONTENTS_LSF_PARAM
)

DEFAULT_CONF_CONTENTS_AWS = (
    """backend=aws

# ARN for AWS Batch.
aws-batch-arn=
# AWS region (e.g. us-west-1)
aws-region=
# Output bucket path for AWS. This should start with `s3://`.
aws-out-dir=

# use this modified cromwell to fix input file localization failures
# (104 Connection reset by peer)
# cromwell uses AWS CLI(aws s3 cp)'s native retry feature which is controlled by
# several environment variables but it doesn't seem to work for some reason
# this is an adhoc fix to make cromwell retry up to 5 times in the bash script level
# https://github.com/ENCODE-DCC/cromwell/commit/d16af26483e0019e14d6f8b158eaf64529f57d98
cromwell=https://storage.googleapis.com/caper-data/cromwell/cromwell-65-d16af26-SNAP.jar
"""
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_GCP = (
    """backend=gcp

# Google Cloud Platform Project
gcp-prj=
# Output bucket path for Google Cloud Platform. This should start with `gs://`.
gcp-out-dir=

# Call-cached outputs will be duplicated by making a copy or reference
#   reference: refer to old output file in metadata.json file.
#   copy (not recommended): make a copy for a new workflow.
gcp-call-caching-dup-strat=

# Use Google Cloud Life Sciences API instead of Genomics API (deprecating).
# Make sure to enable Google Cloud Life Sciences API on your Google Cloud Console
use-google-cloud-life-sciences=true

# gcp-region is required for Life Sciences API only.
# Region is different from zone. Zone is more specific.
# Do not define zone here. Check supported regions:
#   https://cloud.google.com/life-sciences/docs/concepts/locations
# e.g. us-central1
gcp-region=

# Comma-separated zones for Genomics API (deprecating).
# This is ignored if use-google-cloud-life-sciences.
# e.g. us-west1-a,us-west1-b,us-west1-c
gcp-zones=

# Number of retrials. This parameter also applies to non-OOM failures.
max-retries=1
"""
    + CONF_CONTENTS_TMP_DIR
)


def init_caper_conf(conf_file, backend):
    """Initialize conf file for a given backend.
    There are two special backend aliases for two Stanford clusters.
    These clusters are based on SLURM.
    Also, download/install Cromwell/Womtool JARs, whose
    default URL and install dir are defined in class Cromwell.
    """
    if backend in (BACKEND_LOCAL, BACKEND_ALIAS_LOCAL):
        contents = DEFAULT_CONF_CONTENTS_LOCAL
    elif backend == BACKEND_SLURM:
        contents = DEFAULT_CONF_CONTENTS_SLURM
    elif backend == BACKEND_SGE:
        contents = DEFAULT_CONF_CONTENTS_SGE
    elif backend == BACKEND_PBS:
        contents = DEFAULT_CONF_CONTENTS_PBS
    elif backend == BACKEND_LSF:
        contents = DEFAULT_CONF_CONTENTS_LSF
    elif backend in BACKEND_GCP:
        contents = DEFAULT_CONF_CONTENTS_GCP
    elif backend in BACKEND_AWS:
        contents = DEFAULT_CONF_CONTENTS_AWS
    else:
        raise ValueError('Unsupported backend {p}'.format(p=backend))

    conf_file = os.path.expanduser(conf_file)
    os.makedirs(os.path.dirname(conf_file), exist_ok=True)

    with open(conf_file, 'w') as fp:
        fp.write(contents + '\n')

        cromwell = Cromwell()
        fp.write(
            '{key}={val}\n'.format(key='cromwell', val=cromwell.install_cromwell())
        )
        fp.write('{key}={val}\n'.format(key='womtool', val=cromwell.install_womtool()))
