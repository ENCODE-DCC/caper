import io
import json
import logging
import os
import re
from collections import defaultdict

import humanfriendly
import numpy as np
import pandas as pd
from autouri import GCSURI, AbsPath, AutoURI, URIBase

from .dict_tool import recurse_dict_value

logger = logging.getLogger(__name__)


def parse_cromwell_disks(s):
    """Parses Cromwell's disks in runtime attribute.
    """
    if s:
        m = re.findall(r'(\d+)', s)
        if m:
            return int(m[0]) * 1024 * 1024 * 1024


def parse_cromwell_memory(s):
    """Parses Cromwell's memory runtime attribute.
    """
    if s:
        return humanfriendly.parse_size(s)


def convert_type_np_to_py(o):
    """Convert numpy type to Python type.
    """
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError


class CromwellMetadata:
    DEFAULT_METADATA_BASENAME = 'metadata.json'
    DEFAULT_GCP_MONITOR_STAT_METHODS = ('mean', 'std', 'max', 'min', 'last')

    def __init__(self, metadata):
        """Parses metadata JSON (dict) object or file.
        """
        if isinstance(metadata, dict):
            self._metadata = metadata
        elif isinstance(metadata, CromwellMetadata):
            self._metadata = metadata._metadata
        else:
            s = AutoURI(metadata).read()
            self._metadata = json.loads(s)

    @property
    def data(self):
        return self._metadata

    @property
    def metadata(self):
        return self._metadata

    @property
    def workflow_id(self):
        return self._metadata.get('id')

    @property
    def workflow_status(self):
        return self._metadata.get('status')

    @property
    def failures(self):
        return self._metadata.get('failures')

    @property
    def calls(self):
        return self._metadata.get('calls')

    def recurse_calls(self, fn_call, parent_call_names=tuple()):
        """Recurse on tasks in metadata.

        Args:
            fn_call:
                Function to be called recursively for each call (task).
                This function should take the following three arguments.
                    call_name:
                        Cromwell workflow's call (task)'s name.
                    call:
                        Cromwell workflow's call (task) itself.
                    parent_call_names:
                        Tuple of parent call's name.
                        e.g. (..., great grand parent, grand parent, parent, ...)
        """
        if not self.calls:
            return
        for call_name, call_list in self.calls.items():
            for call in call_list:
                if 'subWorkflowMetadata' in call:
                    subworkflow = call['subWorkflowMetadata']
                    subworkflow_metadata = CromwellMetadata(subworkflow)
                    subworkflow_metadata.recurse_calls(
                        fn_call, parent_call_names=parent_call_names + (call_name,)
                    )
                else:
                    fn_call(call_name, call, parent_call_names)

    def write_on_workflow_root(self, basename=DEFAULT_METADATA_BASENAME):
        """Update metadata JSON file on metadata's output root directory.
        If there is a subworkflow, nest its metadata into main workflow's one

        Args:
            write_subworkflow:
                Write metadata JSON file for subworkflows.
        """
        if 'workflowRoot' in self._metadata:
            root = self._metadata['workflowRoot']
            metadata_file = os.path.join(root, basename)
            AutoURI(metadata_file).write(json.dumps(self._metadata, indent=4) + '\n')
            logger.info('Wrote metadata file. {f}'.format(f=metadata_file))
        else:
            metadata_file = None
            workflow_id = self._metadata.get('id')
            logger.warning(
                'Failed to write metadata file. workflowRoot not found. '
                'wf_id={i}'.format(i=workflow_id)
            )
        return metadata_file

    def troubleshoot(self, fileobj, show_completed_task=False, show_stdout=False):
        """Troubleshoots a workflow.
        Also, finds failure reasons and prints out STDERR and STDOUT.

        Args:
            fileobj:
                File-like object to write troubleshooting messages to.
            show_completed_task:
                Show STDERR/STDOUT of completed tasks.
            show_stdout:
                Show failed task's STDOUT along with STDERR.
        """
        fileobj.write(
            '* Started troubleshooting workflow: id={id}, status={status}\n'.format(
                id=self.workflow_id, status=self.workflow_status
            )
        )

        if self.workflow_status == 'Succeeded':
            fileobj.write('* Workflow ran Successfully.\n')
            return

        if self.failures:
            fileobj.write(
                '* Found failures JSON object.\n{s}\n'.format(
                    s=json.dumps(self.failures, indent=4)
                )
            )

        def troubleshoot_call(call_name, call, parent_call_names):
            nonlocal fileobj
            nonlocal show_completed_task
            nonlocal show_stdout

            status = call.get('executionStatus')
            shard_index = call.get('shardIndex')
            rc = call.get('returnCode')
            job_id = call.get('jobId')
            stdout = call.get('stdout')
            stderr = call.get('stderr')
            run_start = None
            run_end = None
            for event in call.get('executionEvents', []):
                if event['description'].startswith('Running'):
                    run_start = event['startTime']
                    run_end = event['endTime']
                    break
            if not show_completed_task and status in ('Done', 'Succeeded'):
                return
            fileobj.write(
                '\n==== NAME={name}, STATUS={status}, PARENT={p}\n'
                'SHARD_IDX={shard_idx}, RC={rc}, JOB_ID={job_id}\n'
                'START={start}, END={end}\n'
                'STDOUT={stdout}\nSTDERR={stderr}\n'.format(
                    name=call_name,
                    status=status,
                    p=','.join(parent_call_names),
                    start=run_start,
                    end=run_end,
                    shard_idx=shard_index,
                    rc=rc,
                    job_id=job_id,
                    stdout=stdout,
                    stderr=stderr,
                )
            )
            if stderr:
                if AutoURI(stderr).exists:
                    fileobj.write(
                        'STDERR_CONTENTS=\n{s}\n'.format(s=AutoURI(stderr).read())
                    )
            if show_stdout and stdout:
                if AutoURI(stdout).exists:
                    fileobj.write(
                        'STDOUT_CONTENTS=\n{s}\n'.format(s=AutoURI(stdout).read())
                    )

        fileobj.write('* Recursively finding failures in calls (tasks)...\n')
        self.recurse_calls(troubleshoot_call)

    def gcp_monitor(
        self,
        task_name=None,
        excluded_cols=(0,),
        stat_methods=DEFAULT_GCP_MONITOR_STAT_METHODS,
    ):
        """Recursively parse task(call)'s `monitoringLog`
        (`monitoring.log` in task's execution directory)
        generated by `monitoring_script` defined in workflow options.
        This feature is gcp backend only.
        Check the following for details.
        https://cromwell.readthedocs.io/en/stable/wf_options/Google/#google-pipelines-api-workflow-options

        This functions calculates mean/max/min/last of each column in `monitoring.log` and return
        them with task's input file sizes.

        Args:
            task_name:
                If defined, limit analysis to this task only.
            excluded_cols:
                List of 0-based indices of excluded columns. There will be no mean/max/min
                calculation for these excluded columns.
                col-0 (1st column) is excluded by default since it's usually a column
                for timestamps.
            stat_methods:
                List/tuple of stat method strings.
                Except for `last`, any method of pandas.DataFrame can be used for stat_methods.
                e.g. `mean`, `max`, `min`, ...
                `last` is to get the last element in data, which usually means the latest data.
                Some methods in pandas.DataFrame will return `nan` if the number of data row is
                too small (e.g. `std` requires more than one data row).
        Returns:
            List of mean/std/max/min/last of columns along with size of input files.
            Note that
                - None will be returned if there are no data in the file.
                    - This means that the log file exists but there is no data in it.
                - `shard_idx` is -1 for non-scattered tasks.
                - Dot notation (.) will be used for task_name of subworkflow's task.

            Result format:
            [
                {
                    'workflow_id': WORKFLOW_ID,
                    'task_name': TASK_NAME,
                    'status': TASK_STATUS,
                    'shard_idx': SHARD_INDEX,
                    'attempt': ATTEMPT_RETRIAL,
                    'mean': {
                        COL1_NAME: MEAN_OF_COL1,
                        COL2_NAME: MEAN_OF_COL2,
                        ...
                    },
                    'gcp_instance': {
                        'cpu': NUM_CPU,
                        'disk': DISK_SIZE_USED,
                        'mem': TOTAL_MEMORY_IN_BYTES,
                    },
                    'stats': {
                        'std': {
                            COL1_NAME: STD_OF_COL1,
                            COL2_NAME: STD_OF_COL2,
                            ...
                        },
                        'max': {
                            COL1_NAME: MAX_OF_COL1,
                            COL2_NAME: MAX_OF_COL2,
                            ...
                        },
                        'min': {
                            COL1_NAME: MIN_OF_COL1,
                            COL2_NAME: MIN_OF_COL2,
                            ...
                        },
                        'last': {
                            COL1_NAME: LAST_ENTRY_OF_COL1,
                            COL2_NAME: LAST_ENTRY_OF_COL2,
                            ...
                        },
                    },
                    'input_file_sizes': {
                        INPUT1: [
                            SIZE_OF_FILE1_IN_INPUT1,
                            SIZE_OF_FILE2_IN_INPUT1,
                            ...
                        ],
                        INPUT2: [
                            SIZE_OF_FILE1_IN_INPUT2,
                            ...
                        ],
                        ...
                    },
                },
                ...
            ]
        """
        result = []
        file_size_cache = {}
        workflow_id = self.workflow_id

        def gcp_monitor_call(call_name, call, parent_call_names):
            nonlocal result
            nonlocal excluded_cols
            nonlocal stat_methods
            nonlocal file_size_cache
            nonlocal workflow_id
            nonlocal task_name

            if task_name and task_name != call_name:
                return

            monitoring_log = call.get('monitoringLog')
            if monitoring_log is None:
                return
            if not GCSURI(monitoring_log).is_valid:
                # This feature is for GCSURI only.
                return
            if not GCSURI(monitoring_log).exists:
                # Workaround for Cromwell-52's bug.
                # Call-cached task has `monitoringLog`, but it does not exist.
                return

            dataframe = pd.read_csv(
                io.StringIO(GCSURI(monitoring_log).read()), delimiter='\t'
            )
            rt_attrs = call.get('runtimeAttributes')

            data = {
                'workflow_id': workflow_id,
                'task_name': call_name,
                'shard_idx': call.get('shardIndex'),
                'status': call.get('executionStatus'),
                'attempt': call.get('attempt'),
                'instance': {
                    'cpu': int(rt_attrs.get('cpu')),
                    'disk': parse_cromwell_disks(rt_attrs.get('disks')),
                    'mem': parse_cromwell_memory(rt_attrs.get('memory')),
                },
                'stats': {s: {} for s in stat_methods},
                'input_file_sizes': defaultdict(list),
            }
            for i, col_name in enumerate(dataframe.columns):
                if i in excluded_cols:
                    continue
                for stat_method in stat_methods:
                    if dataframe.empty:
                        val = None
                    elif stat_method == 'last':
                        last_idx = dataframe.tail(1).index.item()
                        val = dataframe[col_name][last_idx]
                    else:
                        val = getattr(dataframe[col_name], stat_method)()
                    data['stats'][stat_method][col_name] = val

            for input_name, input_value in sorted(call['inputs'].items()):
                file_sizes_dict = data['input_file_sizes']

                def add_to_input_files_if_valid(file):
                    nonlocal file_size_cache
                    nonlocal file_sizes_dict
                    nonlocal input_name

                    if GCSURI(file).is_valid:
                        file_size = file_size_cache.get(file)
                        if file_size is None:
                            file_size = GCSURI(file).size
                            file_size_cache[file] = file_size
                        file_sizes_dict[input_name].append(file_size)

                recurse_dict_value(input_value, add_to_input_files_if_valid)

            result.append(data)

        self.recurse_calls(gcp_monitor_call)

        # a bit hacky way to recursively convert numpy type into python type
        json_str = json.dumps(result, default=convert_type_np_to_py)
        return json.loads(json_str)

    def cleanup(
        self, dry_run=False, num_threads=URIBase.DEFAULT_NUM_THREADS, no_lock=False
    ):
        """Cleans up workflow's root output directory.

        Args:
            dry_run:
                Dry-run mode.
            num_threads:
                For outputs on cloud buckets only.
                Number of threads for deleting individual outputs on cloud buckets in parallel.
                Generates one client per thread. This works like `gsutil -m rm -rf`.
            no_lock:
                No file locking.
        """
        root = self._metadata.get('workflowRoot')
        if root is None:
            logger.error(
                'workflowRoot not found in metadata JSON. '
                'Cannot proceed to cleanup outputs.'
            )
            return

        if AbsPath(root).is_valid:
            # num_threads is not available for AbsPath().rmdir()
            AbsPath(root).rmdir(dry_run=dry_run, no_lock=no_lock)
        else:
            AutoURI(root).rmdir(
                dry_run=dry_run, no_lock=no_lock, num_threads=num_threads
            )
