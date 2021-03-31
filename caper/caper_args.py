import argparse
import os
from enum import Enum

from autouri import URIBase

from .arg_tool import update_parsers_defaults_with_conf
from .backward_compatibility import PARAM_KEY_NAME_CHANGE
from .caper_workflow_opts import CaperWorkflowOpts
from .cromwell import Cromwell
from .cromwell_backend import (
    CromwellBackendBase,
    CromwellBackendCommon,
    CromwellBackendDatabase,
    CromwellBackendGCP,
    CromwellBackendLocal,
)
from .cromwell_rest_api import CromwellRestAPI
from .resource_analysis import ResourceAnalysis
from .server_heartbeat import ServerHeartbeat
from .singularity import Singularity

DEFAULT_CAPER_CONF = '~/.caper/default.conf'
DEFAULT_LIST_FORMAT = 'id,status,name,str_label,user,parent,submission'
DEFAULT_OUT_DIR = '.'
DEFAULT_CROMWELL_STDOUT = './cromwell.out'


class ResourceAnalysisReductionMethod(Enum):
    sum = sum
    max = max
    min = min
    none = None


def get_defaults(conf_file=None):
    """Wrapper for `get_parser_and_defaults()`.
    Use this function to get default values updated with `conf_file`.

    Args:
        conf_file:
            `DEFAULT_CAPER_CONF` will be used if it is None.

    Returns updated defaults only.
    """
    _, conf_dict = get_parser_and_defaults(conf_file=conf_file)
    return conf_dict


