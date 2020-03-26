"""Functions for caper init subcommand

Author:
    Jin Lee (leepc12@gmail.com) at ENCODE-DCC
"""

import os
import sys
from autouri import AutoURI, AbsPath
from .caper_backend import BACKENDS, BACKENDS_WITH_ALIASES
from .caper_backend import BACKEND_GCP, BACKEND_AWS, BACKEND_LOCAL
from .caper_backend import BACKEND_SLURM, BACKEND_SGE, BACKEND_PBS
from .caper_backend import BACKEND_ALIAS_LOCAL
from .caper_backend import BACKEND_ALIAS_GOOGLE, BACKEND_ALIAS_AMAZON
from .caper_backend import BACKEND_ALIAS_SHERLOCK, BACKEND_ALIAS_SCG
from .caper_args import DEFAULT_CROMWELL_JAR, DEFAULT_WOMTOOL_JAR


DEFAULT_CROMWELL_JAR_INSTALL_DIR = '~/.caper/cromwell_jar'
DEFAULT_WOMTOOL_JAR_INSTALL_DIR = '~/.caper/womtool_jar'
DEFAULT_CONF_CONTENTS_LOCAL = """backend=local

# DO NOT use /tmp here
# Caper stores all important temp files and cached big data files here
# If not defined, Caper will make .caper_tmp/ on your local output directory
# which is defined by out-dir, --out-dir or $CWD
# Use a local absolute path here
tmp-dir=
"""
DEFAULT_CONF_CONTENTS_SHERLOCK = """backend=slurm
slurm-partition=

# DO NOT use /tmp here
# You can use $OAK or $SCRATCH storages here.
# Caper stores all important temp files and cached big data files here
# If not defined, Caper will make .caper_tmp/ on your local output directory
# which is defined by out-dir, --out-dir or $CWD
# Use a local absolute path here
tmp-dir=

# IMPORTANT warning for Stanford Sherlock cluster
# ====================================================================
# DO NOT install any codes/executables
# (java, conda, python, caper, pipeline's WDL, pipeline's Conda env, ...) on $SCRATCH or $OAK.
# You will see Segmentation Fault errors.
# Install all executables on $HOME or $PI_HOME instead.
# It's STILL OKAY to read input data from and write outputs to $SCRATCH or $OAK.
# ====================================================================
"""
DEFAULT_CONF_CONTENTS_SCG = """backend=slurm
slurm-account=

# DO NOT use /tmp here
# Caper stores all important temp files and cached big data files here
# If not defined, Caper will make .caper_tmp/ on your local output directory
# which is defined by out-dir, --out-dir or $CWD
# Use a local absolute path here
tmp-dir=
"""
DEFAULT_CONF_CONTENTS_SLURM = """backend=slurm

# define one of the followings (or both) according to your
# cluster's SLURM configuration.
slurm-partition=
slurm-account=

# DO NOT use /tmp here
# Caper stores all important temp files and cached big data files here
# If not defined, Caper will make .caper_tmp/ on your local output directory
# which is defined by out-dir, --out-dir or $CWD
# Use a local absolute path here
tmp-dir=
"""
DEFAULT_CONF_CONTENTS_SGE = """backend=sge
sge-pe=

# DO NOT use /tmp here
# Caper stores all important temp files and cached big data files here
# If not defined, Caper will make .caper_tmp/ on your local output directory
# which is defined by out-dir, --out-dir or $CWD
# Use a local absolute path here
tmp-dir=
"""
DEFAULT_CONF_CONTENTS_PBS = """backend=pbs

# DO NOT use /tmp here
# Caper stores all important temp files and cached big data files here
# If not defined, Caper will make .caper_tmp/ on your local output directory
# which is defined by out-dir, --out-dir or $CWD
# Use a local absolute path here
tmp-dir=
"""
DEFAULT_CONF_CONTENTS_AWS = """backend=aws
aws-batch-arn=
aws-region=
out-s3-bucket=

# DO NOT use /tmp here
# Caper stores all important temp files and cached big data files here
# If not defined, Caper will make .caper_tmp/ on your local output directory
# which is defined by out-dir, --out-dir or $CWD
# Use a local absolute path here
tmp-dir=
"""
DEFAULT_CONF_CONTENTS_GCP = """backend=gcp
gcp-prj=
out-gcs-bucket=

# call-cached outputs will be duplicated by making a copy or reference
#  reference: refer to old output file in metadata.json file.
#  copy: make a copy
gcp-call-caching-dup-strat=

# DO NOT use /tmp here
# Caper stores all important temp files and cached big data files here
# If not defined, Caper will make .caper_tmp/ on your local output directory
# which is defined by out-dir, --out-dir or $CWD
# Use a local absolute path here
tmp-dir=
"""


def install_cromwell_jar(uri):
    """Download cromwell-X.jar
    """
    u = AutoURI(uri)
    if isinstance(u, AbsPath):
        return u.uri
    print('Downloading Cromwell JAR... {f}'.format(f=uri), file=sys.stderr)
    path = os.path.join(
        os.path.expanduser(DEFAULT_CROMWELL_JAR_INSTALL_DIR),
        os.path.basename(uri))
    return u.cp(path)


def install_womtool_jar(uri):
    """Download womtool-X.jar
    """
    u = AutoURI(uri)
    if isinstance(u, AbsPath):
        return u.uri
    print('Downloading Womtool JAR... {f}'.format(f=uri), file=sys.stderr)
    path = os.path.join(
        os.path.expanduser(DEFAULT_WOMTOOL_JAR_INSTALL_DIR),
        os.path.basename(uri))
    return u.cp(path)


def init_caper_conf(args):
    """Initialize conf file for a given platform.
    Also, download/install Cromwell/Womtool JARs.
    """
    backend = args.get('platform')
    assert(backend in BACKENDS_WITH_ALIASES)
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
    elif backend in (BACKEND_GCP, BACKEND_ALIAS_GOOGLE):
        contents = DEFAULT_CONF_CONTENTS_GCP
    elif backend in (BACKEND_AWS, BACKEND_ALIAS_AMAZON):
        contents = DEFAULT_CONF_CONTENTS_AWS
    else:
        raise Exception('Unsupported platform/backend/alias.')

    conf_file = os.path.expanduser(args.get('conf'))
    with open(conf_file, 'w') as fp:
        fp.write(contents + '\n')
        fp.write('{key}={val}\n'.format(
            key='cromwell',
            val=install_cromwell_jar(DEFAULT_CROMWELL_JAR)))
        fp.write('{key}={val}\n'.format(
            key='womtool',
            val=install_womtool_jar(DEFAULT_WOMTOOL_JAR)))
