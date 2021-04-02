import json
import logging
from collections import UserDict
from copy import deepcopy
from textwrap import dedent

from .dict_tool import merge_dict

logger = logging.getLogger(__name__)


BACKEND_GCP = 'gcp'
BACKEND_AWS = 'aws'
BACKEND_LOCAL = 'Local'
BACKEND_ALIAS_LOCAL = 'local'
BACKEND_SLURM = 'slurm'
BACKEND_SGE = 'sge'
BACKEND_PBS = 'pbs'
DEFAULT_BACKEND = BACKEND_LOCAL


def get_s3_bucket_name(s3_uri):
    return s3_uri.replace('s3://', '', 1).split('/')[0]


class CromwellBackendCommon(UserDict):
    """Basic stanzas for Cromwell backend conf.
    """

    TEMPLATE = {
        'backend': {},
        'webservice': {},
        'services': {
            'LoadController': {
                'class': 'cromwell.services.loadcontroller.impl'
                '.LoadControllerServiceActor',
                'config': {
                    # added due to issues on stanford sherlock/scg
                    'control-frequency': '21474834 seconds'
                },
            }
        },
        'system': {
            'job-rate-control': {'jobs': 1, 'per': '2 seconds'},
            'abort-jobs-on-terminate': True,
            'graceful-server-shutdown': True,
        },
        'call-caching': {'invalidate-bad-cache-results': True},
    }

    DEFAULT_MAX_CONCURRENT_WORKFLOWS = 40
    DEFAULT_MEMORY_RETRY_ERROR_KEYS = ['OutOfMemory', 'Killed']

    def __init__(
        self,
        default_backend,
        disable_call_caching=False,
        max_concurrent_workflows=DEFAULT_MAX_CONCURRENT_WORKFLOWS,
        memory_retry_error_keys=DEFAULT_MEMORY_RETRY_ERROR_KEYS,
    ):
        """
        Args:
            memory_retry_error_keys:
                List of error strings to catch out-of-memory error
                See https://cromwell.readthedocs.io/en/develop/cromwell_features/RetryWithMoreMemory
                for details.
        """
        super().__init__(deepcopy(CromwellBackendCommon.TEMPLATE))

        if default_backend is None:
            default_backend = DEFAULT_BACKEND
        self['backend']['default'] = default_backend
        self['call-caching']['enabled'] = not disable_call_caching
        self['system']['max-concurrent-workflows'] = max_concurrent_workflows
        # Cromwell's bug in memory-retry feature.
        # Disabled until it's fixed on Cromwell's side.
        # self['system']['memory-retry-error-keys'] = memory_retry_error_keys


class CromwellBackendServer(UserDict):
    """Stanzas for Cromwell server.
    """

    TEMPLATE = {'webservice': {}}

    DEFAULT_SERVER_PORT = 8000

    def __init__(self, server_port=DEFAULT_SERVER_PORT):
        super().__init__(deepcopy(CromwellBackendServer.TEMPLATE))

        self['webservice']['port'] = server_port


