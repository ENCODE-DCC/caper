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
BACKEND_LSF = 'lsf'
DEFAULT_BACKEND = BACKEND_LOCAL

ENVIRONMENT_DOCKER = 'docker'
ENVIRONMENT_SINGULARITY = 'singularity'
ENVIRONMENT_CONDA = 'conda'

FILESYSTEM_GCS = 'gcs'
FILESYSTEM_LOCAL = 'local'
FILESYSTEM_S3 = 's3'

LOCALIZATION_STRAT_COPY = 'copy'
LOCALIZATION_STRAT_HARDLINK = 'hard-link'
LOCALIZATION_STRAT_SOFTLINK = 'soft-link'

CALL_CACHING_DUP_STRAT_COPY = 'copy'
CALL_CACHING_DUP_STRAT_HARDLINK = 'hard-link'
CALL_CACHING_DUP_STRAT_REFERENCE = 'reference'
CALL_CACHING_DUP_STRAT_SOFTLINK = 'soft-link'

LOCAL_HASH_STRAT_FILE = 'file'
LOCAL_HASH_STRAT_PATH = 'path'
LOCAL_HASH_STRAT_PATH_MTIME = 'path+modtime'
SOFT_GLOB_OUTPUT_CMD = 'ln -sL GLOB_PATTERN GLOB_DIRECTORY 2> /dev/null'


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
        'akka': {'http': {'server': {'request-timeout': '60 seconds'}}},
    }

    DEFAULT_MAX_CONCURRENT_WORKFLOWS = 40
    DEFAULT_MEMORY_RETRY_ERROR_KEYS = ('OutOfMemory', 'Killed')

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
        # if memory_retry_error_keys:
        #     if isinstance(memory_retry_error_keys, tuple):
        #         memory_retry_error_keys = list(memory_retry_error_keys)
        #     self['system']['memory-retry-error-keys'] = memory_retry_error_keys


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
    TEMPLATE_BACKEND = {'config': {'default-runtime-attributes': {}, 'filesystems': {}}}
    DEFAULT_CALL_CACHING_DUP_STRAT = (
        CALL_CACHING_DUP_STRAT_SOFTLINK,
        CALL_CACHING_DUP_STRAT_HARDLINK,
        CALL_CACHING_DUP_STRAT_COPY,
    )
    DEFAULT_CONCURRENT_JOB_LIMIT = 1000

    def __init__(
        self,
        backend_name,
        max_concurrent_tasks=DEFAULT_CONCURRENT_JOB_LIMIT,
        filesystem_name=None,
        call_caching_dup_strat=DEFAULT_CALL_CACHING_DUP_STRAT,
    ):
        """
        Args:
            backend_name:
                Backend's name.
            max_concurrent_tasks:
                Maximum number of tasks (regardless of number of workflows).
            filesystem_name:
                Filesystem's name to set up call-caching strategy within.
            call_caching_dup_strat:
                Call-caching strategy string.
                This can be either a strategy or a list of strategies.
        """
        super().__init__(deepcopy(CromwellBackendBase.TEMPLATE))

        if backend_name is None:
            raise ValueError('backend_name must be provided.')
        self._backend_name = backend_name

        self.backend = CromwellBackendBase.TEMPLATE_BACKEND

        config = self.backend_config
        config['concurrent-job-limit'] = max_concurrent_tasks

        if filesystem_name:
            if isinstance(call_caching_dup_strat, tuple):
                call_caching_dup_strat = list(call_caching_dup_strat)

            config['filesystems'][filesystem_name] = {
                'caching': {'duplication-strategy': call_caching_dup_strat}
            }

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


