#!/usr/bin/env python3
import copy
import csv
import json
import logging
import os
import re
import sys

from autouri import GCSURI, AutoURI

from . import __version__ as version
from .caper_args import ResourceAnalysisReductionMethod, get_parser_and_defaults
from .caper_client import CaperClient, CaperClientSubmit
from .caper_init import init_caper_conf
from .caper_labels import CaperLabels
from .caper_runner import CaperRunner
from .cromwell_backend import (
    BACKEND_ALIAS_LOCAL,
    BACKEND_LOCAL,
    CromwellBackendDatabase,
)
from .cromwell_metadata import CromwellMetadata
from .dict_tool import flatten_dict
from .resource_analysis import LinearResourceAnalysis
from .server_heartbeat import ServerHeartbeat

logger = logging.getLogger(__name__)


DEFAULT_DB_FILE_PREFIX = 'caper_file_db'
DEFAULT_SERVER_HEARTBEAT_FILE = '~/.caper/default_server_heartbeat'
USER_INTERRUPT_WARNING = (
    '\n\n'
    '*** DO NOT CTRL+C MULTIPLE TIMES! ***\n'
    '*** OR CAPER WILL NOT BE ABLE TO STOP CROMWELL AND RUNNING WORKFLOWS/TASKS ***'
    '\n\n'
)
REGEX_DELIMITER_PARAMS = r',| '
PRINT_ROW_DELIMITER = '\t'


def get_abspath(path):
    """Get abspath from a string.
    This function is mainly used to make a command line argument an abspath
    since AutoURI module only works with abspath and full URIs
    (e.g. /home/there, gs://here/there).
    For example, "caper run toy.wdl --docker ubuntu:latest".
    AutoURI cannot recognize toy.wdl on CWD as a file path.
    It should be converted to an abspath first.
    To do so, use this function for local file path strings only (e.g. toy.wdl).
    Do not use this function for other non-local-path strings (e.g. --docker).
    """
    if path:
        if not AutoURI(path).is_valid:
            return os.path.abspath(os.path.expanduser(path))
    return path


def print_version(parser, args):
    if args.version:
        print(version)
        parser.exit()


def init_logging(args):
    if args.debug:
        log_level = 'DEBUG'
    else:
        log_level = 'INFO'
    logging.basicConfig(
        level=log_level, format='%(asctime)s|%(name)s|%(levelname)s| %(message)s'
    )
    # suppress filelock logging
    logging.getLogger('filelock').setLevel('CRITICAL')


def init_autouri(args):
    if hasattr(args, 'use_gsutil_for_s3'):
        GCSURI.init_gcsuri(use_gsutil_for_s3=args.use_gsutil_for_s3)


def check_flags(args):
    singularity_flag = False
    docker_flag = False

    if hasattr(args, 'singularity') and args.singularity is not None:
        singularity_flag = True
        if args.singularity.endswith(('.wdl', '.cwl')):
            raise ValueError(
                '--singularity ate up positional arguments (e.g. WDL, CWL). '
                'Define --singularity at the end of command line arguments. '
                'singularity={p}'.format(p=args.singularity)
            )

    if hasattr(args, 'docker') and args.docker is not None:
        docker_flag = True
        if args.docker.endswith(('.wdl', '.cwl')):
            raise ValueError(
                '--docker ate up positional arguments (e.g. WDL, CWL). '
                'Define --docker at the end of command line arguments. '
                'docker={p}'.format(p=args.docker)
            )
        if hasattr(args, 'soft_glob_output') and args.soft_glob_output:
            raise ValueError(
                '--soft-glob-output and --docker are mutually exclusive. '
                'Delocalization from docker container will fail '
                'for soft-linked globbed outputs.'
            )

    if singularity_flag and docker_flag:
        raise ValueError('--docker and --singularity are mutually exclusive.')


