import logging
import re
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


class CromwellBackendCommon(UserDict):
    """Common stanzas for Cromwell backend conf.
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
    DEFAULT_SERVER_PORT = 8000

    def __init__(
        self,
        default_backend,
        server_port=DEFAULT_SERVER_PORT,
        disable_call_caching=False,
        max_concurrent_workflows=DEFAULT_MAX_CONCURRENT_WORKFLOWS,
    ):
        super().__init__(deepcopy(CromwellBackendCommon.TEMPLATE))

        self['backend']['default'] = default_backend
        self['webservice']['port'] = server_port
        self['call-caching']['enabled'] = not disable_call_caching
        self['system']['max-concurrent-workflows'] = max_concurrent_workflows


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
            db_obj['driver'] = CromwellBackendDatabase.DRIVER_MYSQL
            db_obj['url'] = CromwellBackendDatabase.JDBC_URL_MYSQL.format(
                ip=mysql_db_ip, port=mysql_db_port, name=mysql_db_name
            )
            db_obj['user'] = mysql_db_user
            db_obj['password'] = mysql_db_password

        elif db == CromwellBackendDatabase.DB_POSTGRESQL:
            database['profile'] = CromwellBackendDatabase.PROFILE_POSTGRESQL
            db_obj['driver'] = CromwellBackendDatabase.DRIVER_POSTGRESQL
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

        self.set_backend(CromwellBackendBase.TEMPLATE_BACKEND)

        config = self.get_backend_config()
        config['concurrent-job-limit'] = max_concurrent_tasks

    def set_backend(self, backend):
        self['backend']['providers'][self._backend_name] = deepcopy(backend)

    def merge_backend(self, backend):
        merge_dict(self.get_backend(), backend)

    def get_backend(self):
        return self['backend']['providers'][self._backend_name]

    def get_backend_config(self):
        return self.get_backend()['config']

    def get_backend_config_dra(self):
        """Backend's default runtime attributes (DRA).
        """
        return self.get_backend_config()['default-runtime-attributes']


class CromwellBackendGCP(CromwellBackendBase):
    TEMPLATE = {
        'google': {
            'application-name': 'cromwell',
            'auths': [{'name': 'application-default', 'scheme': 'application_default'}],
        }
    }
    TEMPLATE_BACKEND = {
        'actor-factory': 'cromwell.backend.google.pipelines.v2alpha1.PipelinesApiLifecycleActorFactory',
        'config': {
            'default-runtime-attributes': {},
            'genomics-api-queries-per-100-seconds': 1000,
            'maximum-polling-interval': 600,
            'genomics': {
                'auth': 'application-default',
                'compute-service-account': 'default',
                'endpoint-url': 'https://genomics.googleapis.com/',
                'restrict-metadata-access': False,
            },
            'filesystems': {'gcs': {'auth': 'application-default', 'caching': {}}},
        },
    }

    REGEX_DELIMITER_GCP_ZONES = r',| '
    CALL_CACHING_DUP_STRAT_REFERENCE = 'reference'
    CALL_CACHING_DUP_STRAT_COPY = 'copy'

    DEFAULT_GCP_CALL_CACHING_DUP_STRAT = CALL_CACHING_DUP_STRAT_REFERENCE

    def __init__(
        self,
        gcp_prj,
        out_gcs_bucket,
        call_caching_dup_strat=DEFAULT_GCP_CALL_CACHING_DUP_STRAT,
        gcp_zones=None,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
    ):
        super().__init__(
            backend_name=BACKEND_GCP, max_concurrent_tasks=max_concurrent_tasks
        )
        merge_dict(self.data, CromwellBackendGCP.TEMPLATE)
        self.merge_backend(CromwellBackendGCP.TEMPLATE_BACKEND)

        config = self.get_backend_config()
        config['project'] = gcp_prj
        if not out_gcs_bucket.startswith('gs://'):
            raise ValueError(
                'Wrong GCS bucket URI for out_gcs_bucket: {v}'.format(v=out_gcs_bucket)
            )
        config['root'] = out_gcs_bucket

        caching = config['filesystems']['gcs']['caching']
        if call_caching_dup_strat not in (
            CromwellBackendGCP.CALL_CACHING_DUP_STRAT_REFERENCE,
            CromwellBackendGCP.CALL_CACHING_DUP_STRAT_COPY,
        ):
            raise ValueError(
                'Wrong call_caching_dup_strat: {v}'.format(v=call_caching_dup_strat)
            )
        caching['duplication-strategy'] = call_caching_dup_strat

        dra = self.get_backend_config_dra()
        if gcp_zones:
            zones = ' '.join(
                re.split(CromwellBackendGCP.REGEX_DELIMITER_GCP_ZONES, gcp_zones)
            )
            dra['zones'] = zones


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
        out_s3_bucket,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
    ):
        super().__init__(
            backend_name=BACKEND_AWS, max_concurrent_tasks=max_concurrent_tasks
        )
        merge_dict(self.data, CromwellBackendAWS.TEMPLATE)
        self.merge_backend(CromwellBackendAWS.TEMPLATE_BACKEND)

        aws = self[BACKEND_AWS]
        aws['region'] = aws_region

        config = self.get_backend_config()
        if not out_s3_bucket.startswith('s3://'):
            raise ValueError(
                'Wrong S3 bucket URI for out_s3_bucket: {v}'.format(v=out_s3_bucket)
            )
        config['root'] = out_s3_bucket

        dra = self.get_backend_config_dra()
        dra['queueArn'] = aws_batch_arn


class CromwellBackendLocal(CromwellBackendBase):
    """Class constants:
        MAKE_CMD_SUBMIT:
            Includes BASH command line for Singularity.
    """

    TEMPLATE_BACKEND = {
        'actor-factory': 'cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory',
        'config': {
            'script-epilogue': 'sleep 10 && sync',
            'filesystems': {'local': {'caching': {'check-sibling-md5': True}}},
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
    DUP_STRAT_FOR_PATH = ['soft-link']
    SOFT_GLOB_OUTPUT_CMD = 'ln -sL GLOB_PATTERN GLOB_DIRECTORY 2> /dev/null'

    DEFAULT_LOCAL_HASH_STRAT = LOCAL_HASH_STRAT_FILE

    def __init__(
        self,
        out_dir,
        backend_name=BACKEND_LOCAL,
        soft_glob_output=False,
        local_hash_strat=DEFAULT_LOCAL_HASH_STRAT,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
    ):
        super().__init__(
            backend_name=backend_name, max_concurrent_tasks=max_concurrent_tasks
        )
        self.merge_backend(CromwellBackendLocal.TEMPLATE_BACKEND)

        config = self.get_backend_config()
        caching = config['filesystems']['local']['caching']

        if local_hash_strat not in (
            CromwellBackendLocal.LOCAL_HASH_STRAT_FILE,
            CromwellBackendLocal.LOCAL_HASH_STRAT_PATH,
            CromwellBackendLocal.LOCAL_HASH_STRAT_PATH_MTIME,
        ):
            raise ValueError(
                'Wrong local_hash_strat: {strat}'.format(strat=local_hash_strat)
            )
        caching['hashing-strategy'] = local_hash_strat

        if local_hash_strat in (
            CromwellBackendLocal.LOCAL_HASH_STRAT_PATH,
            CromwellBackendLocal.LOCAL_HASH_STRAT_PATH_MTIME,
        ):
            caching['duplication-strategy'] = CromwellBackendLocal.DUP_STRAT_FOR_PATH

        if soft_glob_output:
            config['glob-link-command'] = CromwellBackendLocal.SOFT_GLOB_OUTPUT_CMD

        if out_dir is None:
            raise ValueError('out_dir must be provided.')
        config['root'] = out_dir


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
                        ${'--mem=' + memory_mb} \\
                        ${'-p ' + slurm_partition} \\
                        ${'--account ' + slurm_account} \\
                        ${'--gres gpu:' + gpu}$ \\
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
        out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        slurm_partition=None,
        slurm_account=None,
        slurm_extra_param=None,
    ):
        super().__init__(
            out_dir=out_dir,
            backend_name=BACKEND_SLURM,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
        )
        self.merge_backend(CromwellBackendSLURM.TEMPLATE_BACKEND)

        dra = self.get_backend_config_dra()
        if slurm_partition:
            dra['slurm_partition'] = slurm_partition
        if slurm_account:
            dra['slurm_account'] = slurm_account
        if slurm_extra_param:
            dra['slurm_extra_param'] = slurm_extra_param


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
                    ${'-l h_vmem=' + memory_mb/cpu + 'm'} \\
                    ${'-l s_vmem=' + memory_mb/cpu + 'm'} \\
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
        out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        sge_pe=None,
        sge_queue=None,
        sge_extra_param=None,
    ):
        super().__init__(
            out_dir=out_dir,
            backend_name=BACKEND_SGE,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
        )
        self.merge_backend(CromwellBackendSGE.TEMPLATE_BACKEND)

        dra = self.get_backend_config_dra()
        if sge_pe:
            dra['sge_pe'] = sge_pe
        if sge_queue:
            dra['sge_queue'] = sge_queue
        if sge_extra_param:
            dra['sge_extra_param'] = sge_extra_param


class CromwellBackendPBS(CromwellBackendLocal):
    TEMPLATE_BACKEND = {
        'config': {
            'default-runtime-attributes': {'time': 24},
            'script-epilogue': 'sleep 30 && sync',
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
                    ${'-lselect=1:ncpus=' + cpu}${':mem=' + memory_mb + 'mb'} \\
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
        out_dir,
        max_concurrent_tasks=CromwellBackendBase.DEFAULT_CONCURRENT_JOB_LIMIT,
        soft_glob_output=False,
        local_hash_strat=CromwellBackendLocal.DEFAULT_LOCAL_HASH_STRAT,
        pbs_queue=None,
        pbs_extra_param=None,
    ):
        super().__init__(
            out_dir=out_dir,
            backend_name=BACKEND_PBS,
            max_concurrent_tasks=max_concurrent_tasks,
            soft_glob_output=soft_glob_output,
            local_hash_strat=local_hash_strat,
        )
        self.merge_backend(CromwellBackendPBS.TEMPLATE_BACKEND)

        dra = self.get_backend_config_dra()
        if pbs_queue:
            dra['pbs_queue'] = pbs_queue
        if pbs_extra_param:
            dra['pbs_extra_param'] = pbs_extra_param