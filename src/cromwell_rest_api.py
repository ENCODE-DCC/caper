#!/usr/bin/env python3
"""CromwellRestAPI
"""

import requests
import io


def get_string_io_from_file(fname):
    with open(fname, 'r') as fp:
        return io.StringIO(fp.read())


class CromwellRestAPI(object):
    _QUERY_URL = 'http://{ip}:{port}'
    _ENDPOINT_WORKFLOWS = '/api/workflows/v1/query'
    _ENDPOINT_METADATA = '/api/workflows/v1/{wf_id}/metadata'
    _ENDPOINT_LABELS = '/api/workflows/v1/{wf_id}/labels'
    _ENDPOINT_ABORT = '/api/workflows/v1/{wf_id}/abort'
    _ENDPOINT_SUBMIT = '/api/workflows/v1'
    _KEY_LABEL = 'cromwell_rest_api_label'

    @staticmethod
    def get_key_label():
        return CromwellRestAPI._KEY_LABEL

    def __init__(self, server_ip='localhost', server_port=8000,
            server_user=None, server_password=None):
        self._server_ip = server_ip
        self._server_port = server_port
        
        self._server_user = server_user
        self._server_password = server_password
        self.__init_auth()

    def submit(self, source, dependencies=None,
        inputs_file=None, options_file=None, string_label=None):
        """Submit a workflow. Labels file is not allowed. Instead, 
        a string label can be given under the key CromwellRestAPI._KEY_LABEL
        """
        manifest = {}
        manifest['workflowSource'] = get_string_io_from_file(source) # WDL or CWL
        if dependencies is not None:
            manifest['workflowDependencies'] = get_string_io_from_file(dependencies)
        if inputs_file is not None:
            manifest['workflowInputs'] = get_string_io_from_file(inputs_file)
        else:
            manifest['workflowInputs'] = io.StringIO('{}')
        if options_file is not None:
            manifest['workflowOptions'] = get_string_io_from_file(options_file)
        if string_label is not None:
            manifest['labels'] = io.StringIO(
                '{{ "{key}":"{val}" }}'.format(
                    key=CromwellRestAPI._KEY_LABEL,
                    val=string_label))
        return self.__query_post(CromwellRestAPI._ENDPOINT_SUBMIT,
            manifest)

    def abort(self, workflow_id):
        """Abort a workflow
        """
        if workflow_id is None:
            return None
        return self.__query_get(            
            CromwellRestAPI._ENDPOINT_ABORT.format(
                wf_id=workflow_id))

    def get_workflows(self):
        """Get dict of all workflows
        """
        return self.__query_get(
            CromwellRestAPI._ENDPOINT_WORKFLOWS)

    def get_metadata(self, workflow_id):
        """Get dict of metadata for a specified workflow
        """
        if workflow_id is None:
            return None
        return self.__query_get(
            CromwellRestAPI._ENDPOINT_METADATA.format(
                wf_id=workflow_id))

    def get_string_label(self, workflow_id):
        """Get a string label for a special key
        CromwellRestAPI._KEY_LABEL in labels json
        """
        labels = self.__get_labels(workflow_id)
        if labels is None or not 'labels' in labels:
            return None
        for key in labels['labels']:
            if key==CromwellRestAPI._KEY_LABEL:
                return labels['labels'][key]
        return None

    def find_by_string_label(self, label):
        """Find a workflow with matching label dict
        """
        workflows = self.get_workflows()
        for w in workflows:
            if not 'id' in w:
                continue
            workflow_id = w['id']
            if label==get_string_label(workflow_id):
                return workflow_id
        return None

    def __init_auth(self):
        """Init auth object
        """
        if self._server_user is not None and \
            self._server_password is not None:
            self._auth = (self._server_user, self._server_password)
        else:
            self._auth = None

    def __get_labels(self, workflow_id):
        """Get dict of a label for a specified workflow
        """
        if workflow_id is None:
            return None
        return self.__query_get(
            CromwellRestAPI._ENDPOINT_LABELS.format(
                wf_id=workflow_id))

    def __query_get(self, endpoint):
        """GET/POST
        """
        url = CromwellRestAPI._QUERY_URL.format(
                ip=self._server_ip,
                port=self._server_port) + endpoint
        resp = requests.get(url,
            headers={'accept': 'application/json'},
            auth=self._auth)
        if resp.ok:
            return resp.json()
        else:
            print("HTTP Error: ", resp.status_code, resp.content)
            print("Query: ", url)
            return None

    def __query_post(self, endpoint, manifest):
        """POST
        """
        url = CromwellRestAPI._QUERY_URL.format(
                ip=self._server_ip,
                port=self._server_port) + endpoint
        resp = requests.post(url,
            headers={'accept': 'application/json'},
            files=manifest,
            auth=self._auth)
        if resp.ok:
            return resp.json()
        else:
            print("HTTP Error: ", resp.status_code, resp.content)
            print("Query: ", url, manifest)
            return None

def main():
    pass

if __name__ == '__main__':
    main()