class CromwellBackendDatabase(UserDict):
    """Common stanzas for Cromwell's metadata database.
    """

    TEMPLATE = {'database': {'db': {'connectionTimeout': 5000, 'numThreads': 1}}}

    DB_IN_MEMORY = 'in-memory'
    DB_FILE = 'file'
    DB_MYSQL = 'mysql'
    DB_POSTGRESQL = 'postgresql'

    PROFILE_MYSQL = 'slick.jdbc.MySQLProfile$'
    PROFILE_POSTGRESQL = 'slick.jdbc.PostgresProfile$'
    JDBC_DRIVER_MYSQL = 'com.mysql.cj.jdbc.Driver'
    JDBC_DRIVER_POSTGRESQL = 'org.postgresql.Driver'
    JDBC_URL_FILE = (
        'jdbc:hsqldb:file:{file};shutdown=false;hsqldb.tx=mvcc;'
        'hsqldb.lob_compressed=true;'
        'hsqldb.default_table_type=cached;'
        'hsqldb.result_max_memory_rows=10000;'
        'hsqldb.large_data=true;'
        'hsqldb.applog=1;'
        'hsqldb.script_format=3'
    )
    JDBC_URL_MYSQL = (
        'jdbc:mysql://{ip}:{port}/{name}?'
        'allowPublicKeyRetrieval=true&useSSL=false&'
        'rewriteBatchedStatements=true&serverTimezone=UTC'
    )
    JDBC_URL_POSTGRESQL = 'jdbc:postgresql://{ip}:{port}/{name}'

    DEFAULT_DB = DB_IN_MEMORY
    DEFAULT_DB_TIMEOUT_MS = 30000
    DEFAULT_MYSQL_DB_IP = 'localhost'
    DEFAULT_MYSQL_DB_PORT = 3306
    DEFAULT_MYSQL_DB_USER = 'cromwell'
    DEFAULT_MYSQL_DB_PASSWORD = 'cromwell'
    DEFAULT_MYSQL_DB_NAME = 'cromwell'
    DEFAULT_POSTGRESQL_DB_IP = 'localhost'
    DEFAULT_POSTGRESQL_DB_PORT = 5432
    DEFAULT_POSTGRESQL_DB_USER = 'cromwell'
    DEFAULT_POSTGRESQL_DB_PASSWORD = 'cromwell'
    DEFAULT_POSTGRESQL_DB_NAME = 'cromwell'

    def __init__(
        self,
        db=DEFAULT_DB,
        db_timeout=DEFAULT_DB_TIMEOUT_MS,
        mysql_db_ip=DEFAULT_MYSQL_DB_IP,
        mysql_db_port=DEFAULT_MYSQL_DB_PORT,
        mysql_db_user=DEFAULT_MYSQL_DB_USER,
        mysql_db_password=DEFAULT_MYSQL_DB_PASSWORD,
        mysql_db_name=DEFAULT_MYSQL_DB_NAME,
        postgresql_db_ip=DEFAULT_POSTGRESQL_DB_IP,
        postgresql_db_port=DEFAULT_POSTGRESQL_DB_PORT,
        postgresql_db_user=DEFAULT_POSTGRESQL_DB_USER,
        postgresql_db_password=DEFAULT_POSTGRESQL_DB_PASSWORD,
        postgresql_db_name=DEFAULT_POSTGRESQL_DB_NAME,
        file_db=None,
    ):
        super().__init__(deepcopy(CromwellBackendDatabase.TEMPLATE))

        database = self['database']
        db_obj = database['db']

        db_obj['connectionTimeout'] = db_timeout

        if db == CromwellBackendDatabase.DB_FILE:
            if not file_db:
                raise ValueError('file_db must be defined for db {db}'.format(db=db))

        if db == CromwellBackendDatabase.DB_IN_MEMORY:
            pass

        elif db == CromwellBackendDatabase.DB_FILE:
            db_obj['url'] = CromwellBackendDatabase.JDBC_URL_FILE.format(file=file_db)

        elif db == CromwellBackendDatabase.DB_MYSQL:
            database['profile'] = CromwellBackendDatabase.PROFILE_MYSQL
            db_obj['driver'] = CromwellBackendDatabase.JDBC_DRIVER_MYSQL
            db_obj['url'] = CromwellBackendDatabase.JDBC_URL_MYSQL.format(
                ip=mysql_db_ip, port=mysql_db_port, name=mysql_db_name
            )
            db_obj['user'] = mysql_db_user
            db_obj['password'] = mysql_db_password

        elif db == CromwellBackendDatabase.DB_POSTGRESQL:
            database['profile'] = CromwellBackendDatabase.PROFILE_POSTGRESQL
            db_obj['driver'] = CromwellBackendDatabase.JDBC_DRIVER_POSTGRESQL
            db_obj['url'] = CromwellBackendDatabase.JDBC_URL_POSTGRESQL.format(
                ip=postgresql_db_ip, port=postgresql_db_port, name=postgresql_db_name
            )
            db_obj['port'] = postgresql_db_port
            db_obj['user'] = postgresql_db_user
            db_obj['password'] = postgresql_db_password

        else:
            raise ValueError('Unsupported DB type {db}'.format(db=db))


