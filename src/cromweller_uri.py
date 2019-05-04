#!/usr/bin/env python3
"""CromwellerURI: Easy transfer between cloud/local storages

Author:
    Jin Lee (leepc12@gmail.com) at ENCODE-DCC
"""

import os
import json
from copy import deepcopy
from collections import OrderedDict
from subprocess import Popen, check_call, check_output, run, \
    PIPE, CalledProcessError


URI_URL = 'url'     # URL (http, https, ftp)
URI_S3 = 's3'       # AWS S3 bucket
URI_GCS = 'gcs'     # Google Cloud Storage bucket
URI_LOCAL = 'local'


def init_cromweller_uri(tmp_dir, tmp_s3_bucket=None, tmp_gcs_bucket=None,
                        http_user=None, http_password=None,
                        use_gsutil_over_aws_s3=False, verbose=False):
    """Initialize static members in CromwellerURI class
    """
    assert(tmp_dir is not None)
    path = os.path.abspath(os.path.expanduser(tmp_dir))
    # adds slash (/) to the end of string if missing
    CromwellerURI.TMP_DIR = path.rstrip('/') + '/'
    if tmp_s3_bucket is not None:
        CromwellerURI.TMP_S3_BUCKET = tmp_s3_bucket.rstrip('/') + '/'
        assert(CromwellerURI.TMP_S3_BUCKET.startswith('s3://'))
    if tmp_gcs_bucket is not None:
        CromwellerURI.TMP_GCS_BUCKET = tmp_gcs_bucket.rstrip('/') + '/'
        assert(CromwellerURI.TMP_GCS_BUCKET.startswith('gs://'))
    CromwellerURI.HTTP_USER = http_user
    CromwellerURI.HTTP_PASSWORD = http_password
    CromwellerURI.USE_GSUTIL_OVER_AWS_S3 = use_gsutil_over_aws_s3
    CromwellerURI.VERBOSE = verbose


