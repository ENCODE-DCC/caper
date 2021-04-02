import logging
import re
import time

from .cromwell_metadata import CromwellMetadata
from .cromwell_rest_api import CromwellRestAPI

logger = logging.getLogger(__name__)


class WorkflowStatusTransition:
    def __init__(self, regex, status_transitions, auto_write_metadata=False):
        """
        Args:
            regex:
                Regular expression to catch workflow's status transition from
                a string (Cromwell's stderr).
                This reg-ex should have only one group which can catch
                workflow's string UUID.
            status_transitions:
                List (or tuple) of possible status transitions.
                Transition is defined by a tuple of previous and next
                statuses where each status is a plain string.
                e.g. [('Submitted', 'Running'),]
                Iterating over this list, only the first valid transition,
                where a previous status is matched, found will be used.
        """
        self._regex = regex
        self._status_transitions = status_transitions
        self._auto_write_metadata = auto_write_metadata

    def parse(self, line, workflow_status_map):
        """
        Args:
            line:
                Line to be parsed to catch status transition.
            workflow_status_map:
                Dict of workflow_id (key) and previus_status (value) pairs.
                This is used to get previous status of a workflow.
                If None then previous status will be ignored.
        Returns:
            workflow_id:
                Workflow's string ID.
            status:
                New status after transition.
            auto_write_metadata:
                For this status transition metadataJSON file should be written
                on workflow's root output directory.
        """
        r = re.findall(self._regex, line)
        if r:
            wf_id = r[0].strip()
            if wf_id in workflow_status_map:
                prev_status = workflow_status_map[wf_id]
            else:
                prev_status = None
            for st1, st2 in self._status_transitions:
                if st1 is None or st1 == prev_status:
                    if st1 != st2:
                        logger.info(
                            'Workflow: id={id}, status={status}'.format(
                                id=wf_id, status=st2
                            )
                        )
                        return wf_id, st2, self._auto_write_metadata
                    break
        return None, None, False


