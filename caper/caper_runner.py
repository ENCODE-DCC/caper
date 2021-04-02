import logging
import os

from autouri import AbsPath, AutoURI

from .caper_backend_conf import CaperBackendConf
from .caper_base import CaperBase
from .caper_labels import CaperLabels
from .caper_workflow_opts import CaperWorkflowOpts
from .cromwell import Cromwell
from .cromwell_backend import (
    CromwellBackendBase,
    CromwellBackendCommon,
    CromwellBackendDatabase,
    CromwellBackendGCP,
    CromwellBackendLocal,
)
from .cromwell_metadata import CromwellMetadata
from .cromwell_rest_api import CromwellRestAPI
from .singularity import Singularity
from .wdl_parser import WDLParser

logger = logging.getLogger(__name__)


class CaperRunner(CaperBase):
    ENV_GOOGLE_CLOUD_PROJECT = 'GOOGLE_CLOUD_PROJECT'
    DEFAULT_FILE_DB_PREFIX = 'default_caper_file_db'
    SERVER_TMP_DIR_PREFIX = '.caper_server'

    def __init__(
        self,
        default_backend,
        local_loc_dir=None,
        local_out_dir=None,
        gcp_loc_dir=None,
        aws_loc_dir=None,
        cromwell=Cromwell.DEFAULT_CROMWELL,
        womtool=Cromwell.DEFAULT_WOMTOOL,
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
        """See docstring of base class for other arguments.

        Args:
            default_backend:
                Default backend.
            cromwell:
                Cromwell JAR URI.
            womtool:
                Womtool JAR URI.
            disable_call_caching:
            max_concurrent_workflows:
            memory_retry_error_keys
            max_concurrent_tasks:
            soft_glob_output:
            local_hash_strat:
            db:
            db_timeout:
            mysql_db_ip:
            mysql_db_port:
            mysql_db_user:
            mysql_db_password:
            mysql_db_name:
            postgresql_db_ip:
            postgresql_db_port:
            postgresql_db_user:
            postgresql_db_password:
            postgresql_db_name:
            file_db:
            gcp_prj:
            gcp_call_caching_dup_strat:
            gcp_service_account_key_json:
                This will be added to environment variable
                GOOGLE_APPLICATION_CREDENTIALS
                If not match with existing key then error out.
            use_google_cloud_life_sciences:
                Use Google Cloud Life Sciences API instead of Genomics API
                which has beed deprecated.
            gcp_region:
                Region for Google Cloud Life Sciences API.
                Ignored if not use_google_cloud_life_sciences.
            gcp_out_dir:
            aws_batch_arn:
            aws_region:
            aws_out_dir:
            gcp_zones:
                For this and all below arguments,
                see details in CaperWorkflowOpts.__init__.
            slurm_partition:
                SLURM partition if required to sbatch jobs.
            slurm_account:
                SLURM account if required to sbatch jobs.
            slurm_extra_param:
                SLURM extra parameter to be appended to sbatch command line.
            sge_pe:
                SGE parallel environment (required to run with multiple cpus).
            sge_queue:
                SGE queue.
            sge_extra_param:
                SGE extra parameter to be appended to qsub command line.
            pbs_queue:
                PBS queue.
            pbs_extra_param:
                PBS extra parameter to be appended to qsub command line.
        """
        super().__init__(
            local_loc_dir=local_loc_dir,
            gcp_loc_dir=gcp_loc_dir,
            aws_loc_dir=aws_loc_dir,
            gcp_service_account_key_json=gcp_service_account_key_json,
        )
        self._set_env_gcp_prj(gcp_prj)

        self._cromwell = Cromwell(cromwell=cromwell, womtool=womtool)

        if local_out_dir is None:
            local_out_dir = os.getcwd()

        self._caper_backend_conf = CaperBackendConf(
            default_backend=default_backend,
            local_out_dir=local_out_dir,
            disable_call_caching=disable_call_caching,
            max_concurrent_workflows=max_concurrent_workflows,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
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
            gcp_prj=gcp_prj,
            gcp_out_dir=gcp_out_dir,
            memory_retry_error_keys=memory_retry_error_keys,
            gcp_call_caching_dup_strat=gcp_call_caching_dup_strat,
            gcp_service_account_key_json=gcp_service_account_key_json,
            use_google_cloud_life_sciences=use_google_cloud_life_sciences,
            gcp_region=gcp_region,
            aws_batch_arn=aws_batch_arn,
            aws_region=aws_region,
            aws_out_dir=aws_out_dir,
            gcp_zones=gcp_zones,
            slurm_partition=slurm_partition,
            slurm_account=slurm_account,
            slurm_extra_param=slurm_extra_param,
            sge_pe=sge_pe,
            sge_queue=sge_queue,
            sge_extra_param=sge_extra_param,
            pbs_queue=pbs_queue,
            pbs_extra_param=pbs_extra_param,
        )

        self._caper_workflow_opts = CaperWorkflowOpts(
            use_google_cloud_life_sciences=use_google_cloud_life_sciences,
            gcp_zones=gcp_zones,
            slurm_partition=slurm_partition,
            slurm_account=slurm_account,
            slurm_extra_param=slurm_extra_param,
            sge_pe=sge_pe,
            sge_queue=sge_queue,
            sge_extra_param=sge_extra_param,
            pbs_queue=pbs_queue,
            pbs_extra_param=pbs_extra_param,
        )

        self._caper_labels = CaperLabels()

    def _set_env_gcp_prj(self, gcp_prj=None, env_name=ENV_GOOGLE_CLOUD_PROJECT):
        """Initalizes environment for authentication (storage).
        Args:
            gcp_prj:
                Environment variable GOOGLE_CLOUD_PROJECT will be updated with
                this.
        """
        if gcp_prj:
            if env_name in os.environ:
                prj = os.environ[env_name]
                if prj != gcp_prj:
                    logger.warning(
                        'Env var {env} does not match with '
                        'gcp_prj {prj}.'.format(env=env_name, prj=gcp_prj)
                    )
            logger.debug(
                'Adding {prj} to env var {env}'.format(prj=gcp_prj, env=env_name)
            )
            os.environ[env_name] = gcp_prj

    def run(
        self,
        backend,
        wdl,
        inputs=None,
        options=None,
        labels=None,
        imports=None,
        metadata_output=None,
        str_label=None,
        user=None,
        docker=None,
        singularity=None,
        singularity_cachedir=Singularity.DEFAULT_SINGULARITY_CACHEDIR,
        no_build_singularity=False,
        custom_backend_conf=None,
        max_retries=CaperWorkflowOpts.DEFAULT_MAX_RETRIES,
        memory_retry_multiplier=CaperWorkflowOpts.DEFAULT_MEMORY_RETRY_MULTIPLIER,
        gcp_monitoring_script=CaperWorkflowOpts.DEFAULT_GCP_MONITORING_SCRIPT,
        ignore_womtool=False,
        no_deepcopy=False,
        fileobj_stdout=None,
        fileobj_troubleshoot=None,
        work_dir=None,
        java_heap_run=Cromwell.DEFAULT_JAVA_HEAP_CROMWELL_RUN,
        java_heap_womtool=Cromwell.DEFAULT_JAVA_HEAP_WOMTOOL,
        dry_run=False,
    ):
        """Run a workflow using Cromwell run mode.

        Args:
            backend:
                Choose among Caper's built-in backends.
                (aws, gcp, Local, slurm, sge, pbs).
                Or use a backend defined in your custom backend config file
                (above "backend_conf" file).
            wdl:
                WDL file.
            inputs:
                Input JSON file. Cromwell's parameter -i.
            options:
                Workflow options JSON file. Cromwell's parameter -o.
            labels:
                Labels JSON file. Cromwell's parameter -l.
            imports:
                imports ZIP file. Cromwell's parameter -p.
            metadata_output:
                Output metadata file path. Metadata JSON file will be written to
                this path. Caper also automatiacally generates it on each workflow's
                root directory.  Cromwell's parameter -m.
            str_label:
                Caper's string label, which will be written
                to labels JSON object.
            user:
                Username. If not defined, find username from system.
            docker:
                Docker image to run a workflow on.
                This will be overriden by "docker" attr defined in
                WDL's task's "runtime {} section.

                If this is None:
                    Docker will not be used for this workflow.
                If this is an emtpy string (working like a flag):
                    Docker will be used. Caper will try to find docker image
                    in WDL (from a comment "#CAPER docker" or
                    from workflow.meta.caper_docker).
            singularity:
                Singularity image to run a workflow on.
                This will be overriden by "singularity" attr defined in
                WDL's task's "runtime {} section.

                If this is None:
                    Singularity will not be used for this workflow.
                If this is an emtpy string:
                    Singularity will be used. Caper will try to find Singularity image
                    in WDL (from a comment "#CAPER singularity" or
                    from workflow.meta.caper_singularlity).
            singularity_cachedir:
                Cache directory for local Singularity images.
                If there is a shell environment variable SINGULARITY_CACHEDIR
                define then this parameter will be ignored.
            no_build_singularity:
                Do not build local singularity image.
                However, a local singularity image will be eventually built on
                env var SINGULARITY_CACHEDIR.
                Therefore, use this flag if you have already built it.
            custom_backend_conf:
                Backend config file (HOCON) to override Caper's
                auto-generated backend config.
            max_retries:
                Number of retrial for a failed task in a workflow.
                This applies to every task in a workflow.
                0 means no retrial. "attemps" attribute in a task's metadata
                increments from 1 as it is retried. attempts==2 means first retrial.
            memory_retry_multiplier:
                Multiplier for the memory retry feature.
                See https://cromwell.readthedocs.io/en/develop/cromwell_features/RetryWithMoreMemory/
                for details.
            ignore_womtool:
                Disable Womtool validation for WDL/input JSON/imports.
            no_deepcopy:
                Disable recursive localization of files defined in input JSON.
                Input JSON file itself will still be localized.
            fileobj_stdout:
                File-like object to write Cromwell's STDOUT.
            fileobj_troubleshoot:
                File-like object to write auto-troubleshooting after workflow is done.
            work_dir:
                Local temporary directory to store all temporary files.
                Temporary files mean intermediate files used for running Cromwell.
                For example, backend config file, workflow options file.
                Localized (recursively) data files defined in input JSON
                will NOT be stored here.
                They will be localized on self._local_loc_dir instead.
                If this is not defined, then cache directory self._local_loc_dir will be used.
                However, Cromwell Java process itself will run on CWD instead of this directory.
            java_heap_run:
                Java heap (java -Xmx) for Cromwell server mode.
            java_heap_womtool:
                Java heap (java -Xmx) for Womtool.
            dry_run:
                Stop before running Java command line for Cromwell.
        Returns:
            metadata_file:
                URI of metadata JSON file.
        """
        if not AutoURI(wdl).exists:
            raise FileNotFoundError('WDL does not exists. {wdl}'.format(wdl=wdl))

        if str_label is None and inputs:
            str_label = AutoURI(inputs).basename_wo_ext

        if work_dir is None:
            work_dir = self.create_timestamped_work_dir(
                prefix=AutoURI(wdl).basename_wo_ext
            )

        logger.info('Localizing files on work_dir. {d}'.format(d=work_dir))

        if inputs:
            maybe_remote_file = self.localize_on_backend_if_modified(
                inputs, backend=backend, recursive=not no_deepcopy, make_md5_file=True
            )
            inputs = AutoURI(maybe_remote_file).localize_on(work_dir)

        if imports:
            imports = AutoURI(imports).localize_on(work_dir)
        elif not AbsPath(wdl).exists:
            # auto-zip sub WDLs only if main WDL is remote
            imports = WDLParser(wdl).create_imports_file(work_dir)

        # localize WDL to be passed to Cromwell Java
        wdl = AutoURI(wdl).localize_on(work_dir)

        if metadata_output:
            if not AbsPath(metadata_output).is_valid:
                raise ValueError(
                    'metadata_output is not a valid local abspath. {m}'.format(
                        m=metadata_output
                    )
                )
        else:
            metadata_output = os.path.join(
                work_dir, CromwellMetadata.DEFAULT_METADATA_BASENAME
            )

        backend_conf = self._caper_backend_conf.create_file(
            directory=work_dir, backend=backend, custom_backend_conf=custom_backend_conf
        )

        options = self._caper_workflow_opts.create_file(
            directory=work_dir,
            wdl=wdl,
            inputs=inputs,
            custom_options=options,
            docker=docker,
            singularity=singularity,
            singularity_cachedir=singularity_cachedir,
            backend=backend,
            max_retries=max_retries,
            memory_retry_multiplier=memory_retry_multiplier,
            gcp_monitoring_script=gcp_monitoring_script,
        )

        labels = self._caper_labels.create_file(
            directory=work_dir,
            backend=backend,
            custom_labels=labels,
            str_label=str_label,
            user=user,
        )

        if not ignore_womtool:
            if not self._cromwell.validate(wdl=wdl, inputs=inputs, imports=imports):
                return

        logger.info(
            'launching run: wdl={w}, inputs={i}, backend_conf={b}'.format(
                w=wdl, i=inputs, b=backend_conf
            )
        )
        th = self._cromwell.run(
            wdl=wdl,
            backend_conf=backend_conf,
            inputs=inputs,
            options=options,
            imports=imports,
            labels=labels,
            metadata=metadata_output,
            fileobj_stdout=fileobj_stdout,
            fileobj_troubleshoot=fileobj_troubleshoot,
            dry_run=dry_run,
        )
        return th

    def server(
        self,
        default_backend,
        server_port=CromwellRestAPI.DEFAULT_PORT,
        server_hostname=None,
        server_heartbeat=None,
        custom_backend_conf=None,
        fileobj_stdout=None,
        embed_subworkflow=False,
        java_heap_server=Cromwell.DEFAULT_JAVA_HEAP_CROMWELL_SERVER,
        auto_write_metadata=True,
        work_dir=None,
        dry_run=False,
    ):
        """Run a Cromwell server.
            default_backend:
                Default backend. If backend is not specified for a submitted workflow
                then default backend will be used.
                Choose among Caper's built-in backends.
                (aws, gcp, Local, slurm, sge, pbs).
                Or use a backend defined in your custom backend config file
                (above "backend_conf" file).
            server_heartbeat:
                Server heartbeat to write hostname/port of a server.
            server_port:
                Server port to run Cromwell server.
                Make sure to use different port for multiple Cromwell servers on the same
                machine.
            server_hostname:
                Server hostname. If not defined then socket.gethostname() will be used.
                If server_heartbeat is given, then this hostname will be written to
                the server heartbeat file defined in server_heartbeat.
            custom_backend_conf:
                Backend config file (HOCON) to override Caper's auto-generated backend config.
            fileobj_stdout:
                File-like object to write Cromwell's STDOUT.
            embed_subworkflow:
                Caper stores/updates metadata.JSON file on
                each workflow's root directory whenever there is status change
                of workflow (or its tasks).
                This flag ensures that any subworkflow's metadata JSON will be
                embedded in main (this) workflow's metadata JSON.
                This is to mimic behavior of Cromwell run mode's -m parameter.
            java_heap_server:
                Java heap (java -Xmx) for Cromwell server mode.
            auto_write_metadata:
                Automatic retrieval/writing of metadata.json upon workflow/task's status change.
            work_dir:
                Local temporary directory to store all temporary files.
                Temporary files mean intermediate files used for running Cromwell.
                For example, auto-generated backend config file and workflow options file.
                If this is not defined, then cache directory self._local_loc_dir with a timestamp
                will be used.
                However, Cromwell Java process itself will run on CWD instead of this directory.
            dry_run:
                Stop before running Java command line for Cromwell.
        """
        if work_dir is None:
            work_dir = self.create_timestamped_work_dir(
                prefix=CaperRunner.SERVER_TMP_DIR_PREFIX
            )

        backend_conf = self._caper_backend_conf.create_file(
            directory=work_dir,
            backend=default_backend,
            custom_backend_conf=custom_backend_conf,
        )
        logger.info('launching server: backend_conf={b}'.format(b=backend_conf))

        th = self._cromwell.server(
            backend_conf=backend_conf,
            server_port=server_port,
            server_hostname=server_hostname,
            server_heartbeat=server_heartbeat,
            fileobj_stdout=fileobj_stdout,
            embed_subworkflow=embed_subworkflow,
            java_heap_cromwell_server=java_heap_server,
            auto_write_metadata=auto_write_metadata,
            dry_run=dry_run,
        )
        return th
