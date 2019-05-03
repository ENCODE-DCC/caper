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
    ENDPOINT_WORKFLOWS = '/api/workflows/v1/query'
    ENDPOINT_METADATA = '/api/workflows/v1/{wf_id}/metadata'
    ENDPOINT_LABELS = '/api/workflows/v1/{wf_id}/labels'
    ENDPOINT_ABORT = '/api/workflows/v1/{wf_id}/abort'
    ENDPOINT_SUBMIT = '/api/workflows/v1'
    KEY_LABEL = 'cromwell_rest_api_label'

    def __init__(self, ip='localhost', port=8000,
                 user=None, password=None, verbose=False):
        self._verbose = verbose
        self._ip = ip
        self._port = port

        self._user = user
        self._password = password
        self.__init_auth()

    def submit(self, source, dependencies=None,
               inputs_file=None, options_file=None, str_label=None):
        """Submit a workflow. Labels file is not allowed. Instead,
        a string label can be given and it is written to a labels file
        as a value under the key name CromwellRestAPI.KEY_LABEL
        ("cromwell_rest_api_label")

        Returns:
            JSON Response from POST request submit a workflow
        """
        manifest = {}
        manifest['workflowSource'] = \
            CromwellRestAPI.__get_string_io_from_file(source)
        if dependencies is not None:
            manifest['workflowDependencies'] = \
                CromwellRestAPI.__get_string_io_from_file(dependencies)
        if inputs_file is not None:
            manifest['workflowInputs'] = \
                CromwellRestAPI.__get_string_io_from_file(inputs_file)
        else:
            manifest['workflowInputs'] = io.StringIO('{}')
        if options_file is not None:
            manifest['workflowOptions'] = \
                CromwellRestAPI.__get_string_io_from_file(options_file)
        if str_label is not None:
            manifest['labels'] = io.StringIO(
                '{{ "{key}":"{val}" }}'.format(
                    key=CromwellRestAPI.KEY_LABEL, val=str_label))
        r = self.__query_post(CromwellRestAPI.ENDPOINT_SUBMIT, manifest)
        if self._verbose:
            print("CromwellRestAPI.submit: ", r)
        return r

    def abort(self, workflow_ids=None, str_labels=None):
        """Abort a workflow

        Returns:
            List of JSON responses from POST request
            for aborting workflows
        """
        workflows = self.find(workflow_ids, str_labels)
        if workflows is None:
            return None        
        result = []
        for w in workflows:
            r = self.__query_post(
                CromwellRestAPI.ENDPOINT_ABORT.format(
                    wf_id=w['id']))
            result.append(r)
        if self._verbose:
            print("CromwellRestAPI.abort: ", result)
        return result

    def get_metadata(self, workflow_ids=None, str_labels=None):
        """Retrieve metadata for a workflow

        Returns:
            List of metadata JSONs
        """
        workflows = self.find(workflow_ids, str_labels)
        if workflows is None:
            return None        
        result = []
        for w in workflows:
            m = self.__query_get(
                CromwellRestAPI.ENDPOINT_METADATA.format(wf_id=w['id']))
            result.append(m)
        if self._verbose:
            print(json.dumps(result, indent=4))
        return result

    def get_str_label(self, workflow_id):
        """Get a string label for a specified workflow

        Returns:
            String label. This is different from raw "labels"
            JSON directly retrieved from Cromwell server.
            This string label is one of the values in it.
            See __get_labels() for details about JSON labels.
        """
        labels = self.__get_labels(workflow_id)
        if labels is None or 'labels' not in labels:
            return None
        for key in labels['labels']:
            if key == CromwellRestAPI.KEY_LABEL:
                return labels['labels'][key]
        return None

    def find(self, workflow_ids=None, str_labels=None):
        """Find a workflow by matching workflow_ids or string labels.
        Wildcards (? and *) are allowed for both.

        Returns:
            List of matched workflow JSONs
        """
        r = self.__query_get(
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
            s = self.get_str_label(w['id'])
            if workflow_ids is not None:
                for wf_id in workflow_ids:
                    if fnmatch.fnmatchcase(w['id'], wf_id):
                        matched.add(w['id'])
            if str_labels is not None and s is not None:
                for str_label in str_labels:
                    if fnmatch.fnmatchcase(s, str_label):
                        matched.add(w['id'])
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

    def __get_labels(self, workflow_id):
        """Get dict of a label for a specified workflow
        This is different from string label.
        String label is one of the values in
        Cromwell's labels dict.

        Returns:
            JSON labels for a workflow
        """
        if workflow_id is None:
            return None
        return self.__query_get(
            CromwellRestAPI.ENDPOINT_LABELS.format(
                wf_id=workflow_id))

    def __query_get(self, endpoint):
        """GET request

        Returns:
            JSON response
        """
        url = CromwellRestAPI.QUERY_URL.format(
                ip=self._ip,
                port=self._port) + endpoint
        try:
            resp = requests.get(url, headers={'accept': 'application/json'},
                                auth=self._auth)
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

    def __query_post(self, endpoint, manifest=None):
        """POST request

        Returns:
            JSON response
        """
        url = CromwellRestAPI.QUERY_URL.format(
                ip=self._ip,
                port=self._port) + endpoint
        try:
            resp = requests.post(url, headers={'accept': 'application/json'},
                                 files=manifest, auth=self._auth)
        except Exception as e:
            # traceback.print_exc()
            print(e)
            sys.exit(1)

        if resp.ok:
            return resp.json()
        else:
            print("HTTP Post error: ", resp.status_code, resp.content, 
                  url, manifest)
            return None

    @staticmethod
    def __get_string_io_from_file(fname):
        with open(fname, 'r') as fp:
            return io.StringIO(fp.read())


def main():
    pass


if __name__ == '__main__':
    main()
