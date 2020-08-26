import logging
import os
from datetime import datetime

from autouri import GCSURI, S3URI, AbsPath, AutoURI

from .cromwell_backend import BACKEND_AWS, BACKEND_GCP

logger = logging.getLogger(__name__)


class CaperBase:
    ENV_GOOGLE_APPLICATION_CREDENTIALS = 'GOOGLE_APPLICATION_CREDENTIALS'
    DEFAULT_LOC_DIR_NAME = '.caper_tmp'

    def __init__(
        self,
        local_loc_dir=None,
        gcp_loc_dir=None,
        aws_loc_dir=None,
        gcp_service_account_key_json=None,
    ):
        """Manages work/cache/temp directories for localization on the following
        storages:
            - Local*: Local path -> local_loc_dir**
            - gcp: GCS bucket path -> gcp_loc_dir
            - aws: S3 bucket path -> aws_loc_dir

        * Note that it starts with capital L, which is a default backend of Cromwell's
        default configuration file (application.conf).
        ** /tmp is not recommended. This directory is very important to store
        intermediate files used by Cromwell/AutoURI (file transfer/localization).

        Also manages Google Cloud auth (key JSON file) since both Caper client/server
        require permission to access to storage.

        Args:
            local_loc_dir:
                Local cache directory to store files localized for local backends.
                Unlike other two directories. This directory is also used to make a
                working directory to store intermediate files to run Cromwell.
                e.g. backend.conf and workflow_opts.json.
            gcp_loc_dir:
                GCS cache directory to store files localized on GCS for gcp backend.
            aws_loc_dir:
                S3 cache directory to store files localized on S3 for aws backend.
            gcp_service_account_key_json:
                Google Cloud service account for authentication.
                This service account should have enough permission to storage.
        """
        if local_loc_dir is None:
            local_loc_dir = os.path.join(os.getcwd(), CaperBase.DEFAULT_LOC_DIR_NAME)

        if not AbsPath(local_loc_dir).is_valid:
            raise ValueError(
                'local_loc_dir should be a valid local abspath. {f}'.format(
                    f=local_loc_dir
                )
            )
        if gcp_loc_dir and not GCSURI(gcp_loc_dir).is_valid:
            raise ValueError(
                'gcp_loc_dir should be a valid GCS path. {f}'.format(f=gcp_loc_dir)
            )
        if aws_loc_dir and not S3URI(aws_loc_dir).is_valid:
            raise ValueError(
                'aws_loc_dir should be a valid S3 path. {f}'.format(f=aws_loc_dir)
            )

        self._local_loc_dir = local_loc_dir
        self._gcp_loc_dir = gcp_loc_dir
        self._aws_loc_dir = aws_loc_dir

        self._set_env_gcp_app_credentials(gcp_service_account_key_json)

    def _set_env_gcp_app_credentials(
        self,
        gcp_service_account_key_json=None,
        env_name=ENV_GOOGLE_APPLICATION_CREDENTIALS,
    ):
        """Initalizes environment for authentication (VM instance/storage).

        Args:
            gcp_service_account_key_json:
                Secret key JSON file for auth.
                This service account should have full permission to storage and
                VM instance.
                Environment variable GOOGLE_APPLICATION_CREDENTIALS will be
                updated with this.
        """
        if gcp_service_account_key_json:
            gcp_service_account_key_json = os.path.expanduser(
                gcp_service_account_key_json
            )
            if env_name in os.environ:
                auth_file = os.environ[env_name]
                if not os.path.samefile(auth_file, gcp_service_account_key_json):
                    logger.warning(
                        'Env var {env} does not match with '
                        'gcp_service_account_key_json. '
                        'Using application default credentials? '.format(env=env_name)
                    )
            logger.debug(
                'Adding GCP service account key JSON {key} to '
                'env var {env}'.format(key=gcp_service_account_key_json, env=env_name)
            )
            os.environ[env_name] = gcp_service_account_key_json

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
            - gcp -> gcp_loc_dir
            - aws -> aws_loc_dir
            - all others (local) -> local_loc_dir

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
            loc_prefix = self._gcp_loc_dir
        elif backend == BACKEND_AWS:
            loc_prefix = self._aws_loc_dir
        else:
            loc_prefix = self._local_loc_dir

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
        work_dir = os.path.join(self._local_loc_dir, prefix, timestamp)
        os.makedirs(work_dir, exist_ok=True)
        logger.info(
            'Creating a timestamped temporary directory. {d}'.format(d=work_dir)
        )

        return work_dir

    def get_loc_dir(self, backend):
        """Get localization directory for a backend.
        """
        if backend == BACKEND_GCP:
            return self._gcp_loc_dir
        elif backend == BACKEND_AWS:
            return self._aws_loc_dir
        else:
            return self._local_loc_dir
