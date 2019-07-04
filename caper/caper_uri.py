#!/usr/bin/env python3
"""CaperURI: Easy transfer between cloud/local storages

Author:
    Jin Lee (leepc12@gmail.com) at ENCODE-DCC
"""

import re
import os
import errno
import json
import shutil
import time
import hashlib
from copy import deepcopy
from collections import OrderedDict
from subprocess import Popen, check_call, check_output, \
    PIPE, CalledProcessError


URI_URL = 'url'     # URL (http, https, ftp)
URI_S3 = 's3'       # AWS S3 bucket
URI_GCS = 'gcs'     # Google Cloud Storage bucket
URI_LOCAL = 'local'


def init_caper_uri(tmp_dir, tmp_s3_bucket=None, tmp_gcs_bucket=None,
                   http_user=None, http_password=None,
                   use_netrc=False,
                   use_gsutil_over_aws_s3=False, verbose=False):
    """Initialize static members in CaperURI class
    """
    assert(tmp_dir is not None)
    path = os.path.abspath(os.path.expanduser(tmp_dir))
    # adds slash (/) to the end of string if missing
    CaperURI.TMP_DIR = path.rstrip('/') + '/'
    if tmp_s3_bucket is not None:
        CaperURI.TMP_S3_BUCKET = tmp_s3_bucket.rstrip('/') + '/'
        assert(CaperURI.TMP_S3_BUCKET.startswith('s3://'))
    if tmp_gcs_bucket is not None:
        CaperURI.TMP_GCS_BUCKET = tmp_gcs_bucket.rstrip('/') + '/'
        assert(CaperURI.TMP_GCS_BUCKET.startswith('gs://'))
    CaperURI.HTTP_USER = http_user
    CaperURI.HTTP_PASSWORD = http_password
    CaperURI.USE_NETRC = use_netrc
    CaperURI.USE_GSUTIL_OVER_AWS_S3 = use_gsutil_over_aws_s3
    CaperURI.VERBOSE = verbose


