#!/usr/bin/env python3
"""Cromweller backend
"""

BACKEND_GCP = 'gcp'
BACKEND_AWS = 'aws'
BACKEND_LOCAL = 'local'
BACKEND_SLURM = 'slurm'
BACKEND_SGE = 'sge'
BACKEND_PBS = 'pbs'


class CromwellerBackendCommon(dict):
    """Common stanzas for all Cromweller backends
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
            "abort-jobs-on-terminate": True,
            "graceful-server-shutdown": True,
            "max-concurrent-workflows": 40
        },
        "call-caching": {
            "enabled": False,
            "invalidate-bad-cache-results": True
        }
    }

    def __init__(self, port=None, use_call_caching=None,
                 max_concurrent_workflows=None):
        super(CromwellerBackendCommon, self).__init__(
            CromwellerBackendCommon.TEMPLATE)
        if port is not None:
            self['webservice']['port'] = port
        if use_call_caching is not None:
            self['call-caching']['enabled'] = use_call_caching
        if use_call_caching is not None:
            self['system']['max-concurrent-workflows'] = \
                max_concurrent_workflows


class CromwellerBackendMySQL(dict):
    """Common stanzas for MySQL
    """
    TEMPLATE = {
        "database": {
            "profile": "slick.jdbc.MySQLProfile$",
            "db": {
                "url": "jdbc:mysql://localhost:3306/cromwell_db?"
                "allowPublicKeyRetrieval=true&useSSL=false&"
                "rewriteBatchedStatements=true",
                "user": "cromwell",
                "password": "cromwell",
                "driver": "com.mysql.cj.jdbc.Driver",
                "connectionTimeout": 5000
            }
        }
    }

    def __init__(self, ip, port, user, password):
        super(CromwellerBackendMySQL, self).__init__(
            CromwellerBackendMySQL.TEMPLATE)
        db = self['database']['db']
        db['user'] = user
        db['password'] = password
        db['url'] = db['url'].replace('localhost:3306', '{ip}:{port}'.format(
            ip=ip, port=port))


class CromwellerBackendGCP(dict):
    """Google Cloud backend
    """
    TEMPLATE = {
        "backend": {
            "providers": {
                BACKEND_GCP: {
                    "actor-factory": "cromwell.backend.impl.jes."
                    "JesBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes": {
                        },
                        "project": "YOUR_GC_PROJECT",
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

    def __init__(self, gc_project, out_gcs_bucket, concurrent_job_limit=None):
        super(CromwellerBackendGCP, self).__init__(
            CromwellerBackendGCP.TEMPLATE)
        config = self['backend']['providers'][BACKEND_GCP]['config']
        config['project'] = gc_project
        config['root'] = out_gcs_bucket
        assert(out_gcs_bucket.startswith('gs://'))

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CromwellerBackendAWS(dict):
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
        super(CromwellerBackendAWS, self).__init__(
            CromwellerBackendAWS.TEMPLATE)
        self[BACKEND_AWS]['region'] = aws_region
        config = self['backend']['providers'][BACKEND_AWS]['config']
        config['default-runtime-attributes']['queueArn'] = aws_batch_arn
        config['root'] = out_s3_bucket
        assert(out_s3_bucket.startswith('s3://'))

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CromwellerBackendLocal(dict):
    """Local backend
    """
    RUNTIME_ATTRIBUTES = """
    Int? gpu
    String? docker
    String? docker_user
    String? singularity
    """
    SUBMIT = """
    ${if defined(singularity) then "" else "/bin/bash ${script} #"} \
    if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; \
    singularity exec --cleanenv --home ${cwd} \
    ${if defined(gpu) then '--nv' else ''} \
    ${singularity} /bin/bash ${script}
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
                        "submit": SUBMIT
                    }
                }
            }
        }
    }

    def __init__(self, out_dir, concurrent_job_limit=None):
        super(CromwellerBackendLocal, self).__init__(
            CromwellerBackendLocal.TEMPLATE)
        config = self['backend']['providers'][BACKEND_LOCAL]['config']
        config['root'] = out_dir

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CromwellerBackendSLURM(dict):
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
    String singularity
    """
    SUBMIT = """
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
            '/bin/bash ${script} #'} if [ -z $SINGULARITY_BINDPATH ]; then \
            SINGULARITY_BINDPATH=/; fi; \
            singularity exec --cleanenv --home ${cwd} \
            ${if defined(gpu) then '--nv' else ''} \
            ${singularity} /bin/bash ${script}"
    """
    CHECK_ALIVE = """
    CHK_ALIVE=$(squeue --noheader -j ${job_id}); if [ -z $CHK_ALIVE ]; then \
    /bin/bash -c 'exit 1'; else echo $CHK_ALIVE; fi
    """
    TEMPLATE = {
        "backend": {
            "providers": {
                BACKEND_SLURM: {
                    "actor-factory": "cromwell.backend.impl.sfs.config."
                    "ConfigBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes": {
                        },
                        "script-epilogue": "sleep 10 && sync",
                        "concurrent-job-limit": 1000,
                        "runtime-attributes": RUNTIME_ATTRIBUTES,
                        "submit": SUBMIT,
                        "kill": "scancel ${job_id}",
                        "exit-code-timeout-seconds": 180,
                        "check-alive": CHECK_ALIVE,
                        "job-id-regex": "Submitted batch job (\\\\d+).*"
                    }
                }
            }
        }
    }

    def __init__(self, partition=None, account=None, extra_param=None,
                 concurrent_job_limit=None):
        super(CromwellerBackendSLURM, self).__init__(
            CromwellerBackendSLURM.TEMPLATE)
        config = self['backend']['providers'][BACKEND_SLURM]['config']
        key = 'default-runtime-attributes'

        if partition is not None:
            config[key]['slurm_partition'] = partition
        if account is not None:
            config[key]['slurm_account'] = account
        if extra_param is not None:
            config[key]['slurm_extra_param'] = extra_param
        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CromwellerBackendSGE(dict):
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
    String singularity
    """
    SUBMIT = """
    echo "${if defined(singularity) then '' else '/bin/bash ${script} #'} \
    if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; \
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

    def __init__(self, pe=None, queue=None, extra_param=None,
                 concurrent_job_limit=None):
        super(CromwellerBackendSGE, self).__init__(
            CromwellerBackendSGE.TEMPLATE)
        config = self['backend']['providers'][BACKEND_SGE]['config']
        key = 'default-runtime-attributes'

        if pe is not None:
            config[key]['sge_pe'] = pe
        if queue is not None:
            config[key]['sge_queue'] = queue
        if extra_param is not None:
            config[key]['sge_extra_param'] = extra_param
        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CromwellerBackendPBS(dict):
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
    String singularity
    """
    SUBMIT = """
    echo "${if defined(singularity) then '' else '/bin/bash ${script} #'} \
    if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; \
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
                        },
                        "script-epilogue": "sleep 30 && sync",
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

    def __init__(self, queue=None, extra_param=None,
                 concurrent_job_limit=None):
        super(CromwellerBackendPBS, self).__init__(
            CromwellerBackendPBS.TEMPLATE)
        config = self['backend']['providers'][BACKEND_PBS]['config']
        key = 'default-runtime-attributes'

        if queue is not None:
            config[key]['pbs_queue'] = queue
        if extra_param is not None:
            config[key]['pbs_extra_param'] = extra_param
        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


def main():
    pass


if __name__ == '__main__':
    main()
