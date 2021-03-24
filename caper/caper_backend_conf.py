import logging
import os
from copy import deepcopy

from autouri import AutoURI

from .cromwell_backend import (
    BACKEND_AWS,
    BACKEND_GCP,
    BACKEND_SGE,
    CromwellBackendAWS,
    CromwellBackendBase,
    CromwellBackendCommon,
    CromwellBackendDatabase,
    CromwellBackendGCP,
    CromwellBackendLocal,
    CromwellBackendPBS,
    CromwellBackendSGE,
    CromwellBackendSLURM,
)
from .dict_tool import merge_dict
from .hocon_string import HOCONString

logger = logging.getLogger(__name__)


class CaperBackendConf:
    BACKEND_CONF_INCLUDE = 'include required(classpath("application"))'
    BASENAME_BACKEND_CONF = 'backend.conf'

    def __init__(
        self,
        default_backend,
        local_out_dir,
        disable_call_caching=False,
        max_concurrent_workflows=CromwellBackendCommon.DEFAULT_MAX_CONCURRENT_WORKFLOWS,
        memory_retry_error_keys=CromwellBackendCommon.DEFAULT_MEMORY_RETRY_ERROR_KEYS,
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
        gcp_out_dir=None,
        gcp_call_caching_dup_strat=CromwellBackendGCP.DEFAULT_GCP_CALL_CACHING_DUP_STRAT,
        gcp_service_account_key_json=None,
        use_google_cloud_life_sciences=False,
        gcp_region=CromwellBackendGCP.DEFAULT_REGION,
        aws_batch_arn=None,
        aws_region=None,
        aws_out_dir=None,
        gcp_zones=None,
        slurm_partition=None,
        slurm_account=None,
        slurm_extra_param=None,
        sge_pe=None,
        sge_queue=None,
        sge_extra_param=None,
        pbs_queue=None,
        pbs_extra_param=None,
    ):
        """Initializes the backend conf's stanzas.

        Args:
            default_backend:
                Default backend.
            local_out_dir:
                Output directory for all local backends.
                Define this even if you don't want to run on local backends
                since "Local" is a Cromwell's default backend and it needs this.
            disable_call_caching:
                Disable call-caching (re-using outputs from previous workflows/tasks)
            max_concurrent_workflows:
                Limit for concurrent number of workflows.
            memory_retry_error_keys:
                List of error messages to catch failures due to OOM (out of memory error).
                e.g. ['OutOfMemory', 'Killed']
                If an error occurs caught by these keys, then instance's memory will
                be increased for next retrial by memory_retry_error_multiplier defined
                in workflow options JSON.
            max_concurrent_tasks:
                Limit for concurrent number of tasks for each workflow.
            soft_glob_output:
                Local backends only (Local, sge, pbs, slurm).
                Glob with ln -s instead of hard-linking (ln alone).
                Useful for file-system like beeGFS, which does not allow hard-linking.
            local_hash_strat:
                Local file hashing strategy for call-caching.
            db:
                Metadata DB type. Defauling to use in-memory DB if not defined.
                You may need to define other parameters according to this DB type.
            db_timeout:
                DB connection timeout. Cromwell tries to connect to DB within this timeout.
            mysql_db_ip:
                MySQL DB hostname.
            mysql_db_port:
                MySQL DB port.
            mysql_db_user:
                MySQL DB username.
            mysql_db_password:
                MySQL DB password.
            mysql_db_name:
                MySQL DB name.
            postgresql_db_ip:
                PostgreSQL DB hostname.
            postgresql_db_port:
                PostgreSQL DB port.
            postgresql_db_user:
                PostgreSQL DB user.
            postgresql_db_password:
                PostgreSQL DB password.
            postgresql_db_name:
                PostgreSQL DB name.
            file_db:
                For db == "file". File DB path prefix.
                File DB does not allow multiple connections, which means that
                you cannot run multiple caper run/server with the same file DB.
            gcp_prj:
                Google project name.
            gcp_out_dir:
                Output bucket path for gcp backend. Must start with gs://.
            gcp_call_caching_dup_strat:
                Call-caching duplication strategy.
            gcp_service_account_key_json:
                GCP service account key JSON.
                If defined, service_account scheme will be used instead of application_default
                in Cromwell.
            use_google_cloud_life_sciences:
                Use Google Cloud Life Sciences API.
                This requires only one zone specified in gcp_zones.
                If not specified default zone will be used.
                See Cromwell document:
                    https://cromwell.readthedocs.io/en/stable/backends/Google/.
                Also check supported zones:
                    https://cloud.google.com/life-sciences/docs/concepts/locations
            gcp_region:
                Region for Google Cloud Life Sciences API.
                Ignored if not use_google_cloud_life_sciences.
            aws_batch_arn:
                ARN for AWS Batch.
            aws_region:
                AWS region. Multple regions are not allowed.
            aws_out_dir:
                Output bucket path for aws backend. Must start with s3://.
            gcp_zones:
                List of zones for Google Cloud Genomics API.
                For this and all arguments below this,
                see details in CaperWorkflowOpts.__init__.
                These parameters can be defined either in a backend conf file or
                in a workflow options JSON file.
                One major difference is that the former will also be used as defaults.
            slurm_partition:
            slurm_account:
            slurm_extra_param:
            sge_pe:
            sge_queue:
            sge_extra_param:
            pbs_queue:
            pbs_extra_param:
        """
        self._template = {}

        merge_dict(
            self._template,
            CromwellBackendCommon(
                default_backend=default_backend,
                disable_call_caching=disable_call_caching,
                max_concurrent_workflows=max_concurrent_workflows,
                memory_retry_error_keys=memory_retry_error_keys,
            ),
        )

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
                postgresql_db_name=postgresql_db_name,
            ),
        )

        # local backends
        merge_dict(
            self._template,
            CromwellBackendLocal(
                local_out_dir=local_out_dir,
                max_concurrent_tasks=max_concurrent_tasks,
                soft_glob_output=soft_glob_output,
                local_hash_strat=local_hash_strat,
            ),
        )

        merge_dict(
            self._template,
            CromwellBackendSLURM(
                local_out_dir=local_out_dir,
                max_concurrent_tasks=max_concurrent_tasks,
                soft_glob_output=soft_glob_output,
                local_hash_strat=local_hash_strat,
                slurm_partition=slurm_partition,
                slurm_account=slurm_account,
                slurm_extra_param=slurm_extra_param,
            ),
        )

        merge_dict(
            self._template,
            CromwellBackendSGE(
                local_out_dir=local_out_dir,
                max_concurrent_tasks=max_concurrent_tasks,
                soft_glob_output=soft_glob_output,
                local_hash_strat=local_hash_strat,
                sge_pe=sge_pe,
                sge_queue=sge_queue,
                sge_extra_param=sge_extra_param,
            ),
        )

        merge_dict(
            self._template,
            CromwellBackendPBS(
                local_out_dir=local_out_dir,
                max_concurrent_tasks=max_concurrent_tasks,
                soft_glob_output=soft_glob_output,
                local_hash_strat=local_hash_strat,
                pbs_queue=pbs_queue,
                pbs_extra_param=pbs_extra_param,
            ),
        )

        # cloud backends
        if gcp_prj and gcp_out_dir:
            if gcp_service_account_key_json:
                gcp_service_account_key_json = os.path.expanduser(
                    gcp_service_account_key_json
                )
                if not os.path.exists(gcp_service_account_key_json):
                    raise FileNotFoundError(
                        'gcp_service_account_key_json does not exist. f={f}'.format(
                            f=gcp_service_account_key_json
                        )
                    )

            merge_dict(
                self._template,
                CromwellBackendGCP(
                    max_concurrent_tasks=max_concurrent_tasks,
                    gcp_prj=gcp_prj,
                    gcp_out_dir=gcp_out_dir,
                    call_caching_dup_strat=gcp_call_caching_dup_strat,
                    gcp_service_account_key_json=gcp_service_account_key_json,
                    use_google_cloud_life_sciences=use_google_cloud_life_sciences,
                    gcp_region=gcp_region,
                    gcp_zones=gcp_zones,
                ),
            )

        if aws_batch_arn and aws_region and aws_out_dir:
            merge_dict(
                self._template,
                CromwellBackendAWS(
                    max_concurrent_tasks=max_concurrent_tasks,
                    aws_batch_arn=aws_batch_arn,
                    aws_region=aws_region,
                    aws_out_dir=aws_out_dir,
                ),
            )

        # keep these variables for a backend checking later
        self._sge_pe = sge_pe
        self._gcp_prj = gcp_prj
        self._gcp_out_dir = gcp_out_dir

        self._aws_batch_arn = aws_batch_arn
        self._aws_region = aws_region
        self._aws_out_dir = aws_out_dir

    def create_file(
        self,
        directory,
        backend=None,
        custom_backend_conf=None,
        basename=BASENAME_BACKEND_CONF,
    ):
        """Create a HOCON string and create a backend.conf file.

        Args:
            backend:
                Backend to run a workflow on.
                Default backend will be use if not defined.
            custom_backend_conf:
                User's custom backend conf file to override on
                Caper's auto-generated backend conf.
            basename:
                Basename.
        """
        template = deepcopy(self._template)

        if backend == BACKEND_SGE:
            if self._sge_pe is None:
                raise ValueError(
                    'sge-pe (Sun GridEngine parallel environment) '
                    'is required for backend sge.'
                )
        elif backend == BACKEND_GCP:
            if self._gcp_prj is None:
                raise ValueError(
                    'gcp-prj (Google Cloud Platform project) '
                    'is required for backend gcp.'
                )
            if self._gcp_out_dir is None:
                raise ValueError(
                    'gcp-out-dir (gs:// output bucket path) '
                    'is required for backend gcp.'
                )
        elif backend == BACKEND_AWS:
            if self._aws_batch_arn is None:
                raise ValueError(
                    'aws-batch-arn (ARN for AWS Batch) ' 'is required for backend aws.'
                )
            if self._aws_region is None:
                raise ValueError(
                    'aws-region (AWS region) ' 'is required for backend aws.'
                )
            if self._aws_out_dir is None:
                raise ValueError(
                    'aws-out-dir (s3:// output bucket path) '
                    'is required for backend aws.'
                )

        hocon_s = HOCONString.from_dict(
            template, include=CaperBackendConf.BACKEND_CONF_INCLUDE
        )

        if custom_backend_conf is not None:
            s = AutoURI(custom_backend_conf).read()
            hocon_s.merge(s)

        final_backend_conf_file = os.path.join(directory, basename)
        AutoURI(final_backend_conf_file).write(str(hocon_s) + '\n')
        return final_backend_conf_file
