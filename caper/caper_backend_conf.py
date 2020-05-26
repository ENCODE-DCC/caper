import logging
import os
from autouri import AutoURI
from copy import deepcopy
from .cromwell_backend import CromwellBackendCommon, CromwellBackendBase
from .cromwell_backend import CromwellBackendDatabase
from .cromwell_backend import CromwellBackendLocal, CromwellBackendGCP
from .cromwell_backend import CromwellBackendAWS, CromwellBackendSLURM
from .cromwell_backend import CromwellBackendSGE, CromwellBackendPBS
from .cromwell_backend import DEFAULT_BACKEND
from .cromwell_backend import BACKEND_SGE, BACKEND_GCP, BACKEND_AWS
from .dict_tool import merge_dict
from .hocon_string import HOCONString


logger = logging.getLogger(__name__)


class CaperBackendConf:
    BACKEND_CONF_INCLUDE = 'include required(classpath("application"))'
    BASENAME_BACKEND_CONF = 'backend.conf'

    def __init__(
            self,
            default_backend,
            out_dir,
            server_port=CromwellBackendCommon.DEFAULT_SERVER_PORT,
            disable_call_caching=False,
            max_concurrent_workflows=CromwellBackendCommon.DEFAULT_MAX_CONCURRENT_WORKFLOWS,
            max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
            soft_glob_output=False,
            local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
            db=CromwellBackendDatabase.DEFAULT_DB,
            db_timeout=CromwellBackendDatabase.DEFAULT_DB_TIMEOUT_MS,
            mysql_db_ip=CromwellBackendDatabase.DEFAULT_MYSQL_DB_IP,
            mysql_db_port=CromwellBackendDatabase.DEFAULT_MYSQL_DB_PORT,
            mysql_db_user=CromwellBackendDatabase.DEFAULT_MYSQL_DB_USER,
            mysql_db_password=CromwellBackendDatabase.DEFAULT_MYSQL_DB_PASSWORD,
            mysql_db_name=CromwellBackendDatabase.DEFAULT_MYSQL_DB_NAME,
            postgresql_db_ip=CromwellBackendDatabase.DEFAULT_POSTGRESQL_DB_IP,
            postgresql_db_port=CromwellBackendDatabase.DEFAULT_POSTGRESQL_DB_PORT,
            postgresql_db_user=CromwellBackendDatabase.DEFAULT_POSTGRESQL_DB_USER,
            postgresql_db_password=CromwellBackendDatabase.DEFAULT_POSTGRESQL_DB_PASSWORD,
            postgresql_db_name=CromwellBackendDatabase.DEFAULT_POSTGRESQL_DB_NAME,
            file_db=None,
            gcp_prj=None,
            gcp_zones=None,
            out_gcs_bucket=None,
            gcp_call_caching_dup_strat=CromwellBackendGCP.DEFAULT_GCP_CALL_CACHING_DUP_STRAT,
            aws_batch_arn=None,
            aws_region=None,
            out_s3_bucket=None,
            slurm_partition=None,
            slurm_account=None,
            slurm_extra_param=None,
            sge_pe=None,
            sge_queue=None,
            sge_extra_param=None,
            pbs_queue=None,
            pbs_extra_param=None):
        """Initializes the backend conf's stanzas.

        Args:
            default_backend:
                Default backend.
            out_dir:
                Output directory for all local backends.
                Define this even if you don't want to run on local backends
                since "Local" is a Cromwell's default backend and it needs this.
        """
        self._template = {}

        merge_dict(
            self._template,
            CromwellBackendCommon(
                default_backend=default_backend,
                server_port=server_port,
                disable_call_caching=disable_call_caching,
                max_concurrent_workflows=max_concurrent_workflows))

        merge_dict(
            self._template,
            CromwellBackendDatabase(
                db=db,
                db_timeout=db_timeout,
                file_db=file_db,
                mysql_db_ip=mysql_db_ip,
                mysql_db_port=mysql_db_port,
                mysql_db_user=mysql_db_user,
                mysql_db_password=mysql_db_password,
                mysql_db_name=mysql_db_name,
                postgresql_db_ip=postgresql_db_ip,
                postgresql_db_port=postgresql_db_port,
                postgresql_db_user=postgresql_db_user,
                postgresql_db_password=postgresql_db_password,
                postgresql_db_name=postgresql_db_name))

        # local backends
        merge_dict(
            self._template,
            CromwellBackendLocal(
                out_dir=out_dir,
                max_concurrent_tasks=max_concurrent_tasks,
                soft_glob_output=soft_glob_output,
                local_hash_strat=local_hash_strat))

        merge_dict(
            self._template,
            CromwellBackendSLURM(
                out_dir=out_dir,
                max_concurrent_tasks=max_concurrent_tasks,
                soft_glob_output=soft_glob_output,
                local_hash_strat=local_hash_strat,
                slurm_partition=slurm_partition,
                slurm_account=slurm_account,
                slurm_extra_param=slurm_extra_param))

        merge_dict(
            self._template,
            CromwellBackendSGE(
                out_dir=out_dir,
                max_concurrent_tasks=max_concurrent_tasks,
                soft_glob_output=soft_glob_output,
                local_hash_strat=local_hash_strat,
                sge_pe=sge_pe,
                sge_queue=sge_queue,
                sge_extra_param=sge_extra_param))

        merge_dict(
            self._template,
            CromwellBackendPBS(
                out_dir=out_dir,
                max_concurrent_tasks=max_concurrent_tasks,
                soft_glob_output=soft_glob_output,
                local_hash_strat=local_hash_strat,
                pbs_queue=pbs_queue,
                pbs_extra_param=pbs_extra_param))

        # cloud backends
        if gcp_prj and out_gcs_bucket:
            merge_dict(
                self._template,
                CromwellBackendGCP(
                    max_concurrent_tasks=max_concurrent_tasks,
                    gcp_prj=gcp_prj,
                    out_gcs_bucket=out_gcs_bucket,
                    call_caching_dup_strat=gcp_call_caching_dup_strat,
                    gcp_zones=gcp_zones))

        if aws_batch_arn and aws_region and out_s3_bucket:
            merge_dict(
                self._template,
                CromwellBackendAWS(
                    max_concurrent_tasks=max_concurrent_tasks,
                    aws_batch_arn=aws_batch_arn,
                    aws_region=aws_region,
                    out_s3_bucket=out_s3_bucket))

        # keep these variables for a backend checking later
        self._sge_pe = sge_pe
        self._gcp_prj = gcp_prj
        self._out_gcs_bucket = out_gcs_bucket

        self._aws_batch_arn = aws_batch_arn
        self._aws_region = aws_region
        self._out_s3_bucket = out_s3_bucket

    def create_file(
            self,
            directory,
            backend=None,
            custom_backend_conf=None,
            basename=BASENAME_BACKEND_CONF):
        """Create a HOCON string and create a backend.conf file.
        """
        template = deepcopy(self._template)

        if backend == BACKEND_SGE:
            if self._sge_pe is None:
                raise Exception(
                    '--sge-pe (Sun GridEngine parallel environment) '
                    'is required for backend sge.')
        elif backend == BACKEND_GCP:
            if self._gcp_prj is None:
                raise Exception(
                    '--gcp-prj (Google Cloud Platform project) '
                    'is required for backend gcp.')
            if self._out_gcs_bucket is None:
                raise Exception(
                    '--out-gcs-bucket (gs:// output bucket path) '
                    'is required for backend gcp.')
        elif backend == BACKEND_AWS:
            if self._aws_batch_arn is None:
                raise Exception(
                    '--aws-batch-arn (ARN for AWS Batch) '
                    'is required for backend aws.')
            if self._aws_region is None:
                raise Exception(
                    '--aws-region (AWS region) '
                    'is required for backend aws.')
            if self._out_s3_bucket is None:
                raise Exception(
                    '--out-s3-bucket (s3:// output bucket path) '
                    'is required for backend aws.')

        hocon_s = HOCONString.from_dict(
            template,
            include=CaperBackendConf.BACKEND_CONF_INCLUDE)

        if custom_backend_conf is not None:
            s = AutoURI(custom_backend_conf).read()
            hocon_s.merge(s)

        final_backend_conf_file = os.path.join(directory, basename)
        AutoURI(final_backend_conf_file).write(
            str(hocon_s) + '\n')
        return final_backend_conf_file
