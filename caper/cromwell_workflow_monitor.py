import logging
import re
import time
from collections import defaultdict

from .cromwell_metadata import CromwellMetadata
from .cromwell_rest_api import CromwellRestAPI

logger = logging.getLogger(__name__)


class CromwellWorkflowMonitor:
    """Class constants include several regular expressions to catch
    status changes of workflow/task by Cromwell's STDERR.
    """

    RE_WORKFLOW_SUBMITTED = r'workflow (\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b) submitted'
    RE_WORKFLOW_START = r'started WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)'
    RE_WORKFLOW_FINISH = r'WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b) is in a terminal state'
    RE_WORKFLOW_FAILED = r'Workflow (\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b) failed'
    RE_WORKFLOW_ABORT_REQUESTED = r'Abort requested for workflow (\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)\.'
    RE_CROMWELL_SERVER_START = r'Cromwell \d+ service started on'
    RE_TASK_START = r'\[UUID\((\b[0-9a-f]{8})\)(.+):(\d+):(\d+)\]: job id: (\d+)'
    RE_TASK_STATUS = (
        r'\[UUID\((\b[0-9a-f]{8})\)(.+):(\d+):(\d+)\]: Status change from (.+) to (.+)'
    )
    MAX_RETRY_UPDATE_METADATA = 3
    SEC_INTERVAL_RETRY_UPDATE_METADATA = 10.0
    DEFAULT_SERVER_HOSTNAME = 'localhost'
    DEFAULT_SERVER_PORT = 8000

    def __init__(
        self,
        is_server=False,
        server_hostname=DEFAULT_SERVER_HOSTNAME,
        server_port=DEFAULT_SERVER_PORT,
        embed_subworkflow=False,
        on_status_change=None,
        on_server_start=None,
    ):
        """Parses STDERR from Cromwell to updates workflow/task information.
        Also, write/update metadata.json on each workflow's root directory.

        Args:
            is_server:
                Cromwell server mode. metadata JSON file update is available
                for server mode only.
                It tries to write/update metadata JSON file on workflow's
                root directory when there is any status change of it.
            metadata_basename:
                Basename for metadata JSON file to be written on each workflow's
                root directory.
            server_hostname:
                Cromwell server hostname for Cromwell REST API.
                This is used to get metadata JSON of a workflow.
            server_hostname:
                Cromwell server port for Cromwell REST API.
                This is used to get metadata JSON of a workflow.
            embed_subworkflow:
                Whenever there is any status change of workflow (or any of it's tasks)
                It tries to write/update metadata JSON file on workflow's root.
                For this metadata JSON file, embed subworkflow's metadata JSON in it.
                If this is turned off, then metadata JSON will just have subworkflow's ID.
            on_status_change:
                Callback function called on any workflow/task status change.
                This should take one parameter (workflow's metadata dict).
                You can parse this dict to get status of workflow and all its task.
                For example,
                    metadata['status']: to get status of a workflow,
                    metadata['id']: to get workflow's ID,
                    metadata['calls']: to get access to list of each task's dict.
                    ...
            on_server_start:
                Callback function called on server start.
                This function should not take parameter.
        """
        self._is_server = is_server

        if self._is_server:
            self._cromwell_rest_api = CromwellRestAPI(
                hostname=server_hostname, port=server_port
            )
        else:
            self._cromwell_rest_api = None

        self._embed_subworkflow = embed_subworkflow
        self._on_status_change = on_status_change
        self._on_server_start = on_server_start

        self._workflows = defaultdict(dict)
        self._tasks = defaultdict(lambda: defaultdict(dict))
        self._is_server_started = False
        self._stderr_buffer = ''

    def is_server_started(self):
        return self._is_server_started

    def get_workflows(self):
        """Returns a dict with workflow_id and status:
        {
            WORKFLOW_ID: {
                'status': STATUS
            }
        }

        STATUS:
            - Submitted
            - Running
            - Failed
            - Succeeded
        """
        return self._workflows

    def get_tasks(self):
        """Returns a dict with workflows_id and tasks with status:
        {
            WORKFLOW_ID: {
                (TASK_NAME, SHARD_IDX): {
                    'status': STATUS,
                    'job_id': JOB_ID
                }
            }
        }

        STATUS:
            - WaitingForReturnCode
            - Done
        """
        return self._tasks

    def update(self, stderr):
        """Update workflows by parsing Cromwell's stderr.

        This method will pass only full lines with a newline character \\n in stderr.
        Therefore, any string without newline character is kept until next update
        in a member variable _stderr_buffer and this will be used in the next update.

        This is because methods self._update_*(stderr) can only parse a full line (regex).
        For example, one sentence can be split into two consecutive stderrs.
        This examples shows starting of two workflows.
            1st stderr: 'Workflow started WORKFLOW_ID1\\nWorkflow star'
            2nd stderr: 'ted WORLFLOW_ID2\\n'
        'Workflow started WORKFLOW_ID1\\n' is processed in the first update() and 'Workflow star'
        is kept in the buffer. In the next update where 'ted WORLFLOW_ID2\\n' is coming in stderr.
        'Workflow star' in the buffer is prepended to the second stderr and buffer is cleaned.

        Args:
            stderr:
                stderr from Cromwell.
        """
        split = (self._stderr_buffer + stderr).split('\n')
        stderr = '\n'.join(split[0:-1])
        self._stderr_buffer = split[-1]

        if self._is_server:
            self._update_server_start(stderr)

        updated_workflows = set()
        updated_workflows.union(self._update_workflows(stderr))
        updated_workflows.union(self._update_tasks(stderr))

        for w in updated_workflows:
            self._update_metadata(w)

    def _update_server_start(self, stderr):
        if not self._is_server_started:
            for line in stderr.split('\n'):
                r1 = re.findall(CromwellWorkflowMonitor.RE_CROMWELL_SERVER_START, line)
                if len(r1) > 0:
                    self._is_server_started = True
                    if self._on_server_start:
                        self._on_server_start()
                    logger.info('Cromwell server started. Ready to take submissions.')
                    break
        return

    def _update_workflows(self, stderr):
        """Workflow statuses:
            - Submitted
            - Running
            - Failed
            - Succeeded
        """
        updated_workflows = set()
        for line in stderr.split('\n'):
            r = re.findall(CromwellWorkflowMonitor.RE_WORKFLOW_SUBMITTED, line)
            if len(r) > 0:
                wf_id = r[0].strip()
                self._workflows[wf_id]['status'] = 'Submitted'
                updated_workflows.add(wf_id)
                logger.info(
                    'Workflow status change: id={id}, status={status}'.format(
                        id=wf_id, status='Submitted'
                    )
                )

            r = re.findall(CromwellWorkflowMonitor.RE_WORKFLOW_START, line)
            if len(r) > 0:
                wf_id = r[0].strip()
                self._workflows[wf_id]['status'] = 'Running'
                updated_workflows.add(wf_id)
                logger.info(
                    'Workflow status change: id={id}, status={status}'.format(
                        id=wf_id, status='Running'
                    )
                )

            r = re.findall(CromwellWorkflowMonitor.RE_WORKFLOW_FAILED, line)
            if len(r) > 0:
                wf_id = r[0].strip()
                self._workflows[wf_id]['status'] = 'Failed'
                updated_workflows.add(wf_id)
                logger.info(
                    'Workflow status change: id={id}, status={status}'.format(
                        id=wf_id, status='Failed'
                    )
                )

            r = re.findall(CromwellWorkflowMonitor.RE_WORKFLOW_ABORT_REQUESTED, line)
            if len(r) > 0:
                wf_id = r[0].strip()
                self._workflows[wf_id]['status'] = 'Aborting'
                updated_workflows.add(wf_id)
                logger.info(
                    'Workflow status change: id={id}, status={status}'.format(
                        id=wf_id, status='Aborting'
                    )
                )

            r = re.findall(CromwellWorkflowMonitor.RE_WORKFLOW_FINISH, line)
            if len(r) > 0:
                wf_id = r[0].strip()
                w = self._workflows[wf_id]
                if 'status' in w:
                    if w['status'] == 'Aborting':
                        w['status'] = 'Aborted'
                        updated_workflows.add(wf_id)
                        logger.info(
                            'Workflow status change: id={id}, status={status}'.format(
                                id=wf_id, status='Aborted'
                            )
                        )
                    elif w['status'] == 'Failed':
                        pass
                    else:
                        w['status'] = 'Succeeded'
                        updated_workflows.add(wf_id)
                        logger.info(
                            'Workflow status change: id={id}, status={status}'.format(
                                id=wf_id, status='Succeeded'
                            )
                        )

        return updated_workflows

    def _update_tasks(self, stderr):
        """Task statuses:
            - WaitingForReturnCode
            - Done
        """
        updated_workflows = set()
        for line in stderr.split('\n'):
            r = re.findall(CromwellWorkflowMonitor.RE_TASK_START, line)
            if len(r) > 0:
                short_id, task_name = r[0], r[1]
                shard_idx = -1 if r[2] == 'NA' else int(r[1])
                job_id = r[4]
                wf_id = self._find_workflow_id_by_short_id(short_id)
                t = self._tasks[wf_id][(task_name, shard_idx)]
                t['job_id'] = job_id
                t['status'] = 'WaitingForReturnCode'
                updated_workflows.add(wf_id)

            r = re.findall(CromwellWorkflowMonitor.RE_TASK_STATUS, line)
            if len(r) > 0:
                short_id, task_name = r[0], r[1]
                shard_idx = -1 if r[2] == 'NA' else int(r[1])
                status = r[5]
                wf_id = self._find_workflow_id_by_short_id(short_id)
                t = self._tasks[wf_id][(task_name, shard_idx)]
                t['status'] = status
                updated_workflows.add(wf_id)

        return updated_workflows

    def _update_metadata(self, workflow_id):
        """Update metadata on Cromwell'e exec root.
        """
        if not self._is_server:
            return

        metadata = None
        for trial in range(CromwellWorkflowMonitor.MAX_RETRY_UPDATE_METADATA + 1):
            try:
                time.sleep(CromwellWorkflowMonitor.SEC_INTERVAL_RETRY_UPDATE_METADATA)
                metadata = self._cromwell_rest_api.get_metadata(
                    workflow_ids=[workflow_id],
                    embed_subworkflow=self._embed_subworkflow,
                )[0]
                if self._on_status_change:
                    self._on_status_change(metadata)
                cm = CromwellMetadata(metadata)
                cm.write_on_workflow_root()
            except Exception:
                logger.error(
                    'Failed to retrieve metadata from Cromwell server. '
                    'trial={t}, id={wf_id}'.format(t=trial, wf_id=workflow_id)
                )
                continue
            break

    def _find_workflow_id_by_short_id(self, short_id):
        for w in self._workflows:
            if w.startswith(short_id):
                return w