class CromwellBackendGcp(CromwellBackendBase):
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
    DEFAULT_CALL_CACHING_DUP_STRAT = CALL_CACHING_DUP_STRAT_REFERENCE

    def __init__(
        self,
        gcp_prj,
        gcp_out_dir,
        gcp_service_account_key_json=None,
        use_google_cloud_life_sciences=False,
        gcp_region=DEFAULT_REGION,
        gcp_zones=None,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        call_caching_dup_strat=DEFAULT_CALL_CACHING_DUP_STRAT,
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
        if call_caching_dup_strat not in (
            CALL_CACHING_DUP_STRAT_REFERENCE,
            CALL_CACHING_DUP_STRAT_COPY,
        ):
            raise ValueError(
                'Wrong call_caching_dup_strat for GCP: {v}'.format(
                    v=call_caching_dup_strat
                )
            )

        super().__init__(
            backend_name=BACKEND_GCP,
            max_concurrent_tasks=max_concurrent_tasks,
            filesystem_name=FILESYSTEM_GCS,
            call_caching_dup_strat=call_caching_dup_strat,
        )
        merge_dict(self.data, CromwellBackendGcp.TEMPLATE)
        self.merge_backend(CromwellBackendGcp.TEMPLATE_BACKEND)

        config = self.backend_config
        genomics = config['genomics']
        filesystems = config['filesystems']

        if gcp_service_account_key_json:
            genomics['auth'] = 'service-account'
            filesystems[FILESYSTEM_GCS]['auth'] = 'service-account'
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
            filesystems[FILESYSTEM_GCS]['auth'] = 'application-default'
            self['google']['auths'] = [
                {'name': 'application-default', 'scheme': 'application_default'}
            ]

        if use_google_cloud_life_sciences:
            self.backend['actor-factory'] = CromwellBackendGcp.ACTOR_FACTORY_V2BETA
            genomics['endpoint-url'] = CromwellBackendGcp.GENOMICS_ENDPOINT_V2BETA
            genomics['location'] = gcp_region
        else:
            self.backend['actor-factory'] = CromwellBackendGcp.ACTOR_FACTORY_V2ALPHA
            genomics['endpoint-url'] = CromwellBackendGcp.GENOMICS_ENDPOINT_V2ALPHA
            if gcp_zones:
                self.default_runtime_attributes['zones'] = ' '.join(gcp_zones)

        config['project'] = gcp_prj

        if not gcp_out_dir.startswith('gs://'):
            raise ValueError(
                'Wrong GCS bucket URI for gcp_out_dir: {v}'.format(v=gcp_out_dir)
            )
        config['root'] = gcp_out_dir


class CromwellBackendAws(CromwellBackendBase):
    TEMPLATE = {
        'aws': {
            'application-name': 'cromwell',
            'auths': [{'name': 'default', 'scheme': 'default'}],
        },
        'engine': {'filesystems': {FILESYSTEM_S3: {'auth': 'default'}}},
    }
    TEMPLATE_BACKEND = {
        'actor-factory': 'cromwell.backend.impl.aws.AwsBatchBackendLifecycleActorFactory',
        'config': {
            'default-runtime-attributes': {},
            'numSubmitAttempts': 6,
            'numCreateDefinitionAttempts': 6,
            'auth': 'default',
            'filesystems': {FILESYSTEM_S3: {'auth': 'default'}},
        },
    }
    DEFAULT_CALL_CACHING_DUP_STRAT = CALL_CACHING_DUP_STRAT_REFERENCE

    def __init__(
        self,
        aws_batch_arn,
        aws_region,
        aws_out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        call_caching_dup_strat=DEFAULT_CALL_CACHING_DUP_STRAT,
    ):
        if call_caching_dup_strat not in (
            CALL_CACHING_DUP_STRAT_REFERENCE,
            CALL_CACHING_DUP_STRAT_COPY,
        ):
            raise ValueError(
                'Wrong call_caching_dup_strat for S3: {v}'.format(
                    v=call_caching_dup_strat
                )
            )
        if call_caching_dup_strat == CALL_CACHING_DUP_STRAT_REFERENCE:
            logger.warning(
                'Warning for aws backend: "reference" mode for call_caching_dup_strat currently '
                'does not work with Cromwell<=61. Cromwell will still use the "copy" mode '
                'It will make cache copies for all call-cached outputs, which will lead to '
                'unnecessary extra charge for the output S3 bucket. '
                '"reference" mode on gcp backend works fine. '
                'See the following link for details. '
                'https://github.com/broadinstitute/cromwell/issues/6327. '
                'It is recommend to clean up previous workflow\'s outputs manually '
                'with "caper cleanup WORKFLOW_ID_OR_METADATA_JSON_FILE" or '
                'with AWS CLI. e.g. '
                '"aws s3 rm --recursive s3://some-bucket/a/b/c/WORKFLOW_ID". '
            )
        super().__init__(
            backend_name=BACKEND_AWS,
            max_concurrent_tasks=max_concurrent_tasks,
            filesystem_name=FILESYSTEM_S3,
            call_caching_dup_strat=call_caching_dup_strat,
        )
        merge_dict(self.data, CromwellBackendAws.TEMPLATE)
        self.merge_backend(CromwellBackendAws.TEMPLATE_BACKEND)

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

        SUBMIT_DOCKER:
            Cromwell falls back to 'submit_docker' instead of 'submit' if WDL task has
            'docker' in runtime and runtime-attributes are declared in backend's config.

            Docker and Singularity can map paths between inside and outside of the container.
            So this is not an issue for those container environments.

            For Conda, any container paths (docker_cwd, e.g. /cromwell-executions/**)
            in the script is simply replaced with CWD.

            This also replaces filenames written in write_*.tsv files (globbed by WDL functions).
            e.g. write_lines(), write_tsv(), ...

            See the following document for such WDL functions:
            https://github.com/openwdl/wdl/blob/main/versions/development/SPEC.md#file-write_linesarraystring

            Possible issue:
            - 'sed' is used here with a delimiter as hash mark (#)
              so hash marks in output path can result in error.
            - Files globbed by WDL functions other than write_*() will still have paths inside a container.
    """

    RUNTIME_ATTRIBUTES = dedent(
        """
        ## Caper custom attributes
        # Environment choices = (docker, conda, singularity)
        # If environment is not specified then prioritize docker > singularity > conda
        # gpu is a plain string (to be able to specify gpu's name)
        String? environment
        String? conda
        String? singularity
        String? singularity_bindpath
        String? gpu
    """
    )
    # need to separate docker-related attributes
    # to be able ignore docker in WDL task's runtime
    RUNTIME_ATTRIBUTES_DOCKER = dedent(
        """
        ## Cromwell built-in attributes for docker
        String? docker
        String? docker_user
    """
    )
    SUBMIT = dedent(
        """
        if [ '${defined(environment)}' == 'true' ] && [ '${environment}' == 'singularity' ] || \\
           [ '${defined(environment)}' == 'false' ] && [ '${defined(singularity)}' == 'true' ] && [ ! -z '${singularity}' ]
        then
            mkdir -p $HOME/.singularity/lock/
            flock --exclusive --timeout 600 \\
                $HOME/.singularity/lock/`echo -n '${singularity}' | md5sum | cut -d' ' -f1` \\
                singularity exec --containall ${singularity} echo 'Successfully pulled ${singularity}'

            singularity exec --cleanenv --home=`dirname ${cwd}` \\
                --bind=${singularity_bindpath}, \\
                ${if defined(gpu) then ' --nv' else ''} \\
                ${singularity} ${job_shell} ${script}

        elif [ '${defined(environment)}' == 'true' ] && [ '${environment}' == 'conda' ] || \\
             [ '${defined(environment)}' == 'false' ] && [ '${defined(conda)}' == 'true' ] && [ ! -z '${conda}' ]
        then
            conda run --name=${conda} ${job_shell} ${script}

        else
            ${job_shell} ${script}
        fi
    """
    )
    SUBMIT_DOCKER = dedent(
        """
        rm -f ${docker_cid}

        if [ '${defined(environment)}' == 'true' ] && [ '${environment}' == 'docker' ] || \\
           [ '${defined(environment)}' == 'false' ] && [ '${defined(docker)}' == 'true' ] && [ ! -z '${docker}' ]
        then
            docker run -i --cidfile=${docker_cid} --user=${docker_user} --entrypoint=${job_shell} \\
              --volume=${cwd}:${docker_cwd}:delegated ${docker} ${docker_script}
            rc=$(docker wait `cat ${docker_cid}`)
            docker rm `cat ${docker_cid}`
        else
            # recover GID lost due to Cromwell running chmod 777 on CWD
            chown :`stat -c '%G' ${cwd}` -R ${cwd}
            chmod g+s ${cwd}

            if [ '${defined(environment)}' == 'true' ] && [ '${environment}' == 'singularity' ] || \\
               [ '${defined(environment)}' == 'false' ] && [ '${defined(singularity)}' == 'true' ] && [ ! -z '${singularity}' ]
            then
                mkdir -p $HOME/.singularity/lock/
                flock --exclusive --timeout 600 \\
                    $HOME/.singularity/lock/`echo -n '${singularity}' | md5sum | cut -d' ' -f1` \\
                    singularity exec --containall ${singularity} echo 'Successfully pulled ${singularity}'

                singularity exec --cleanenv --home=`dirname ${cwd}` \\
                    --bind=${singularity_bindpath},${cwd}:${docker_cwd} \\
                    ${if defined(gpu) then ' --nv' else ''} \\
                    ${singularity} ${job_shell} ${script} & echo $! > ${docker_cid}
            else
                # remap paths between inside and outside of a docker container
                shopt -s nullglob
                sed -i 's#${docker_cwd}#${cwd}#g' ${script} `dirname ${script}`/write_*.tmp

                if [ '${defined(environment)}' == 'true' ] && [ '${environment}' == 'conda' ] || \\
                   [ '${defined(environment)}' == 'false' ] && [ '${defined(conda)}' == 'true' ] && [ ! -z '${conda}' ]
                then
                    conda run --name=${conda} ${job_shell} ${script} & echo $! > ${docker_cid}
                else
                    ${job_shell} ${script} & echo $! > ${docker_cid}
                fi
            fi

            touch ${docker_cid}.not_docker
            wait `cat ${docker_cid}`
            rc=`echo $?`
        fi

        exit $rc
    """
    )
    KILL_DOCKER = dedent(
        """
        if [ -f '${docker_cid}.not_docker' ]
        then
            kill `cat ${docker_cid}`
        else
            docker kill `cat ${docker_cid}`
        fi
    """
    )
    TEMPLATE_BACKEND = {
        'actor-factory': 'cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory',
        'config': {
            'script-epilogue': 'sleep 5',
            'filesystems': {
                FILESYSTEM_LOCAL: {
                    'localization': [
                        LOCALIZATION_STRAT_SOFTLINK,
                        LOCALIZATION_STRAT_HARDLINK,
                        LOCALIZATION_STRAT_COPY,
                    ],
                    'caching': {'check-sibling-md5': True},
                }
            },
            'run-in-background': True,
            'runtime-attributes': RUNTIME_ATTRIBUTES + RUNTIME_ATTRIBUTES_DOCKER,
            'submit': SUBMIT,
            'submit-docker': SUBMIT_DOCKER,
            'kill-docker': KILL_DOCKER,
        },
    }
    DEFAULT_LOCAL_HASH_STRAT = LOCAL_HASH_STRAT_PATH_MTIME

    def __init__(
        self,
        local_out_dir,
        backend_name=BACKEND_LOCAL,
        soft_glob_output=False,
        local_hash_strat=DEFAULT_LOCAL_HASH_STRAT,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
    ):
        """Base class for local backends.

        Used flock to synchronize local Singularity image building.
        Image building will occur in the first task and other parallel tasks will wait.

        See https://github.com/broadinstitute/cromwell/issues/5063 for details.
        """
        super().__init__(
            backend_name=backend_name,
            max_concurrent_tasks=max_concurrent_tasks,
            filesystem_name=FILESYSTEM_LOCAL,
        )
        self.merge_backend(CromwellBackendLocal.TEMPLATE_BACKEND)

        config = self.backend_config
        filesystem_local = config['filesystems'][FILESYSTEM_LOCAL]
        caching = filesystem_local['caching']

        if local_hash_strat not in (
            LOCAL_HASH_STRAT_FILE,
            LOCAL_HASH_STRAT_PATH,
            LOCAL_HASH_STRAT_PATH_MTIME,
        ):
            raise ValueError(
                'Wrong local_hash_strat: {strat}'.format(strat=local_hash_strat)
            )
        caching['hashing-strategy'] = local_hash_strat

        if soft_glob_output:
            config['glob-link-command'] = SOFT_GLOB_OUTPUT_CMD

        if local_out_dir is None:
            raise ValueError('local_out_dir must be provided.')
        config['root'] = local_out_dir


class CromwellBackendHpc(CromwellBackendLocal):
    HPC_RUNTIME_ATTRIBUTES = dedent(
        """
        Int cpu = 1
        Int? time
        Int? memory_mb
    """
    )

    def __init__(
        self,
        local_out_dir,
        backend_name=None,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        check_alive=None,
        kill=None,
        job_id_regex=None,
        submit=None,
        runtime_attributes=None,
    ):
        """Base class for HPCs.
        No docker support. docker attribute in WDL task's runtime will be just ignored.

        Args:
            check_alive:
                Shell command lines to check if a job exists.
                WDL syntax allowed in ${} notation.
            kill:
                Shell command lines to kill a job.
                WDL syntax allowed in ${} notation.
                This will be passed to both 'kill' and 'kill-docker'.
                On HPCs jobs are managed in terms of job ID (not PID).
            job_id_regex:
                Regular expression to find job ID.
                Make sure to escape backslash (\\) since this is directly used in a shell script.
                WDL syntax NOT allowed.
            submit:
                Shell command lines to submit a job.
                WDL syntax allowed in ${} notation.
            runtime_attributes:
                Declaration of WDL variables (attributes) used in submit, submit-docker.
                This is not a shell command line but plain WDL syntax.
                Make sure that non-Cromwell variables (attributes) used in submit, submit-docker
                are defined here.
                e.g. cpu, memory, docker, docker_user are Cromwell's built-in variables
                so they don't need to be defined but slurm_partition, sge_pe are
                Caper's custom variables so such variables should be defined there.
        """
        super().__init__(
            local_out_dir=local_out_dir,
            backend_name=backend_name,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
        )
        config = self.backend_config

        if not check_alive:
            raise ValueError('check_alive not defined!')
        if not kill:
            raise ValueError('kill not defined!')
        if not job_id_regex:
            raise ValueError('job_id_regex not defined!')
        if not submit:
            raise ValueError('submit not defined!')

        config['check-alive'] = check_alive
        config['kill'] = kill
        # jobs are managed based on a job ID (not PID or docker_cid) on HPCs
        config['kill-docker'] = None
        config['job-id-regex'] = job_id_regex
        config['submit'] = submit
        config['submit-docker'] = None
        config['runtime-attributes'] = '\n'.join(
            [
                CromwellBackendLocal.RUNTIME_ATTRIBUTES,
                CromwellBackendHpc.HPC_RUNTIME_ATTRIBUTES,
                runtime_attributes if runtime_attributes else '',
            ]
        )


class CromwellBackendSlurm(CromwellBackendHpc):
    SLURM_RUNTIME_ATTRIBUTES = dedent(
        """
        String? slurm_partition
        String? slurm_account
        String? slurm_extra_param
    """
    )
    SLURM_CHECK_ALIVE = dedent(
        """
        for ITER in 1 2 3
        do
            CHK_ALIVE=$(squeue --noheader -j ${job_id} --format=%i | grep ${job_id})
            if [ -z "$CHK_ALIVE" ]
            then
                if [ "$ITER" == 3 ]
                then
                    ${job_shell} -c 'exit 1'
                else
                    sleep 30
                fi
            else
                echo $CHK_ALIVE
                break
            fi
        done
    """
    )
    SLURM_KILL = 'scancel ${job_id}'
    SLURM_JOB_ID_REGEX = 'Submitted batch job ([0-9]+).*'

    # this is a template that requires formatting
    # (submit, slurm_resource_param)
    TEMPLATE_SLURM_SUBMIT = dedent(
        """
        cat << EOF > ${{script}}.caper
        #!/bin/bash
        {submit}
        EOF

        for ITER in 1 2 3
        do
            sbatch --export=ALL -J ${{job_name}} -D ${{cwd}} -o ${{out}} -e ${{err}} \\
                ${{'-p ' + slurm_partition}} ${{'--account ' + slurm_account}} \\
                {slurm_resource_param} \\
                ${{slurm_extra_param}} \\
                ${{script}}.caper && exit 0
            sleep 30
        done
        exit 1
    """
    )
    DEFAULT_SLURM_RESOURCE_PARAM = (
        '-n 1 --ntasks-per-node=1 --cpus-per-task=${cpu} '
        '${if defined(memory_mb) then "--mem=" else ""}${memory_mb}${if defined(memory_mb) then "M" else ""} '
        '${if defined(time) then "--time=" else ""}${time*60} '
        '${if defined(gpu) then "--gres=gpu:" else ""}${gpu} '
    )

    def __init__(
        self,
        local_out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        slurm_partition=None,
        slurm_account=None,
        slurm_extra_param=None,
        slurm_resource_param=DEFAULT_SLURM_RESOURCE_PARAM,
    ):
        """SLURM backend.
        Try sbatching up to 3 times every 30 second to prevent Cromwell
        from halting the whole pipeline immediately after the first failure.

        Example busy server errors:
            slurm_load_jobs error: Socket timed out on send/recv operation
            slurm_load_jobs error: Slurm backup controller in standby mode

        Squeues every 30 second up to 3 times for the same reason.
        Unlike qstat -j JOB_ID, squeue -j JOB_ID doesn't return 1 when there is no such job
        So 'squeue --noheader -j JOB_ID' is used here and it checks if output is empty

        Args:
            slurm_resource_param:
                String of a set of resource parameters for the job submission engine.
                WDL syntax allowed in ${} notation.
                This will be appended to the job sumbission command line.
                e.g. sbatch ... THIS_RESOURCE_PARAM
        """
        submit = CromwellBackendSlurm.TEMPLATE_SLURM_SUBMIT.format(
            submit=CromwellBackendLocal.SUBMIT,
            slurm_resource_param=slurm_resource_param,
        )

        super().__init__(
            local_out_dir=local_out_dir,
            backend_name=BACKEND_SLURM,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
            check_alive=CromwellBackendSlurm.SLURM_CHECK_ALIVE,
            kill=CromwellBackendSlurm.SLURM_KILL,
            job_id_regex=CromwellBackendSlurm.SLURM_JOB_ID_REGEX,
            submit=submit,
            runtime_attributes=CromwellBackendSlurm.SLURM_RUNTIME_ATTRIBUTES,
        )

        if slurm_partition:
            self.default_runtime_attributes['slurm_partition'] = slurm_partition
        if slurm_account:
            self.default_runtime_attributes['slurm_account'] = slurm_account
        if slurm_extra_param:
            self.default_runtime_attributes['slurm_extra_param'] = slurm_extra_param


class CromwellBackendSge(CromwellBackendHpc):
    SGE_RUNTIME_ATTRIBUTES = dedent(
        """
        String? sge_pe
        String? sge_queue
        String? sge_extra_param
    """
    )
    SGE_CHECK_ALIVE = 'qstat -j ${job_id}'
    SGE_KILL = 'qdel ${job_id}'

    # qsub -terse is used to simply this regex
    SGE_JOB_ID_REGEX = '([0-9]+)'

    # this is a template that requires formatting
    # (submit, sge_resource_param)
    TEMPLATE_SGE_SUBMIT = dedent(
        """
        cat << EOF > ${{script}}.caper
        #!/bin/bash
        {submit}
        EOF

        for ITER in 1 2 3; do
            qsub -V -terse -S ${{job_shell}} -N ${{job_name}} -wd ${{cwd}} -o ${{out}} -e ${{err}} \\
                ${{'-q ' + sge_queue}} \\
                {sge_resource_param} \\
                ${{sge_extra_param}} \\
                ${{script}}.caper && break
            sleep 30
        done
    """
    )
    DEFAULT_SGE_RESOURCE_PARAM = (
        '${if cpu > 1 then "-pe " + sge_pe + " " else ""} ${if cpu > 1 then cpu else ""} '
        '${true="-l h_vmem=$(expr " false="" defined(memory_mb)}${memory_mb}${true=" / " false="" defined(memory_mb)}${if defined(memory_mb) then cpu else ""}${true=")m" false="" defined(memory_mb)} '
        '${true="-l s_vmem=$(expr " false="" defined(memory_mb)}${memory_mb}${true=" / " false="" defined(memory_mb)}${if defined(memory_mb) then cpu else ""}${true=")m" false="" defined(memory_mb)} '
        '${"-l h_rt=" + time + ":00:00"} ${"-l s_rt=" + time + ":00:00"} '
        '${"-l gpu=" + gpu} '
    )

    def __init__(
        self,
        local_out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        sge_pe=None,
        sge_queue=None,
        sge_extra_param=None,
        sge_resource_param=DEFAULT_SGE_RESOURCE_PARAM,
    ):
        """SGE backend. Try qsubbing up to 3 times every 30 second.

        Args:
            sge_resource_param:
                String of a set of resource parameters for the job submission engine.
                WDL syntax allowed in ${} notation.
                This will be appended to the job sumbission command line.
                e.g. qsub ... THIS_RESOURCE_PARAM
        """
        submit = CromwellBackendSge.TEMPLATE_SGE_SUBMIT.format(
            submit=CromwellBackendLocal.SUBMIT, sge_resource_param=sge_resource_param
        )

        super().__init__(
            local_out_dir=local_out_dir,
            backend_name=BACKEND_SGE,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
            check_alive=CromwellBackendSge.SGE_CHECK_ALIVE,
            kill=CromwellBackendSge.SGE_KILL,
            job_id_regex=CromwellBackendSge.SGE_JOB_ID_REGEX,
            submit=submit,
            runtime_attributes=CromwellBackendSge.SGE_RUNTIME_ATTRIBUTES,
        )

        if sge_pe:
            self.default_runtime_attributes['sge_pe'] = sge_pe
        if sge_queue:
            self.default_runtime_attributes['sge_queue'] = sge_queue
        if sge_extra_param:
            self.default_runtime_attributes['sge_extra_param'] = sge_extra_param


class CromwellBackendPbs(CromwellBackendHpc):
    PBS_RUNTIME_ATTRIBUTES = dedent(
        """
        String? pbs_queue
        String? pbs_extra_param
    """
    )
    PBS_CHECK_ALIVE = 'qstat ${job_id}'
    PBS_KILL = 'qdel ${job_id}'
    PBS_JOB_ID_REGEX = '([0-9]+)'

    # this is a template that requires formatting
    # (submit, pbs_resource_param)
    TEMPLATE_PBS_SUBMIT = dedent(
        """
        cat << EOF > ${{script}}.caper
        #!/bin/bash
        {submit}
        EOF

        for ITER in 1 2 3; do
            qsub -V -N ${{job_name}} -o ${{out}} -e ${{err}} \\
                ${{'-q ' + pbs_queue}} \\
                {pbs_resource_param} \\
                ${{pbs_extra_param}} \\
                ${{script}}.caper && break
            sleep 30
        done
    """
    )
    DEFAULT_PBS_RESOURCE_PARAM = (
        '${"-lnodes=1:ppn=" + cpu}${if defined(gpu) then ":gpus=" + gpu else ""} '
        '${if defined(memory_mb) then "-l mem=" else ""}${memory_mb}${if defined(memory_mb) then "mb" else ""} '
        '${"-lwalltime=" + time + ":0:0"} '
    )

    def __init__(
        self,
        local_out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        pbs_queue=None,
        pbs_extra_param=None,
        pbs_resource_param=DEFAULT_PBS_RESOURCE_PARAM,
    ):
        """PBS backend. Try qsubbing up to 3 times every 30 second.

        Args:
            pbs_resource_param:
                String of a set of resource parameters for the job submission engine.
                WDL syntax allowed in ${} notation.
                This will be appended to the job sumbission command line.
                e.g. qsub ... THIS_RESOURCE_PARAM
        """
        submit = CromwellBackendPbs.TEMPLATE_PBS_SUBMIT.format(
            submit=CromwellBackendLocal.SUBMIT, pbs_resource_param=pbs_resource_param
        )

        super().__init__(
            local_out_dir=local_out_dir,
            backend_name=BACKEND_PBS,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
            check_alive=CromwellBackendPbs.PBS_CHECK_ALIVE,
            kill=CromwellBackendPbs.PBS_KILL,
            job_id_regex=CromwellBackendPbs.PBS_JOB_ID_REGEX,
            submit=submit,
            runtime_attributes=CromwellBackendPbs.PBS_RUNTIME_ATTRIBUTES,
        )

        if pbs_queue:
            self.default_runtime_attributes['pbs_queue'] = pbs_queue
        if pbs_extra_param:
            self.default_runtime_attributes['pbs_extra_param'] = pbs_extra_param


class CromwellBackendLsf(CromwellBackendHpc):
    LSF_RUNTIME_ATTRIBUTES = dedent(
        """
        String? lsf_queue
        String? lsf_extra_param
    """
    )
    LSF_CHECK_ALIVE = 'bjobs ${job_id}'
    LSF_KILL = 'bkill ${job_id}'
    LSF_JOB_ID_REGEX = 'Job <([0-9]+)>.*'

    # this is a template that requires formatting
    # (submit, lsf_resource_param)
    TEMPLATE_LSF_SUBMIT = dedent(
        """
        cat << EOF > ${{script}}.caper
        #!/bin/bash
        {submit}
        EOF

        for ITER in 1 2 3; do
            bsub -env "all" -J ${{job_name}} -cwd ${{cwd}} -o ${{out}} -e ${{err}} \\
                ${{'-q ' + lsf_queue}} \\
                {lsf_resource_param} \\
                ${{lsf_extra_param}} \\
                ${{job_shell}} ${{script}}.caper && break
            sleep 30
        done
    """
    )
    DEFAULT_LSF_RESOURCE_PARAM = (
        '${"-n " + cpu} '
        '${if defined(gpu) then "-gpu " + gpu else ""} '
        '${if defined(memory_mb) then "-M " else ""}${memory_mb}${if defined(memory_mb) then "m" else ""} '
        '${"-W " + 60*time} '
    )

    def __init__(
        self,
        local_out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        lsf_queue=None,
        lsf_extra_param=None,
        lsf_resource_param=DEFAULT_LSF_RESOURCE_PARAM,
    ):
        """LSF backend. Try bsubbing up to 3 times every 30 second.

        Args:
            lsf_resource_param:
                String of a set of resource parameters for the job submission engine.
                WDL syntax allowed in ${} notation.
                This will be appended to the job sumbission command line.
                e.g. qsub ... THIS_RESOURCE_PARAM
        """
        submit = CromwellBackendLsf.TEMPLATE_LSF_SUBMIT.format(
            submit=CromwellBackendLocal.SUBMIT, lsf_resource_param=lsf_resource_param
        )

        super().__init__(
            local_out_dir=local_out_dir,
            backend_name=BACKEND_LSF,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
            check_alive=CromwellBackendLsf.LSF_CHECK_ALIVE,
            kill=CromwellBackendLsf.LSF_KILL,
            job_id_regex=CromwellBackendLsf.LSF_JOB_ID_REGEX,
            submit=submit,
            runtime_attributes=CromwellBackendLsf.LSF_RUNTIME_ATTRIBUTES,
        )

        if lsf_queue:
            self.default_runtime_attributes['lsf_queue'] = lsf_queue
        if lsf_extra_param:
            self.default_runtime_attributes['lsf_extra_param'] = lsf_extra_param