def get_parser_and_defaults(conf_file=None):
    """Creates a main parser and make a subparser for each subcommand.
    There are many parent parsers defined here.
    Each subparser will take a certain combination of these parent parsers
    to share the same parameter arguments between subcommands.
    e.g. subcommand run and server share the same --cromwell argument, which
    is defined in a parent parser "parent_runner".

    Finally each subparser's default is updated with values defined in conf_file.

    Args:
        conf_file:
            If defined, this will be used instead of partially parsing command line
            arguments to find conf_file (-c).
            `DEFAULT_CAPER_CONF` will be used if it is None.
    Returns:
        parser:
            ArgumentParser object with all arguments defined for each sub-
            command (subparser).
        conf_dict:
            Dict of key/value pairs parsed from conf_file.
            Such value is converted into a correct type guessed from
            defaults of arguments defined in ArgumentParser object.
    """
    parser = argparse.ArgumentParser(
        description='Caper (Cromwell-assisted Pipeline ExecutioneR)'
    )
    parser.add_argument('-v', '--version', action='store_true', help='Show version')

    subparser = parser.add_subparsers(dest='action')

    parent_init = argparse.ArgumentParser(add_help=False)
    parent_init.add_argument('platform', help='Platform to initialize Caper for.')

    # all
    parent_all = argparse.ArgumentParser(add_help=False)
    parent_all.add_argument(
        '-c', '--conf', help='Specify config file', default=DEFAULT_CAPER_CONF
    )
    parent_all.add_argument(
        '-D', '--debug', action='store_true', help='Prints all logs >= DEBUG level'
    )
    parent_all.add_argument(
        '--gcp-service-account-key-json',
        help='Secret key JSON file for Google Cloud Platform service account. '
        'This service account should have enough permission to '
        'Storage for client functions and '
        'Storage/Compute Engine/Genomics API/Life Sciences API '
        'for server/runner functions.',
    )

    group_loc = parent_all.add_argument_group(
        title='cache directories for localization'
    )
    group_loc.add_argument(
        '--local-loc-dir',
        '--tmp-dir',
        help='Temporary directory to store Cromwell\'s intermediate backend files. '
        'These files include backend.conf, workflow_opts.json, imports.zip. and '
        'localized input JSON files due to deepcopying (recursive localization). '
        'Cromwell\'s MySQL/PostgreSQL DB password can be exposed on backend.conf '
        'on this directory. Therefore, DO NOT USE /tmp HERE. This directory is '
        'also used for storing cached files for local/slurm/sge/pbs backends.',
    )
    group_loc.add_argument(
        '--gcp-loc-dir',
        '--tmp-gcs-bucket',
        help='Temporary directory to store cached files for gcp backend. '
        'e.g. gs://my-bucket/caper-cache-dir. ',
    )
    group_loc.add_argument(
        '--aws-loc-dir',
        '--tmp-s3-bucket',
        help='Temporary directory to store cached files for aws backend. '
        'e.g. s3://my-bucket/caper-cache-dir. ',
    )

    # run, server, submit
    parent_backend = argparse.ArgumentParser(add_help=False)
    parent_backend.add_argument('-b', '--backend', help='Backend to run a workflow')
    parent_backend.add_argument(
        '--dry-run',
        action='store_true',
        help='Caper localizes remote files and validates WDL '
        'but does not run/submit a pipeline.',
    )

    # run, server
    parent_runner = argparse.ArgumentParser(add_help=False)

    parent_runner = parent_runner.add_argument_group(title='Cromwell logging arguments')
    parent_runner.add_argument(
        '--cromwell-stdout',
        default=DEFAULT_CROMWELL_STDOUT,
        help='Local file to write STDOUT of Cromwell Java process to. '
        'This is for Cromwell (not for Caper\'s logging system).',
    )
    group_db = parent_runner.add_argument_group(
        title='General DB settings (for both file DB and MySQL DB)'
    )
    group_db.add_argument(
        '--db',
        default=CromwellBackendDatabase.DEFAULT_DB,
        help='Cromwell metadata database type',
    )
    group_db.add_argument(
        '--db-timeout',
        type=int,
        default=CromwellBackendDatabase.DEFAULT_DB_TIMEOUT_MS,
        help='Milliseconds to wait for DB connection.',
    )

    group_file_db = parent_runner.add_argument_group(
        title='HyperSQL file DB arguments (unstable, not recommended)'
    )
    group_file_db.add_argument(
        '--file-db',
        '-d',
        help='Default DB file for Cromwell\'s built-in HyperSQL database.',
    )

    group_mysql = parent_runner.add_argument_group(title='MySQL DB arguments')
    group_mysql.add_argument(
        '--mysql-db-ip',
        default=CromwellBackendDatabase.DEFAULT_MYSQL_DB_IP,
        help='MySQL Database IP address (e.g. localhost)',
    )
    group_mysql.add_argument(
        '--mysql-db-port',
        type=int,
        default=CromwellBackendDatabase.DEFAULT_MYSQL_DB_PORT,
        help='MySQL Database TCP/IP port (e.g. 3306)',
    )
    group_mysql.add_argument(
        '--mysql-db-user',
        default=CromwellBackendDatabase.DEFAULT_MYSQL_DB_USER,
        help='MySQL DB username',
    )
    group_mysql.add_argument(
        '--mysql-db-password',
        default=CromwellBackendDatabase.DEFAULT_MYSQL_DB_PASSWORD,
        help='MySQL DB password',
    )
    group_mysql.add_argument(
        '--mysql-db-name',
        default=CromwellBackendDatabase.DEFAULT_MYSQL_DB_NAME,
        help='MySQL DB name for Cromwell',
    )

    group_postgresql = parent_runner.add_argument_group(title='PostgreSQL DB arguments')
    group_postgresql.add_argument(
        '--postgresql-db-ip',
        default=CromwellBackendDatabase.DEFAULT_POSTGRESQL_DB_IP,
        help='PostgreSQL DB IP address (e.g. localhost)',
    )
    group_postgresql.add_argument(
        '--postgresql-db-port',
        type=int,
        default=CromwellBackendDatabase.DEFAULT_POSTGRESQL_DB_PORT,
        help='PostgreSQL DB TCP/IP port (e.g. 5432)',
    )
    group_postgresql.add_argument(
        '--postgresql-db-user',
        default=CromwellBackendDatabase.DEFAULT_POSTGRESQL_DB_USER,
        help='PostgreSQL DB username',
    )
    group_postgresql.add_argument(
        '--postgresql-db-password',
        default=CromwellBackendDatabase.DEFAULT_POSTGRESQL_DB_PASSWORD,
        help='PostgreSQL DB password',
    )
    group_postgresql.add_argument(
        '--postgresql-db-name',
        default=CromwellBackendDatabase.DEFAULT_POSTGRESQL_DB_NAME,
        help='PostgreSQL DB name for Cromwell',
    )

    group_cromwell = parent_runner.add_argument_group(title='Cromwell settings')
    group_cromwell.add_argument(
        '--cromwell',
        default=Cromwell.DEFAULT_CROMWELL,
        help='Path or URL for Cromwell JAR file',
    )
    group_cromwell.add_argument(
        '--max-concurrent-tasks',
        type=int,
        default=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        help='Number of concurrent tasks. '
        '"config.concurrent-job-limit" in Cromwell backend configuration '
        'for each backend',
    )
    group_cromwell.add_argument(
        '--max-concurrent-workflows',
        type=int,
        default=CromwellBackendCommon.DEFAULT_MAX_CONCURRENT_WORKFLOWS,
        help='Number of concurrent workflows. '
        '"system.max-concurrent-workflows" in backend configuration',
    )
    group_cromwell.add_argument(
        '--memory-retry-error-keys',
        default=','.join(CromwellBackendCommon.DEFAULT_MEMORY_RETRY_ERROR_KEYS),
        help='(CURRENTLY NOT WORKING) '
        'If an error caught by these comma-separated keys occurs, '
        'then increase memory by --memory-retry-multiplier '
        'for retrials controlled by --max-retries. '
        'See https://cromwell.readthedocs.io/en/develop/cromwell_features/RetryWithMoreMemory/ '
        'for details. ',
    )
    group_cromwell.add_argument(
        '--disable-call-caching',
        action='store_true',
        help='Disable Cromwell\'s call caching, which re-uses outputs from '
        'previous workflows',
    )
    group_cromwell.add_argument(
        '--backend-file',
        help='Custom Cromwell backend configuration file to override all',
    )
    group_cromwell.add_argument(
        '--soft-glob-output',
        action='store_true',
        help='Use soft-linking when globbing outputs for a filesystem that '
        'does not allow hard-linking. e.g. beeGFS. '
        'This flag does not work with backends based on a Docker container. '
        'i.e. gcp and aws. Also, '
        'it does not work with local backends (local/slurm/sge/pbs) '
        'with --. However, it works fine with --singularity.',
    )
    group_cromwell.add_argument(
        '--local-hash-strat',
        default=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        choices=[
            CromwellBackendLocal.LOCAL_HASH_STRAT_FILE,
            CromwellBackendLocal.LOCAL_HASH_STRAT_PATH,
            CromwellBackendLocal.LOCAL_HASH_STRAT_PATH_MTIME,
        ],
        help='File hashing strategy for call caching. '
        'For local backends (local/slurm/sge/pbs) only. '
        'file: use md5sum hash (slow), path: use path only, '
        'path+modtime (default): use path + mtime.',
    )

    group_local = parent_runner.add_argument_group(title='local backend arguments')
    group_local.add_argument(
        '--local-out-dir',
        '--out-dir',
        default=DEFAULT_OUT_DIR,
        help='Output directory path for local backend. '
        'Cloud backends (gcp, aws) use different output directories. '
        'For gcp, define --gcp-out-dir. '
        'For aws, define --aws-out-dir.',
    )

    group_gc_all = parent_backend.add_argument_group(
        title='GCP backend arguments for server/runner/client'
    )
    group_gc = parent_runner.add_argument_group(
        title='GCP backend arguments for server/runner'
    )
    group_gc.add_argument('--gcp-prj', help='GC project')
    group_gc_all.add_argument(
        '--use-google-cloud-life-sciences',
        action='store_true',
        help='Use Google Cloud Life Sciences API (v2beta) instead of '
        'deprecated Genomics API (v2alpha1).'
        'Life Sciences API requires only one region specified with'
        'gcp-region. gcp-zones will be ignored since it is for Genomics API.'
        'See https://cloud.google.com/life-sciences/docs/concepts/locations '
        'for supported regions.',
    )
    group_gc.add_argument(
        '--gcp-region',
        default=CromwellBackendGCP.DEFAULT_REGION,
        help='GCP region for Google Cloud Life Sciences API. '
        'This is used only when --use-google-cloud-life-sciences is defined.',
    )
    group_gc_all.add_argument(
        '--gcp-zones',
        help='Comma-separated GCP zones used for Genomics API. '
        '(e.g. us-west1-b,us-central1-b). '
        'If you use --use-google-cloud-life-sciences then '
        'define --gcp-region instead.',
    )
    group_gc.add_argument(
        '--gcp-call-caching-dup-strat',
        default=CromwellBackendGCP.DEFAULT_GCP_CALL_CACHING_DUP_STRAT,
        choices=[
            CromwellBackendGCP.CALL_CACHING_DUP_STRAT_REFERENCE,
            CromwellBackendGCP.CALL_CACHING_DUP_STRAT_REFERENCE,
        ],
        help='Duplication strategy for call-cached outputs for GCP backend: '
        'copy: make a copy, reference: refer to old output in metadata.json.',
    )
    group_gc.add_argument(
        '--gcp-out-dir',
        '--out-gcs-bucket',
        help='Output directory path for GCP backend. ' 'e.g. gs://my-bucket/my-output.',
    )

    group_aws = parent_runner.add_argument_group(title='AWS backend arguments')
    group_aws.add_argument('--aws-batch-arn', help='ARN for AWS Batch')
    group_aws.add_argument('--aws-region', help='AWS region (e.g. us-west-1)')
    group_aws.add_argument(
        '--aws-out-dir',
        '--out-s3-bucket',
        help='Output path on S3 bucket for AWS backend. '
        'e.g. s3://my-bucket/my-output.',
    )

    # run, submit
    parent_submit = argparse.ArgumentParser(add_help=False)

    parent_submit.add_argument(
        'wdl',
        help='Path, URL or URI for WDL script '
        'Example: /scratch/my.wdl, gs://some/where/our.wdl, '
        'http://hello.com/world/your.wdl',
    )
    parent_submit.add_argument('-i', '--inputs', help='Workflow inputs JSON file')
    parent_submit.add_argument('-o', '--options', help='Workflow options JSON file')
    parent_submit.add_argument('-l', '--labels', help='Workflow labels JSON file')
    parent_submit.add_argument(
        '-p', '--imports', help='Zip file of imported subworkflows'
    )
    parent_submit.add_argument(
        '-s',
        '--str-label',
        help='Caper\'s special label for a workflow '
        'This label will be added to a workflow labels JSON file '
        'as a value for a key "caper-label". '
        'DO NOT USE IRREGULAR CHARACTERS. USE LETTERS, NUMBERS, '
        'DASHES AND UNDERSCORES ONLY (^[A-Za-z0-9\\-\\_]+$) '
        'since this label is used to compose a path for '
        'workflow\'s temporary/cache directory (.caper_tmp/label/timestamp/)',
    )
    parent_submit.add_argument(
        '--hold',
        action='store_true',
        help='Put a hold on a workflow when submitted to a Cromwell server.',
    )
    parent_submit.add_argument(
        '--singularity-cachedir',
        default=Singularity.DEFAULT_SINGULARITY_CACHEDIR,
        help='Singularity cache directory. Equivalent to exporting an '
        'environment variable SINGULARITY_CACHEDIR. '
        'Define it to prevent repeatedly building a singularity image '
        'for every pipeline task',
    )
    parent_submit.add_argument(
        '--use-gsutil-for-s3',
        action='store_true',
        help='Use gsutil CLI for direct trasnfer between S3 and GCS buckets. '
        'Otherwise, such file transfer will stream through local machine. '
        'Make sure that gsutil is installed on your system and it has access to '
        'credentials for AWS (e.g. ~/.boto or ~/.aws/credentials).',
    )
    parent_submit.add_argument(
        '--no-deepcopy',
        action='store_true',
        help='(IMPORTANT) --deepcopy has been deprecated. '
        'Deepcopying is now activated by default. '
        'This flag disables deepcopy for '
        'JSON (.json), TSV (.tsv) and CSV (.csv) '
        'files specified in an input JSON file (--inputs). '
        'Find all path/URI string values in an input JSON file '
        'and make copies of files on a local/remote storage '
        'for a target backend. Make sure that you have installed '
        'gsutil for GCS and aws for S3.',
    )
    parent_submit.add_argument(
        '--ignore-womtool',
        action='store_true',
        help='Ignore warnings from womtool.jar.',
    )
    parent_submit.add_argument(
        '--womtool',
        default=Cromwell.DEFAULT_WOMTOOL,
        help='Path or URL for Cromwell\'s womtool JAR file',
    )
    parent_submit.add_argument(
        '--java-heap-womtool',
        default=Cromwell.DEFAULT_JAVA_HEAP_WOMTOOL,
        help='Java heap size for Womtool (java -Xmx)',
    )
    parent_submit.add_argument(
        '--max-retries',
        type=int,
        default=CaperWorkflowOpts.DEFAULT_MAX_RETRIES,
        help='Number of retries for failing tasks. '
        'equivalent to "maxRetries" in workflow options JSON file.',
    )
    parent_submit.add_argument(
        '--memory-retry-multiplier',
        default=CaperWorkflowOpts.DEFAULT_MEMORY_RETRY_MULTIPLIER,
        help='(CURRENTLY NOT WORKING) '
        'If an error caught by --memory-retry-error-keys occurs, '
        'then increase memory by this '
        'for retrials controlled by --max-retries. '
        'See https://cromwell.readthedocs.io/en/develop/cromwell_features/RetryWithMoreMemory/ '
        'for details.',
    )
    parent_submit.add_argument(
        '--gcp-monitoring-script',
        default=CaperWorkflowOpts.DEFAULT_GCP_MONITORING_SCRIPT,
        help='Monitoring script for gcp backend only. '
        'Caper defaults to use its own monitoring script which works fine '
        'with subcommand gcp_profile. '
        'To make your script work with gcp_profile, '
        'make this script generate a TSV with a header in the first row. '
        'The first column of such TSV will be ignored since it is usually timestamp. '
        'Check monitoring_script in '
        'https://cromwell.readthedocs.io/en/stable/wf_options/Google/'
        '#google-pipelines-api-workflow-options '
        'for details.',
    )
    group_dep = parent_submit.add_argument_group(
        title='dependency resolver for all backends',
        description='Cloud-based backends (gc and aws) will only use Docker '
        'so that "--docker URI_FOR_DOCKER_IMG" must be specified '
        'in the command line argument or as a comment "#CAPER '
        'docker URI_FOR_DOCKER_IMG" or value for "workflow.meta.caper_docker"'
        'in a WDL file',
    )
    group_dep.add_argument(
        '--docker',
        nargs='?',
        const='',
        default=None,
        help='URI for Docker image (e.g. ubuntu:latest). '
        'This can also be used as a flag to use Docker image address '
        'defined in your WDL file as a comment ("#CAPER docker") or '
        'as "workflow.meta.caper_docker" in WDL.',
    )
    group_dep_local = parent_submit.add_argument_group(
        title='dependency resolver for local backend',
        description='Singularity is for local backend only. Other backends '
        '(gcp and aws) will use Docker only. '
        'Local backend defaults to not use any container-based methods. '
        'Use "--singularity" or "--docker" to use containers',
    )
    group_dep_local.add_argument(
        '--singularity',
        nargs='?',
        const='',
        default=None,
        help='URI or path for Singularity image '
        '(e.g. ~/.singularity/ubuntu-latest.simg, '
        'docker://ubuntu:latest, shub://vsoch/hello-world). '
        'This can also be used as a flag to use Docker image address '
        'defined in your WDL file as a comment ("#CAPER singularity") or '
        'as "workflow.meta.caper_singularity" in WDL.',
    )
    group_dep_local.add_argument(
        '--no-build-singularity',
        action='store_true',
        help='Do not build singularity image before running a workflow. ',
    )

    group_slurm = parent_submit.add_argument_group('SLURM arguments')
    group_slurm.add_argument('--slurm-partition', help='SLURM partition')
    group_slurm.add_argument('--slurm-account', help='SLURM account')
    group_slurm.add_argument(
        '--slurm-extra-param', help='SLURM extra parameters. Must be double-quoted'
    )

    group_sge = parent_submit.add_argument_group('SGE arguments')
    group_sge.add_argument(
        '--sge-pe', help='SGE parallel environment. Check with "qconf -spl"'
    )
    group_sge.add_argument('--sge-queue', help='SGE queue. Check with "qconf -sql"')
    group_sge.add_argument(
        '--sge-extra-param', help='SGE extra parameters. Must be double-quoted'
    )

    group_pbs = parent_submit.add_argument_group('PBS arguments')
    group_pbs.add_argument('--pbs-queue', help='PBS queue')
    group_pbs.add_argument(
        '--pbs-extra-param', help='PBS extra parameters. Must be double-quoted'
    )

    # server
    parent_server = argparse.ArgumentParser(add_help=False)
    parent_server.add_argument(
        '--java-heap-server',
        default=Cromwell.DEFAULT_JAVA_HEAP_CROMWELL_SERVER,
        help='Cromwell Java heap size for "server" mode (java -Xmx)',
    )
    parent_server.add_argument(
        '--disable-auto-write-metadata',
        action='store_true',
        help='Disable automatic retrieval/update/writing of metadata.json upon workflow/task status change.',
    )

    # run
    parent_run = argparse.ArgumentParser(add_help=False)
    parent_run.add_argument(
        '-m',
        '--metadata-output',
        help='An optional directory path to output metadata JSON file',
    )
    parent_run.add_argument(
        '--java-heap-run',
        default=Cromwell.DEFAULT_JAVA_HEAP_CROMWELL_RUN,
        help='Cromwell Java heap size for "run" mode (java -Xmx)',
    )

    # list, metadata, abort
    parent_search_wf = argparse.ArgumentParser(add_help=False)
    parent_search_wf.add_argument(
        'wf_id_or_label',
        nargs='*',
        help='List of workflow IDs to find matching workflows to '
        'commit a specified action (list, metadata and abort). '
        'Wildcards (* and ?) are allowed.',
    )

    # server, all client subcommands
    parent_server_client = argparse.ArgumentParser(add_help=False)
    parent_server_client.add_argument(
        '--port',
        type=int,
        default=Cromwell.DEFAULT_SERVER_PORT,
        help='Port for Caper server',
    )
    parent_server_client.add_argument(
        '--no-server-heartbeat',
        action='store_true',
        help='Disable server heartbeat file.',
    )
    parent_server_client.add_argument(
        '--server-heartbeat-file',
        default=ServerHeartbeat.DEFAULT_SERVER_HEARTBEAT_FILE,
        help='Heartbeat file for Caper clients to get IP and port of a server',
    )
    parent_server_client.add_argument(
        '--server-heartbeat-timeout',
        type=int,
        default=ServerHeartbeat.DEFAULT_HEARTBEAT_TIMEOUT_MS,
        help='Timeout for a heartbeat file in Milliseconds. '
        'A heartbeat file older than '
        'this interval will be ignored.',
    )

    parent_client = argparse.ArgumentParser(add_help=False)
    parent_client.add_argument(
        '--hostname',
        '--ip',
        default=CromwellRestAPI.DEFAULT_HOSTNAME,
        help='Hostname (or IP address) of Caper server.',
    )

    # list
    parent_list = argparse.ArgumentParser(add_help=False)
    parent_list.add_argument(
        '-f',
        '--format',
        default=DEFAULT_LIST_FORMAT,
        help='Comma-separated list of items to be shown for "list" '
        'subcommand. Any key name in workflow JSON from Cromwell '
        'server\'s response is allowed. '
        'Available keys are "id" (workflow ID), "status", "str_label", '
        '"name" (WDL/CWL name), "submission" (date/time), "start", '
        '"end" and "user". '
        '"str_label" is a special key for Caper. See help context '
        'of "--str-label" for details',
    )
    parent_list.add_argument(
        '--hide-result-before',
        help='Hide workflows submitted before this date/time. '
        'Use the same (or shorter) date/time format shown in '
        '"caper list". '
        'e.g. 2019-06-13, 2019-06-13T10:07',
    )
    parent_list.add_argument(
        '--show-subworkflow',
        action='store_true',
        help='Show subworkflows in "caper list". '
        'WARNING: If there are too many subworkflows, '
        'this can result in crash of Caper/Cromwell server ',
    )

    # troubleshoot/debug
    parent_troubleshoot = argparse.ArgumentParser(add_help=False)
    parent_troubleshoot.add_argument(
        '--show-completed-task',
        action='store_true',
        help='Show information about completed tasks.',
    )
    parent_troubleshoot.add_argument(
        '--show-stdout', action='store_true', help='Show STDOUT for failed tasks.'
    )

    # gcp_monitor
    parent_gcp_monitor = argparse.ArgumentParser(add_help=False)
    parent_gcp_monitor.add_argument(
        '--json-format',
        action='store_true',
        help='Prints out outputs in a JSON format.',
    )

    # gcp_res_analysis
    parent_gcp_res_analysis = argparse.ArgumentParser(add_help=False)
    parent_gcp_res_analysis.add_argument(
        '--in-file-vars-def-json',
        help='JSON file to define task name and input file variabless '
        'to be included in resource analysis. '
        'Key: task name, wild-cards (*, ?) are allowed. '
        'Value: list of input file var names. '
        'e.g. "atac.align*": ["fastqs_R1", "fastqs_R2"]. '
        'Once this file is defined, tasks not included in it will be ignored.',
    )
    parent_gcp_res_analysis.add_argument(
        '--reduce-in-file-vars',
        choices=[method.name for method in list(ResourceAnalysisReductionMethod)],
        default=ResourceAnalysisReductionMethod.sum.name,
        help='Reduce X matrix (resource data) into a vector. '
        'e.g. summing up all input file sizes. '
        'Reducing X will convert a multiple linear regression into a single linear regression. '
        'This is useful since single linear regression requires much less data '
        '(at least 2 for each task). '
        'Choose NONE to keep all input file variables '
        'without reduction in the analysis. '
        '2D Scatter plot (--plot-pdf) will not available for analysis without reduction. '
        'If NONE then make sure that number of datasets (per task) '
        '> number of input file variables in a task.',
    )
    parent_gcp_res_analysis.add_argument(
        '--target-resources',
        nargs='+',
        default=list(ResourceAnalysis.DEFAULT_TARGET_RESOURCES),
        help='Keys for resources in a JSON gcp_monitor outputs, '
        'which forms y vector for a linear problem. '
        'Analysis will be done separately for each key (resource metric). '
        'See help for gcp_monitor to find available resources. '
        'e.g. stats.max.disk, stats.mean.cpu_pct.',
    )
    parent_gcp_res_analysis.add_argument(
        '--plot-pdf',
        help='Local path for a 2D scatter plot PDF file. '
        'Scatter plot will not be available if --reduce-in-file-vars is none.',
    )

    # cleanup
    parent_cleanup = argparse.ArgumentParser(add_help=False)
    parent_cleanup.add_argument(
        '--delete',
        action='store_true',
        help='DELETE OUTPUTS. caper cleanup runs in a dry-run mode by default. ',
    )
    parent_cleanup.add_argument(
        '--num-threads',
        default=URIBase.DEFAULT_NUM_THREADS,
        type=int,
        help='Number of threads for cleaning up workflow\'s outputs. '
        'This is used for cloud backends only.',
    )

    # all subcommands
    p_init = subparser.add_parser(
        'init',
        help='Initialize Caper\'s configuration file. THIS WILL OVERWRITE ON '
        'A SPECIFIED(-c)/DEFAULT CONF FILE. e.g. ~/.caper/default.conf.',
        parents=[parent_all, parent_init],
    )
    p_run = subparser.add_parser(
        'run',
        help='Run a single workflow without server',
        parents=[parent_all, parent_submit, parent_run, parent_runner, parent_backend],
    )
    p_server = subparser.add_parser(
        'server',
        help='Run a Cromwell server',
        parents=[
            parent_all,
            parent_server_client,
            parent_server,
            parent_runner,
            parent_backend,
        ],
    )
    p_submit = subparser.add_parser(
        'submit',
        help='Submit a workflow to a Cromwell server',
        parents=[
            parent_all,
            parent_server_client,
            parent_client,
            parent_submit,
            parent_backend,
        ],
    )
    p_abort = subparser.add_parser(
        'abort',
        help='Abort running/pending workflows on a Cromwell server',
        parents=[parent_all, parent_server_client, parent_client, parent_search_wf],
    )
    p_unhold = subparser.add_parser(
        'unhold',
        help='Release hold of workflows on a Cromwell server',
        parents=[parent_all, parent_server_client, parent_client, parent_search_wf],
    )
    p_list = subparser.add_parser(
        'list',
        help='List running/pending workflows on a Cromwell server',
        parents=[
            parent_all,
            parent_server_client,
            parent_client,
            parent_search_wf,
            parent_list,
        ],
    )
    p_metadata = subparser.add_parser(
        'metadata',
        help='Retrieve metadata JSON for workflows from a Cromwell server',
        parents=[parent_all, parent_server_client, parent_client, parent_search_wf],
    )
    p_troubleshoot = subparser.add_parser(
        'troubleshoot',
        help='Troubleshoot workflow problems from metadata JSON file or '
        'workflow IDs',
        parents=[
            parent_all,
            parent_server_client,
            parent_client,
            parent_search_wf,
            parent_troubleshoot,
        ],
    )
    p_debug = subparser.add_parser(
        'debug',
        help='Identical to "troubleshoot"',
        parents=[
            parent_all,
            parent_server_client,
            parent_client,
            parent_search_wf,
            parent_troubleshoot,
        ],
    )
    p_gcp_monitor = subparser.add_parser(
        'gcp_monitor',
        help='Tabulate task\'s resource data collected on '
        'instances run on Google Cloud Compute. '
        'Use this for any workflows run with Caper>=1.2.0 on gcp backend. '
        'This is for gcp backend only.',
        parents=[
            parent_all,
            parent_server_client,
            parent_client,
            parent_search_wf,
            parent_gcp_monitor,
        ],
    )
    p_gcp_res_analysis = subparser.add_parser(
        'gcp_res_analysis',
        help='Linear resource analysis on monitoring data collected on '
        'instances run on Google Cloud Compute. This is for gcp backend only. '
        'Use this for any workflows run with Caper>=1.2.0 on gcp backend. '
        'Calculates coefficients/intercept for task\'s required resources '
        'based on input file size of a task. '
        'For each task it solves a linear regression problem of y=Xc + i1 + e where '
        'X is a matrix (m by n) of input file sizes and '
        'c is a coefficient vector (n by 1) and '
        'i is intercept and 1 is ones vector. '
        'y is a vector (m by 1) of resource taken and '
        'e is residual to be minimized. '
        'm is number of dataset and n is number of input file variables. '
        'Each resource metric will be solved separately. '
        'Refer to --target-resources for details about available resource metrics. '
        'Output will be a tuple of coefficient vector and intercept. ',
        parents=[
            parent_all,
            parent_server_client,
            parent_client,
            parent_search_wf,
            parent_gcp_res_analysis,
        ],
    )
    p_cleanup = subparser.add_parser(
        'cleanup',
        help='Cleanup outputs of workflows.',
        parents=[
            parent_all,
            parent_server_client,
            parent_client,
            parent_search_wf,
            parent_cleanup,
        ],
    )

    if conf_file is None:
        # partially parse args to get conf file from cmd line
        known_args, _ = parent_all.parse_known_args()
        conf_file = known_args.conf
    conf_file = os.path.expanduser(conf_file)

    subparsers = [
        p_init,
        p_run,
        p_server,
        p_submit,
        p_abort,
        p_unhold,
        p_list,
        p_metadata,
        p_troubleshoot,
        p_debug,
        p_gcp_monitor,
        p_gcp_res_analysis,
        p_cleanup,
    ]
    if os.path.exists(conf_file):
        conf_dict = update_parsers_defaults_with_conf(
            parsers=subparsers, conf_file=conf_file, conf_key_map=PARAM_KEY_NAME_CHANGE
        )
    else:
        conf_dict = None

    return parser, conf_dict
