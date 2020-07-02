import logging
import re
import time

from .cromwell_metadata import CromwellMetadata
from .cromwell_rest_api import CromwellRestAPI

logger = logging.getLogger(__name__)


class CromwellWorkflowMonitor:
    """Class constants include several regular expressions to catch
    status changes of workflow/task by Cromwell's STDERR (logging level>=INFO).
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
    INTERVAL_RETRY_UPDATE_METADATA = 10.0
    DEFAULT_SERVER_HOSTNAME = 'localhost'
    DEFAULT_SERVER_PORT = 8000

    def __init__(
        self,
        is_server=False,
        server_hostname=DEFAULT_SERVER_HOSTNAME,
        server_port=DEFAULT_SERVER_PORT,
        embed_subworkflow=False,
        auto_update_metadata=False,
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
            auto_update_metadata:
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
        self._auto_update_metadata = auto_update_metadata
        self._on_status_change = on_status_change
        self._on_server_start = on_server_start

        self._wf_statuses = dict()
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

        updated_workflows = set()
        updated_workflows |= self._update_workflows(stderr)
        updated_workflows |= self._update_tasks(stderr)

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
                self._wf_statuses[wf_id] = 'Submitted'
                updated_workflows.add(wf_id)
                logger.info(
                    'Workflow status change: id={id}, status={status}'.format(
                        id=wf_id, status='Submitted'
                    )
                )

            r = re.findall(CromwellWorkflowMonitor.RE_WORKFLOW_START, line)
            if len(r) > 0:
                wf_id = r[0].strip()
                self._wf_statuses[wf_id] = 'Running'
                updated_workflows.add(wf_id)
                logger.info(
                    'Workflow status change: id={id}, status={status}'.format(
                        id=wf_id, status='Running'
                    )
                )

            r = re.findall(CromwellWorkflowMonitor.RE_WORKFLOW_FAILED, line)
            if len(r) > 0:
                wf_id = r[0].strip()
                self._wf_statuses[wf_id] = 'Failed'
                updated_workflows.add(wf_id)
                logger.info(
                    'Workflow status change: id={id}, status={status}'.format(
                        id=wf_id, status='Failed'
                    )
                )

            r = re.findall(CromwellWorkflowMonitor.RE_WORKFLOW_ABORT_REQUESTED, line)
            if len(r) > 0:
                wf_id = r[0].strip()
                self._wf_statuses[wf_id] = 'Aborting'
                updated_workflows.add(wf_id)
                logger.info(
                    'Workflow status change: id={id}, status={status}'.format(
                        id=wf_id, status='Aborting'
                    )
                )

            r = re.findall(CromwellWorkflowMonitor.RE_WORKFLOW_FINISH, line)
            if len(r) > 0:
                wf_id = r[0].strip()
                status = self._wf_statuses[wf_id]
                if status == 'Aborting':
                    status = 'Aborted'
                    updated_workflows.add(wf_id)
                    logger.info(
                        'Workflow status change: id={id}, status={status}'.format(
                            id=wf_id, status=status
                        )
                    )
                elif status == 'Failed':
                    pass
                else:
                    status = 'Succeeded'
                    self._wf_statuses[wf_id] = status
                    updated_workflows.add(wf_id)
                    logger.info(
                        'Workflow status change: id={id}, status={status}'.format(
                            id=wf_id, status=status
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
                short_id = r[0]
                wf_id = self._find_workflow_id_by_short_id(short_id)
                updated_workflows.add(wf_id)

            r = re.findall(CromwellWorkflowMonitor.RE_TASK_STATUS, line)
            if len(r) > 0:
                short_id = r[0]
                wf_id = self._find_workflow_id_by_short_id(short_id)
                updated_workflows.add(wf_id)

        return updated_workflows

    def _update_metadata(self, workflow_id):
        """Update metadata on Cromwell'e exec root.
        """
        if not self._is_server or not self._auto_update_metadata:
            return
        for trial in range(CromwellWorkflowMonitor.MAX_RETRY_UPDATE_METADATA + 1):
            try:
                time.sleep(CromwellWorkflowMonitor.INTERVAL_RETRY_UPDATE_METADATA)
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
        for wf_id in self._wf_statuses:
            if wf_id.startswith(short_id):
                return wf_id