class CromwellBackendBase(UserDict):
    """Base skeleton backend for all backends
    """

    TEMPLATE = {'backend': {'providers': {}}}
    TEMPLATE_BACKEND = {'config': {'default-runtime-attributes': {}}}

    DEFAULT_CONCURRENT_JOB_LIMIT = 1000

    def __init__(self, backend_name, max_concurrent_tasks=DEFAULT_CONCURRENT_JOB_LIMIT):
        """
        Args:
            backend_name:
                Backend's name.
            max_concurrent_tasks:
                Maximum number of tasks (regardless of number of workflows).
        """
        super().__init__(deepcopy(CromwellBackendBase.TEMPLATE))

        if backend_name is None:
            raise ValueError('backend_name must be provided.')
        self._backend_name = backend_name

        self.backend = CromwellBackendBase.TEMPLATE_BACKEND

        config = self.backend_config
        config['concurrent-job-limit'] = max_concurrent_tasks

    @property
    def backend(self):
        return self['backend']['providers'][self._backend_name]

    @backend.setter
    def backend(self, backend):
        self['backend']['providers'][self._backend_name] = deepcopy(backend)

    def merge_backend(self, backend):
        merge_dict(self.backend, backend)

    @property
    def backend_config(self):
        return self.backend['config']

    @property
    def default_runtime_attributes(self):
        """Backend's default runtime attributes in self.backend_config.
        """
        return self.backend_config['default-runtime-attributes']


class CromwellBackendGCP(CromwellBackendBase):
    TEMPLATE = {'google': {'application-name': 'cromwell'}}
    TEMPLATE_BACKEND = {
        'config': {
            'default-runtime-attributes': {},
            'genomics-api-queries-per-100-seconds': 1000,
            'maximum-polling-interval': 600,
            'localization-attempts': 3,
            'genomics': {
                'restrict-metadata-access': False,
                'compute-service-account': 'default',
            },
            'filesystems': {'gcs': {'caching': {}}},
        }
    }
    ACTOR_FACTORY_V2ALPHA = (
        'cromwell.backend.google.pipelines.v2alpha1.PipelinesApiLifecycleActorFactory'
    )
    ACTOR_FACTORY_V2BETA = (
        'cromwell.backend.google.pipelines.v2beta.PipelinesApiLifecycleActorFactory'
    )
    GENOMICS_ENDPOINT_V2ALPHA = 'https://genomics.googleapis.com/'
    GENOMICS_ENDPOINT_V2BETA = 'https://lifesciences.googleapis.com/'
    DEFAULT_REGION = 'us-central1'

    CALL_CACHING_DUP_STRAT_REFERENCE = 'reference'
    CALL_CACHING_DUP_STRAT_COPY = 'copy'

    DEFAULT_GCP_CALL_CACHING_DUP_STRAT = CALL_CACHING_DUP_STRAT_REFERENCE

    def __init__(
        self,
        gcp_prj,
        gcp_out_dir,
        call_caching_dup_strat=DEFAULT_GCP_CALL_CACHING_DUP_STRAT,
        gcp_service_account_key_json=None,
        use_google_cloud_life_sciences=False,
        gcp_region=DEFAULT_REGION,
        gcp_zones=None,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
    ):
        """
        Args:
            gcp_service_account_key_json:
                Use this key JSON file to use service_account scheme
                instead of application_default.
            use_google_cloud_life_sciences:
                Use Google Cloud Life Sciences API (v2beta) instead of
                deprecated Genomics API (v2alpha1).
            gcp_region:
                Region for Google Cloud Life Sciences API.
            gcp_zones:
                List of zones for Genomics API.
                Ignored if use_google_cloud_life_sciences.
        """
        super().__init__(
            backend_name=BACKEND_GCP, max_concurrent_tasks=max_concurrent_tasks
        )
        merge_dict(self.data, CromwellBackendGCP.TEMPLATE)
        self.merge_backend(CromwellBackendGCP.TEMPLATE_BACKEND)

        config = self.backend_config
        genomics = config['genomics']
        filesystems = config['filesystems']

        if gcp_service_account_key_json:
            genomics['auth'] = 'service-account'
            filesystems['gcs']['auth'] = 'service-account'
            self['google']['auths'] = [
                {
                    'name': 'service-account',
                    'scheme': 'service_account',
                    'json-file': gcp_service_account_key_json,
                }
            ]
            # parse service account key JSON to get client_email.
            with open(gcp_service_account_key_json) as fp:
                key_json = json.loads(fp.read())
            genomics['compute-service-account'] = key_json['client_email']
        else:
            genomics['auth'] = 'application-default'
            filesystems['gcs']['auth'] = 'application-default'
            self['google']['auths'] = [
                {'name': 'application-default', 'scheme': 'application_default'}
            ]

        if use_google_cloud_life_sciences:
            self.backend['actor-factory'] = CromwellBackendGCP.ACTOR_FACTORY_V2BETA
            genomics['endpoint-url'] = CromwellBackendGCP.GENOMICS_ENDPOINT_V2BETA
            genomics['location'] = gcp_region
        else:
            self.backend['actor-factory'] = CromwellBackendGCP.ACTOR_FACTORY_V2ALPHA
            genomics['endpoint-url'] = CromwellBackendGCP.GENOMICS_ENDPOINT_V2ALPHA
            if gcp_zones:
                self.default_runtime_attributes['zones'] = ' '.join(gcp_zones)

        config['project'] = gcp_prj

        if not gcp_out_dir.startswith('gs://'):
            raise ValueError(
                'Wrong GCS bucket URI for gcp_out_dir: {v}'.format(v=gcp_out_dir)
            )
        config['root'] = gcp_out_dir

        caching = filesystems['gcs']['caching']
        if call_caching_dup_strat not in (
            CromwellBackendGCP.CALL_CACHING_DUP_STRAT_REFERENCE,
            CromwellBackendGCP.CALL_CACHING_DUP_STRAT_COPY,
        ):
            raise ValueError(
                'Wrong call_caching_dup_strat: {v}'.format(v=call_caching_dup_strat)
            )
        caching['duplication-strategy'] = call_caching_dup_strat


