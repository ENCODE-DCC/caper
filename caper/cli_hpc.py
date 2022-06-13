import logging
import sys

from .hpc import (SlurmWrapper, SgeWrapper, PbsWrapper, LsfWrapper)

logger = logging.getLogger(__name__)


def make_caper_run_command_for_hpc_submit():
    """Makes `caper run ...` command from `caper hpc submit` command by simply
    replacing `caper hpc submit` with `caper run`.
    This also escapes double quotes in caper run command.
    """
    if sys.argv[1] == 'hpc' and sys.argv[2] == 'submit':
        # Replace "caper hpc submit" with "caper run"
        new_argv = list(sys.argv)
        new_argv.pop(2)
        new_argv[1] = 'run'
        return new_argv
    else:
        raise ValueError('Wrong HPC command')


def subcmd_hpc(args):
    if args.hpc_action == 'submit':

        if args.leader_job_name is None:
            raise ValueError(
                'Define --leader-job-name [LEADER_JOB_NAME] in the command line arguments.'
            )
        caper_run_command = make_caper_run_command_for_hpc_submit()

        if args.backend == 'slurm':
            stdout = SlurmWrapper(
                args.slurm_leader_job_resource_param.split(),
                args.slurm_partition,
                args.slurm_account
            ).submit(args.leader_job_name, caper_run_command)

        elif args.backend == 'sge':
            stdout = SgeWrapper(
                args.sge_leader_job_resource_param.split(),
                args.sge_queue
            ).submit(args.leader_job_name, caper_run_command)
            
        elif args.backend == 'pbs':
            stdout = PbsWrapper(
                args.pbs_leader_job_resource_param.split(),
                args.pbs_queue
            ).submit(args.leader_job_name, caper_run_command)

        elif args.backend == 'lsf':
            stdout = LsfWrapper(
                args.lsf_leader_job_resource_param.split(),
                args.lsf_queue
            ).submit(args.leader_job_name, caper_run_command)

        else:
            raise ValueError('Unsupported backend {b} for hpc'.format(b=args.backend))
    else:
        if args.backend == 'slurm':
            hpc_wrapper = SlurmWrapper()
        elif args.backend == 'sge':
            hpc_wrapper = SgeWrapper()
        elif args.backend == 'pbs':
            hpc_wrapper = PbsWrapper()
        elif args.backend == 'lsf':
            hpc_wrapper = LsfWrapper()
        else:
            raise ValueError('Unsupported backend {b} for hpc'.format(b=args.backend))

        if args.hpc_action == 'list':
            stdout = hpc_wrapper.list()

        elif args.hpc_action == 'abort':
            stdout = hpc_wrapper.abort(args.job_ids)

        else:
            raise ValueError('Unsupported hpc action {act}'.format(act=args.hpc_action))

    print(stdout)
