#!/usr/bin/env python3
"""Caper backend
"""

BACKEND_GCP = 'gcp'
BACKEND_AWS = 'aws'
BACKEND_LOCAL = 'Local'  # should be CAPITAL L
BACKEND_SLURM = 'slurm'
BACKEND_SGE = 'sge'
BACKEND_PBS = 'pbs'
BACKENDS = [BACKEND_GCP, BACKEND_AWS, BACKEND_LOCAL, BACKEND_SLURM,
    BACKEND_SGE, BACKEND_PBS]

BACKEND_ALIAS_LOCAL = 'local'  # with small L
BACKEND_ALIAS_GOOGLE = 'google'
BACKEND_ALIAS_AMAZON = 'amazon'
BACKEND_ALIAS_SHERLOCK = 'sherlock'
BACKEND_ALIAS_SCG = 'scg'
BACKEND_ALIASES = [BACKEND_ALIAS_LOCAL, BACKEND_ALIAS_GOOGLE, BACKEND_ALIAS_AMAZON, BACKEND_ALIAS_SHERLOCK,
    BACKEND_ALIAS_SCG]

BACKENDS_WITH_ALIASES = BACKENDS + BACKEND_ALIASES


def get_backend(backend):
    if backend == BACKEND_ALIAS_GOOGLE:
        backend = BACKEND_GCP
    elif backend == BACKEND_ALIAS_AMAZON:
        backend = BACKEND_AWS
    elif backend == BACKEND_ALIAS_SHERLOCK:
        backend = BACKEND_SLURM
    elif backend == BACKEND_ALIAS_SCG:
        backend = BACKEND_SLURM
    elif backend == BACKEND_ALIAS_LOCAL:
        backend = BACKEND_LOCAL
    if backend not in BACKENDS:
        raise Exception('Unsupported backend: {}'.format(backend))
    return backend


class CaperBackendCommon(dict):
    """Common stanzas for all Caper backends
    """
    TEMPLATE = {
        "backend": {
            "default": BACKEND_LOCAL
        },
        "webservice": {
            "port": 8000
        },
        "services": {
            "LoadController": {
                "class": "cromwell.services.loadcontroller.impl"
                ".LoadControllerServiceActor",
                "config": {
                    # due to issues on stanford sherlock/scg
                    "control-frequency": "21474834 seconds"
                }
            }
        },
        "system": {
            "job-rate-control": {
                "jobs": 1,
                "per": "2 seconds"
            },
            "abort-jobs-on-terminate": True,
            "graceful-server-shutdown": True,
            "max-concurrent-workflows": 40
        },
        "call-caching": {
            "enabled": True,
            "invalidate-bad-cache-results": True
        }
    }

    def __init__(self, port=None, disable_call_caching=None,
                 max_concurrent_workflows=None):
        super(CaperBackendCommon, self).__init__(
            CaperBackendCommon.TEMPLATE)
        if port is not None:
            self['webservice']['port'] = port
        if disable_call_caching is not None:
            self['call-caching']['enabled'] = not disable_call_caching
        if max_concurrent_workflows is not None:
            self['system']['max-concurrent-workflows'] = \
                max_concurrent_workflows