class CromwellerURI(object):
    """Easy transfer between cloud/local storages based on cloud
    platform CLIs (gsutil, aws s3).

    Args:
        URI or local path for a file (not a directory).

    Supported URI's:
        URL:
            http://, https:// and ftp://
        AWS S3 bucket:
            s3://
        Google Cloud Storage bucket:
            gs://
        local path:
            absolute path starting with "/" or "~"

    TMP_DIR, TMP_S3_BUCKET and TMP_GCS_BUCKET must be absolute
    paths with a trailing "/".

    Deepcopy makes a copy of the original file with a target "uri_type" as
    a suffix to the filename.
    For example, if any URIs in gs://somewhere/input.json need to be
    deepcopied to S3 bucket, then s3://tmp_s3_bucket/somewhere/input.s3.json
    will be created with all URIs in it deepcopied to S3 under
    s3://tmp_s3_bucket/ while keeping their original directory structure in
    GCS.

    Deepcopy is supported for the following extensions:
        .json: recursively find all URIs in values only (not keys)
        .tsv: find all URIs in all columns and rows
        .csv: find all URIs in all columns and rows
    """

    TMP_DIR = None
    TMP_S3_BUCKET = None
    TMP_GCS_BUCKET = None
    HTTP_USER = None
    HTTP_PASSWORD = None
    USE_GSUTIL_OVER_AWS_S3 = False
    VERBOSE = False

    def __init__(self, uri_or_path):
        if CromwellerURI.TMP_DIR is None:
            raise Exception(
                'Call init_cromweller_uri() first '
                'to initialize CromwellerURI. TMP_DIR must be '
                'specified.')
        elif not CromwellerURI.TMP_DIR.endswith('/'):
            raise Exception(
                'CromwellerURI.TMP_DIR must ends '
                'with a slash (/).')
        if CromwellerURI.TMP_S3_BUCKET is not None and \
           not CromwellerURI.TMP_S3_BUCKET.endswith('/'):
            raise Exception(
                'CromwellerURI.TMP_S3_BUCKET must ends '
                'with a slash (/).')
        if CromwellerURI.TMP_GCS_BUCKET is not None and \
           not CromwellerURI.TMP_GCS_BUCKET.endswith('/'):
            raise Exception(
                'CromwellerURI.TMP_GCS_BUCKET must ends '
                'with a slash (/).')

        self._uri = uri_or_path
        self._uri_type = CromwellerURI.__get_uri_type(uri_or_path)
        self.__init_uri()

    @property
    def uri_type(self):
        return self._uri

    @uri_type.setter
    def uri_type(self, value):
        assert(value in (URI_URL, URI_S3, URI_GCS, URI_LOCAL))
        if self._uri_type == value:
            return
        self._uri = self.get_file(value)
        self._uri_type = value

    def get_uri(self):
        return self._uri

    def can_deepcopy(self):
        return self._can_deepcopy

    def file_exists(self):
        return CromwellerURI.__file_exists(self._uri)

    def get_local_file(self):
        """Get local version of URI. Make a copy if required
        """
        return self.get_file(uri_type=URI_LOCAL)

    def get_gcs_file(self):
        """Get GCS bucket version of URI. Make a copy if required
        """
        return self.get_file(uri_type=URI_GCS)

    def get_s3_file(self):
        """Get S3 bucket version of URI. Make a copy if required
        """
        return self.get_file(uri_type=URI_S3)

    def get_url(self):
        """Get URL version of URI. Local files cannot have a URL
        """
        return self.get_file(uri_type=URI_URL)

    def get_file(self, uri_type):
        """Get a URI on a specified storage. Make a copy if required
        """
        if uri_type == self._uri_type:
            return self._uri
        if CromwellerURI.VERBOSE:
            print('[CromwellerURI] copying from '
                  '{src} to {target}, src: {uri}'.format(
                    src=self._uri_type, target=uri_type, uri=self._uri))

        path = None
        if uri_type == URI_URL:
            if self._uri_type == URI_GCS:
                path = 'http://storage.googleapis.com/{}'.format(
                    self._uri.replace('gs://', '', 1))
            elif self._uri_type == URI_S3:
                path = 'http://s3.amazonaws.com/{}'.format(
                    self._uri.replace('s3://', '', 1))

        elif uri_type == URI_GCS:
            path = self.__get_gcs_file_name()
            if self._uri_type == URI_URL:
                ps = Popen(
                    ['curl', '-u',
                     '{}:{}'.format(CromwellerURI.HTTP_USER,
                                    CromwellerURI.HTTP_PASSWORD),
                     '-f', self._uri], stdout=PIPE)
                check_call(['gsutil', '-q', 'cp', '-n', '-', path],
                           stdin=ps.stdout)
            elif self._uri_type == URI_S3 or self._uri_type == URI_LOCAL:
                check_call(['gsutil', '-q', 'cp', '-n', self._uri, path])
            else:
                path = None

        elif uri_type == URI_S3:
            path = self.__get_s3_file_name()
            if self._uri_type == URI_URL:
                ps = Popen([
                    'curl',
                    '-u', '{}:{}'.format(CromwellerURI.HTTP_USER,
                                         CromwellerURI.HTTP_PASSWORD),
                    '-f', self._uri], stdout=PIPE)
                if CromwellerURI.USE_GSUTIL_OVER_AWS_S3:
                    check_call(['gsutil', 'cp', '-n', '-', path],
                               stdin=ps.stdout)
                else:
                    if not CromwellerURI.__file_exists(path):
                        check_call(['aws', 's3', 'cp', '--only-show-errors',
                                    '-', path], stdin=ps.stdout)
            elif self._uri_type == URI_GCS:
                check_call(['gsutil', '-q', 'cp', '-n', self._uri, path])
            elif self._uri_type == URI_LOCAL:
                if CromwellerURI.USE_GSUTIL_OVER_AWS_S3:
                    check_call(['gsutil', '-q', 'cp', '-n', self._uri, path])
                elif not CromwellerURI.__file_exists(path):
                    check_call(['aws', 's3', 'cp', '--only-show-errors',
                                self._uri, path])
            else:
                path = None

        elif uri_type == URI_LOCAL:
            path = self.__get_local_file_name()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if self._uri_type == URI_URL:
                check_call([
                    'wget', '--no-check-certificate', '-qc',
                    '--user', str(CromwellerURI.HTTP_USER),
                    '--password', str(CromwellerURI.HTTP_PASSWORD),
                    self._uri, '-O', path])
            elif self._uri_type == URI_GCS or \
                self._uri_type == URI_S3 and \
                    CromwellerURI.USE_GSUTIL_OVER_AWS_S3:
                check_call(['gsutil', '-q', 'cp', '-n', self._uri, path])
            elif self._uri_type == URI_S3:
                if not CromwellerURI.__file_exists(path):
                    check_call(['aws', 's3', 'cp', '--only-show-errors',
                                self._uri, path])
            else:
                path = None

        else:
            raise NotImplementedError('uri_type: {}'.format(uri_type))

        if path is None:
            raise NotImplementedError('uri_types: {}, {}'.format(
                self._uri_type, uri_type))

        if CromwellerURI.VERBOSE:
            print('[CromwellerURI] copying done, target: {target}'.format(
                    target=path))

        assert(CromwellerURI.__file_exists(path))
        return path

    def get_file_contents(self):
        """Get file contents
        """
        if CromwellerURI.VERBOSE:
            print('[CromwellerURI] read from {src}, src: {uri}'.format(
                src=self._uri_type, uri=self._uri))

        if self._uri_type == URI_URL:
            return check_output([
                'curl',
                '-u', '{}:{}'.format(CromwellerURI.HTTP_USER,
                                     CromwellerURI.HTTP_PASSWORD),
                '-f', self._uri]).decode()

        elif self._uri_type == URI_GCS or self._uri_type == URI_S3 \
                and CromwellerURI.USE_GSUTIL_OVER_AWS_S3:
            return check_output(['gsutil', '-q', 'cat', self._uri]).decode()

        elif self._uri_type == URI_S3:
            return check_output(['aws', 's3', 'cp', '--only-show-errors',
                                 self._uri, '-']).decode()

        elif self._uri_type == URI_LOCAL:
            with open(self._uri, 'r') as fp:
                return fp.read()
        else:
            raise NotImplementedError('uri_type: {}'.format(
                self._uri_type))

    def write_str_to_file(self, s):
        if CromwellerURI.VERBOSE:
            print('[CromwellerURI] write to '
                  '{target}, target: {uri}, size: {size}'.format(
                    target=self._uri_type, uri=self._uri, size=len(s)))

        if self._uri_type == URI_LOCAL:
            with open(self._uri, 'w') as fp:
                fp.write(s)
        elif self._uri_type == URI_GCS or self._uri_type == URI_S3 \
                and CromwellerURI.USE_GSUTIL_OVER_AWS_S3:
            run(['gsutil', '-q', 'cp', '-', self._uri],
                input=s, encoding='ascii')
        elif self._uri_type == URI_S3:
            run(['aws', 's3', 'cp', '--only-show-errors', '-', self._uri],
                input=s, encoding='ascii')
        else:
            raise NotImplementedError('uri_type: {}'.format(self._uri_type))
        return self

    def __get_rel_uri(self):
        if self._uri_type == URI_LOCAL:
            if CromwellerURI.TMP_DIR is None or \
                not self._uri.startswith(
                    CromwellerURI.TMP_DIR):
                rel_uri = self._uri.replace('/', '', 1)
            else:
                rel_uri = self._uri.replace(
                    CromwellerURI.TMP_DIR, '', 1)

        elif self._uri_type == URI_GCS:
            if CromwellerURI.TMP_GCS_BUCKET is None or \
                not self._uri.startswith(
                    CromwellerURI.TMP_GCS_BUCKET):
                rel_uri = self._uri.replace('gs://', '', 1)
            else:
                rel_uri = self._uri.replace(
                    CromwellerURI.TMP_GCS_BUCKET, '', 1)

        elif self._uri_type == URI_S3:
            if CromwellerURI.TMP_S3_BUCKET is None or \
                not self._uri.startswith(
                    CromwellerURI.TMP_S3_BUCKET):
                rel_uri = self._uri.replace('s3://', '', 1)
            else:
                rel_uri = self._uri.replace(
                    CromwellerURI.TMP_S3_BUCKET, '', 1)

        elif self._uri_type == URI_URL:
            rel_uri = os.path.basename(self._uri)
        else:
            raise NotImplementedError('uri_type: {}'.format(self._uri_type))
        return rel_uri

    def __get_local_file_name(self):
        if self._uri_type == URI_LOCAL:
            return self._uri

        elif self._uri_type in (URI_GCS, URI_S3, URI_URL):
            return os.path.join(CromwellerURI.TMP_DIR, self.__get_rel_uri())
        else:
            raise NotImplementedError('uri_type: {}'.format(self._uri_type))

    def __get_gcs_file_name(self):
        if self._uri_type == URI_GCS:
            return self._uri

        elif self._uri_type in (URI_LOCAL, URI_S3, URI_URL):
            return os.path.join(CromwellerURI.TMP_GCS_BUCKET,
                                self.__get_rel_uri())
        else:
            raise NotImplementedError('uri_type: {}'.format(
                self._uri_type))

    def __get_s3_file_name(self):
        if self._uri_type == URI_S3:
            return self._uri

        elif self._uri_type in (URI_LOCAL, URI_GCS, URI_URL):
            return os.path.join(CromwellerURI.TMP_S3_BUCKET,
                                self.__get_rel_uri())
        else:
            raise NotImplementedError('uri_type: {}'.format(
                self._uri_type))

    def __init_uri(self):
        if self._uri_type == URI_LOCAL:
            # replace tilde (~) and get absolute path
            path = os.path.expanduser(self._uri)
            # local URI can be deepcopied only when
            #   absolute path is given and it's an existing file
            if os.path.isabs(path) and os.path.isfile(path):
                self._can_deepcopy = True
            else:
                self._can_deepcopy = False
            self._uri = os.path.abspath(path)
        else:
            self._can_deepcopy = True

    def __deepcopy_tsv(self, uri_type=None, uri_exts=(), delim='\t'):
        if uri_type is None or len(uri_exts) == 0:
            return self
        fname_wo_ext, ext = os.path.splitext(self._uri)
        assert(ext in ('.tsv', '.csv'))

        contents = self.get_file_contents()
        updated = False

        new_contents = []
        for line in contents.split('\n'):
            new_values = []
            for v in line.split(delim):
                c = CromwellerURI(v)
                if c.can_deepcopy() and c.uri_type != uri_type:
                    updated = True
                    if CromwellerURI.VERBOSE:
                        print('[CromwellerURI] deepcopy_tsv from '
                              '{src} to {tgt}, src: {uri}, tsv: {uri2}'.format(
                                src=c._uri_type, tgt=uri_type,
                                uri=c._uri, uri2=self._uri))
                    # copy file to target storage
                    new_file = c.deepcopy(uri_type=uri_type,
                                          uri_exts=uri_exts).get_file(uri_type)
                    new_values.append(new_file)
                else:
                    new_values.append(v)
            new_contents.append(delim.join(new_values))

        if updated:
            print(ext)
            new_uri = '{prefix}.{uri_type}{ext}'.format(
                prefix=fname_wo_ext, uri_type=uri_type, ext=ext)
            return CromwellerURI(new_uri).write_str_to_file(
                '\n'.join(new_contents))
        else:
            return self

    def __deepcopy_json(self, uri_type=None, uri_exts=()):
        if uri_type is None or len(uri_exts) == 0:
            return self
        fname_wo_ext, ext = os.path.splitext(self._uri)
        assert(ext in ('.json'))

        contents = self.get_file_contents()

        def recurse_dict(d, uri_type, d_parent=None, d_parent_key=None,
                         lst=None, lst_idx=None, updated=False):
            if isinstance(d, dict):
                for k, v in d.items():
                    updated |= recurse_dict(v, uri_type, d_parent=d,
                                            d_parent_key=k, updated=updated)
            elif isinstance(d, list):
                for i, v in enumerate(d):
                    updated |= recurse_dict(v, uri_type, lst=d,
                                            lst_idx=i, updated=updated)
            elif type(d) == str:
                assert(d_parent is not None or lst is not None)
                c = CromwellerURI(d)
                if c.can_deepcopy() and c.uri_type != uri_type:
                    if CromwellerURI.VERBOSE:
                        print('[CromwellerURI] deepcopy_json from '
                              '{src} to {tgt}, src: {uri}, json: {u2}'.format(
                                src=c._uri_type, tgt=uri_type,
                                uri=c._uri, u2=self._uri))
                    new_file = c.deepcopy(
                        uri_type=uri_type, uri_exts=uri_exts).get_file(
                            uri_type)
                    if d_parent is not None:
                        d_parent[d_parent_key] = new_file
                    elif lst is not None:
                        lst[lst_idx] = new_file
                    else:
                        raise ValueError('Recursion failed.')
                    return True
            return updated

        org_d = json.loads(contents, object_pairs_hook=OrderedDict)
        # make a copy to compare to original later
        new_d = deepcopy(org_d)
        # recurse for all values in new_d
        updated = recurse_dict(new_d, uri_type)

        if updated:
            new_uri = '{prefix}.{uri_type}{ext}'.format(
                prefix=fname_wo_ext, uri_type=uri_type, ext=ext)
            j = json.dumps(new_d, indent=4)
            return CromwellerURI(new_uri).write_str_to_file(j)
        else:
            return self

    def deepcopy(self, uri_type=None, uri_exts=()):
        """Supported file extensions: .json, .tsv and .csv
        """
        fname_wo_ext, ext = os.path.splitext(self._uri)

        if ext in uri_exts:
            if ext == '.json':
                return self.__deepcopy_json(uri_type, uri_exts)
            elif ext == '.tsv':
                return self.__deepcopy_tsv(uri_type, uri_exts, delim='\t')
            elif ext == '.csv':
                return self.__deepcopy_tsv(uri_type, uri_exts, delim=',')
            else:
                NotImplementedError('ext: {}.'.format(ext))
        return self

    @staticmethod
    def __get_uri_type(uri):
        if uri.startswith(('http://', 'https://', 'ftp://')):
            return URI_URL
        elif uri.startswith('s3://'):
            return URI_S3
        elif uri.startswith('gs://'):
            return URI_GCS
        else:
            return URI_LOCAL

    @staticmethod
    def __file_exists(uri):
        uri_type = CromwellerURI.__get_uri_type(uri)
        if uri_type == URI_LOCAL:
            path = os.path.expanduser(uri)
            return os.path.isfile(path)
        else:
            try:
                if uri_type == URI_URL:
                    rc = check_call([
                        'curl', '--head', '--silent', '--fail',
                        '-u', '{}:{}'.format(CromwellerURI.HTTP_USER,
                                             CromwellerURI.HTTP_PASSWORD),
                        uri])
                elif uri_type == URI_GCS or uri_type == URI_S3 \
                        and CromwellerURI.USE_GSUTIL_OVER_AWS_S3:
                    rc = check_call(['gsutil', '-q', 'ls', uri])
                elif uri_type == URI_S3:
                    rc = check_call(['aws', 's3', 'ls', path])
                else:
                    raise NotImplementedError('uri_type: {}'.format(uri_type))
            except CalledProcessError as e:
                rc = e.returncode
            return rc == 0


def main():
    pass


if __name__ == '__main__':
    main()
