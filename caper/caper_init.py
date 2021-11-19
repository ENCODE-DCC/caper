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

BACKEND_ALIAS_SHERLOCK = 'sherlock'
BACKEND_ALIAS_SCG = 'scg'


CONF_CONTENTS_DB = """
# Metadata DB for call-caching (reusing previous outputs):
# Cromwell supports restarting workflows based on a metadata DB
# DB is in-memory by default
#db=in-memory

# If you use 'caper server' then you can use one unified '--file-db'
# for all submitted workflows. In such case, uncomment the following two lines
# and defined file-db as an absolute path to store metadata of all workflows
#db=file
#file-db=

# If you use 'caper run' and want to use call-caching:
# Make sure to define different 'caper run ... --db file --file-db DB_PATH'
# for each pipeline run.
# But if you want to restart then define the same '--db file --file-db DB_PATH'
# then Caper will collect/re-use previous outputs without running the same task again
# Previous outputs will be simply hard/soft-linked.

"""

CONF_CONTENTS_LOCAL_HASH_STRAT = """
# Hashing strategy for call-caching (3 choices)
# This parameter is for local (local/slurm/sge/pbs/lsf) backend only.
# This is important for call-caching,
# which means re-using outputs from previous/failed workflows.
# Cache will miss if different strategy is used.
# "file" method has been default for all old versions of Caper<1.0.
# "path+modtime" is a new default for Caper>=1.0,
#   file: use md5sum hash (slow).
#   path: use path.
#   path+modtime: use path and modification time.
local-hash-strat=path+modtime
"""

CONF_CONTENTS_TMP_DIR = """
# Local directory for localized files and Cromwell's intermediate files
# If not defined, Caper will make .caper_tmp/ on local-out-dir or CWD.
# /tmp is not recommended here since Caper store all localized data files
# on this directory (e.g. input FASTQs defined as URLs in input JSON).
local-loc-dir=
"""

CONF_CONTENTS_COMMON_RESOURCE_PARAM_HELP = """
# This parameter is NOT for 'caper submit' BUT for 'caper run' and 'caper server' only.
# This resource parameter string will be passed to sbatch, qsub, bsub, ...
# You can customize it according to your cluster's configuration.

# Note that Cromwell's implicit type conversion (String to Integer)
# seems to be buggy for WomLong type memory variables (memory_mb and memory_gb).
# So be careful about using the + operator between WomLong and other types (String, even Int).
# For example, ${"--mem=" + memory_mb} will not work since memory_mb is WomLong.
# Use ${"if defined(memory_mb) then "--mem=" else ""}{memory_mb}${"if defined(memory_mb) then "mb " else " "}
# See https://github.com/broadinstitute/cromwell/issues/4659 for details

# Cromwell's built-in variables (attributes defined in WDL task's runtime)
# Use them within ${} notation.
# - cpu: number of cores for a job (default = 1)
# - memory_mb, memory_gb: total memory for a job in MB, GB
#   * these are converted from 'memory' string attribute (including size unit)
#     defined in WDL task's runtime
# - time: time limit for a job in hour
# - gpu: specified gpu name or number of gpus (it's declared as String)
"""

CONF_CONTENTS_SLURM_PARAM = """
{help_context}
slurm-resource-param={slurm_resource_param}

# If needed uncomment and define any extra SLURM sbatch parameters here
# YOU CANNOT USE WDL SYNTAX AND CROMWELL BUILT-IN VARIABLES HERE
#slurm-extra-param=
""".format(
    help_context=CONF_CONTENTS_COMMON_RESOURCE_PARAM_HELP,
    slurm_resource_param=CromwellBackendSlurm.DEFAULT_SLURM_RESOURCE_PARAM,
)

CONF_CONTENTS_SGE_PARAM = """
{help_context}
# Parallel environment of SGE:
# Find one with `$ qconf -spl` or ask you admin to add one if not exists.
# If your cluster works without PE then edit the below sge-resource-param
sge-pe=
sge-resource-param={sge_resource_param}

# If needed uncomment and define any extra SGE qsub parameters here
# YOU CANNOT USE WDL SYNTAX AND CROMWELL BUILT-IN VARIABLES HERE
#sge-extra-param=
""".format(
    help_context=CONF_CONTENTS_COMMON_RESOURCE_PARAM_HELP,
    sge_resource_param=CromwellBackendSge.DEFAULT_SGE_RESOURCE_PARAM,
)