class CromwellBackendAWS(CromwellBackendBase):
    TEMPLATE = {
        'aws': {
            'application-name': 'cromwell',
            'auths': [{'name': 'default', 'scheme': 'default'}],
        },
        'engine': {'filesystems': {'s3': {'auth': 'default'}}},
    }
    TEMPLATE_BACKEND = {
        'actor-factory': 'cromwell.backend.impl.aws.AwsBatchBackendLifecycleActorFactory',
        'config': {
            'default-runtime-attributes': {},
            'numSubmitAttempts': 6,
            'numCreateDefinitionAttempts': 6,
            'auth': 'default',
            'filesystems': {'s3': {'auth': 'default'}},
        },
    }

    def __init__(
        self,
        aws_batch_arn,
        aws_region,
        aws_out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
    ):
        super().__init__(
            backend_name=BACKEND_AWS, max_concurrent_tasks=max_concurrent_tasks
        )
        merge_dict(self.data, CromwellBackendAWS.TEMPLATE)
        self.merge_backend(CromwellBackendAWS.TEMPLATE_BACKEND)

        aws = self[BACKEND_AWS]
        aws['region'] = aws_region

        config = self.backend_config
        if not aws_out_dir.startswith('s3://'):
            raise ValueError(
                'Wrong S3 bucket URI for aws_out_dir: {v}'.format(v=aws_out_dir)
            )
        config['root'] = aws_out_dir
        self.default_runtime_attributes['scriptBucketName'] = get_s3_bucket_name(
            aws_out_dir
        )
        self.default_runtime_attributes['queueArn'] = aws_batch_arn


