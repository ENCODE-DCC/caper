import fnmatch
import io
import logging
from uuid import UUID

import requests

from .cromwell_metadata import CromwellMetadata

logger = logging.getLogger(__name__)


def requests_error_handler(func):
    """Re-raise ConnectionError with help message.
    Re-raise from None to hide nested tracebacks.
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.ConnectionError as err:
            message = (
                '{err}\n\n'
                'Failed to connect to Cromwell server. '
                'Check if Caper server is running. '
                'Also check if hostname and port are correct. '
                'method={method}, '
                'url={url}'.format(
                    err=err, method=err.request.method, url=err.request.url
                )
            )
            raise requests.exceptions.ConnectionError(message) from None

    return wrapper


def is_valid_uuid(workflow_id, version=4):
    """To validate Cromwell's UUID (lowercase only).
    This does not allow uppercase UUIDs.
    """
    if not isinstance(workflow_id, str):
        return False
    if workflow_id.lower() != workflow_id:
        return False

    try:
        UUID(workflow_id, version=version)
    except ValueError:
        return False
    return True


def has_wildcard(str_or_array):
    """Check if string or any element in list/tuple has a wildcard.
    """
    if str_or_array is None:
        return False
    if isinstance(str_or_array, (list, tuple)):
        for val in str_or_array:
            if '?' in val or '*' in val:
                return True
        return False
    else:
        return '?' in str_or_array or '*' in str_or_array


class CromwellRestAPI:
    QUERY_URL = 'http://{hostname}:{port}'
    ENDPOINT_BACKEND = '/api/workflows/v1/backends'
    ENDPOINT_WORKFLOWS = '/api/workflows/v1/query'
    ENDPOINT_METADATA = '/api/workflows/v1/{wf_id}/metadata'
    ENDPOINT_LABELS = '/api/workflows/v1/{wf_id}/labels'
    ENDPOINT_SUBMIT = '/api/workflows/v1'
    ENDPOINT_ABORT = '/api/workflows/v1/{wf_id}/abort'
    ENDPOINT_RELEASE_HOLD = '/api/workflows/v1/{wf_id}/releaseHold'
    DEFAULT_HOSTNAME = 'localhost'
    DEFAULT_PORT = 8000

    def __init__(
        self, hostname=DEFAULT_HOSTNAME, port=DEFAULT_PORT, user=None, password=None
    ):
        self._hostname = hostname
        self._port = port

        self._user = user
        self._password = password
        self.__init_auth()

    def submit(
        self,
        source,
        dependencies=None,
        inputs=None,
        options=None,
        labels=None,
        on_hold=False,
    ):
        """Submit a workflow.

        Returns:
            JSON Response from POST request submit a workflow
        """
        manifest = {}
        with open(source) as fp:
            manifest['workflowSource'] = io.StringIO(fp.read())
        if dependencies:
            with open(dependencies, 'rb') as fp:
                manifest['workflowDependencies'] = io.BytesIO(fp.read())
        if inputs:
            with open(inputs) as fp:
                manifest['workflowInputs'] = io.StringIO(fp.read())
        else:
            manifest['workflowInputs'] = io.StringIO('{}')
        if options:
            with open(options) as fp:
                manifest['workflowOptions'] = io.StringIO(fp.read())
        if labels:
            with open(labels) as fp:
                manifest['labels'] = io.StringIO(fp.read())
        if on_hold:
            manifest['workflowOnHold'] = True

        r = self.__request_post(CromwellRestAPI.ENDPOINT_SUBMIT, manifest)
        logger.debug('submit: {r}'.format(r=r))
        return r

    def abort(self, workflow_ids=None, labels=None):
        """Abort workflows matching workflow IDs or labels

        Returns:
            List of JSON responses from POST request
            for aborting workflows
        """
        valid_workflow_ids = self.find_valid_workflow_ids(
            workflow_ids=workflow_ids, labels=labels
        )
        if valid_workflow_ids is None:
            return

        result = []
        for workflow_id in valid_workflow_ids:
            r = self.__request_post(
                CromwellRestAPI.ENDPOINT_ABORT.format(wf_id=workflow_id)
            )
            result.append(r)
        logger.debug('abort: {r}'.format(r=result))
        return result

    def release_hold(self, workflow_ids=None, labels=None):
        """Release hold of workflows matching workflow IDs or labels

        Returns:
            List of JSON responses from POST request
            for releasing hold of workflows
        """
        valid_workflow_ids = self.find_valid_workflow_ids(
            workflow_ids=workflow_ids, labels=labels
        )
        if valid_workflow_ids is None:
            return

        result = []
        for workflow_id in valid_workflow_ids:
            r = self.__request_post(
                CromwellRestAPI.ENDPOINT_RELEASE_HOLD.format(wf_id=workflow_id)
            )
            result.append(r)
        logger.debug('release_hold: {r}'.format(r=result))
        return result

    def get_default_backend(self):
        """Retrieve default backend name

        Returns:
            Default backend name
        """
        return self.get_backends()['defaultBackend']

    def get_backends(self):
        """Retrieve available backend names and default backend name

        Returns:
            JSON response with keys "defaultBackend" and "supportedBackends"
            Example: {"defaultBackend":"Local","supportedBackends":
                      ["Local","aws","gcp","pbs","sge","slurm"]}
        """
        return self.__request_get(CromwellRestAPI.ENDPOINT_BACKEND)

    def find_valid_workflow_ids(
        self, workflow_ids=None, labels=None, exclude_subworkflow=True
    ):
        """Checks if workflow ID in `workflow_ids` are already valid UUIDs (without wildcards).
        If so then we don't have to send the server a query to get matching workflow IDs.
        """
        if not labels and workflow_ids and all(is_valid_uuid(i) for i in workflow_ids):
            return workflow_ids
        else:
            workflows = self.find(
                workflow_ids=workflow_ids,
                labels=labels,
                exclude_subworkflow=exclude_subworkflow,
            )
            if not workflows:
                return
            return [w['id'] for w in workflows]

    def get_metadata(self, workflow_ids=None, labels=None, embed_subworkflow=False):
        """Retrieve metadata for workflows matching workflow IDs or labels

        Args:
            workflow_ids:
                List of workflows IDs to find workflows matched.
            labels:
                List of Caper's string labels to find workflows matched.
            embed_subworkflow:
                Recursively embed subworkflow's metadata in main
                workflow's metadata.
                This flag is to mimic behavior of Cromwell run mode with -m.
                Metadata JSON generated with Cromwell run mode
                includes all subworkflows embedded in main workflow's JSON file.
        """
        valid_workflow_ids = self.find_valid_workflow_ids(
            workflow_ids=workflow_ids, labels=labels
        )
        if valid_workflow_ids is None:
            return

        result = []
        for workflow_id in valid_workflow_ids:
            params = {}
            if embed_subworkflow:
                params['expandSubWorkflows'] = True

            m = self.__request_get(
                CromwellRestAPI.ENDPOINT_METADATA.format(wf_id=workflow_id),
                params=params,
            )
            cm = CromwellMetadata(m)
            result.append(cm.metadata)
        return result

    def get_labels(self, workflow_id):
        """Get labels JSON for a specified workflow

        Returns:
            Labels JSON for a workflow
        """
        if workflow_id is None or not is_valid_uuid(workflow_id):
            return

        r = self.__request_get(
            CromwellRestAPI.ENDPOINT_LABELS.format(wf_id=workflow_id)
        )
        if r is None:
            return
        return r['labels']

    def get_label(self, workflow_id, key):
        """Get a label for a key in a specified workflow

        Returns:
            Value for a specified key in labels JSON for a workflow
        """
        labels = self.get_labels(workflow_id)
        if labels is None:
            return
        if key in labels:
            return labels[key]

    def update_labels(self, workflow_id, labels):
        """Update labels for a specified workflow with
        a list of (key, val) tuples
        """
        if workflow_id is None or labels is None:
            return
        r = self.__request_patch(
            CromwellRestAPI.ENDPOINT_LABELS.format(wf_id=workflow_id), labels
        )
        logger.debug('update_labels: {r}'.format(r=r))
        return r

    def find(self, workflow_ids=None, labels=None, exclude_subworkflow=True):
        """Find workflows by matching workflow IDs, label (key, value) tuples.
        Invalid UUID in `workflows_ids` will be ignored with warning.
        Does OR search for both parameters.

        IMPORTANT:
            Wildcards (? and *) are allowed for both parameters.
            If wildcards are given for any item in `workflows_ids` or `labels`
            then Caper retrieves a full list of all workflows and try to find matched,
            which can result in HTTP 503 error (Service Unavailable).
        Args:
            workflow_ids:
                Workflow ID string or list of ID strings.
                OR search for multiple workflow IDs.
                Wild cards (? and *) are not allowed.
            labels:
                (key, val) tuple or list of tuples.
                OR search for multiple tuples.
                then Caper will costly request for a list of all workflows on the server.
            exclude_subworkflow:
                Exclude subworkflows.
        Returns:
            List of matched workflow JSONs.
        """
        wildcard_found = has_wildcard(workflow_ids) or has_wildcard(
            [v for k, v in labels] if labels else None
        )
        params = {
            'additionalQueryResultFields': 'labels',
            'includeSubworkflows': not exclude_subworkflow,
        }

        result = []
        if not wildcard_found:
            if workflow_ids:
                # exclude any invalid workflow UUID
                workflow_ids = [wf_id for wf_id in workflow_ids if is_valid_uuid(wf_id)]
            if workflow_ids:
                resp_by_workflow_ids = self.__request_get(
                    CromwellRestAPI.ENDPOINT_WORKFLOWS,
                    params={**params, 'id': workflow_ids},
                )
                if resp_by_workflow_ids and resp_by_workflow_ids['results']:
                    result.extend(resp_by_workflow_ids['results'])

            if labels:
                resp_by_labels = self.__request_get(
                    CromwellRestAPI.ENDPOINT_WORKFLOWS,
                    params={
                        **params,
                        'labelor': [
                            '{key}:{val}'.format(key=key, val=val)
                            for key, val in labels
                        ],
                    },
                )
                if resp_by_labels and resp_by_labels['results']:
                    result.extend(resp_by_labels['results'])
        else:
            # if wildcard found, then retrieve information of all workflows
            # and find matching workflows by ID or labels.
            resp = self.__request_get(CromwellRestAPI.ENDPOINT_WORKFLOWS, params=params)
            if resp and resp['results']:
                matched_workflow_ids = set()
                for workflow in resp['results']:
                    if 'id' not in workflow:
                        continue
                    if workflow_ids:
                        for wf_id in workflow_ids:
                            if fnmatch.fnmatchcase(workflow['id'], wf_id):
                                matched_workflow_ids.add(workflow['id'])
                                break
                    if workflow['id'] in matched_workflow_ids:
                        continue
                    if labels and 'labels' in workflow:
                        labels_ = workflow['labels']
                        for k, v in labels:
                            if k in labels_:
                                v_ = labels_[k]
                                if isinstance(v_, str) and isinstance(v, str):
                                    # wildcard allowed for str values
                                    if fnmatch.fnmatchcase(v_, v):
                                        matched_workflow_ids.add(workflow['id'])
                                        break
                                elif v_ == v:
                                    matched_workflow_ids.add(workflow['id'])
                                    break

                for workflow in resp['results']:
                    if 'id' not in workflow:
                        continue
                    if workflow['id'] in matched_workflow_ids:
                        result.append(workflow)
        logger.debug(
            'find: has_wildcard={has_wildcard},'
            'workflow_ids={workflow_ids}, labels={labels}, '
            'result={result}'.format(
                has_wildcard=wildcard_found,
                workflow_ids=workflow_ids,
                labels=labels,
                result=result,
            )
        )
        return result

    def __init_auth(self):
        """Init auth object
        """
        if self._user is not None and self._password is not None:
            self._auth = (self._user, self._password)
        else:
            self._auth = None

    @requests_error_handler
    def __request_get(self, endpoint, params=None):
        """GET request

        Returns:
            JSON response
        """
        url = (
            CromwellRestAPI.QUERY_URL.format(hostname=self._hostname, port=self._port)
            + endpoint
        )
        resp = requests.get(
            url, auth=self._auth, params=params, headers={'accept': 'application/json'}
        )
        resp.raise_for_status()
        return resp.json()

    @requests_error_handler
    def __request_post(self, endpoint, manifest=None):
        """POST request

        Returns:
            JSON response
        """
        url = (
            CromwellRestAPI.QUERY_URL.format(hostname=self._hostname, port=self._port)
            + endpoint
        )
        resp = requests.post(
            url, files=manifest, auth=self._auth, headers={'accept': 'application/json'}
        )
        resp.raise_for_status()
        return resp.json()

    @requests_error_handler
    def __request_patch(self, endpoint, data):
        """POST request

        Returns:
            JSON response
        """
        url = (
            CromwellRestAPI.QUERY_URL.format(hostname=self._hostname, port=self._port)
            + endpoint
        )
        resp = requests.patch(
            url,
            data=data,
            auth=self._auth,
            headers={'accept': 'application/json', 'content-type': 'application/json'},
        )
        resp.raise_for_status()
        return resp.json()