def check_dirs(args):
    """Convert local directories (local_out_dir, local_loc_dir) to absolute ones.
    Also, if temporary/cache directory is not defined for each storage,
    then append ".caper_tmp" on output directory and use it.
    """
    if hasattr(args, 'local_out_dir'):
        args.local_out_dir = get_abspath(args.local_out_dir)
        if not args.local_loc_dir:
            args.local_loc_dir = os.path.join(
                args.local_out_dir, CaperRunner.DEFAULT_LOC_DIR_NAME
            )
    else:
        if not args.local_loc_dir:
            args.local_loc_dir = os.path.join(
                os.getcwd(), CaperRunner.DEFAULT_LOC_DIR_NAME
            )

    args.local_loc_dir = get_abspath(args.local_loc_dir)

    if hasattr(args, 'gcp_out_dir'):
        if args.gcp_out_dir and not args.gcp_loc_dir:
            args.gcp_loc_dir = os.path.join(
                args.gcp_out_dir, CaperRunner.DEFAULT_LOC_DIR_NAME
            )

    if hasattr(args, 'aws_out_dir'):
        if args.aws_out_dir and not args.aws_loc_dir:
            args.aws_loc_dir = os.path.join(
                args.aws_out_dir, CaperRunner.DEFAULT_LOC_DIR_NAME
            )


def check_db_path(args):
    if hasattr(args, 'db') and args.db == CromwellBackendDatabase.DB_FILE:
        args.file_db = get_abspath(args.file_db)

        if not args.file_db:
            prefix = DEFAULT_DB_FILE_PREFIX
            if hasattr(args, 'inputs') and args.inputs:
                prefix += '_' + os.path.splitext(os.path.basename(args.inputs))[0]

            args.file_db = os.path.join(args.local_out_dir, prefix)


def check_backend(args):
    """Check if local backend is in lower cases.
    "Local" should be capitalized. i.e. local -> Local.
    BACKEND_LOCAL is Local.
    BACKEND_ALIAS_LOCAL is local.
    """
    if hasattr(args, 'backend') and args.backend == BACKEND_ALIAS_LOCAL:
        args.backend = BACKEND_LOCAL


def runner(args, nonblocking_server=False):
    if args.gcp_zones:
        args.gcp_zones = re.split(REGEX_DELIMITER_PARAMS, args.gcp_zones)
    if args.memory_retry_error_keys:
        args.memory_retry_error_keys = re.split(
            REGEX_DELIMITER_PARAMS, args.memory_retry_error_keys
        )

    c = CaperRunner(
        local_loc_dir=args.local_loc_dir,
        local_out_dir=args.local_out_dir,
        default_backend=args.backend,
        gcp_loc_dir=args.gcp_loc_dir,
        aws_loc_dir=args.aws_loc_dir,
        gcp_service_account_key_json=get_abspath(args.gcp_service_account_key_json),
        cromwell=get_abspath(args.cromwell),
        womtool=get_abspath(getattr(args, 'womtool', None)),
        disable_call_caching=args.disable_call_caching,
        max_concurrent_workflows=args.max_concurrent_workflows,
        memory_retry_error_keys=args.memory_retry_error_keys,
        max_concurrent_tasks=args.max_concurrent_tasks,
        soft_glob_output=args.soft_glob_output,
        local_hash_strat=args.local_hash_strat,
        db=args.db,
        db_timeout=args.db_timeout,
        file_db=args.file_db,
        mysql_db_ip=args.mysql_db_ip,
        mysql_db_port=args.mysql_db_port,
        mysql_db_user=args.mysql_db_user,
        mysql_db_password=args.mysql_db_password,
        mysql_db_name=args.mysql_db_name,
        postgresql_db_ip=args.postgresql_db_ip,
        postgresql_db_port=args.postgresql_db_port,
        postgresql_db_user=args.postgresql_db_user,
        postgresql_db_password=args.postgresql_db_password,
        postgresql_db_name=args.postgresql_db_name,
        gcp_prj=args.gcp_prj,
        use_google_cloud_life_sciences=args.use_google_cloud_life_sciences,
        gcp_region=args.gcp_region,
        gcp_zones=args.gcp_zones,
        gcp_call_caching_dup_strat=args.gcp_call_caching_dup_strat,
        gcp_out_dir=args.gcp_out_dir,
        aws_batch_arn=args.aws_batch_arn,
        aws_region=args.aws_region,
        aws_out_dir=args.aws_out_dir,
        slurm_partition=getattr(args, 'slurm_partition', None),
        slurm_account=getattr(args, 'slurm_account', None),
        slurm_extra_param=getattr(args, 'slurm_extra_param', None),
        sge_pe=getattr(args, 'sge_pe', None),
        sge_queue=getattr(args, 'sge_queue', None),
        sge_extra_param=getattr(args, 'sge_extra_param', None),
        pbs_queue=getattr(args, 'pbs_queue', None),
        pbs_extra_param=getattr(args, 'pbs_extra_param', None),
    )

    if args.action == 'run':
        subcmd_run(c, args)

    elif args.action == 'server':
        return subcmd_server(c, args, nonblocking=nonblocking_server)

    else:
        raise ValueError('Unsupported runner action {act}'.format(act=args.action))