class CromwellBackendLocal(CromwellBackendBase):
    """Class constants:
        MAKE_CMD_SUBMIT:
            Includes BASH command line for Singularity.
    """

    TEMPLATE_BACKEND = {
        'actor-factory': 'cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory',
        'config': {
            'script-epilogue': 'sleep 5',
            'filesystems': {
                'local': {
                    'localization': ['soft-link', 'hard-link', 'copy'],
                    'caching': {
                        'check-sibling-md5': True,
                        'duplication-strategy': ['soft-link', 'hard-link', 'copy'],
                    },
                }
            },
            'run-in-background': True,
            'runtime-attributes': dedent(
                """\
                Int? gpu
                String? docker
                String? docker_user
                String? singularity
                String? singularity_bindpath
                String? singularity_cachedir
                """
            ),
            'submit': dedent(
                """\
                if [ -z \\"$SINGULARITY_BINDPATH\\" ]; then export SINGULARITY_BINDPATH=${singularity_bindpath}; fi; \\
                if [ -z \\"$SINGULARITY_CACHEDIR\\" ]; then export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi;
                ${if !defined(singularity) then '/bin/bash ' + script
                  else
                    'singularity exec --cleanenv ' +
                    '--home ' + cwd + ' ' +
                    (if defined(gpu) then '--nv ' else '') +
                    singularity + ' /bin/bash ' + script}
            """
            ),
            'submit-docker': dedent(
                """\
                rm -f ${docker_cid}
                docker run \\
                  --cidfile ${docker_cid} \\
                  -i \\
                  ${'--user ' + docker_user} \\
                  --entrypoint ${job_shell} \\
                  -v ${cwd}:${docker_cwd} \\
                  ${docker} ${docker_script}
                """
            ),
        },
    }

    LOCAL_HASH_STRAT_FILE = 'file'
    LOCAL_HASH_STRAT_PATH = 'path'
    LOCAL_HASH_STRAT_PATH_MTIME = 'path+modtime'
    SOFT_GLOB_OUTPUT_CMD = 'ln -sL GLOB_PATTERN GLOB_DIRECTORY 2> /dev/null'

    DEFAULT_LOCAL_HASH_STRAT = LOCAL_HASH_STRAT_PATH_MTIME

    def __init__(
        self,
        local_out_dir,
        backend_name=BACKEND_LOCAL,
        soft_glob_output=False,
        local_hash_strat=DEFAULT_LOCAL_HASH_STRAT,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
    ):
        super().__init__(
            backend_name=backend_name, max_concurrent_tasks=max_concurrent_tasks
        )
        self.merge_backend(CromwellBackendLocal.TEMPLATE_BACKEND)

        config = self.backend_config
        filesystem_local = config['filesystems']['local']
        caching = filesystem_local['caching']

        if local_hash_strat not in (
            CromwellBackendLocal.LOCAL_HASH_STRAT_FILE,
            CromwellBackendLocal.LOCAL_HASH_STRAT_PATH,
            CromwellBackendLocal.LOCAL_HASH_STRAT_PATH_MTIME,
        ):
            raise ValueError(
                'Wrong local_hash_strat: {strat}'.format(strat=local_hash_strat)
            )
        caching['hashing-strategy'] = local_hash_strat

        if soft_glob_output:
            config['glob-link-command'] = CromwellBackendLocal.SOFT_GLOB_OUTPUT_CMD

        if local_out_dir is None:
            raise ValueError('local_out_dir must be provided.')
        config['root'] = local_out_dir


