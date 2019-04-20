#!/usr/bin/env python
"""
Cromweller Utils: Libraries for Cromweller
"""

import os
from logged_bash_cli import bash_run_cmd


class CromwellerURI(object):
    """URI or path for a file used in Cromweller
    """

    tmp_dir = None
    tmp_s3_bucket = None
    tmp_gcs_bucket = None

    http_user = None
    http_password = None

    use_gsutil_over_aws_s3 = False

    @staticmethod
    def __get_curl_auth_param(self):
        if CromwellerURI.http_user and CromwellerURI.http_password:
            return '-u {user}:{pass}'.format(
                CromwellerURI.http_user,
                CromwellerURI.http_password)
        return ''

    @staticmethod
    def __get_wget_auth_param(self):
        if CromwellerURI.http_user and CromwellerURI.http_password:
            return '--user {user} --password {pass}'.format(
                CromwellerURI.http_user,
                CromwellerURI.http_password)
        return ''

    @staticmethod
    def __mkdir_p(path):        
        bash_run_cmd('mkdir -p {}'.format(path))

    def __init__(self, uri_or_path):
        if uri_or_path.startswith(('http://', 'https://')):
            self.uri_type = 'url'
        elif uri_or_path.startswith('s3://'):
            self.uri_type = 's3'
        elif uri_or_path.startswith('gs://'):
            self.uri_type = 'gcs'
        else:
            self.uri_type = 'local'
        self.uri = uri_or_path

    def __get_local_file_name(self):
        if self.uri_type == 'local':
            return os.path.expanduser(self.uri)

        if self.uri_type == 'url':
            path = os.path.join(
                os.path.expanduser(CromwellerURI.tmp_dir),
                os.path.basename(self.uri))
        elif self.uri_type == 'gcs':
            path = os.path.join(
                os.path.expanduser(CromwellerURI.tmp_dir),
                self.uri.lstrip('gs://'))
        elif self.uri_type == 's3':
            path = os.path.join(
                os.path.expanduser(CromwellerURI.tmp_dir),
                self.uri.lstrip('s3://'))
        else:
            raise NotImplementedError('uri_type: {}'.format(self.uri_type))
        return path

    def __get_gcs_file_name(self):
        if self.uri_type == 'gcs':
            return self.uri

        if self.uri_type == 'url':
            path = os.path.join(
                CromwellerURI.tmp_gcs_bucket,
                os.path.basename(self.uri))
        elif self.uri_type == 's3':
            path = os.path.join(
                CromwellerURI.tmp_gcs_bucket,
                self.uri.lstrip('s3://'))
        elif self.uri_type == 'local':
            path = os.path.join(
                CromwellerURI.tmp_gcs_bucket,
                os.path.abspath(self.uri))
        else:
            raise NotImplementedError('uri_type: {}'.format(self.uri_type))
        return path

    def __get_s3_file_name(self):
        if self.uri_type == 's3':
            return self.uri

        if self.uri_type == 'url':
            path = os.path.join(
                CromwellerURI.tmp_s3_bucket,
                os.path.basename(self.uri))
        elif self.uri_type == 'gcs':
            path = os.path.join(
                CromwellerURI.tmp_s3_bucket,
                self.uri.lstrip('gs://'))
        elif self.uri_type == 'local':
            path = os.path.join(
                CromwellerURI.tmp_s3_bucket,
                os.path.abspath(self.uri))
        else:
            raise NotImplementedError('uri_type: {}'.format(self.uri_type))
        return path

    def get_local_file(self):
        path = self.__get_local_file_name()        
        if self.uri_type == 'local':
            return path

        # mkdir
        dirname = os.path.dirname(path)
        CromwellerURI.__mkdir_p(dirname)

        if self.uri_type == 'url':
            cmd = 'wget --no-check-certificate -qc {auth_param} {url} -O {local_path}'.format(
                auth_param=CromwellerURI.__get_wget_auth_param(),
                url=self.uri,
                local_path=path)
        elif self.uri_type == 'gcs':
            cmd = 'gsutil cp -n {gcs_uri} {local_path}'.format(
                gcs_uri=self.uri,
                local_path=path)
        elif self.uri_type == 's3':
            if CromwellerURI.use_gsutil_over_aws_s3:
                cmd = 'gsutil cp -n {s3_uri} {local_path}'.format(
                    s3_uri=self.uri,
                    local_path=path)
            else:
                cmd = 'aws s3 cp {s3_uri} {local_path}'.format(
                    s3_uri=self.uri,
                    local_path=path)
        else:
            raise NotImplementedError('uri_type: {}'.format(self.uri_type))
        bash_run_cmd(cmd)

        # check file exists
        assert(os.path.exists(path))
        return path

    def get_gcs_file(self):
        path = self.__get_gcs_file_name()
        if self.uri_type == 'gcs':
            return path

        if self.uri_type == 'url':
            cmd = 'curl -f {auth_param} {url} | gsutil cp -n - {s3_uri}'.format(
                auth_param=CromwellerURI.__get_curl_auth_param(),
                url=self.uri,
                gcs_uri=path)
        elif self.uri_type == 's3':
            cmd = 'gsutil cp -n {s3_uri} {gcs_uri}'.format(
                s3_uri=self.uri,
                gcs_uri=path)
        elif self.uri_type == 'local':
            cmd = 'gsutil cp -n {local_path} {s3_uri}'.format(
                local_path=self.uri,
                s3_uri=path)
        else:
            raise NotImplementedError('uri_type: {}'.format(self.uri_type))
        bash_run_cmd(cmd)

        # check file exists
        # bash_run_cmd('gsutil ls {}'.format(path))
        return path

    def get_s3_file(self):
        path = self.__get_s3_file_name()
        if self.uri_type == 's3':
            return path

        if self.uri_type == 'url':
            cmd = 'curl -f {auth_param} {url} | gsutil cp -n - {s3_uri}'.format(
                auth_param=CromwellerURI.__get_curl_auth_param(),
                url=self.uri,
                gcs_uri=path)
        elif self.uri_type == 'gcs':
            cmd = 'gsutil cp -n {gcs_uri} {s3_uri}'.format(
                gcs_uri=self.uri,
                s3_uri=path)
        elif self.uri_type == 'local':
            cmd = 'aws s3 cp --follow-symlinks {local_path} {s3_uri}'.format(
                local_path=self.uri,
                s3_uri=path)
        else:
            raise NotImplementedError('uri_type: {}'.format(self.uri_type))
        bash_run_cmd(cmd)

        # check file exists
        # bash_run_cmd('gsutil ls {}'.format(path))
        return path

    def get_url(self):
        if self.uri_type == 'url':
            return self.uri
        elif self.uri_type == 'gcs':
            return 'http://storage.googleapis.com/{}'.format(
                self.uri.lstrip('gs://'))
        elif self.uri_type == 's3':
            return 'http://s3.amazonaws.com/{}'.format(
                self.uri.lstrip('s3://'))
        else:
            raise NotImplementedError('uri_type: {}'.format(self.uri_type))        

    def get_file(self, uri_type):
        if uri_type == 's3':
            return path
        if uri_type == 'url':
            cmd = 'curl -f {auth_param} {url} | gsutil cp -n - {s3_uri}'.format(
                auth_param=CromwellerURI.__get_curl_auth_param(),
                url=self.uri,
                gcs_uri=path)
        elif uri_type == 'gcs':
            cmd = 'gsutil cp -n {gcs_uri} {s3_uri}'.format(
                gcs_uri=self.uri,
                s3_uri=path)
        elif uri_type == 'local':
            if CromwellerURI.use_gsutil_over_aws_s3:
                cmd = 'gsutil cp -n {local_path} {s3_uri}'.format(
                    local_path=self.uri,
                    s3_uri=path)
            else:
                cmd = 'aws s3 cp --follow-symlinks {local_path} {s3_uri}'.format(
                    local_path=self.uri,
                    s3_uri=path)
        else:
            raise NotImplementedError('uri_type: {}'.format(uri_type))


def main():
    pass

if __name__ == '__main__':
    main()
