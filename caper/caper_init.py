import os

from .cromwell import Cromwell
from .cromwell_backend import (BACKEND_ALIAS_LOCAL, BACKEND_AWS, BACKEND_GCP,
                               BACKEND_LOCAL, BACKEND_PBS, BACKEND_SGE,
                               BACKEND_SLURM)

BACKEND_ALIAS_SHERLOCK = 'sherlock'
BACKEND_ALIAS_SCG = 'scg'

CONF_CONTENTS_LOCAL_HASH_STRAT = """
# Hashing strategy for call-caching (3 choices)
# This parameter is for local (local/slurm/sge/pbs) backend only.
# This is important for re-using outputs from previous/failed workflows.
# Cache will miss if different strategy is used.
# "file" method has been default for all old versions of Caper.
# So we will keep "file" as default to be compatible with old metadata DB.
# But "path+modtime" is recommended for new users.
#   file: md5sum hash (slow).
#   path: path.
#   path+modtime: path + mtime.
local-hash-strat=file
"""

CONF_CONTENTS_TMP_DIR = """
# Temporary cache directory.
# DO NOT USE /tmp. Use local absolute path here.
# Caper stores important temporary/cached files here.
# If not defined, Caper will make .caper_tmp/ on CWD
# or your local output directory (--out-dir).
tmp-dir=
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
out-s3-bucket=
"""
    + CONF_CONTENTS_TMP_DIR
)

DEFAULT_CONF_CONTENTS_GCP = (
    """
backend=gcp
gcp-prj=
out-gcs-bucket=

# Call-cached outputs will be duplicated by making a copy or reference
#   reference: refer to old output file in metadata.json file.
#   copy: make a copy.
gcp-call-caching-dup-strat=
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
    cromwell = Cromwell()
    with open(conf_file, 'w') as fp:
        fp.write(contents + '\n')
        fp.write(
            '{key}={val}\n'.format(key='cromwell', val=cromwell.install_cromwell())
        )
        fp.write('{key}={val}\n'.format(key='womtool', val=cromwell.install_womtool()))
