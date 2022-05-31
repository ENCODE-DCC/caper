"""Caper's HPC Wrapper based on job engine's CLI (shell command).
e.g. sbatch, squeue, qsub, qstat
"""
import logging
import os
import subprocess
from abc import ABC, abstractmethod
from collections import namedtuple
from pathlib import Path
from tempfile import NamedTemporaryFile

logger = logging.getLogger(__name__)

CAPER_LEADER_JOB_NAME_PREFIX = 'CAPER_'
ILLEGAL_CHARS_IN_JOB_NAME = [',', ' ', '\t']


def get_user_from_os_environ():
    return os.environ['USER']

def make_bash_script_contents(contents):
    return f'#!/bin/bash\n{contents}\n'

def make_caper_leader_job_name(job_name):
    """Check if job name contains Comma, TAB or whitespace.
    They are not allowed since they can be used as separators.
    """
    if any(illegal_char in job_name for illegal_char in ILLEGAL_CHARS_IN_JOB_NAME):
        raise ValueError('Illegal character {chr} in job name {job}'.format(
            chr=illegal_chr, job=job_name
        ))
    return CAPER_LEADER_JOB_NAME_PREFIX + job_name


class HpcWrapper(ABC):
    def __init__(
        self,
        leader_job_resource_param=[],
    ):
        """Base class for HPC job engines.

        Args:
            leader_job_resource_param:
                List of command line parameters to be passed to
                subprocess.Popen(leader_job_resource_param, shell=False, ...).
        """
        self.leader_job_resource_param = leader_job_resource_param

    def submit(self, job_name, caper_run_command):
        """Submits a caper leader job to HPC (e.g. sbatch, qsub).
        Such leader job will be prefixed with CAPER_LEADER_JOB_NAME_PREFIX.

        Returns output STDOUT from submission command.
        """
        home_dir = f'{str(Path.home())}{os.sep}'
        with NamedTemporaryFile(prefix=home_dir, suffix='.sh') as shell_script:
            shell_script.write(make_bash_script_contents(caper_run_command).encode())
            shell_script.flush()

            return self._submit(job_name, shell_script.name)

    def list(self):
        """Filters out non-caper jobs from the job list keeping the first line (header).
        And then returns output STDOUT.
        """
        result = []
        lines = self._list().split('\n')

        # keep header
        result.append(lines[0])

        # filter out non-caper lines
        for line in lines[1:]:
            if CAPER_LEADER_JOB_NAME_PREFIX in line:
                lines.append(line)

        return '\n'.join(lines)

    def abort(self, job_ids):
        """Returns output STDOUT from job engine's abort command (e.g. scancel, qdel).
        """
        return self._abort(job_ids)

    @abstractmethod
    def _submit(self, job_name, shell_script):        
        pass

    def _list(self):
        pass

    @abstractmethod
    def _abort(self, job_ids):
        pass

    def _run_command(self, command):
        """Runs a shell command line and returns STDOUT.
        """
        logger.info(f'Running shell command: {" ".join(command)}')
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            env=os.environ,
        ).stdout.decode().strip()


class SlurmWrapper(HpcWrapper):
    DEFAULT_LEADER_JOB_RESOURCE_PARAM = ['-t', '48:00:00', '--mem', '4G']

    def __init__(
        self,
        leader_job_resource_param=DEFAULT_LEADER_JOB_RESOURCE_PARAM,
        slurm_partition=None,
        slurm_account=None,
    ):
        super().__init__(
            leader_job_resource_param=leader_job_resource_param,
        )
        slurm_partition_param = ['-p', slurm_partition] if slurm_partition else []
        slurm_account_param = ['-A', slurm_account] if slurm_account else []
        self.slurm_extra_param = slurm_partition_param + slurm_account_param

    def _submit(self, job_name, shell_script):
        command = ['sbatch'] + self.leader_job_resource_param + self.slurm_extra_param + [
            '--export=ALL', '-J', make_caper_leader_job_name(job_name),
            shell_script,
        ]
        return self._run_command(command)

    def _list(self):
        return self._run_command([
            'squeue', '-u', get_user_from_os_environ(), '--Format=JobID,Name,SubmitTime'
        ])

    def _abort(self, job_ids):
        return self._run_command(['scancel', '--signal=SIGTERM', '-j'] + job_ids)


class SgeWrapper(HpcWrapper):
    DEFAULT_LEADER_JOB_RESOURCE_PARAM = ['-l', 'h_rt=48:00:00,h_vmem=4G']

    def __init__(
        self,
        leader_job_resource_param=DEFAULT_LEADER_JOB_RESOURCE_PARAM,
        sge_queue=None,
    ):
        super().__init__(
            leader_job_resource_param=leader_job_resource_param,
        )
        self.sge_queue_param = ['-q', sge_queue] if sge_queue else []

    def _submit(self, job_name, shell_script):
        command = ['qsub'] + self.leader_job_resource_param + self.sge_queue_param + [
            '-V', '-terse', '-N', make_caper_leader_job_name(job_name),
            shell_script
        ]
        return self._run_command(command)

    def _list(self):
        return self._run_command([
            'qstat', '-u', get_user_from_os_environ()
        ])

    def abort(self, job_ids):
        return self._run_command(['qdel'] + job_ids)


class PbsWrapper(HpcWrapper):
    DEFAULT_LEADER_JOB_RESOURCE_PARAM = ['-l', 'walltime=48:00:00,mem=4gb']

    def __init__(
        self,
        leader_job_resource_param=DEFAULT_LEADER_JOB_RESOURCE_PARAM,
        pbs_queue=None,
    ):
        super().__init__(
            leader_job_resource_param=leader_job_resource_param,
        )
        self.pbs_queue_param = ['-q', pbs_queue] if pbs_queue else []

    def _submit(self, job_name, shell_script):
        command = ['qsub'] + self.leader_job_resource_param + self.pbs_queue_param + [
            '-V', '-N', make_caper_leader_job_name(job_name),
            shell_script
        ]
        return self._run_command(command)

    def _list(self):
        return self._run_command([
            'qstat', '-u', get_user_from_os_environ()
        ])

    def abort(self, job_ids):
        return self._run_command(['qdel'] + job_ids)


class LsfWrapper(HpcWrapper):
    DEFAULT_LEADER_JOB_RESOURCE_PARAM = ['-W', '2880', '-M', '4g']

    def __init__(
        self,
        leader_job_resource_param=DEFAULT_LEADER_JOB_RESOURCE_PARAM,
        lsf_queue=None,
    ):
        super().__init__(
            leader_job_resource_param=leader_job_resource_param,
        )
        self.lsf_queue_param = ['-q', lsf_queue] if lsf_queue else []

    def _submit(self, job_name, shell_script):
        command = ['bsub'] + self.leader_job_resource_param + self.lsf_queue_param + [
            '-env', 'all', '-J', make_caper_leader_job_name(job_name),
            shell_script
        ]
        return self._run_command(command)

    def _list(self):
        return self._run_command([
            'bjobs', '-u', get_user_from_os_environ()
        ])

    def abort(self, job_ids):
        return self._run_command(['bkill'] + job_ids)
