#!/usr/bin/env python3
import logging
import sys
from autouri import AbsPath, GCSURI, S3URI, URIBase
from .caper import Caper
from .caper_args import parse_caper_arguments
from .caper_init import init_caper_conf


def init_logging(args):
    if args.get('debug'):
        log_level = 'DEBUG'
    else:
        log_level = 'INFO'
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s|%(name)s|%(levelname)s| %(message)s')
    # suppress filelock logging
    logging.getLogger('filelock').setLevel('CRITICAL')


def main():
    """CLI for Caper
    """
    # parse arguments: note that args is a dict
    args = parse_caper_arguments()

    action = args['action']
    if action == 'init':
        init_caper_conf(args)
        sys.exit(0)

    init_logging(args)

    GCSURI.init_gcsuri(
        use_gsutil_for_s3=args.get('use_gsutil_for_s3')
    )

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

    sys.exit(0)


if __name__ == '__main__':
    main()