class CaperBackendDatabase(dict):
    """Common stanzas for database
    """
    DB_TYPE_IN_MEMORY = 'in-memory'
    DB_TYPE_FILE = 'file'
    DB_TYPE_MYSQL = 'mysql'
    DB_TYPE_POSTGRESQL = 'postgresql'

    TEMPLATE = {
    }

    TEMPLATE_DB_IN_MEMORY = {
    }

    TEMPLATE_DB_FILE = {
        "db": {
            "url": "jdbc:hsqldb:file:{file};shutdown=false;"
                "hsqldb.tx=mvcc;hsqldb.lob_compressed=true",
            "connectionTimeout": 5000
        }
    }

    TEMPLATE_DB_MYSQL = {
        "profile": "slick.jdbc.MySQLProfile$",
        "db": {
            "driver": "com.mysql.cj.jdbc.Driver",
            "url": "jdbc:mysql://{ip}:{port}/{name}?"
                "allowPublicKeyRetrieval=true&useSSL=false&"
                "rewriteBatchedStatements=true&serverTimezone=UTC",
            "user": "cromwell",
            "password": "cromwell",
            "connectionTimeout": 5000
        }
    }

    TEMPLATE_DB_POSTGRESQL = {
        "profile": "slick.jdbc.PostgresProfile$",
        "db": {
            "driver": "org.postgresql.Driver",
            "url": "jdbc:postgresql://{ip}:{port}/{name}",
            "port": 5432,
            "user": "cromwell",
            "password": "cromwell",
            "connectionTimeout": 5000
        }
    }

    def __init__(self, db_type=None, db_timeout=None,
                 file_db=None,
                 mysql_ip=None, mysql_port=None,
                 mysql_user=None, mysql_password=None,
                 mysql_name=None,
                 postgresql_ip=None, postgresql_port=None,
                 postgresql_user=None, postgresql_password=None,
                 postgresql_name=None):
        super(CaperBackendDatabase, self).__init__(
            CaperBackendDatabase.TEMPLATE)

        if db_type == CaperBackendDatabase.DB_TYPE_IN_MEMORY:
            self['database'] = CaperBackendDatabase.TEMPLATE_DB_IN_MEMORY

        elif db_type == CaperBackendDatabase.DB_TYPE_FILE:
            self['database'] = CaperBackendDatabase.TEMPLATE_DB_FILE
            db = self['database']['db']
            db['url'] = db['url'].format(
                file=file_db)

        elif db_type == CaperBackendDatabase.DB_TYPE_MYSQL:
            self['database'] = CaperBackendDatabase.TEMPLATE_DB_MYSQL            
            db = self['database']['db']
            db['url'] = db['url'].format(
                ip=mysql_ip, port=mysql_port, name=mysql_name)
            db['user'] = mysql_user
            db['password'] = mysql_password

        elif db_type == CaperBackendDatabase.DB_TYPE_POSTGRESQL:
            self['database'] = CaperBackendDatabase.TEMPLATE_DB_POSTGRESQL
            db = self['database']['db']
            db['url'] = db['url'].format(
                ip=postgresql_ip, port=postgresql_port, name=postgresql_name)
            db['port'] = postgresql_port
            db['user'] = postgresql_user
            db['password'] = postgresql_password

        else:
            raise Exception('Unsupported DB type {}'.format(db_type))

        if db_timeout is not None and 'db' in self['database']:
            self['database']['db']['connectionTimeout'] = db_timeout


