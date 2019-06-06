#!/usr/bin/env python3
"""CaperArgs: Command line arguments parser for Caper

Author:
    Jin Lee (leepc12@gmail.com) at ENCODE-DCC
"""

import argparse
from configparser import ConfigParser
import sys
import os
from distutils.util import strtobool


DEFAULT_CAPER_CONF = '~/.caper/default.conf'
DEFAULT_FILE_DB = '~/.caper/default_file_db'
DEFAULT_SINGULARITY_CACHEDIR = '~/.caper/singularity_cachedir'
DEFAULT_CROMWELL_JAR = 'https://github.com/broadinstitute/cromwell/releases/download/40/cromwell-40.jar'
DEFAULT_MYSQL_DB_IP = 'localhost'
DEFAULT_MYSQL_DB_PORT = 3306
DEFAULT_MAX_CONCURRENT_WORKFLOWS = 40
DEFAULT_MAX_CONCURRENT_TASKS = 1000
DEFAULT_PORT = 8000
DEFAULT_IP = 'localhost'
DEFAULT_FORMAT = 'id,status,name,str_label,submission'
DEFAULT_DEEPCOPY_EXT = 'json,tsv'
DEFAULT_CAPER_CONF_CONTENTS = """[defaults]

############# Caper settings

## default backend
#backend=local

## Put a hold on submitted jobs.
## You need to run "caper unhold [WORKFLOW_ID]" to release hold
#hold=True

### Workflow settings
## deepcopy recursively all file URIs in a file URI
##  with supported extensions (json,tsv,csv)
##  to a target remote/local storage
#deepcopy=True
#deepcopy-ext=json,tsv

############# local backend
## Singularity image will be pulled to this directory
## if you don't specify this, then Singularity will pull image
## from remote repo everytime for each task.
## to prevent this overhead DEFINE IT
## user's scratch is recommended
#singularity-cachedir=~/.caper/singularity_cachedir

## local singularity image will not be built before running
## a workflow. this can result in conflicts between tasks
## trying to write on the same image file.
#no-build-singularity=True

## actual workflow outputs will be written to
## out-dir/[WDL_NAME]/[WORKFLOW_ID]/
#out-dir=

## all temporary files (including deepcopied data files,
## cromwell.jar, backend conf, worflow_opts JSONs, ...)
## will be written to this directory
## DON'T USE /tmp. User's scratch directory is recommended
#tmp-dir=

############# Google Cloud Platform backend
#gcp-prj=encode-dcc-1016
#out-gcs-bucket=gs://encode-pipeline-test-runs/caper/out
#tmp-gcs-bucket=gs://encode-pipeline-test-runs/caper/tmp

############# AWS backend
#aws-batch-arn=
#aws-region=us-west-1
#out-s3-bucket=s3://encode-pipeline-test-runs/caper/out
#tmp-s3-bucket=s3://encode-pipeline-test-runs/caper/tmp

## gsutil can work with s3 buckets it outperforms over aws s3 CLI
#use-gsutil-over-aws-s3=True

############# HTTP auth to download from URLs (http://, https://)
#http-user=
#http-password=

############# Cromwell's built-in HyperSQL database settings
## DB file prefix path
#file-db=~/.caper/default_file_db

## disable file-db
## Detach DB from Cromwell
## you can run multiple workflows with 'caper run' command
## but Caper will not be able re-use outputs from previous workflows
#no-file-db=True

############# MySQL database settings
## both caper run/server modes will attach to MySQL db
## uncomment/define all of the followings to use MySQL database
#mysql-db-ip=
#mysql-db-port=
#mysql-db-user=cromwell
#mysql-db-password=cromwell

############# Cromwell general settings
#cromwell=https://github.com/broadinstitute/cromwell/releases/download/40/cromwell-40.jar
#max-concurrent-tasks=1000
#max-concurrent-workflows=40
#disable-call-caching=False
#backend-file=

## Cromwell server
#ip=localhost
#port=8000

############# SLURM backend
#slurm-partition=akundaje
#slurm-account=akundaje
#slurm-extra-param=

############# SGE backend
#sge-queue=q
#sge-pe=shm
#sge-extra-param=

############# PBS backend
#pbs-queue=q
#pbs-extra-param=

## list workflow format
#format=id,status,name,str_label,submission

"""


