"""CaperCheck: Caper arguments/configuration checker

Author:
    Jin Lee (leepc12@gmail.com) at ENCODE-DCC
"""

import os
from .caper_backend import BACKENDS, BACKEND_SLURM, get_backend

DEFAULT_FILE_DB_PREFIX = 'caper_file_db'
DEFAULT_CAPER_TMP_DIR_SUFFIX = '.caper_tmp'


def check_caper_conf(args_d):
    """Check arguments/configuration for Caper
    """
    backend = args_d.get('backend')
    if backend is not None:
        backend = get_backend(backend)
    args_d['backend'] = backend

    # init some important path variables
    if args_d.get('out_dir') is None:
        args_d['out_dir'] = os.getcwd()
    else:
        args_d['out_dir'] = os.path.abspath(
            os.path.expanduser(args_d['out_dir']))

    if args_d.get('tmp_dir') is None:
        args_d['tmp_dir'] = os.path.abspath(
            os.path.join(args_d['out_dir'], DEFAULT_CAPER_TMP_DIR_SUFFIX))
    else:
        args_d['tmp_dir'] = os.path.abspath(
            os.path.expanduser(args_d['tmp_dir']))

    if args_d.get('tmp_s3_bucket') is None:
        if args_d.get('out_s3_bucket'):
            args_d['tmp_s3_bucket'] = os.path.join(args_d['out_s3_bucket'],
                                                   DEFAULT_CAPER_TMP_DIR_SUFFIX)
    if args_d.get('tmp_gcs_bucket') is None:
        if args_d.get('out_gcs_bucket'):
            args_d['tmp_gcs_bucket'] = os.path.join(args_d['out_gcs_bucket'],
                                                    DEFAULT_CAPER_TMP_DIR_SUFFIX)

    return args_d