class CromwellBackendSLURM(CromwellBackendLocal):
    """SLURM backend.
    Try sbatching up to 3 times every 30 second.
    Some busy SLURM clusters spit out error, which results in a failure of the whole workflow

    Squeues every 30 second (up to 3 times)
    Unlike qstat -j JOB_ID, squeue -j JOB_ID doesn't return 1 when there is no such job
    So we need to use squeue -j JOB_ID --noheader and check if output is empty
    Try polling up to 3 times since squeue fails on some busy SLURM clusters
    e.g. on Stanford Sherlock, squeue didn't work when server is busy
    """

    TEMPLATE_BACKEND = {
        'config': {
            'default-runtime-attributes': {'time': 24},
            'exit-code-timeout-seconds': 360,
            'runtime-attributes': dedent(
                """\
                String? docker
                String? docker_user
                Int cpu = 1
                Int? gpu
                Int? time
                Int? memory_mb
                String? slurm_partition
                String? slurm_account
                String? slurm_extra_param
                String? singularity
                String? singularity_bindpath
                String? singularity_cachedir
            """
            ),
            'submit': dedent(
                """\
                if [ -z \\"$SINGULARITY_BINDPATH\\" ]; then export SINGULARITY_BINDPATH=${singularity_bindpath}; fi; \\
                if [ -z \\"$SINGULARITY_CACHEDIR\\" ]; then export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi;

                ITER=0
                until [ $ITER -ge 3 ]; do
                    sbatch \\
                        --export=ALL \\
                        -J ${job_name} \\
                        -D ${cwd} \\
                        -o ${out} \\
                        -e ${err} \\
                        ${'-t ' + time*60} \\
                        -n 1 \\
                        --ntasks-per-node=1 \\
                        ${'--cpus-per-task=' + cpu} \\
                        ${true="--mem=" false="" defined(memory_mb)}${memory_mb} \\
                        ${'-p ' + slurm_partition} \\
                        ${'--account ' + slurm_account} \\
                        ${'--gres gpu:' + gpu} \\
                        ${slurm_extra_param} \\
                        --wrap "${if !defined(singularity) then '/bin/bash ' + script
                                  else
                                    'singularity exec --cleanenv ' +
                                    '--home ' + cwd + ' ' +
                                    (if defined(gpu) then '--nv ' else '') +
                                    singularity + ' /bin/bash ' + script}" \\
                        && break
                    ITER=$[$ITER+1]
                    sleep 30
                done
            """
            ),
            'check-alive': dedent(
                """\
                for ITER in 1 2 3; do
                    CHK_ALIVE=$(squeue --noheader -j ${job_id} --format=%i | grep ${job_id})
                    if [ -z "$CHK_ALIVE" ]; then if [ "$ITER" == 3 ]; then /bin/bash -c 'exit 1'; else sleep 30; fi; else echo $CHK_ALIVE; break; fi
                done
            """
            ),
            'kill': 'scancel ${job_id}',
            'job-id-regex': 'Submitted batch job (\\d+).*',
        }
    }

    def __init__(
        self,
        local_out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        slurm_partition=None,
        slurm_account=None,
        slurm_extra_param=None,
    ):
        super().__init__(
            local_out_dir=local_out_dir,
            backend_name=BACKEND_SLURM,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
        )
        self.merge_backend(CromwellBackendSLURM.TEMPLATE_BACKEND)
        self.backend_config.pop('submit-docker')

        if slurm_partition:
            self.default_runtime_attributes['slurm_partition'] = slurm_partition
        if slurm_account:
            self.default_runtime_attributes['slurm_account'] = slurm_account
        if slurm_extra_param:
            self.default_runtime_attributes['slurm_extra_param'] = slurm_extra_param