def client(args):
    sh = None
    if not args.no_server_heartbeat:
        sh = ServerHeartbeat(
            heartbeat_file=args.server_heartbeat_file,
            heartbeat_timeout=args.server_heartbeat_timeout,
        )
    if args.action == 'submit':
        if args.gcp_zones:
            args.gcp_zones = re.split(REGEX_DELIMITER_PARAMS, args.gcp_zones)

        c = CaperClientSubmit(
            local_loc_dir=args.local_loc_dir,
            gcp_loc_dir=args.gcp_loc_dir,
            aws_loc_dir=args.aws_loc_dir,
            gcp_service_account_key_json=get_abspath(args.gcp_service_account_key_json),
            server_hostname=args.hostname,
            server_port=args.port,
            server_heartbeat=sh,
            womtool=get_abspath(args.womtool),
            use_google_cloud_life_sciences=args.use_google_cloud_life_sciences,
            gcp_zones=args.gcp_zones,
            slurm_partition=args.slurm_partition,
            slurm_account=args.slurm_account,
            slurm_extra_param=args.slurm_extra_param,
            sge_pe=args.sge_pe,
            sge_queue=args.sge_queue,
            sge_extra_param=args.sge_extra_param,
            pbs_queue=args.pbs_queue,
            pbs_extra_param=args.pbs_extra_param,
        )
        subcmd_submit(c, args)

    else:
        c = CaperClient(
            local_loc_dir=args.local_loc_dir,
            gcp_loc_dir=args.gcp_loc_dir,
            aws_loc_dir=args.aws_loc_dir,
            gcp_service_account_key_json=get_abspath(args.gcp_service_account_key_json),
            server_hostname=args.hostname,
            server_port=args.port,
            server_heartbeat=sh,
        )
        if args.action == 'abort':
            subcmd_abort(c, args)
        elif args.action == 'unhold':
            subcmd_unhold(c, args)
        elif args.action == 'list':
            subcmd_list(c, args)
        elif args.action == 'metadata':
            subcmd_metadata(c, args)
        elif args.action in ('troubleshoot', 'debug'):
            subcmd_troubleshoot(c, args)
        elif args.action == 'gcp_monitor':
            subcmd_gcp_monitor(c, args)
        elif args.action == 'gcp_res_analysis':
            subcmd_gcp_res_analysis(c, args)
        elif args.action == 'cleanup':
            subcmd_cleanup(c, args)
        else:
            raise ValueError('Unsupported client action {act}'.format(act=args.action))