class CromwellWorkflowMonitor:
    """Class constants include several regular expressions to catch
    status changes of workflow/task by Cromwell's STDERR (logging level>=INFO).
    """

    ALL_STATUS_TRANSITIONS = (
        WorkflowStatusTransition(
            regex=r'workflow (\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b) submitted',
            status_transitions=((None, 'Submitted'),),
        ),
        WorkflowStatusTransition(
            regex=r'started WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)',
            status_transitions=((None, 'Running'),),
        ),
        WorkflowStatusTransition(
            regex=r'Workflow (\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b) failed',
            status_transitions=((None, 'Failed'),),
        ),
        WorkflowStatusTransition(
            regex=r'Abort requested for workflow (\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)\.',
            status_transitions=((None, 'Aborting'),),
        ),
        WorkflowStatusTransition(
            regex=r'WorkflowActor-(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b) is in a terminal state',
            status_transitions=(
                ('Failed', 'Failed'),
                ('Aborting', 'Aborted'),
                (None, 'Succeeded'),
            ),
            auto_write_metadata=True,
        ),
        WorkflowStatusTransition(
            regex=r'Workflow actor for (\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b) completed with status',
            status_transitions=(
                ('Failed', 'Failed'),
                ('Aborting', 'Aborted'),
                (None, 'Succeeded'),
            ),
            auto_write_metadata=True,
        ),
    )

    RE_CROMWELL_SERVER_START = r'Cromwell \d+ service started on'
    RE_TASK_START = r'\[UUID\((\b[0-9a-f]{8})\)(.+):(.+):(\d+)\]: job id: (.+)'
    RE_TASK_STATUS_CHANGE = (
        r'\[UUID\((\b[0-9a-f]{8})\)(.+):(.+):(\d+)\]: Status change from (.+) to (.+)'
    )
    RE_TASK_CALL_CACHED = r'\[UUID\((\b[0-9a-f]{8})\)\]: Job results retrieved \(CallCached\): \'(.+)\' \(scatter index: (.+), attempt (\d+)\)'
    RE_SUBWORKFLOW_FOUND = r'(\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)-SubWorkflowActor-SubWorkflow'

    MAX_RETRY_WRITE_METADATA = 3
    INTERVAL_RETRY_WRITE_METADATA = 10.0
    DEFAULT_SERVER_HOSTNAME = 'localhost'
    DEFAULT_SERVER_PORT = 8000

    def __init__(
        self,
        is_server=False,
        server_hostname=DEFAULT_SERVER_HOSTNAME,
        server_port=DEFAULT_SERVER_PORT,
        embed_subworkflow=False,
        auto_write_metadata=False,
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
                Whenever there is any status change of workflow (or any of its tasks)
                It tries to write/update metadata JSON file on workflow's root.
                For this metadata JSON file, embed subworkflow's metadata JSON in it.
                If this is turned off, then metadata JSON will just have subworkflow's ID.
            auto_write_metadata:
                This is server-only feature. For any change of workflow's status,
                automatically updates metadata JSON file on workflow's root directory.
                metadata JSON is retrieved by communicating with Cromwell server via
                REST API.
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
        self._auto_write_metadata = auto_write_metadata
        self._on_status_change = on_status_change
        self._on_server_start = on_server_start

        self._workflow_status_map = dict()
        self._subworkflows = set()
        self._is_server_started = False

    def is_server_started(self):
        return self._is_server_started

    def update(self, stderr):
        """Update workflows by parsing Cromwell's stderr.

        Args:
            stderr:
                stderr from Cromwell.
                Should be a full line (or lines) ending with blackslash n.
        """
        if self._is_server:
            self._update_server_start(stderr)

        updated_workflows, workflows_to_write_metadata = self._update_workflows(stderr)
        self._update_subworkflows(stderr)
        self._update_tasks(stderr)

        for w in workflows_to_write_metadata:
            self._write_metadata(w)

    def _update_server_start(self, stderr):
        if not self._is_server_started:
            for line in stderr.split('\n'):
                r1 = re.findall(CromwellWorkflowMonitor.RE_CROMWELL_SERVER_START, line)
                if r1:
                    self._is_server_started = True
                    if self._on_server_start:
                        self._on_server_start()
                    logger.info('Cromwell server started. Ready to take submissions.')
                    break

    def _update_workflows(self, stderr):
        """Updates workflow status by parsing Cromwell's stderr lines.
        """
        updated_workflows = set()
        workflows_to_write_metadata = set()
        for line in stderr.split('\n'):
            for st_transitions in CromwellWorkflowMonitor.ALL_STATUS_TRANSITIONS:
                workflow_id, status, auto_write_metadata = st_transitions.parse(
                    line, self._workflow_status_map
                )
                if workflow_id:
                    self._workflow_status_map[workflow_id] = status
                    updated_workflows.add(workflow_id)
                    if auto_write_metadata:
                        workflows_to_write_metadata.add(workflow_id)

        return updated_workflows, workflows_to_write_metadata

    def _update_subworkflows(self, stderr):
        for line in stderr.split('\n'):
            r_sub = re.findall(CromwellWorkflowMonitor.RE_SUBWORKFLOW_FOUND, line)
            if r_sub:
                subworkflow_id = r_sub[0]
                if subworkflow_id not in self._subworkflows:
                    logger.info('Subworkflow found: {id}'.format(id=subworkflow_id))
                self._subworkflows.add(subworkflow_id)

    def _update_tasks(self, stderr):
        """Check if workflow's task status changed by parsing Cromwell's stderr lines.
        """
        for line in stderr.split('\n'):
            r_common = None
            r_start = re.findall(CromwellWorkflowMonitor.RE_TASK_START, line)
            if r_start:
                r_common = r_start[0]
                status = 'Started'
                job_id = r_common[4]

            r_callcached = re.findall(CromwellWorkflowMonitor.RE_TASK_CALL_CACHED, line)
            if r_callcached:
                r_common = r_callcached[0]
                status = 'CallCached'
                job_id = None

            r_status_change = re.findall(
                CromwellWorkflowMonitor.RE_TASK_STATUS_CHANGE, line
            )
            if r_status_change:
                r_common = r_status_change[0]
                status = r_common[5]
                job_id = None

            if r_common:
                short_id = r_common[0]
                workflow_id = self._find_workflow_id_from_short_id(short_id)
                task_name = r_common[1]
                shard_idx = r_common[2]
                try:
                    shard_idx = int(shard_idx)
                except ValueError:
                    shard_idx = -1
                retry = int(r_common[3])

                msg = 'Task: id={id}, task={name}:{shard_idx}, retry={retry}, status={status}'.format(
                    id=workflow_id,
                    name=task_name,
                    shard_idx=shard_idx,
                    retry=retry - 1,
                    status=status,
                )
                if job_id:
                    msg += ', job_id={job_id}'.format(job_id=job_id)
                logger.info(msg)

    def _find_workflow_id_from_short_id(self, short_id):
        for w in self._subworkflows.union(set(self._workflow_status_map.keys())):
            if w.startswith(short_id):
                return w

    def _write_metadata(self, workflow_id):
        """Update metadata on Cromwell'e exec root.
        """
        if not self._is_server or not self._auto_write_metadata:
            return
        if workflow_id in self._subworkflows and self._embed_subworkflow:
            logger.debug(
                'Skipped writing metadata JSON file of subworkflow {wf_id}'.format(
                    wf_id=workflow_id
                )
            )
            return
        for trial in range(CromwellWorkflowMonitor.MAX_RETRY_WRITE_METADATA + 1):
            try:
                time.sleep(CromwellWorkflowMonitor.INTERVAL_RETRY_WRITE_METADATA)
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
