#!/usr/bin/env python3
from autouri import AbsPath, GCSURI, S3URI, URIBase
from .caper import Caper
from .caper_args import parse_caper_arguments
from .caper_check import check_caper_conf
from .caper_init import init_caper_conf
from .logger import logger


def main():
    """CLI for Caper
    """
    # parse arguments: note that args is a dict
    args = parse_caper_arguments()
    action = args['action']
    if action == 'init':
        init_caper_conf(args)
        sys.exit(0)
    args = check_caper_conf(args)

    # init Autouri classes to transfer files across various storages
    #   e.g. gs:// to s3://, http:// to local, ...
    # loc_prefix means prefix (root directory)
    # for localizing files of different storages
    AbsPath.init_abspath(
        loc_prefix=args.get('tmp_dir')
    )
    GCSURI.init_gcsuri(
        loc_prefix=args.get('tmp_gcs_bucket'),
        use_gsutil_for_s3=args.get('use_gsutil_for_s3')
    )
    S3URI.init_s3uri(
        loc_prefix=args.get('tmp_s3_bucket')
    )
    # init both loggers of Autouri and Caper
    if args.get('verbose'):
        # autouri_logger.setLevel('INFO')
        logger.setLevel('INFO')
    elif args.get('debug'):
        # autouri_logger.setLevel('DEBUG')
        logger.setLevel('DEBUG')

    c = Caper(args)
    if action == 'run':
        c.run()
    elif action == 'server':
        c.server()
    elif action == 'submit':
        c.submit()
    elif action == 'abort':
        c.abort()
    elif action == 'list':
        c.list()
    elif action == 'metadata':
        c.metadata()
    elif action == 'unhold':
        c.unhold()
    elif action in ['troubleshoot', 'debug']:
        c.troubleshoot()
    else:
        raise ValueError(
        	'Unsupported or unspecified action. act={a}'.format(a=action))
    return 0


if __name__ == '__main__':
    main()