def subcmd_server(caper_runner, args, nonblocking=False):
    """
    Args:
        nonblocking:
            Make this function return a Thread object
            instead of blocking (Thread.join()).
            Also writes Cromwell's STDOUT to sys.stdout
            instead of a file (args.cromwell_stdout).
    """
    sh = None
    if not args.no_server_heartbeat:
        sh = ServerHeartbeat(
            heartbeat_file=args.server_heartbeat_file,
            heartbeat_timeout=args.server_heartbeat_timeout,
        )

    args_from_cli = {
        'default_backend': args.backend,
        'server_port': args.port,
        'server_heartbeat': sh,
        'custom_backend_conf': get_abspath(args.backend_file),
        'embed_subworkflow': True,
        'auto_write_metadata': not args.disable_auto_write_metadata,
        'java_heap_server': args.java_heap_server,
        'dry_run': args.dry_run,
    }

    if nonblocking:
        return caper_runner.server(fileobj_stdout=sys.stdout, **args_from_cli)

    cromwell_stdout = get_abspath(args.cromwell_stdout)
    with open(cromwell_stdout, 'w') as f:
        try:
            thread = caper_runner.server(fileobj_stdout=f, **args_from_cli)
            if thread:
                thread.join()
                thread.stop(wait=True)
                if thread.returncode:
                    logger.error('Check stdout in {file}'.format(file=cromwell_stdout))

        except KeyboardInterrupt:
            logger.error(USER_INTERRUPT_WARNING, exc_info=True)


def subcmd_run(caper_runner, args):
    cromwell_stdout = get_abspath(args.cromwell_stdout)

    with open(cromwell_stdout, 'w') as f:
        try:
            thread = caper_runner.run(
                backend=args.backend,
                wdl=get_abspath(args.wdl),
                inputs=get_abspath(args.inputs),
                options=get_abspath(args.options),
                labels=get_abspath(args.labels),
                imports=get_abspath(args.imports),
                metadata_output=get_abspath(args.metadata_output),
                str_label=args.str_label,
                docker=args.docker,
                singularity=args.singularity,
                singularity_cachedir=args.singularity_cachedir,
                no_build_singularity=args.no_build_singularity,
                custom_backend_conf=get_abspath(args.backend_file),
                max_retries=args.max_retries,
                memory_retry_multiplier=args.memory_retry_multiplier,
                gcp_monitoring_script=args.gcp_monitoring_script,
                ignore_womtool=args.ignore_womtool,
                no_deepcopy=args.no_deepcopy,
                fileobj_stdout=f,
                fileobj_troubleshoot=sys.stdout,
                java_heap_run=args.java_heap_run,
                java_heap_womtool=args.java_heap_womtool,
                dry_run=args.dry_run,
            )
            if thread:
                thread.join()
                thread.stop(wait=True)
                if thread.returncode:
                    logger.error('Check stdout in {file}'.format(file=cromwell_stdout))

        except KeyboardInterrupt:
            logger.error(USER_INTERRUPT_WARNING, exc_info=True)


def subcmd_submit(caper_client, args):
    caper_client.submit(
        wdl=get_abspath(args.wdl),
        backend=args.backend,
        inputs=get_abspath(args.inputs),
        options=get_abspath(args.options),
        labels=get_abspath(args.labels),
        imports=get_abspath(args.imports),
        str_label=args.str_label,
        docker=args.docker,
        singularity=args.singularity,
        singularity_cachedir=args.singularity_cachedir,
        no_build_singularity=args.no_build_singularity,
        max_retries=args.max_retries,
        memory_retry_multiplier=args.memory_retry_multiplier,
        gcp_monitoring_script=args.gcp_monitoring_script,
        ignore_womtool=args.ignore_womtool,
        no_deepcopy=args.no_deepcopy,
        hold=args.hold,
        java_heap_womtool=args.java_heap_womtool,
        dry_run=args.dry_run,
    )


def subcmd_abort(caper_client, args):
    caper_client.abort(args.wf_id_or_label)


def subcmd_unhold(caper_client, args):
    caper_client.unhold(args.wf_id_or_label)