CONF_CONTENTS_PBS_PARAM = """
{help_context}
pbs-resource-param={pbs_resource_param}

# If needed uncomment and define any extra PBS qsub parameters here
# YOU CANNOT USE WDL SYNTAX AND CROMWELL BUILT-IN VARIABLES HERE
#pbs-extra-param=
""".format(
    help_context=CONF_CONTENTS_COMMON_RESOURCE_PARAM_HELP,
    pbs_resource_param=CromwellBackendPbs.DEFAULT_PBS_RESOURCE_PARAM,
)

CONF_CONTENTS_LSF_PARAM = """
{help_context}
lsf-resource-param={lsf_resource_param}

# If needed uncomment and define any extra LSF bsub parameters here
# YOU CANNOT USE WDL SYNTAX AND CROMWELL BUILT-IN VARIABLES HERE
#lsf-extra-param=
""".format(
    help_context=CONF_CONTENTS_COMMON_RESOURCE_PARAM_HELP,
    lsf_resource_param=CromwellBackendLsf.DEFAULT_LSF_RESOURCE_PARAM,
)

DEFAULT_CONF_CONTENTS_LOCAL = (
    """
backend=local
"""
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_DB
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_SHERLOCK = (
    """
backend=slurm

# SLURM partition. Define only if required by a cluster. You must define it for Stanford Sherlock.
slurm-partition=

# IMPORTANT warning for Stanford Sherlock cluster
# ====================================================================
# DO NOT install any codes/executables/Miniconda
# (java, conda, python, caper, pipeline's WDL, pipeline's Conda env, ...) on $SCRATCH or $OAK.
# You will see Segmentation Fault errors.
# Install all executables on $HOME or $PI_HOME instead.
# It's STILL OKAY to read input data from and write outputs to $SCRATCH or $OAK.
# ====================================================================
"""
    + CONF_CONTENTS_SLURM_PARAM
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_DB
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_SCG = (
    """
backend=slurm

# SLURM account. Define only if required by a cluster. You must define it for Stanford SCG.
slurm-account=

# IMPORTANT warning for Stanford SCG cluster
# ====================================================================
# DO NOT install any codes/executables/Miniconda
# (java, conda, python, caper, pipeline's WDL, pipeline's Conda env, ...) on your home (/home/$USER).
# Pipelines will get stuck due to slow filesystem.
# ALSO DO NOT USE /local/scratch to run pipelines. This directory is not static.
# Use $OAK storage to run pipelines, and to store codes/WDLs/executables.
# ====================================================================

"""
    + CONF_CONTENTS_SLURM_PARAM
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_DB
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_SLURM = (
    """
backend=slurm

# define one of the followings (or both) according to your
# cluster's SLURM configuration.

# SLURM partition. Define only if required by a cluster. You must define it for Stanford Sherlock.
slurm-partition=
# SLURM account. Define only if required by a cluster. You must define it for Stanford SCG.
slurm-account=
"""
    + CONF_CONTENTS_SLURM_PARAM
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_DB
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_SGE = (
    """
backend=sge

# Parallel environement is required, ask your administrator to create one
# If your cluster doesn't support PE then edit 'sge-resource-param'
# to fit your cluster's configuration.
sge-pe=
"""
    + CONF_CONTENTS_SGE_PARAM
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_DB
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_PBS = (
    """
backend=pbs
"""
    + CONF_CONTENTS_PBS_PARAM
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_DB
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_LSF = (
    """
backend=lsf
"""
    + CONF_CONTENTS_LSF_PARAM
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_DB
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_AWS = (
    """
backend=aws
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
    """
backend=gcp
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

# Increase instance's memory when retrying upon OOM (out of memory) error.
gcp-memory-retry-multiplier=1.2

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
    elif backend == BACKEND_ALIAS_SHERLOCK:
        contents = DEFAULT_CONF_CONTENTS_SHERLOCK
    elif backend == BACKEND_ALIAS_SCG:
        contents = DEFAULT_CONF_CONTENTS_SCG
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