def parse_caper_arguments():
    """Argument parser for Caper
    """
    # write default conf file if not exists
    default_caper_conf = os.path.expanduser(DEFAULT_CAPER_CONF)
    if not os.path.exists(default_caper_conf):
        os.makedirs(os.path.dirname(default_caper_conf), exist_ok=True)
        with open(default_caper_conf, 'w') as fp:
            fp.write(DEFAULT_CAPER_CONF_CONTENTS)

    conf_parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    conf_parser.add_argument('-c', '--conf', help='Specify config file',
                             metavar='FILE',
                             default=DEFAULT_CAPER_CONF)
    known_args, remaining_argv = conf_parser.parse_known_args()

    # read conf file if it exists
    defaults = {}

    if known_args.conf is not None:
        # resolve tilde (~) in conf path
        known_args.conf = os.path.expanduser(known_args.conf)
        if os.path.exists(known_args.conf):
            config = ConfigParser()
            config.read([known_args.conf])
            d = dict(config.items("defaults"))
            # replace - with _
            defaults.update({k.replace('-', '_'): v for k, v in d.items()})

    parser = argparse.ArgumentParser(parents=[conf_parser])
    subparser = parser.add_subparsers(dest='action')

    # run, server, submit
    parent_backend = argparse.ArgumentParser(add_help=False)
    parent_backend.add_argument(
        '-b', '--backend', help='Backend to run a workflow')

    # run, server
    parent_host = argparse.ArgumentParser(add_help=False)

    group_mysql = parent_host.add_argument_group(
        title='MySQL arguments')
    group_mysql.add_argument(
        '--mysql-db-ip', default=DEFAULT_MYSQL_DB_IP,
        help='MySQL Database IP address (e.g. localhost)')
    group_mysql.add_argument(
        '--mysql-db-port', default=DEFAULT_MYSQL_DB_PORT,
        help='MySQL Database TCP/IP port (e.g. 3306)')
    group_mysql.add_argument(
        '--mysql-db-user', help='MySQL Database username')
    group_mysql.add_argument(
        '--mysql-db-password', help='MySQL Database password')

    group_cromwell = parent_host.add_argument_group(
        title='Cromwell settings')
    group_cromwell.add_argument(
        '--cromwell', default=DEFAULT_CROMWELL_JAR,
        help='Path or URL for Cromwell JAR file')
    group_cromwell.add_argument(
        '--max-concurrent-tasks', default=DEFAULT_MAX_CONCURRENT_TASKS,
        type=int,
        help='Number of concurrent tasks. '
             '"config.concurrent-job-limit" in Cromwell backend configuration '
             'for each backend')
    group_cromwell.add_argument(
        '--max-concurrent-workflows', default=DEFAULT_MAX_CONCURRENT_WORKFLOWS,
        type=int,
        help='Number of concurrent workflows. '
             '"system.max-concurrent-workflows" in backend configuration')
    group_cromwell.add_argument(
        '--disable-call-caching', action='store_true',
        help='Disable Cromwell\'s call caching, which re-uses outputs from '
             'previous workflows')
    group_cromwell.add_argument(
        '--backend-file',
        help='Custom Cromwell backend configuration file to override all')

    group_local = parent_host.add_argument_group(
        title='local backend arguments')
    group_local.add_argument(
        '--out-dir', default='.', help='Output directory for local backend')
    group_local.add_argument(
        '--tmp-dir', help='Temporary directory for local backend')

    group_gc = parent_host.add_argument_group(
        title='GC backend arguments')
    group_gc.add_argument('--gcp-prj', help='GC project')
    group_gc.add_argument(
        '--out-gcs-bucket', help='Output GCS bucket for GC backend')
    group_gc.add_argument(
        '--tmp-gcs-bucket', help='Temporary GCS bucket for GC backend')

    group_aws = parent_host.add_argument_group(
        title='AWS backend arguments')
    group_aws.add_argument('--aws-batch-arn', help='ARN for AWS Batch')
    group_aws.add_argument('--aws-region', help='AWS region (e.g. us-west-1)')
    group_aws.add_argument(
        '--out-s3-bucket', help='Output S3 bucket for AWS backend')
    group_aws.add_argument(
        '--tmp-s3-bucket', help='Temporary S3 bucket for AWS backend')
    group_aws.add_argument(
        '--use-gsutil-over-aws-s3', action='store_true',
        help='Use gsutil instead of aws s3 CLI even for S3 buckets.')

    group_http = parent_host.add_argument_group(
        title='HTTP/HTTPS authentication arguments')
    group_http.add_argument(
        '--http-user',
        help='Username to directly download data from URLs')
    group_http.add_argument(
        '--http-password',
        help='Password to directly download data from URLs')

    # run, submit
    parent_submit = argparse.ArgumentParser(add_help=False)

    parent_submit.add_argument(
        'wdl',
        help='Path, URL or URI for WDL script '
             'Example: /scratch/my.wdl, gs://some/where/our.wdl, '
             'http://hello.com/world/your.wdl')
    parent_submit.add_argument(
        '-i', '--inputs', help='Workflow inputs JSON file')
    parent_submit.add_argument(
        '-o', '--options', help='Workflow options JSON file')
    parent_submit.add_argument(
        '-l', '--labels',
        help='Workflow labels JSON file')
    parent_submit.add_argument(
        '-p', '--imports',
        help='Zip file of imported subworkflows')
    parent_submit.add_argument(
        '-s', '--str-label',
        help='Caper\'s special label for a workflow '
             'This label will be added to a workflow labels JSON file '
             'as a value for a key "caper-label". '
             'DO NOT USE IRREGULAR CHARACTERS. USE LETTERS, NUMBERS, '
             'DASHES AND UNDERSCORES ONLY (^[A-Za-z0-9\\-\\_]+$) '
             'since this label is used to compose a path for '
             'workflow\'s temporary directory (tmp_dir/label/timestamp/)')
    parent_submit.add_argument(
        '--hold', action='store_true',
        help='Put a hold on a workflow when submitted to a Cromwell server.')
    parent_submit.add_argument(
        '--singularity-cachedir', default=DEFAULT_SINGULARITY_CACHEDIR,
        help='Singularity cache directory. Equivalent to exporting an '
             'environment variable SINGULARITY_CACHEDIR. '
             'Define it to prevent repeatedly building a singularity image '
             'for every pipeline task')
    parent_submit.add_argument(
        '--file-db', default=DEFAULT_FILE_DB,
        help='Default DB file for Cromwell\'s built-in HyperSQL database.')
    parent_submit.add_argument(
        '--no-file-db', action='store_true',
        help='Disable file DB for Cromwell\'s built-in HyperSQL database. '
             'An in-memory DB will still be available for server mode.')

    # run
    parent_run = argparse.ArgumentParser(add_help=False)
    parent_run.add_argument(
        '-m', '--metadata-output',
        help='An optional directory path to output metadata JSON file')

    parent_submit.add_argument(
        '--deepcopy', action='store_true',
        help='Deepcopy for JSON (.json), TSV (.tsv) and CSV (.csv) '
             'files specified in an input JSON file (--inputs). '
             'Find all path/URI string values in an input JSON file '
             'and make copies of files on a local/remote storage '
             'for a target backend. Make sure that you have installed '
             'gsutil for GCS and aws for S3.')
    parent_submit.add_argument(
        '--deepcopy-ext', default=DEFAULT_DEEPCOPY_EXT,
        help='Comma-separated list of file extensions to be deepcopied')

    group_dep = parent_submit.add_argument_group(
        title='dependency resolver for all backends',
        description=''
        'Cloud-based backends (gc and aws) will only use Docker '
        'so that "--docker URI_FOR_DOCKER_IMG" must be specified '
        'in the command line argument or as a comment "#CAPER '
        'docker URI_FOR_DOCKER_IMG" in a WDL file')
    group_dep.add_argument(
        '--docker', help='URI for Docker image (e.g. ubuntu:latest). '
        'Defining it automatically turn on flag "--use-docker"')
    group_dep.add_argument(
        '--use-docker', action='store_true',
        help='Use Singularity to resolve dependency for local backend.')
    group_dep_local = parent_submit.add_argument_group(
        title='dependency resolver for local backend',
        description=''
        'Singularity is for local backend only. Other backends '
        '(gcp and aws) will use Docker only. '
        'Local backend defaults to not use any container-based methods. '
        'Activate "--use-singularity" or "--use-docker" to use containers')
    group_dep_local.add_argument(
        '--singularity',
        help='URI or path for Singularity image '
             '(e.g. ~/.singularity/ubuntu-latest.simg, '
             'docker://ubuntu:latest, shub://vsoch/hello-world). '
             'Defining it automatically turn on flag "--use-singularity"')
    group_dep_local.add_argument(
        '--use-singularity', action='store_true',
        help='Use Singularity to resolve dependency for local backend.')
    group_dep_local.add_argument(
        '--no-build-singularity', action='store_true',
        help='Do not build singularity image before running a workflow. ')

    group_slurm = parent_submit.add_argument_group('SLURM arguments')
    group_slurm.add_argument('--slurm-partition', help='SLURM partition')
    group_slurm.add_argument('--slurm-account', help='SLURM account')
    group_slurm.add_argument(
        '--slurm-extra-param',
        help='SLURM extra parameters. Must be double-quoted')

    group_sge = parent_submit.add_argument_group('SGE arguments')
    group_sge.add_argument(
        '--sge-pe', help='SGE parallel environment. Check with "qconf -spl"')
    group_sge.add_argument(
        '--sge-queue', help='SGE queue. Check with "qconf -sql"')
    group_sge.add_argument(
        '--sge-extra-param',
        help='SGE extra parameters. Must be double-quoted')

    group_pbs = parent_submit.add_argument_group('PBS arguments')
    group_pbs.add_argument(
        '--pbs-queue', help='PBS queue')
    group_pbs.add_argument(
        '--pbs-extra-param',
        help='PBS extra parameters. Must be double-quoted')

    # list, metadata, abort
    parent_search_wf = argparse.ArgumentParser(add_help=False)
    parent_search_wf.add_argument(
        'wf_id_or_label', nargs='*',
        help='List of workflow IDs to find matching workflows to '
             'commit a specified action (list, metadata and abort). '
             'Wildcards (* and ?) are allowed.')

    parent_server_client = argparse.ArgumentParser(add_help=False)
    parent_server_client.add_argument(
        '--port', default=DEFAULT_PORT,
        help='Port for Caper server')
    parent_client = argparse.ArgumentParser(add_help=False)
    parent_client.add_argument(
        '--ip', default=DEFAULT_IP,
        help='IP address for Caper server')
    parent_list = argparse.ArgumentParser(add_help=False)
    parent_list.add_argument(
        '-f', '--format', default=DEFAULT_FORMAT,
        help='Comma-separated list of items to be shown for "list" '
        'subcommand. Any key name in workflow JSON from Cromwell '
        'server\'s response is allowed. '
        'Available keys are "id" (workflow ID), "status", "str_label", '
        '"name" (WDL/CWL name), "submission" (date/time), "start", "end". '
        '"str_label" is a special key for Caper. See help context '
        'of "--str-label" for details')

    p_run = subparser.add_parser(
        'run', help='Run a single workflow without server',
        parents=[parent_submit, parent_run, parent_host, parent_backend])
    p_server = subparser.add_parser(
        'server', help='Run a Cromwell server',
        parents=[parent_server_client, parent_host, parent_backend])
    p_submit = subparser.add_parser(
        'submit', help='Submit a workflow to a Cromwell server',
        parents=[parent_server_client, parent_client, parent_submit,
                 parent_backend])
    p_abort = subparser.add_parser(
        'abort', help='Abort running/pending workflows on a Cromwell server',
        parents=[parent_server_client, parent_client, parent_search_wf])
    p_unhold = subparser.add_parser(
        'unhold', help='Release hold of workflows on a Cromwell server',
        parents=[parent_server_client, parent_client, parent_search_wf])
    p_list = subparser.add_parser(
        'list', help='List running/pending workflows on a Cromwell server',
        parents=[parent_server_client, parent_client, parent_search_wf,
                 parent_list])
    p_metadata = subparser.add_parser(
        'metadata',
        help='Retrieve metadata JSON for workflows from a Cromwell server',
        parents=[parent_server_client, parent_client, parent_search_wf])
    p_troubleshoot = subparser.add_parser(
        'troubleshoot',
        help='Troubleshoot workflow problems from metadata JSON file or '
             'workflow IDs',
        parents=[parent_server_client, parent_client, parent_search_wf])

    for p in [p_run, p_server, p_submit, p_abort, p_unhold, p_list,
              p_metadata, p_troubleshoot]:
        p.set_defaults(**defaults)

    if len(sys.argv[1:]) == 0:
        parser.print_help()
        parser.exit()
    # parse all args
    args = parser.parse_args(remaining_argv)

    # convert to dict
    args_d = vars(args)

    # boolean string to boolean
    disable_call_caching = args_d.get('disable_call_caching')
    if disable_call_caching is not None \
            and isinstance(disable_call_caching, str):
        args_d['disable_call_caching'] = \
            bool(strtobool(disable_call_caching))

    use_gsutil_over_aws_s3 = args_d.get('use_gsutil_over_aws_s3')
    if use_gsutil_over_aws_s3 is not None \
            and isinstance(use_gsutil_over_aws_s3, str):
        args_d['use_gsutil_over_aws_s3'] = \
            bool(strtobool(use_gsutil_over_aws_s3))

    hold = args_d.get('hold')
    if hold is not None and isinstance(hold, str):
        args_d['hold'] = bool(strtobool(hold))

    deepcopy = args_d.get('deepcopy')
    if deepcopy is not None and isinstance(deepcopy, str):
        args_d['deepcopy'] = bool(strtobool(deepcopy))

    use_docker = args_d.get('use_docker')
    if use_docker is not None and isinstance(use_docker, str):
        args_d['use_docker'] = bool(strtobool(use_docker))

    use_singularity = args_d.get('use_singularity')
    if use_singularity is not None and isinstance(use_singularity, str):
        args_d['use_singularity'] = bool(strtobool(use_singularity))

    no_build_singularity = args_d.get('no_build_singularity')
    if no_build_singularity is not None \
            and isinstance(no_build_singularity, str):
        args_d['no_build_singularity'] = bool(strtobool(no_build_singularity))

    no_file_db = args_d.get('no_file_db')
    if no_file_db is not None and isinstance(no_file_db, str):
        args_d['no_file_db'] = bool(strtobool(no_file_db))

    # int string to int
    max_concurrent_tasks = args_d.get('max_concurrent_tasks')
    if max_concurrent_tasks is not None \
            and isinstance(max_concurrent_tasks, str):
        args_d['max_concurrent_tasks'] = int(max_concurrent_tasks)

    max_concurrent_workflows = args_d.get('max_concurrent_workflows')
    if max_concurrent_workflows is not None \
            and isinstance(max_concurrent_workflows, str):
        args_d['max_concurrent_workflows'] = int(max_concurrent_workflows)

    # init some important path variables
    if args_d.get('out_dir') is None:
        args_d['out_dir'] = os.getcwd()

    if args_d.get('tmp_dir') is None:
        args_d['tmp_dir'] = os.path.join(args_d['out_dir'], 'caper_tmp')

    if args_d.get('tmp_s3_bucket') is None:
        if args_d.get('out_s3_bucket'):
            args_d['tmp_s3_bucket'] = os.path.join(args_d['out_s3_bucket'],
                                                   'caper_tmp')
    if args_d.get('tmp_gcs_bucket') is None:
        if args_d.get('out_gcs_bucket'):
            args_d['tmp_gcs_bucket'] = os.path.join(args_d['out_gcs_bucket'],
                                                    'caper_tmp')
    file_db = args_d.get('file_db')
    if file_db is not None:
        file_db = os.path.abspath(os.path.expanduser(file_db))
        args_d['file_db'] = file_db

    singularity_cachedir = args_d.get('singularity_cachedir')
    if singularity_cachedir is not None:
        singularity_cachedir = os.path.abspath(
            os.path.expanduser(singularity_cachedir))
        args_d['singularity_cachedir'] = singularity_cachedir
        os.makedirs(singularity_cachedir, exist_ok=True)

    return args_d