class CaperBackendGCP(dict):
    """Google Cloud backend
    """
    TEMPLATE = {
        "backend": {
            "providers": {
                BACKEND_GCP: {
                    "actor-factory": "cromwell.backend.google.pipelines."
                    "v2alpha1.PipelinesApiLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes": {
                        },
                        "project": "YOUR_GCP_PROJECT",
                        "root": "gs://YOUR_GCS_BUCKET",
                        "concurrent-job-limit": 1000,
                        "genomics-api-queries-per-100-seconds": 1000,
                        "maximum-polling-interval": 600,
                        "genomics": {
                            "auth": "application-default",
                            "compute-service-account": "default",
                            "endpoint-url": "https://genomics.googleapis.com/",
                            "restrict-metadata-access": False
                        },
                        "filesystems": {
                            "gcs": {
                                "auth": "application-default"
                            }
                        }
                    }
                }
            }
        },
        "google": {
            "application-name": "cromwell",
            "auths": [
                {
                    "name": "application-default",
                    "scheme": "application_default"
                }
            ]
        }
    }

    def __init__(self, gcp_prj, out_gcs_bucket, concurrent_job_limit=None):
        super(CaperBackendGCP, self).__init__(
            CaperBackendGCP.TEMPLATE)
        config = self['backend']['providers'][BACKEND_GCP]['config']
        config['project'] = gcp_prj
        config['root'] = out_gcs_bucket
        assert(out_gcs_bucket.startswith('gs://'))

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CaperBackendAWS(dict):
    """AWS backend
    """
    TEMPLATE = {
        "backend": {
            "providers": {
                BACKEND_AWS: {
                    "actor-factory": "cromwell.backend.impl.aws."
                    "AwsBatchBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes": {
                            "queueArn": "YOUR_AWS_BATCH_ARN"
                        },
                        "numSubmitAttempts": 6,
                        "numCreateDefinitionAttempts": 6,
                        "root": "s3://YOUR_S3_BUCKET",
                        "concurrent-job-limit": 1000,
                        "auth": "default",
                        "filesystems": {
                            "s3": {
                                "auth": "default"
                            }
                        }
                    }
                },
            }
        },
        "aws": {
            "application-name": "cromwell",
            "auths": [
                {
                    "name": "default",
                    "scheme": "default"
                }
            ],
            "region": "YOUR_AWS_REGION"
        },
        "engine": {
            "filesystems": {
                "s3": {
                    "auth": "default"
                }
            }
        }
    }

    def __init__(self, aws_batch_arn, aws_region, out_s3_bucket,
                 concurrent_job_limit=None):
        super(CaperBackendAWS, self).__init__(
            CaperBackendAWS.TEMPLATE)
        self[BACKEND_AWS]['region'] = aws_region
        config = self['backend']['providers'][BACKEND_AWS]['config']
        config['default-runtime-attributes']['queueArn'] = aws_batch_arn
        config['root'] = out_s3_bucket
        assert(out_s3_bucket.startswith('s3://'))

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CaperBackendLocal(dict):
    """Local backend
    """
    RUNTIME_ATTRIBUTES = """
        Int? gpu
        String? docker
        String? docker_user
        String? singularity
        String? singularity_bindpath
        String? singularity_cachedir
    """
    SUBMIT = """
        ${if defined(singularity) then "" else "/bin/bash ${script} #"} \
        if [ -z "$SINGULARITY_BINDPATH" ]; then \
        export SINGULARITY_BINDPATH=${singularity_bindpath}; fi; \
        if [ -z "$SINGULARITY_CACHEDIR" ]; then \
        export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi; \
        singularity exec --cleanenv --home ${cwd} \
        ${if defined(gpu) then '--nv' else ''} \
        ${singularity} /bin/bash ${script}
    """
    SUBMIT_DOCKER = """
        # make sure there is no preexisting Docker CID file
        rm -f ${docker_cid}
        # run as in the original configuration without --rm flag (will remove later)
        docker run \
          --cidfile ${docker_cid} \
          -i \
          ${"--user " + docker_user} \
          --entrypoint ${job_shell} \
          -v ${cwd}:${docker_cwd} \
          ${docker} ${docker_script}
    """
    TEMPLATE = {
        "backend": {
            "providers": {
                BACKEND_LOCAL: {
                    "actor-factory": "cromwell.backend.impl.sfs.config."
                    "ConfigBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes": {
                        },
                        "run-in-background": True,
                        "script-epilogue": "sleep 10 && sync",
                        "concurrent-job-limit": 1000,
                        "runtime-attributes": RUNTIME_ATTRIBUTES,
                        "submit": SUBMIT,
                        "submit-docker" : SUBMIT_DOCKER
                    }
                }
            }
        }
    }

    def __init__(self, out_dir, concurrent_job_limit=None):
        super(CaperBackendLocal, self).__init__(
            CaperBackendLocal.TEMPLATE)
        config = self['backend']['providers'][BACKEND_LOCAL]['config']
        config['root'] = out_dir

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CaperBackendSLURM(dict):
    """SLURM backend
    """
    RUNTIME_ATTRIBUTES = """
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
    # try sbatching up to 3 times every 30 second
    # some busy SLURM clusters spit out error, which results in a failure of the whole workflow
    SUBMIT = """ITER=0; until [ $ITER -ge 3 ]; do
        sbatch \
        --export=ALL \
        -J ${job_name} \
        -D ${cwd} \
        -o ${out} \
        -e ${err} \
        ${"-t " + time*60} \
        -n 1 \
        --ntasks-per-node=1 \
        ${true="--cpus-per-task=" false="" defined(cpu)}${cpu} \
        ${true="--mem=" false="" defined(memory_mb)}${memory_mb} \
        ${"-p " + slurm_partition} \
        ${"--account " + slurm_account} \
        ${true="--gres gpu:" false="" defined(gpu)}${gpu} \
        ${slurm_extra_param} \
        --wrap "${if defined(singularity) then '' else \
            '/bin/bash ${script} #'} \
            if [ -z \\"$SINGULARITY_BINDPATH\\" ]; then \
            export SINGULARITY_BINDPATH=${singularity_bindpath}; fi; \
            if [ -z \\"$SINGULARITY_CACHEDIR\\" ]; then \
            export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi; \
            singularity exec --cleanenv --home ${cwd} \
            ${if defined(gpu) then '--nv' else ''} \
            ${singularity} /bin/bash ${script}" && break
    ITER=$[$ITER+1]; sleep 30; done
    """
    # squeue every 30 second (up to 3 times)
    # unlike qstat -j JOB_ID, squeue -j JOB_ID doesn't return 1 when there is no such job
    # so we need to use squeue -j JOB_ID --noheader and check if output is empty
    # try polling up to 3 times since squeue fails on some busy SLURM clusters
    # e.g. on Stanford Sherlock, squeue didn't work when server is busy
    CHECK_ALIVE = """for ITER in 1 2 3; do CHK_ALIVE=$(squeue --noheader -j ${job_id} --format=%i | grep ${job_id}); if [ -z "$CHK_ALIVE" ]; then if [ "$ITER" == 3 ]; then /bin/bash -c 'exit 1'; else sleep 30; fi; else echo $CHK_ALIVE; break; fi; done"""
    TEMPLATE = {
        "backend": {
            "providers": {
                BACKEND_SLURM: {
                    "actor-factory": "cromwell.backend.impl.sfs.config."
                    "ConfigBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes": {
                            "time": 24
                        },
                        "script-epilogue": "sleep 10 && sync",
                        "concurrent-job-limit": 1000,
                        "runtime-attributes": RUNTIME_ATTRIBUTES,
                        "submit": SUBMIT,
                        "kill": "scancel ${job_id}",
                        "exit-code-timeout-seconds": 360,
                        "check-alive": CHECK_ALIVE,
                        "job-id-regex": "Submitted batch job (\\\\d+).*"
                    }
                }
            }
        }
    }

    def __init__(self, out_dir, partition=None, account=None, extra_param=None,
                 concurrent_job_limit=None):
        super(CaperBackendSLURM, self).__init__(
            CaperBackendSLURM.TEMPLATE)
        config = self['backend']['providers'][BACKEND_SLURM]['config']
        key = 'default-runtime-attributes'
        config['root'] = out_dir

        if partition is not None and partition != '':
            config[key]['slurm_partition'] = partition
        if account is not None and account != '':
            config[key]['slurm_account'] = account
        if extra_param is not None and extra_param != '':
            config[key]['slurm_extra_param'] = extra_param
        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CaperBackendSGE(dict):
    """SGE backend
    """
    RUNTIME_ATTRIBUTES = """
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
    SUBMIT = """
        echo "${if defined(singularity) then '' else '/bin/bash ${script} #'} \
        if [ -z \\"$SINGULARITY_BINDPATH\\" ]; then \
        export SINGULARITY_BINDPATH=${singularity_bindpath}; fi; \
        if [ -z \\"$SINGULARITY_CACHEDIR\\" ]; then \
        export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi; \
        singularity exec --cleanenv --home ${cwd} \
        ${if defined(gpu) then '--nv' else ''} \
        ${singularity} /bin/bash ${script}" | qsub \
        -S /bin/sh \
        -terse \
        -b n \
        -N ${job_name} \
        -wd ${cwd} \
        -o ${out} \
        -e ${err} \
        ${if cpu>1 then "-pe " + sge_pe + " " else ""}\
${if cpu>1 then cpu else ""} \
        ${true="-l h_vmem=$(expr " false="" defined(memory_mb)}${memory_mb}\
${true=" / " false="" defined(memory_mb)}\
${if defined(memory_mb) then cpu else ""}\
${true=")m" false="" defined(memory_mb)} \
        ${true="-l s_vmem=$(expr " false="" defined(memory_mb)}${memory_mb}\
${true=" / " false="" defined(memory_mb)}\
${if defined(memory_mb) then cpu else ""}\
${true=")m" false="" defined(memory_mb)} \
        ${true="-l h_rt=" false="" defined(time)}${time}$\
{true=":00:00" false="" defined(time)} \
        ${true="-l s_rt=" false="" defined(time)}${time}$\
{true=":00:00" false="" defined(time)} \
        ${"-q " + sge_queue} \
        ${"-l gpu=" + gpu} \
        ${sge_extra_param} \
        -V
    """
    TEMPLATE = {
        "backend": {
            "providers": {
                BACKEND_SGE: {
                    "actor-factory": "cromwell.backend.impl.sfs.config."
                    "ConfigBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes": {
                            "time": 24
                        },
                        "script-epilogue": "sleep 10 && sync",
                        "concurrent-job-limit": 1000,
                        "runtime-attributes": RUNTIME_ATTRIBUTES,
                        "submit": SUBMIT,
                        "exit-code-timeout-seconds": 180,
                        "kill": "qdel ${job_id}",
                        "check-alive": "qstat -j ${job_id}",
                        "job-id-regex": "(\\\\d+)"
                    }
                }
            }
        }
    }

    def __init__(self, out_dir, pe=None, queue=None, extra_param=None,
                 concurrent_job_limit=None):
        super(CaperBackendSGE, self).__init__(
            CaperBackendSGE.TEMPLATE)
        config = self['backend']['providers'][BACKEND_SGE]['config']
        key = 'default-runtime-attributes'
        config['root'] = out_dir

        if pe is not None and pe != '':
            config[key]['sge_pe'] = pe
        if queue is not None and queue != '':
            config[key]['sge_queue'] = queue
        if extra_param is not None and extra_param != '':
            config[key]['sge_extra_param'] = extra_param
        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CaperBackendPBS(dict):
    """PBS backend
    """
    RUNTIME_ATTRIBUTES = """
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
    SUBMIT = """
        echo "${if defined(singularity) then '' else '/bin/bash ${script} #'} \
        if [ -z \\"$SINGULARITY_BINDPATH\\" ]; then \
        export SINGULARITY_BINDPATH=${singularity_bindpath}; fi; \
        if [ -z \\"$SINGULARITY_CACHEDIR\\" ]; then \
        export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi; \
        singularity exec --cleanenv --home ${cwd} \
        ${if defined(gpu) then '--nv' else ''} \
        ${singularity} /bin/bash ${script}" | qsub \
        -N ${job_name} \
        -o ${out} \
        -e ${err} \
        ${true="-lselect=1:ncpus=" false="" defined(cpu)}${cpu}\