def subcmd_list(caper_client, args):
    workflows = caper_client.list(
        args.wf_id_or_label, exclude_subworkflow=not args.show_subworkflow
    )

    try:
        writer = csv.writer(sys.stdout, delimiter=PRINT_ROW_DELIMITER)

        formats = args.format.split(',')
        writer.writerow(formats)

        if workflows is None:
            return
        for w in workflows:
            row = []
            workflow_id = w.get('id')
            parent_workflow_id = w.get('parentWorkflowId')

            if args.hide_result_before is not None:
                if (
                    w.get('submission')
                    and w.get('submission') <= args.hide_result_before
                ):
                    continue
            for f in formats:
                if f == 'workflow_id':
                    row.append(str(workflow_id))
                elif f == 'str_label':
                    if 'labels' in w and CaperLabels.KEY_CAPER_STR_LABEL in w['labels']:
                        lbl = w['labels'][CaperLabels.KEY_CAPER_STR_LABEL]
                    else:
                        lbl = None
                    row.append(str(lbl))
                elif f == 'user':
                    if 'labels' in w and CaperLabels.KEY_CAPER_USER in w['labels']:
                        lbl = w['labels'][CaperLabels.KEY_CAPER_USER]
                    else:
                        lbl = None
                    row.append(str(lbl))
                elif f == 'parent':
                    row.append(str(parent_workflow_id))
                else:
                    row.append(str(w.get(f)))
            writer.writerow(row)

    except BrokenPipeError:
        logger.debug('Ignored BrokenPipeError.')


def subcmd_metadata(caper_client, args):
    m = caper_client.metadata(
        wf_ids_or_labels=args.wf_id_or_label, embed_subworkflow=True
    )
    if not m:
        raise ValueError('Found no workflow matching with search query.')
    elif len(m) > 1:
        raise ValueError('Found multiple workflow matching with search query.')

    print(json.dumps(m[0], indent=4))


def get_single_cromwell_metadata_obj(caper_client, args, subcmd):
    if not args.wf_id_or_label:
        raise ValueError(
            'Define at least one metadata JSON file or '
            'a search query for workflow ID/string label '
            'if there is a running Caper server.'
        )
    elif len(args.wf_id_or_label) > 1:
        raise ValueError(
            'Multiple files/queries are not allowed for {subcmd}. '
            'Define one metadata JSON file or a search query '
            'for workflow ID/string label.'.format(subcmd=subcmd)
        )

    metadata_file = AutoURI(get_abspath(args.wf_id_or_label[0]))

    if metadata_file.exists:
        metadata = json.loads(metadata_file.read())
    else:
        metadata_objs = caper_client.metadata(
            wf_ids_or_labels=args.wf_id_or_label, embed_subworkflow=True
        )
        if len(metadata_objs) > 1:
            raise ValueError('Found multiple workflows matching with search query.')
        elif len(metadata_objs) == 0:
            raise ValueError('Found no workflow matching with search query.')
        metadata = metadata_objs[0]

    return CromwellMetadata(metadata)


def split_list_into_file_and_non_file(lst):
    """Returns tuple of (list of existing files, list of non-file strings)
    """
    files = []
    non_files = []

    for maybe_file in lst:
        if AutoURI(get_abspath(maybe_file)).exists:
            files.append(maybe_file)
        else:
            non_files.append(maybe_file)

    return files, non_files


def get_multi_cromwell_metadata_objs(caper_client, args):
    if not args.wf_id_or_label:
        raise ValueError(
            'Define at least one metadata JSON file or '
            'a search query for workflow ID/string label '
            'if there is a running Caper server.'
        )

    files, non_files = split_list_into_file_and_non_file(args.wf_id_or_label)

    all_metadata = []
    for file in files:
        metadata = json.loads(AutoURI(get_abspath(file)).read())
        all_metadata.append(metadata)

    if non_files:
        all_metadata.extend(
            caper_client.metadata(wf_ids_or_labels=non_files, embed_subworkflow=True)
        )

    if not all_metadata:
        raise ValueError('Found no metadata/workflow matching with search query.')
    return [CromwellMetadata(m) for m in all_metadata]


def subcmd_troubleshoot(caper_client, args):
    cm = get_single_cromwell_metadata_obj(caper_client, args, 'troubleshoot/debug')
    cm.troubleshoot(
        fileobj=sys.stdout,
        show_completed_task=args.show_completed_task,
        show_stdout=args.show_stdout,
    )


