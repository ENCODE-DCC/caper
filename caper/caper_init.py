import os

from .cromwell import Cromwell
from .cromwell_backend import (
    BACKEND_ALIAS_LOCAL,
    BACKEND_AWS,
    BACKEND_GCP,
    BACKEND_LOCAL,
    BACKEND_PBS,
    BACKEND_SGE,
    BACKEND_SLURM,
)

BACKEND_ALIAS_SHERLOCK = 'sherlock'
BACKEND_ALIAS_SCG = 'scg'

CONF_CONTENTS_LOCAL_HASH_STRAT = """
# Hashing strategy for call-caching (3 choices)
# This parameter is for local (local/slurm/sge/pbs) backend only.
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

DEFAULT_CONF_CONTENTS_LOCAL = (
    """
backend=local
"""
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_SHERLOCK = (
    """
backend=slurm
slurm-partition=

# IMPORTANT warning for Stanford Sherlock cluster
# ====================================================================
# DO NOT install any codes/executables
# (java, conda, python, caper, pipeline's WDL, pipeline's Conda env, ...) on $SCRATCH or $OAK.
# You will see Segmentation Fault errors.
# Install all executables on $HOME or $PI_HOME instead.
# It's STILL OKAY to read input data from and write outputs to $SCRATCH or $OAK.
# ====================================================================
"""
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_SCG = (
    """
backend=slurm
slurm-account=

"""
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_SLURM = (
    """
backend=slurm

# define one of the followings (or both) according to your
# cluster's SLURM configuration.
slurm-partition=
slurm-account=
"""
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_SGE = (
    """
backend=sge
sge-pe=
"""
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_PBS = (
    """
backend=pbs
"""
    + CONF_CONTENTS_LOCAL_HASH_STRAT
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_AWS = (
    """
backend=aws
aws-batch-arn=
aws-region=
aws-out-dir=
"""
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_GCP = (
    """
backend=gcp
gcp-prj=
gcp-out-dir=

# Call-cached outputs will be duplicated by making a copy or reference
#   reference: refer to old output file in metadata.json file.
#   copy (not recommended): make a copy for a new workflow.
gcp-call-caching-dup-strat=

# Use Google Cloud Life Sciences API instead of Genomics API (deprecating).
# Make sure to enable Google Cloud Life Sciences API on your Google Cloud Console
use-google-cloud-life-sciences=false

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