class CromwellBackendSGE(CromwellBackendLocal):
    TEMPLATE_BACKEND = {
        'config': {
            'default-runtime-attributes': {'time': 24},
            'exit-code-timeout-seconds': 180,
            'runtime-attributes': dedent(
                """\
                String? docker
                String? docker_user
                String sge_pe = "shm"
                Int cpu = 1
                Int? gpu
                Int? time
                Int? memory_mb
                String? sge_queue
                String? sge_extra_param
                String? singularity
                String? singularity_bindpath
                String? singularity_cachedir
            """
            ),
            'submit': dedent(
                """\
                if [ -z \\"$SINGULARITY_BINDPATH\\" ]; then export SINGULARITY_BINDPATH=${singularity_bindpath}; fi; \\
                if [ -z \\"$SINGULARITY_CACHEDIR\\" ]; then export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi;

                echo "${if !defined(singularity) then '/bin/bash ' + script
                        else
                          'singularity exec --cleanenv ' +
                          '--home ' + cwd + ' ' +
                          (if defined(gpu) then '--nv ' else '') +
                          singularity + ' /bin/bash ' + script}" | \\
                qsub \\
                    -S /bin/sh \\
                    -terse \\
                    -b n \\
                    -N ${job_name} \\
                    -wd ${cwd} \\
                    -o ${out} \\
                    -e ${err} \\
                    ${if cpu>1 then '-pe ' + sge_pe + ' ' else ''} \\
                    ${if cpu>1 then cpu else ''} \\
                    ${true="-l h_vmem=$(expr " false="" defined(memory_mb)}${memory_mb}${true=" / " false="" defined(memory_mb)}${if defined(memory_mb) then cpu else ""}${true=")m" false="" defined(memory_mb)} \\
                    ${true="-l s_vmem=$(expr " false="" defined(memory_mb)}${memory_mb}${true=" / " false="" defined(memory_mb)}${if defined(memory_mb) then cpu else ""}${true=")m" false="" defined(memory_mb)} \\
                    ${'-l h_rt=' + time + ':00:00'} \\
                    ${'-l s_rt=' + time + ':00:00'} \\
                    ${'-q ' + sge_queue} \\
                    ${'-l gpu=' + gpu} \\
                    ${sge_extra_param} \\
                    -V
            """
            ),
            'check-alive': 'qstat -j ${job_id}',
            'kill': 'qdel ${job_id}',
            'job-id-regex': '(\\d+)',
        }
    }

    def __init__(
        self,
        local_out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        sge_pe=None,
        sge_queue=None,
        sge_extra_param=None,
    ):
        super().__init__(
            local_out_dir=local_out_dir,
            backend_name=BACKEND_SGE,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
        )
        self.merge_backend(CromwellBackendSGE.TEMPLATE_BACKEND)
        self.backend_config.pop('submit-docker')

        if sge_pe:
            self.default_runtime_attributes['sge_pe'] = sge_pe
        if sge_queue:
            self.default_runtime_attributes['sge_queue'] = sge_queue
        if sge_extra_param:
            self.default_runtime_attributes['sge_extra_param'] = sge_extra_param


class CromwellBackendPBS(CromwellBackendLocal):
    TEMPLATE_BACKEND = {
        'config': {
            'default-runtime-attributes': {'time': 24},
            'script-epilogue': 'sleep 5',
            'runtime-attributes': dedent(
                """\
                String? docker
                String? docker_user
                Int cpu = 1
                Int? gpu
                Int? time
                Int? memory_mb
                String? pbs_queue
                String? pbs_extra_param
                String? singularity
                String? singularity_bindpath
                String? singularity_cachedir
            """
            ),
            'submit': dedent(
                """\
                if [ -z \\"$SINGULARITY_BINDPATH\\" ]; then export SINGULARITY_BINDPATH=${singularity_bindpath}; fi; \\
                if [ -z \\"$SINGULARITY_CACHEDIR\\" ]; then export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi;

                echo "${if !defined(singularity) then '/bin/bash ' + script
                        else
                          'singularity exec --cleanenv ' +
                          '--home ' + cwd + ' ' +
                          (if defined(gpu) then '--nv ' else '') +
                          singularity + ' /bin/bash ' + script}" | \\
                qsub \\
                    -N ${job_name} \\
                    -o ${out} \\
                    -e ${err} \\
                    ${true="-lnodes=1:ppn=" false="" defined(cpu)}${cpu}${true=":mem=" false="" defined(memory_mb)}${memory_mb}${true="mb" false="" defined(memory_mb)} \\
                    ${'-lwalltime=' + time + ':0:0'} \\
                    ${'-lngpus=' + gpu} \\
                    ${'-q ' + pbs_queue} \\
                    ${pbs_extra_param} \\
                    -V
            """
            ),
            'exit-code-timeout-seconds': 180,
            'kill': 'qdel ${job_id}',
            'check-alive': 'qstat ${job_id}',
            'job-id-regex': '(\\d+)',
        }
    }

    def __init__(
        self,
        local_out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        pbs_queue=None,
        pbs_extra_param=None,
    ):
        super().__init__(
            local_out_dir=local_out_dir,
            backend_name=BACKEND_PBS,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
        )
        self.merge_backend(CromwellBackendPBS.TEMPLATE_BACKEND)
        self.backend_config.pop('submit-docker')

        if pbs_queue:
            self.default_runtime_attributes['pbs_queue'] = pbs_queue
        if pbs_extra_param:
            self.default_runtime_attributes['pbs_extra_param'] = pbs_extra_param