${true=":mem=" false="" defined(memory_mb)}${memory_mb}\
${true="mb" false="" defined(memory_mb)} \
        ${true="-lwalltime=" false="" defined(time)}${time}\
${true=":0:0" false="" defined(time)} \
        ${true="-lngpus=" false="" gpu>1}${if gpu>1 then gpu else ""} \
        ${"-q " + pbs_queue} \
        ${pbs_extra_param} \
        -V
    """
    TEMPLATE = {
        "backend": {
            "providers": {
                BACKEND_PBS: {
                    "actor-factory": "cromwell.backend.impl.sfs.config."
                    "ConfigBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes": {
                            "time": 24
                        },
                        "script-epilogue": "sleep 30 && sync",
                        "concurrent-job-limit": 1000,
                        "runtime-attributes": RUNTIME_ATTRIBUTES,
                        "submit": SUBMIT,
                        "exit-code-timeout-seconds": 180,
                        "kill": "qdel ${job_id}",
                        "check-alive": "qstat ${job_id}",
                        "job-id-regex": "(\\\\d+)"
                    }
                }
            }
        }
    }

    def __init__(self, out_dir, queue=None, extra_param=None,
                 concurrent_job_limit=None):
        super(CaperBackendPBS, self).__init__(
            CaperBackendPBS.TEMPLATE)
        config = self['backend']['providers'][BACKEND_PBS]['config']
        key = 'default-runtime-attributes'
        config['root'] = out_dir

        if queue is not None and queue != '':
            config[key]['pbs_queue'] = queue
        if extra_param is not None and extra_param != '':
            config[key]['pbs_extra_param'] = extra_param
        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


def main():
    pass


if __name__ == '__main__':
    main()