class CaperURI(object):
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
    USE_NETRC = False
    USE_GSUTIL_OVER_AWS_S3 = False
    VERBOSE = False

    CURL_HTTP_ERROR_PREFIX = '_CaperURI_HTTP_ERROR_'
    CURL_HTTP_ERROR_WRITE_OUT = CURL_HTTP_ERROR_PREFIX + '%{http_code}'
    RE_PATTERN_CURL_HTTP_ERR = r'_CaperURI_HTTP_ERROR_(\d*)'

    LOCK_EXT = '.lock'
    LOCK_WAIT_SEC = 30
    LOCK_MAX_ITER = 100

    def __init__(self, uri_or_path):
        if CaperURI.TMP_DIR is None:
            raise Exception(
                'Call init_caper_uri() first '
                'to initialize CaperURI. TMP_DIR must be '
                'specified.')
        elif not CaperURI.TMP_DIR.endswith('/'):
            raise Exception(
                'CaperURI.TMP_DIR must ends '
                'with a slash (/).')
        if CaperURI.TMP_S3_BUCKET is not None and \
           not CaperURI.TMP_S3_BUCKET.endswith('/'):
            raise Exception(
                'CaperURI.TMP_S3_BUCKET must ends '
                'with a slash (/).')
        if CaperURI.TMP_GCS_BUCKET is not None and \
           not CaperURI.TMP_GCS_BUCKET.endswith('/'):
            raise Exception(
                'CaperURI.TMP_GCS_BUCKET must ends '
                'with a slash (/).')

        self._uri = uri_or_path
        self._uri_type = CaperURI.__get_uri_type(uri_or_path)
        self.__init_uri()

    def __str__(self):
        return self._uri

    @property
    def uri_type(self):
        return self._uri_type

    @uri_type.setter
    def uri_type(self, value):
        assert(value in (URI_URL, URI_S3, URI_GCS, URI_LOCAL))
        if self._uri_type == value:
            return
        self._uri = self.get_file(value)
        self._uri_type = value

    def set_uri_type_no_copy(self, value):
        assert(value in (URI_URL, URI_S3, URI_GCS, URI_LOCAL))
        if self._uri_type == value:
            return
        self._uri = self.get_file(value, no_copy=True)
        self._uri_type = value

    def get_uri(self):
        return self._uri

    def is_valid_uri(self):
        # deepcopy is only available for valid URIs
        return self._can_deepcopy

    def can_deepcopy(self):
        return self._can_deepcopy

    def file_exists(self):
        return CaperURI.__file_exists(self._uri)

    def get_local_file(self, no_copy=False):
        """Get local version of URI. Make a copy if required
        """
        return self.get_file(uri_type=URI_LOCAL, no_copy=no_copy)

    def get_gcs_file(self, no_copy=False):
        """Get GCS bucket version of URI. Make a copy if required
        """
        return self.get_file(uri_type=URI_GCS, no_copy=no_copy)

    def get_s3_file(self, no_copy=False):
        """Get S3 bucket version of URI. Make a copy if required
        """
        return self.get_file(uri_type=URI_S3, no_copy=no_copy)

    def get_url(self, no_copy=False):
        return self.get_file(uri_type=URI_URL, no_copy=no_copy)

    def get_file(self, uri_type, no_copy=False):
        """Get a URI on a specified storage. Make a copy if required
        """
        return self.copy(target_uri_type=uri_type, no_copy=no_copy)

    def copy(self, target_uri_type=None, target_uri=None, soft_link=False,
             no_copy=False):
        """Make a copy of self on a "target_uri_type" tmp_dir or
        tmp_bucket. Or copy self to "target_uri".

        Args:
            target_uri_type, target_uri:
                these are mutually exclusive. Specify only one of them.

            soft_link:
                soft link target if possible. e.g. from local to local
        """
        # XOR: only one of target_uri and target_uri_type
        # should be specified
        assert((target_uri is None) != (target_uri_type is None))
        if target_uri is None:
            path = None
            uri_type = target_uri_type
        elif isinstance(target_uri, CaperURI):
            path = target_uri.get_uri()
            uri_type = target_uri.uri_type
        else:
            path = target_uri
            uri_type = CaperURI.__get_uri_type(target_uri)

        if path is None and uri_type == self._uri_type:
            return self._uri

        # here, path is target path
        # get target path
        if uri_type == URI_URL:
            if path is not None:  # since URL is readonly
                path = None
            elif self._uri_type == URI_GCS:
                path = 'http://storage.googleapis.com/{}'.format(
                    self._uri.replace('gs://', '', 1))
            elif self._uri_type == URI_S3:
                path = 'http://s3.amazonaws.com/{}'.format(
                    self._uri.replace('s3://', '', 1))

        elif uri_type == URI_GCS:
            if path is None:
                path = self.__get_gcs_file_name()

        elif uri_type == URI_S3:
            if path is None:
                path = self.__get_s3_file_name()

        elif uri_type == URI_LOCAL:
            if path is None:
                path = self.__get_local_file_name()
            os.makedirs(os.path.dirname(path), exist_ok=True)

        else:
            raise NotImplementedError('uri_type: {}'.format(uri_type))

        # special treatment for URL to cloud (gcs, s3)
        if uri_type in (URI_GCS, URI_S3) and \
                self._uri_type == URI_URL:
            # # there is no way to get URL's file size before it's downloaded
            # # (since "Content-Length" header is optional)
            # # and not all websites support it (e.g. AWS)
            # wait until .lock file disappears
            # cu_target = CaperURI(path)
            # cu_target.__wait_for_lock()
            # if cu_target.file_exists() and \
            #     self.get_file_size() == cu_target.get_file_size():
            #     if CaperURI.VERBOSE:
            #         print('[CaperURI] copying skipped, '
            #               'target: {target}'.format(target=path))
            #     return cu_target

            # URL to local and then local to cloud
            tmp_local_f = CaperURI(self._uri).get_file(
                uri_type=URI_LOCAL, no_copy=no_copy)
            return CaperURI(tmp_local_f).copy(target_uri=path,
                                              no_copy=no_copy)
        if soft_link:
            if uri_type == URI_GCS and self._uri_type == URI_GCS:
                return self._uri
            elif uri_type == URI_S3 and self._uri_type == URI_S3:
                return self._uri

        if CaperURI.VERBOSE and uri_type not in (URI_URL,):
            if soft_link and self._uri_type == URI_LOCAL \
                    and uri_type == URI_LOCAL:
                method = 'symlinking'
            else:
                method = 'copying'
            print('[CaperURI] {method} from '
                  '{src} to {target}, src: {uri}'.format(
                    method=method,
                    src=self._uri_type, target=uri_type, uri=self._uri))

        action = 'skipped'
        if not no_copy:
            assert(path is not None)
            # wait until .lock file disappears
            cu_target = CaperURI(path)
            cu_target.__wait_for_lock()

            # if target file not exists or file sizes are different
            # then do copy!
            if uri_type not in (URI_URL,) and (not cu_target.file_exists() or \
                    self.get_file_size() != cu_target.get_file_size()):

                action = 'done'
                cu_lock = CaperURI(path + CaperURI.LOCK_EXT)
                try:
                    # create an empty .lock file
                    cu_lock.write_str_to_file('', quiet=True)

                    # do copy
                    if uri_type == URI_GCS:
                        if self._uri_type == URI_URL:
                            assert(False)

                        elif self._uri_type == URI_GCS or \
                                self._uri_type == URI_S3 \
                                or self._uri_type == URI_LOCAL:
                            check_call(['gsutil', '-q', 'cp', self._uri, path])
                        else:
                            path = None

                    elif uri_type == URI_S3:
                        if self._uri_type == URI_URL:
                            assert(False)

                        elif self._uri_type == URI_GCS:
                            check_call(['gsutil', '-q', 'cp', self._uri, path])

                        elif self._uri_type == URI_S3 or \
                                self._uri_type == URI_LOCAL:
                            if CaperURI.USE_GSUTIL_OVER_AWS_S3:
                                check_call(['gsutil', '-q', 'cp',
                                            self._uri, path])
                            else:
                                check_call(['aws', 's3', 'cp',
                                            '--only-show-errors',
                                            self._uri, path])
                        else:
                            path = None

                    elif uri_type == URI_LOCAL:
                        if self._uri_type == URI_LOCAL:
                            if soft_link:
                                if CaperURI.VERBOSE:
                                    method = 'symlinking'
                                try:
                                    os.symlink(self._uri, path)
                                except OSError as e:
                                    if e.errno == errno.EEXIST:
                                        os.remove(path)
                                        os.symlink(self._uri, path)
                            else:
                                if CaperURI.VERBOSE:
                                    method = 'copying'
                                shutil.copy2(self._uri, path)

                        elif self._uri_type == URI_URL:
                            # we need "curl -C -" to resume downloading
                            # but it always fails with HTTP ERR 416 when file
                            # is already fully downloaded, i.e. path exists
                            _, _, _, http_err = CaperURI.__curl_auto_auth(
                                ['curl', '-RL', '-f', '-C', '-',
                                 self._uri, '-o', path],
                                ignored_http_err=(416,))
                            if http_err in (416,):
                                action = 'skipped'

                        elif self._uri_type == URI_GCS or \
                            self._uri_type == URI_S3 and \
                                CaperURI.USE_GSUTIL_OVER_AWS_S3:
                            check_call(['gsutil', '-q', 'cp', self._uri, path])
                        elif self._uri_type == URI_S3:
                            check_call(['aws', 's3', 'cp',
                                        '--only-show-errors',
                                        self._uri, path])
                        else:
                            path = None

                    else:
                        raise NotImplementedError('uri_type: {}'.format(
                            uri_type))

                    if path is None:
                        raise NotImplementedError('uri_types: {}, {}'.format(
                            self._uri_type, uri_type))
                finally:
                    # remove .lock file
                    cu_lock.rm(quiet=True)

        if CaperURI.VERBOSE and uri_type not in (URI_URL,):
            print('[CaperURI] {method} {action}, target: {target}'.format(
                    method=method, action=action, target=path))
        return path

    def get_file_contents(self):
        """Get file contents
        """
        if CaperURI.VERBOSE:
            print('[CaperURI] read from {src}, src: {uri}'.format(
                src=self._uri_type, uri=self._uri))

        if self._uri_type == URI_URL:
            stdout, _, _, _ = CaperURI.__curl_auto_auth(
                ['curl', '-L', '-f', self._uri])
            return stdout

        elif self._uri_type == URI_GCS or self._uri_type == URI_S3 \
                and CaperURI.USE_GSUTIL_OVER_AWS_S3:
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

    def get_file_size(self):
        """Get file size
        Returns:
            File size in bytes or None (for all URLS,
                hard to estimate file size for redirected URLs)
        """
        if self._uri_type == URI_URL:
            return None

        elif self._uri_type == URI_GCS or self._uri_type == URI_S3 \
                and CaperURI.USE_GSUTIL_OVER_AWS_S3:
            s = check_output(['gsutil', '-q', 'ls', '-l', self._uri]).decode()
            # example ['1000982', '2019-05-21T21:06:47Z', ...]
            return int(s.strip('\n').split()[0])

        elif self._uri_type == URI_S3:
            s = check_output(['aws', 's3', 'ls', self._uri]).decode()
            # example ['2019-05-21', '14:06:47', '1000982', 'x.txt']
            return int(s.strip('\n').split()[2])

        elif self._uri_type == URI_LOCAL:
            return os.path.getsize(self._uri)

        else:
            raise NotImplementedError('uri_type: {}'.format(
                self._uri_type))

    def write_str_to_file(self, s, quiet=False):
        if CaperURI.VERBOSE and not quiet:
            print('[CaperURI] write to '
                  '{target}, target: {uri}, size: {size}'.format(
                    target=self._uri_type, uri=self._uri, size=len(s)))

        if self._uri_type == URI_LOCAL:
            os.makedirs(os.path.dirname(self._uri), exist_ok=True)
            with open(self._uri, 'w') as fp:
                fp.write(s)
        elif self._uri_type == URI_GCS or self._uri_type == URI_S3 \
                and CaperURI.USE_GSUTIL_OVER_AWS_S3:
            p = Popen(['gsutil', '-q', 'cp', '-',
                       self._uri], stdin=PIPE)
            p.communicate(input=s.encode('ascii'))
        elif self._uri_type == URI_S3:
            p = Popen(['aws', 's3', 'cp', '--only-show-errors', '-',
                       self._uri], stdin=PIPE)
            p.communicate(input=s.encode('ascii'))
        else:
            raise NotImplementedError('uri_type: {}'.format(self._uri_type))
        return self

    def __get_rel_uri(self):
        if self._uri_type == URI_LOCAL:
            if CaperURI.TMP_DIR is None or \
                not self._uri.startswith(
                    CaperURI.TMP_DIR):
                rel_uri = self._uri.replace('/', '', 1)
            else:
                rel_uri = self._uri.replace(
                    CaperURI.TMP_DIR, '', 1)

        elif self._uri_type == URI_GCS:
            if CaperURI.TMP_GCS_BUCKET is None or \
                not self._uri.startswith(
                    CaperURI.TMP_GCS_BUCKET):
                rel_uri = self._uri.replace('gs://', '', 1)
            else:
                rel_uri = self._uri.replace(
                    CaperURI.TMP_GCS_BUCKET, '', 1)

        elif self._uri_type == URI_S3:
            if CaperURI.TMP_S3_BUCKET is None or \
                not self._uri.startswith(
                    CaperURI.TMP_S3_BUCKET):
                rel_uri = self._uri.replace('s3://', '', 1)
            else:
                rel_uri = self._uri.replace(
                    CaperURI.TMP_S3_BUCKET, '', 1)

        elif self._uri_type == URI_URL:
            # for URLs use hash of the whole URL as a base for filename
            hash_str = hashlib.md5(self._uri.encode('utf-8')).hexdigest()
            rel_uri = os.path.join(hash_str, os.path.basename(self._uri))
        else:
            raise NotImplementedError('uri_type: {}'.format(self._uri_type))
        return rel_uri

    def __get_local_file_name(self):
        if self._uri_type == URI_LOCAL:
            return self._uri

        elif self._uri_type in (URI_GCS, URI_S3, URI_URL):
            return os.path.join(CaperURI.TMP_DIR, self.__get_rel_uri())
        else:
            raise NotImplementedError('uri_type: {}'.format(self._uri_type))

    def __get_gcs_file_name(self):
        if self._uri_type == URI_GCS:
            return self._uri

        elif self._uri_type in (URI_LOCAL, URI_S3, URI_URL):
            return os.path.join(CaperURI.TMP_GCS_BUCKET,
                                self.__get_rel_uri())
        else:
            raise NotImplementedError('uri_type: {}'.format(
                self._uri_type))

    def __get_s3_file_name(self):
        if self._uri_type == URI_S3:
            return self._uri

        elif self._uri_type in (URI_LOCAL, URI_GCS, URI_URL):
            return os.path.join(CaperURI.TMP_S3_BUCKET,
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
                c = CaperURI(v)
                if c.can_deepcopy() and c.uri_type != uri_type:
                    updated = True
                    if CaperURI.VERBOSE:
                        print('[CaperURI] deepcopy_tsv from '
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
            new_uri = '{prefix}.{uri_type}{ext}'.format(
                prefix=fname_wo_ext, uri_type=uri_type, ext=ext)
            s = '\n'.join(new_contents)
            cu = CaperURI(new_uri)
            # we can't write on URLs
            if cu.uri_type == URI_URL:
                cu.set_uri_type_no_copy(uri_type)
            return cu.write_str_to_file(s)
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
                c = CaperURI(d)
                if c.can_deepcopy() and c.uri_type != uri_type:
                    if CaperURI.VERBOSE:
                        print('[CaperURI] deepcopy_json from '
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
            cu = CaperURI(new_uri)
            # we can't write on URLs
            if cu.uri_type == URI_URL:
                cu.set_uri_type_no_copy(uri_type)
            return cu.write_str_to_file(j)
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

    def rm(self, quiet=False):
        """Remove file
        """
        if CaperURI.VERBOSE and not quiet:
            print('[CaperURI] remove {}'.format(self._uri))
        if self._uri_type == URI_GCS or self._uri_type == URI_S3 \
                and CaperURI.USE_GSUTIL_OVER_AWS_S3:
            return check_call(['gsutil', '-q', 'rm', self._uri])

        elif self._uri_type == URI_S3:
            return check_call(['aws', 's3', 'rm', '--only-show-errors',
                               self._uri])

        elif self._uri_type == URI_LOCAL:
            os.remove(self._uri)
        else:
            raise NotImplementedError('uri_type: {}'.format(
                self._uri_type))

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

    def __wait_for_lock(self):
        # wait until .lock file disappears
        it = 0
        cu_lock = CaperURI(self._uri + CaperURI.LOCK_EXT)
        while cu_lock.file_exists():
            it += 1
            if it > CaperURI.LOCK_MAX_ITER:
                raise Exception('File has been locked for too long.', self._uri)
            elif CaperURI.VERBOSE:
                print('[CaperURI] wait {} sec for file being unlocked. '
                      'retries: {}, max_retries: {}. uri: {}'.format(
                        CaperURI.LOCK_WAIT_SEC, it,
                        CaperURI.LOCK_MAX_ITER, self._uri))
            time.sleep(CaperURI.LOCK_WAIT_SEC)

    @staticmethod
    def __file_exists(uri):
        uri_type = CaperURI.__get_uri_type(uri)
        if uri_type == URI_LOCAL:
            path = os.path.expanduser(uri)
            return os.path.isfile(path)
        else:
            try:
                if uri_type == URI_URL:
                    # ignore 416, 404, 403 since it's just a checking
                    _, _, rc, _ = CaperURI.__curl_auto_auth(
                        ['curl', '--head', '-f', uri],
                        ignored_http_err=(416, 404, 403, 401))
                elif uri_type == URI_GCS or uri_type == URI_S3 \
                        and CaperURI.USE_GSUTIL_OVER_AWS_S3:
                    rc = check_call(['gsutil', '-q', 'ls', uri], stderr=PIPE)
                elif uri_type == URI_S3:
                    s = check_output(['aws', 's3', 'ls', uri], stderr=PIPE).decode()
                    rc = 1
                    for line in s.strip('\n').split('\n'):
                        basename = line.split()[-1]
                        if basename == os.path.basename(uri):
                            rc = 0
                            break
                else:
                    raise NotImplementedError('uri_type: {}'.format(uri_type))
            except CalledProcessError as e:
                rc = e.returncode
            return rc == 0

    @staticmethod
    def __curl_auto_auth(cmd_wo_auth, ignored_http_err=()):
        """Try without HTTP auth first if it fails then try with auth

        Returns:
            stdout: decoded STDOUT
            stderr: decoded STDERR
            rc: return code
        """
        try:
            # print http_code to STDOUT
            cmd_wo_auth = cmd_wo_auth + [
                '-w', CaperURI.CURL_HTTP_ERROR_WRITE_OUT]

            p = Popen(cmd_wo_auth, stdout=PIPE, stderr=PIPE)
            stdout, stderr = p.communicate()
            stdout = stdout.decode()
            stderr = stderr.decode()
            rc = p.returncode
            # parse stdout to get http_error
            m = re.findall(CaperURI.RE_PATTERN_CURL_HTTP_ERR, stdout)
            if len(m) > 0:
                http_err = int(m[-1])
                # remove error code from stdout
                stdout = CaperURI.CURL_HTTP_ERROR_PREFIX.join(
                    stdout.split(CaperURI.CURL_HTTP_ERROR_PREFIX)[:-1])
            else:
                http_err = None

            if CaperURI.HTTP_USER is None and not CaperURI.USE_NETRC:
                # if auth info is not given
                pass
            elif http_err in (401, 403):  # permission or auth http error
                if CaperURI.VERBOSE:
                    print('[CaperURI] got HTTP_ERR {}. '
                          're-trying with auth...'.format(http_err))

                # now try with AUTH
                if CaperURI.USE_NETRC:
                    cmd_w_auth = cmd_wo_auth + ['-n']
                else:
                    cmd_w_auth = cmd_wo_auth + [
                        '-u', '{}:{}'.format(CaperURI.HTTP_USER,
                                             CaperURI.HTTP_PASSWORD)]
                p = Popen(cmd_w_auth, stdout=PIPE, stderr=PIPE)
                stdout, stderr = p.communicate()
                stdout = stdout.decode()
                stderr = stderr.decode()
                rc = p.returncode

                # parse stdout to get http_error
                m = re.findall(CaperURI.RE_PATTERN_CURL_HTTP_ERR, stdout)
                if len(m) > 0:
                    http_err = int(m[-1])
                    if CaperURI.CURL_HTTP_ERROR_PREFIX in stdout:
                        # remove error code from stdout
                        stdout = CaperURI.CURL_HTTP_ERROR_PREFIX.join(
                            stdout.split(
                                CaperURI.CURL_HTTP_ERROR_WRITE_OUT)[:-1])
                else:
                    http_err = None

        except CalledProcessError as e:
            stdout = None
            stderr = None
            rc = e.returncode
            http_err = None

        if rc == 0 or http_err in (200,):  # OKAY
            pass
        elif http_err in ignored_http_err:
            # range request bug in curl
            if http_err in (416,):
                if CaperURI.VERBOSE:
                    print('[CaperURI] file already exists. '
                          'skip downloading and ignore HTTP_ERR 416')
        else:
            raise Exception(
                'cURL RC: {}, HTTP_ERR: {}, STDERR: {}'.format(
                    rc, http_err, stderr))
        return stdout, stderr, rc, http_err

def main():
    """To test CaperURI
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('src', help='Source URI')
    parser.add_argument('target', help='Target URI')
    parser.add_argument(
        '--test-write-to-str', action='store_true',
        help='Write [SRC] (string) on [TARGET] instead of copying')
    parser.add_argument(
        '--test-file-exists', action='store_true',
        help='Check if [SRC] exists')
    parser.add_argument(
        '--test-get-file-contents', action='store_true',
        help='Get file contents of [SRC]')
    parser.add_argument(
        '--tmp-dir', help='Temporary directory for local backend')
    parser.add_argument(
        '--tmp-s3-bucket', help='Temporary S3 bucket for AWS backend')
    parser.add_argument(
        '--use-gsutil-over-aws-s3', action='store_true',
        help='Use gsutil instead of aws s3 CLI even for S3 buckets.')
    parser.add_argument(
        '--tmp-gcs-bucket', help='Temporary GCS bucket for GC backend')
    parser.add_argument(
        '--http-user',
        help='Username to directly download data from URLs')
    parser.add_argument(
        '--http-password',
        help='Password to directly download data from URLs')

    args = parser.parse_args()

    init_caper_uri(
        args.tmp_dir,
        tmp_s3_bucket=args.tmp_s3_bucket,
        tmp_gcs_bucket=args.tmp_gcs_bucket,
        http_user=args.http_user,
        http_password=args.http_password,
        use_gsutil_over_aws_s3=args.use_gsutil_over_aws_s3,
        verbose=True)

    if args.test_write_to_str:
        CaperURI(args.target).write_str_to_file(args.src)
    elif args.test_file_exists:
        print(CaperURI(args.src).file_exists())
    elif args.test_get_file_contents:
        print(CaperURI(args.src).get_file_contents())
    else:
        print(CaperURI(args.src).copy(target_uri=args.target))


if __name__ == '__main__':
    main()