def subcmd_gcp_monitor(caper_client, args):
    """Prints out monitoring result either in a TSV format or in a JSON one.

    TSV format:
        TSV will be a flattened JSON with dot notation.
        The last column in the header is `input_file_name_size_pairs`.
        As its name implies, contents for this last columns are dynamic in length.

    JSON format:
        See description at CromwellMetadata.gcp_monitor.__doc__.
        Use a JSON format instead to get more detailed information.
    """
    all_metadata = get_multi_cromwell_metadata_objs(caper_client, args)
    writer = csv.writer(sys.stdout, delimiter=PRINT_ROW_DELIMITER)

    result = []
    for metadata in all_metadata:
        result.extend(metadata.gcp_monitor())

    if args.json_format:
        print(json.dumps(result, indent=4))
    else:
        # input_file_sizes is dynamic in length so exclude and then put it back
        first_data = copy.deepcopy(result[0])
        first_data.pop('input_file_sizes')
        header = list(flatten_dict(first_data, reducer='.').keys())
        header += ['input_file_var_size_pairs']
        writer.writerow(header)

        for task_data in result:
            input_file_sizes = task_data.pop('input_file_sizes')
            row = [str(v) for v in flatten_dict(task_data).values()]

            # append `input_file_sizes` data which couldn't be cleanly
            # flattened by flatten_dict()
            for key, file_sizes in input_file_sizes.items():
                for i, file_size in enumerate(file_sizes):
                    if len(file_sizes) == 1:
                        row.append(key)
                    else:
                        row.append(key + '[{idx}]'.format(idx=i))
                    row.append(str(file_size))

            writer.writerow(row)


def read_json(json_file):
    if json_file:
        json_contents = AutoURI(get_abspath(json_file)).read()
        return json.loads(json_contents)


def subcmd_gcp_res_analysis(caper_client, args):
    """Solves linear regression problem to find coeffs and intercept
    to help optimizing resources for a task based on task's input file size.

    Prints out found coeffs and intercept along with raw dataset (x, y).
        - x: input file sizes for a task
        - y: resources (max_mem, max_disk) taken for a task
    """
    all_metadata = get_multi_cromwell_metadata_objs(caper_client, args)

    res_analysis = LinearResourceAnalysis()
    res_analysis.collect_resource_data(all_metadata)

    result = res_analysis.analyze(
        in_file_vars=read_json(args.in_file_vars_def_json),
        reduce_in_file_vars=getattr(
            ResourceAnalysisReductionMethod, args.reduce_in_file_vars
        ).value,
        target_resources=args.target_resources,
        plot_pdf=get_abspath(args.plot_pdf),
    )
    print(json.dumps(result, indent=4))


def subcmd_cleanup(caper_client, args):
    """Cleanup outputs of a workflow.
    """
    cm = get_single_cromwell_metadata_obj(caper_client, args, 'cleanup')
    cm.cleanup(dry_run=not args.delete, num_threads=args.num_threads, no_lock=True)
    if not args.delete:
        logger.warning(
            'Use --delete to DELETE ALL OUTPUTS of this workflow. '
            'This action is NOT REVERSIBLE. Use this at your own risk.'
        )


def main(args=None, nonblocking_server=False):
    """
    Args:
        args:
            List of command line arguments.
            If defined use it instead of sys.argv.
        nonblocking_server:
            "server" subcommand will return a Thread object
            instead of waiting (Thread.join()).
    """
    parser, _ = get_parser_and_defaults()

    if args is None and len(sys.argv[1:]) == 0:
        parser.print_help()
        parser.exit()

    known_args, _ = parser.parse_known_args(args)
    check_flags(known_args)
    print_version(parser, known_args)

    parsed_args = parser.parse_args(args)
    init_logging(parsed_args)
    init_autouri(parsed_args)

    check_dirs(parsed_args)
    check_db_path(parsed_args)
    check_backend(parsed_args)

    if parsed_args.action == 'init':
        init_caper_conf(parsed_args.conf, parsed_args.platform)

    elif parsed_args.action in ('run', 'server'):
        return runner(parsed_args, nonblocking_server=nonblocking_server)
    else:
        client(parsed_args)


if __name__ == '__main__':
    main()
