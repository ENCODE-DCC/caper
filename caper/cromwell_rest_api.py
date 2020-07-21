import fnmatch
import io
import logging

import requests

from .cromwell_metadata import CromwellMetadata

logger = logging.getLogger(__name__)


class CromwellRestAPI:
    QUERY_URL = 'http://{hostname}:{port}'
    ENDPOINT_BACKEND = '/api/workflows/v1/backends'
    ENDPOINT_WORKFLOWS = '/api/workflows/v1/query'
    ENDPOINT_METADATA = '/api/workflows/v1/{wf_id}/metadata'
    ENDPOINT_LABELS = '/api/workflows/v1/{wf_id}/labels'
    ENDPOINT_SUBMIT = '/api/workflows/v1'
    ENDPOINT_ABORT = '/api/workflows/v1/{wf_id}/abort'
    ENDPOINT_RELEASE_HOLD = '/api/workflows/v1/{wf_id}/releaseHold'
    PARAMS_WORKFLOWS = {'additionalQueryResultFields': 'labels'}
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
        workflows = self.find(workflow_ids, labels)
        if workflows is None:
            return
        result = []
        for w in workflows:
            r = self.__request_post(
                CromwellRestAPI.ENDPOINT_ABORT.format(wf_id=w['id'])
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
        workflows = self.find(workflow_ids, labels)
        if workflows is None:
            return
        result = []
        for w in workflows:
            r = self.__request_post(
                CromwellRestAPI.ENDPOINT_RELEASE_HOLD.format(wf_id=w['id'])
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
        workflows = self.find(workflow_ids, labels)
        if workflows is None:
            return
        result = []
        for w in workflows:
            m = self.__request_get(
                CromwellRestAPI.ENDPOINT_METADATA.format(wf_id=w['id'])
            )
            cm = CromwellMetadata(m)
            if embed_subworkflow:
                cm.recurse_calls(
                    lambda call_name, call, parent_call_names: self.__embed_subworkflow(
                        call_name, call, parent_call_names
                    )
                )
            result.append(cm.metadata)
        return result

    def __embed_subworkflow(self, call_name, call, parent_call_names):
        if 'subWorkflowId' in call:
            call['subWorkflowMetadata'] = self.get_metadata(
                workflow_ids=[call['subWorkflowId']], embed_subworkflow=True
            )[0]

    def get_labels(self, workflow_id):
        """Get labels JSON for a specified workflow

        Returns:
            Labels JSON for a workflow
        """
        if workflow_id is None:
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

    def find(self, workflow_ids=None, labels=None, embed_subworkflow=False):
        """Find workflows by matching workflow IDs, label (key, value) tuples.
        Wildcards (? and *) are allowed for string workflow IDs and values in
        a tuple label. Search criterion is (workflow_ids OR labels).

        Args:
            workflow_ids:
                List of workflows ID strings: [wf_id, ...].
                OR search for multiple workflow IDs
            labels:
                List of (key, val) tuples: [(key: val), (key2: val2), ...].
                OR search for multiple tuples
            embed_subworkflow:
                Embed subworkflows in main workflow's metadata dict.

        Returns:
            List of matched workflow JSONs
        """
        r = self.__request_get(
            CromwellRestAPI.ENDPOINT_WORKFLOWS, params=CromwellRestAPI.PARAMS_WORKFLOWS
        )
        if r is None:
            return
        workflows = r['results']
        if workflows is None:
            return
        matched = set()
        for w in workflows:
            if 'id' not in w:
                continue
            if workflow_ids is not None:
                for wf_id in workflow_ids:
                    if fnmatch.fnmatchcase(w['id'], wf_id):
                        matched.add(w['id'])
                        break
            if w['id'] in matched:
                continue
            if labels is not None and 'labels' in w:
                labels_ = w['labels']
                for k, v in labels:
                    if k in labels_:
                        v_ = labels_[k]
                        if isinstance(v_, str) and isinstance(v, str):
                            # wildcard allowed for str values
                            if fnmatch.fnmatchcase(v_, v):
                                matched.add(w['id'])
                                break
                        elif v_ == v:
                            matched.add(w['id'])
                            break
        result = []
        for w in workflows:
            if 'id' not in w:
                continue
            if w['id'] in matched:
                if embed_subworkflow:
                    self.__embed_subworkflow(w)
                result.append(w)
        logger.debug('find: {r}'.format(r=result))
        return result

    def __init_auth(self):
        """Init auth object
        """
        if self._user is not None and self._password is not None:
            self._auth = (self._user, self._password)
        else:
            self._auth = None

    def __request_get(self, endpoint, params=None):
        """GET request

        Returns:
            JSON response
        """
        url = (
            CromwellRestAPI.QUERY_URL.format(hostname=self._hostname, port=self._port)
            + endpoint
        )
        try:
            resp = requests.get(
                url,
                auth=self._auth,
                params=params,
                headers={'accept': 'application/json'},
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException:
            raise Exception(
                'Failed to connect to Cromwell server. req=GET, url={url}'.format(
                    url=url
                )
            ) from None
        return resp.json()

    def __request_post(self, endpoint, manifest=None):
        """POST request

        Returns:
            JSON response
        """
        url = (
            CromwellRestAPI.QUERY_URL.format(hostname=self._hostname, port=self._port)
            + endpoint
        )
        try:
            resp = requests.post(
                url,
                files=manifest,
                auth=self._auth,
                headers={'accept': 'application/json'},
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException:
            raise Exception(
                'Failed to connect to Cromwell server. req=POST, url={url}'.format(
                    url=url
                )
            ) from None
        return resp.json()

    def __request_patch(self, endpoint, data):
        """POST request

        Returns:
            JSON response
        """
        url = (
            CromwellRestAPI.QUERY_URL.format(hostname=self._hostname, port=self._port)
            + endpoint
        )
        try:
            resp = requests.patch(
                url,
                data=data,
                auth=self._auth,
                headers={
                    'accept': 'application/json',
                    'content-type': 'application/json',
                },
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException:
            raise Exception(
                'Failed to connect to Cromwell server. req=PATCH, url={url}'.format(
                    url=url
                )
            ) from None
        return resp.json()
