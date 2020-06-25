import logging
import os
from datetime import datetime

from autouri import GCSURI, S3URI, AbsPath, AutoURI

from .cromwell_backend import BACKEND_AWS, BACKEND_GCP

logger = logging.getLogger(__name__)


class CaperBase:
    def __init__(self, local_work_dir, gcp_work_dir=None, aws_work_dir=None):
        """Manages work/cache/temp directories for localization on the following
        storages:
            - Local*: Local path -> local_work_dir**
            - gcp: GCS bucket path -> gcp_work_dir
            - aws: S3 bucket path -> aws_work_dir

        * Note that it starts with capital L, which is a default backend of Cromwell's
        default configuration file (application.conf).
        ** /tmp is not recommended. This directory is very important to store
        intermediate files used by Cromwell/AutoURI (file transfer/localization).

        Args:
            local_work_dir:
                Local work/temp/cache directory to store files localized for local backends.
                Unlike other two directories. This directory is also used to make a
                working directory to store intermediate files to run Cromwell.
            gcp_work_dir:
                GCS cache directory to store files localized on GCS for gcp backend.
            aws_work_dir:
                S3 cache directory to store files localized on S3 for aws backend.
        """
        if not AbsPath(local_work_dir).is_valid:
            raise ValueError(
                'local_work_dir should be a valid local abspath. {f}'.format(
                    f=local_work_dir
                )
            )
        if local_work_dir == '/tmp':
            raise ValueError(
                '/tmp is now allowed for local_work_dir. {f}'.format(f=local_work_dir)
            )
        if gcp_work_dir and not GCSURI(gcp_work_dir).is_valid:
            raise ValueError(
                'gcp_work_dir should be a valid GCS path. {f}'.format(f=gcp_work_dir)
            )
        if aws_work_dir and not S3URI(aws_work_dir).is_valid:
            raise ValueError(
                'aws_work_dir should be a valid S3 path. {f}'.format(f=aws_work_dir)
            )

        self._local_work_dir = local_work_dir
        self._gcp_work_dir = gcp_work_dir
        self._aws_work_dir = aws_work_dir

    def localize_on_backend(self, f, backend, recursive=False, make_md5_file=False):
        """Localize a file according to the chosen backend.
        Each backend has its corresponding storage.
            - gcp -> GCS bucket path (starting with gs://)
            - aws -> S3 bucket path (starting with s3://)
            - All others (based on local backend) -> local storage

        If contents of input JSON changes due to recursive localization (deepcopy)
        then a new temporary file suffixed with backend type will be written on loc_prefix.
        For example, /somewhere/test.json -> gs://example-tmp-gcs-bucket/somewhere/test.gcs.json

        loc_prefix will be one of the cache directories according to the backend type
            - gcp -> gcp_work_dir
            - aws -> aws_work_dir
            - all others (local) -> local_work_dir

        Args:
            f:
                File to be localized.
            backend:
                Backend to localize file f on.
            recursive:
                Recursive localization (deepcopy).
                All files (if value is valid path/URI string) in JSON/CSV/TSV
                will be localized together with file f.
            make_md5_file:
                Make .md5 file for localized files. This is for local only since
                GCS/S3 bucket paths already include md5 hash information in their metadata.

        Returns:
            localized URI.
        """
        if backend == BACKEND_GCP:
            loc_prefix = self._gcp_work_dir
        elif backend == BACKEND_AWS:
            loc_prefix = self._aws_work_dir
        else:
            loc_prefix = self._local_work_dir

        return AutoURI(f).localize_on(
            loc_prefix, recursive=recursive, make_md5_file=make_md5_file
        )

    def localize_on_backend_if_modified(
        self, f, backend, recursive=False, make_md5_file=False
    ):
        """Wrapper for localize_on_backend.

        If localized file is not modified due to recursive localization,
        then it means that localization for such file was redundant.
        So returns the original file instead of a redundantly localized one.
        We can check if file is modifed or not by looking at their basename.
        Modified localized file has a suffix of the target storage. e.g. .s3.
        """
        f_loc = self.localize_on_backend(
            f=f, backend=backend, recursive=recursive, make_md5_file=make_md5_file
        )

        if AutoURI(f).basename == AutoURI(f_loc).basename:
            return f
        return f_loc

    def create_timestamped_work_dir(self, prefix=''):
        """Creates/returns a local temporary directory on self._local_work_dir.

        Args:
            prefix:
                Prefix for timstamped directory.
                Directory name will be self._tmpdir / prefix / timestamp.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        work_dir = os.path.join(self._local_work_dir, prefix, timestamp)
        os.makedirs(work_dir, exist_ok=True)
        logger.info(
            'Creating a timestamped temporary directory. {d}'.format(d=work_dir)
        )

        return work_dir

    def get_work_dir_for_backend(self, backend):
        if backend == BACKEND_GCP:
            return self._gcp_work_dir
        elif backend == BACKEND_AWS:
            return self._aws_work_dir
        else:
            return self._local_work_dir
