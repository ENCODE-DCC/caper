#!/usr/bin/env python3
"""CromwellRestAPI
"""

import requests
import io
import fnmatch
import json
import sys
# import traceback


class CromwellRestAPI(object):
    QUERY_URL = 'http://{ip}:{port}'
    ENDPOINT_BACKEND = '/api/workflows/v1/backends'
    ENDPOINT_WORKFLOWS = '/api/workflows/v1/query'
    ENDPOINT_METADATA = '/api/workflows/v1/{wf_id}/metadata'
    ENDPOINT_LABELS = '/api/workflows/v1/{wf_id}/labels'
    ENDPOINT_SUBMIT = '/api/workflows/v1'
    ENDPOINT_ABORT = '/api/workflows/v1/{wf_id}/abort'
    ENDPOINT_RELEASE_HOLD = '/api/workflows/v1/{wf_id}/releaseHold'
    KEY_LABEL = 'cromwell_rest_api_label'

    def __init__(self, ip='localhost', port=8000,
                 user=None, password=None, verbose=False):
        self._verbose = verbose
        self._ip = ip
        self._port = port

        self._user = user
        self._password = password
        self.__init_auth()

    def submit(self, source, dependencies=None, inputs_file=None,
               options_file=None, labels_file=None, on_hold=False):
        """Submit a workflow.

        Returns:
            JSON Response from POST request submit a workflow
        """
        manifest = {}
        manifest['workflowSource'] = \
            CromwellRestAPI.__get_string_io_from_file(source)
        if dependencies is not None:
            manifest['workflowDependencies'] = \
                CromwellRestAPI.__get_bytes_io_from_file(dependencies)
        if inputs_file is not None:
            manifest['workflowInputs'] = \
                CromwellRestAPI.__get_string_io_from_file(inputs_file)
        else:
            manifest['workflowInputs'] = io.StringIO('{}')
        if options_file is not None:
            manifest['workflowOptions'] = \
                CromwellRestAPI.__get_string_io_from_file(options_file)
        if labels_file is not None:
            manifest['labels'] = \
                CromwellRestAPI.__get_string_io_from_file(labels_file)
        if on_hold:
            manifest['workflowOnHold'] = True

        r = self.__request_post(CromwellRestAPI.ENDPOINT_SUBMIT, manifest)
        if self._verbose:
            print("CromwellRestAPI.submit: ", r)
        return r

    def abort(self, workflow_ids=None, labels=None):
        """Abort workflows matching workflow IDs or labels

        Returns:
            List of JSON responses from POST request
            for aborting workflows
        """
        workflows = self.find(workflow_ids, labels)
        if workflows is None:
            return None
        result = []
        for w in workflows:
            r = self.__request_post(
                CromwellRestAPI.ENDPOINT_ABORT.format(
                    wf_id=w['id']))
            result.append(r)
        if self._verbose:
            print("CromwellRestAPI.abort: ", result)
        return result

    def release_hold(self, workflow_ids=None, labels=None):
        """Release hold of workflows matching workflow IDs or labels

        Returns:
            List of JSON responses from POST request
            for releasing hold of workflows
        """
        workflows = self.find(workflow_ids, labels)
        if workflows is None:
            return None
        result = []
        for w in workflows:
            r = self.__request_post(
                CromwellRestAPI.ENDPOINT_RELEASE_HOLD.format(
                    wf_id=w['id']))
            result.append(r)
        if self._verbose:
            print("CromwellRestAPI.release_hold: ", result)
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

    def get_metadata(self, workflow_ids=None, labels=None):
        """Retrieve metadata for workflows matching workflow IDs or labels

        Returns:
            List of metadata JSONs
        """
        workflows = self.find(workflow_ids, labels)
        if workflows is None:
            return None
        result = []
        for w in workflows:
            m = self.__request_get(
                CromwellRestAPI.ENDPOINT_METADATA.format(wf_id=w['id']))
            result.append(m)
        if self._verbose:
            print(json.dumps(result, indent=4))
        return result

    def get_labels(self, workflow_id):
        """Get labels JSON for a specified workflow

        Returns:
            Labels JSON for a workflow
        """
        if workflow_id is None:
            return None
        r = self.__request_get(
            CromwellRestAPI.ENDPOINT_LABELS.format(
                wf_id=workflow_id))
        if r is None:
            return None
        return r['labels']

    def get_label(self, workflow_id, key):
        """Get a label for a key in a specified workflow

        Returns:
            Value for a specified key in labels JSON for a workflow
        """
        labels = self.get_labels(workflow_id)
        if labels is None:
            return None
        if key in labels:
            return labels[key]
        else:
            return None

    def update_labels(self, workflow_id, labels):
        """Update labels for a specified workflow with
        a list of (key, val) tuples
        """
        if workflow_id is None or labels is None:
            return None
        r = self.__request_patch(
            CromwellRestAPI.ENDPOINT_LABELS.format(
                wf_id=workflow_id), labels)
        if self._verbose:
            print("CromwellRestAPI.update_labels: ", r)
        return r

    def find(self, workflow_ids=None, labels=None):
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

        Returns:
            List of matched workflow JSONs
        """
        r = self.__request_get(
            CromwellRestAPI.ENDPOINT_WORKFLOWS)
        if r is None:
            return None
        workflows = r['results']
        if workflows is None:
            return None
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
            if labels is not None:
                labels_ = self.get_labels(w['id'])
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
                result.append(w)
        if self._verbose:
            print('CromwellRestAPI.find: ', result)
        return result

    def __init_auth(self):
        """Init auth object
        """
        if self._user is not None and self._password is not None:
            self._auth = (self._user, self._password)
        else:
            self._auth = None

    def __request_get(self, endpoint):
        """GET request

        Returns:
            JSON response
        """
        url = CromwellRestAPI.QUERY_URL.format(
                ip=self._ip,
                port=self._port) + endpoint
        try:
            resp = requests.get(
                url, auth=self._auth,
                headers={'accept': 'application/json'})
        except Exception as e:
            # traceback.print_exc()
            print(e)
            sys.exit(1)

        if resp.ok:
            return resp.json()
        else:
            print("HTTP GET error: ", resp.status_code, resp.content,
                  url)
            return None

    def __request_post(self, endpoint, manifest=None):
        """POST request

        Returns:
            JSON response
        """
        url = CromwellRestAPI.QUERY_URL.format(
                ip=self._ip,
                port=self._port) + endpoint
        try:
            resp = requests.post(
                url, files=manifest, auth=self._auth,
                headers={'accept': 'application/json'})
        except Exception as e:
            # traceback.print_exc()
            print(e)
            sys.exit(1)

        if resp.ok:
            return resp.json()
        else:
            print("HTTP POST error: ", resp.status_code, resp.content,
                  url, manifest)
            return None

    def __request_patch(self, endpoint, data):
        """POST request

        Returns:
            JSON response
        """
        url = CromwellRestAPI.QUERY_URL.format(
                ip=self._ip,
                port=self._port) + endpoint
        try:
            resp = requests.patch(
                url, data=data, auth=self._auth,
                headers={'accept': 'application/json',
                         'content-type': 'application/json'})
        except Exception as e:
            # traceback.print_exc()
            print(e)
            sys.exit(1)

        if resp.ok:
            return resp.json()
        else:
            print("HTTP PATCH error: ", resp.status_code, resp.content,
                  url, json)
            return None

    @staticmethod
    def __get_string_io_from_file(fname):
        with open(fname, 'r') as fp:
            return io.StringIO(fp.read())

    def __get_bytes_io_from_file(fname):
        with open(fname, 'rb') as fp:
            return io.BytesIO(fp.read())


def main():
    pass


if __name__ == '__main__':
    main()
