#!/usr/bin/env python
"""
Cromweller Utils: Libraries for Cromweller
"""

import os
from logged_bash_cli import bash_run_cmd

def init_cromweller_uri(
    tmp_dir,
    tmp_s3_bucket=None,
    tmp_gcs_bucket=None,
    http_user=None,
    http_password=None,
    use_gsutil_over_aws_s3=None):
    """Initialize static members in CromwellerURI class
    """
    assert(tmp_dir is not None)
    CromwellerURI.TMP_DIR = tmp_dir
    CromwellerURI.TMP_S3_BUCKET = tmp_s3_bucket
    CromwellerURI.TMP_GCS_BUCKET = tmp_gcs_bucket
    CromwellerURI.HTTP_USER = http_user
    CromwellerURI.HTTP_PASSWORD = http_password
    CromwellerURI.USE_GSUTIL_OVER_AWS_S3 = use_gsutil_over_aws_s3

def mkdir_p(path):        
    bash_run_cmd('mkdir -p {}'.format(path))


class CromwellerURI(object):
    """URI or path for a file used in Cromweller
    """

    TMP_DIR = None
    TMP_S3_BUCKET = None
    TMP_GCS_BUCKET = None
    HTTP_USER = None
    HTTP_PASSWORD = None
    USE_GSUTIL_OVER_AWS_S3 = False

    _CACHE = {}

    def __init__(self, uri_or_path):
        if CromwellerURI.TMP_DIR is None:
            raise Exception('Call init_cromweller_uri() first '
                'to initialize CromwellerURI. TMP_DIR must be '
                'specified.')
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
                os.path.expanduser(CromwellerURI.TMP_DIR),
                os.path.basename(self.uri))
        elif self.uri_type == 'gcs':
            path = os.path.join(
                os.path.expanduser(CromwellerURI.TMP_DIR),
                self.uri.lstrip('gs://'))
        elif self.uri_type == 's3':
            path = os.path.join(
                os.path.expanduser(CromwellerURI.TMP_DIR),
                self.uri.lstrip('s3://'))
        else:
            raise NotImplementedError('uri_type: {}'.format(self.uri_type))
        return path

    def __get_gcs_file_name(self):
        if self.uri_type == 'gcs':
            return self.uri

        if self.uri_type == 'url':
            path = os.path.join(
                CromwellerURI.TMP_GCS_BUCKET,
                os.path.basename(self.uri))
        elif self.uri_type == 's3':
            path = os.path.join(
                CromwellerURI.TMP_GCS_BUCKET,
                self.uri.lstrip('s3://'))
        elif self.uri_type == 'local':
            path = os.path.join(
                CromwellerURI.TMP_GCS_BUCKET,
                os.path.abspath(self.uri))
        else:
            raise NotImplementedError('uri_type: {}'.format(self.uri_type))
        return path

    def __get_s3_file_name(self):
        if self.uri_type == 's3':
            return self.uri

        if self.uri_type == 'url':
            path = os.path.join(
                CromwellerURI.TMP_S3_BUCKET,
                os.path.basename(self.uri))
        elif self.uri_type == 'gcs':
            path = os.path.join(
                CromwellerURI.TMP_S3_BUCKET,
                self.uri.lstrip('gs://'))
        elif self.uri_type == 'local':
            path = os.path.join(
                CromwellerURI.TMP_S3_BUCKET,
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
        mkdir_p(dirname)

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
            if CromwellerURI.USE_GSUTIL_OVER_AWS_S3:
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
            if CromwellerURI.USE_GSUTIL_OVER_AWS_S3:
                cmd = 'gsutil cp -n {local_path} {s3_uri}'.format(
                    local_path=self.uri,
                    s3_uri=path)
            else:
                cmd = 'aws s3 cp --follow-symlinks {local_path} {s3_uri}'.format(
                    local_path=self.uri,
                    s3_uri=path)
        else:
            raise NotImplementedError('uri_type: {}'.format(uri_type))

    @staticmethod
    def __get_curl_auth_param():
        if CromwellerURI.HTTP_USER and CromwellerURI.HTTP_PASSWORD:
            return '-u {user}:{pass}'.format(
                CromwellerURI.HTTP_USER,
                CromwellerURI.HTTP_PASSWORD)
        return ''

    @staticmethod
    def __get_wget_auth_param():
        if CromwellerURI.HTTP_USER and CromwellerURI.HTTP_PASSWORD:
            return '--user {user} --password {pass}'.format(
                CromwellerURI.HTTP_USER,
                CromwellerURI.HTTP_PASSWORD)
        return ''


def main():
    pass

if __name__ == '__main__':
    main()

"""
DEV NOTE:
out_dir
num_concurrent_tasks
gc_project
out_gcs_bucket

num_concurrent_tasks

aws_batch_arn
aws_region

slurm_partition
slurm_account
slurm_extra_param

sge_pe
sge_queue
sge_extra_param

pbs_queue
pbs_extra_param

mysql_db_user
mysql_db_password

mysql_db_ip
mysql_db_port
mysql_db_user
mysql_db_password

backend_conf
"""