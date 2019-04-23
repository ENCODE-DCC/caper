#!/usr/bin/env python
"""
Cromweller backend
"""
from copy import deepcopy
from pyhocon import ConfigFactory, HOCONConverter

from cromweller_uri import CromwellerURI
from logged_bash_cli import bash_run_cmd


class CromwellerBackends(object):
    """CromwellerBackend dict manager

    This manager initializes the following backend stanzas (defined in "backend" {}):
        1) local: local backend
        2) gc: Google Cloud backend (optional)
        3) aws: AWS backend (optional)
        4) slurm: SLURM (optional)
        5) sge: SGE (optional)
        6) pbs: PBS (optional)

    and the following common stanzas:
        a) common: required data
        b) mysql: MySQL for call-caching (optional)
    """
    _BACKEND_CONF_HEADER = 'include required(classpath("application"))\n'

    def __init__(self, args):
        """Parses from argparse and then initializes backend configuration
        dict, HOCON and string
        """
        self._backend_dict = {}

        # local backend is required
        self._backend_dict.extend(CromwellerBackendConfLocal(
            ))
        # other backends are optioinal
        if True:
            self._backend_dict.extend(CromwellerBackendConfGC(
                ))
        if True:
            self._backend_dict.extend(CromwellerBackendConfAWS(
                ))
        if True:
            self._backend_dict.extend(CromwellerBackendsLURM(
                ))
        if True:
            self._backend_dict.extend(CromwellerBackendsGE(
                ))
        if True:
            self._backend_dict.extend(CromwellerBackendConfPBS(
                ))
        # MySQL is optional
        if True:
            self._backend_dict.extend(CromwellerBackendConfMySQL(
                ).get_c dict())

        # set header for conf ("include ...")
        assert(CromwellerBackends._BACKEND_CONF_HEADER.endswith('\n'))
        lines_header = [CromwellerBackends._BACKEND_CONF_HEADER]

        # read from user specified backend.conf if exists
        if args.backend_file is not None:
            lines_wo_header = []

            # separate header
            with open(args.backend_file, 'r') as fp:
                for line in fp.readlines()
                    if re.findall('^[\s]*include\s', line):
                        if not line in lines_header:
                            lines_header.append(line)
                    else:
                        lines_wo_header.append(line)

            c = ConfigFactory.parse_string(''.join(lines_wo_header))
            # HOCON to json
            j = HOCONConverter.to_json(c)
            # json to dict
            d = json.loads(j)
            # apply to backend conf
            self._backend_dict.extend(d)

        # specify default backend
        if args.backend is not None:
            self._backend_dict['backend']['default'] = args.backend
        self.backend = args.backend

        # dict to HOCON (excluding header)
        self._backend_hocon = ConfigFactory.parse_string(lines_wo_header)

        # HOCON to string (including header)        
        self._backend_str = ''.join(lines_header)
        self._backend_str += HOCONConverter.to_hocon(self._backend_hocon)

    def get_backend():
        return self_backend

    def get_backend_str():
        return self._backend_str


class CromwellerBackendCommon(dict):
    """Dict of common stanzas for all Cromweller backends
    """
    _TEMPLATE = {
        "backend": {
            "default": "local"
        },
        "services": {
            "LoadController": {
                "class": "cromwell.services.loadcontroller.impl.LoadControllerServiceActor",
                "config": { # issues on stanford sherlock/scg
                    "control-frequency": "21474834 seconds"
                }
            }
        },
        "system": {
            "abort-jobs-on-terminate": True,
            "graceful-server-shutdown": True
        }
        "call-caching": {
            "enabled": False,
            "invalidate-bad-cache-results": True
        }
    }

    def __init__(self, use_call_caching=None):
        super(CromwellerBackendCommon, self).__init__(
            CromwellerBackendCommon._TEMPLATE)
        if use_call_caching is not None:
            self['call-caching']['enabled'] = use_call_caching
        

class CromwellerBackendMySQL(dict):
    """Dict of common stanzas for all Cromweller backends
    """
    _TEMPLATE = {
        "database": {
            "profile": "slick.jdbc.MySQLProfile$"
            "db" {
                "url": "jdbc:mysql://localhost:3306/cromwell_db?useSSL=false&rewriteBatchedStatements=true"    
                "user": "cromwell"
                "password": "cromwell"
                "driver": "com.mysql.jdbc.Driver" 
            }
        }
    }

    def __init__(self, user, password, ip='localhost', port=3306):
        super(CromwellerBackendMySQL, self).__init__(
            CromwellerBackendMySQL._TEMPLATE)
        db = ['database']['db']
        db['user'] = user
        db['password'] = password
        db['url'] = db['url'].replace('localhost:3306', '{ip}:{port}'.format(ip, port))
        

class CromwellerBackendGC(dict):
    """Dict for Cromweller backend GC
    """
    _TEMPLATE = {
        "backend": {
            "providers": {
                "gc": {
                    "actor-factory": "cromwell.backend.impl.jes.JesBackendLifecycleActorFactory",
                    "config": {
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

    def __init__(self, gc_prj, out_gcs_bucket, concurrent_job_limit=None):
        super(CromwellerBackendGC, self).__init__(
            CromwellerBackendGC._TEMPLATE)        
        config = self['backend']['providers']['gc']['config']
        config['project'] = gc_prj
        config['root'] = out_gcs_bucket

        assert(out_gcs_bucket.startswith('gs://'))

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CromwellerBackendAWS(dict):
    """Dict for Cromweller backend AWS
    """
    _TEMPLATE = {
        "backend": {
            "providers": {
                "aws": {
                    "actor-factory": "cromwell.backend.impl.aws.AwsBatchBackendLifecycleActorFactory",
                    "config": {
                        "numSubmitAttempts": 6,
                        "numCreateDefinitionAttempts": 6,
                        "root": "s3://YOUR_S3_BUCKET",
                        "concurrent-job-limit": 1000,
                        "auth": "default",
                        "default-runtime-attributes": {
                            "queueArn": "YOUR_AWS_BATCH_ARN"
                        },
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

    def __init__(self, aws_batch_arn, out_s3_bucket, concurrent_job_limit=None):
        super(CromwellerBackendAWS, self).__init__(
            CromwellerBackendAWS._TEMPLATE)        
        config = self['backend']['providers']['aws']['config']
        config['default-runtime-attributes']['queueArn'] = aws_batch_arn
        config['root'] = out_s3_bucket

        assert(out_s3_bucket.startswith('s3://'))

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CromwellerBackendLocal(dict):
    _TEMPLATE = {
        "backend": {
            "providers": {
                "local": {
                    "actor-factory": "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory",
                    "config": {
                        "run-in-background": True,
                        "script-epilogue": "sleep 10 && sync",
                        "runtime-attributes": "\n          Int? gpu\n          String? docker\n          String? docker_user\n          String? singularity\n        ",
                        "submit": "\n          ${if defined(singularity) then \"\" else \"/bin/bash ${script} #\"} if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; singularity exec --cleanenv --home ${cwd} ${if defined(gpu) then '--nv' else ''} ${singularity} /bin/bash ${script}\n        "
                    }
                }
            }
        }
    }

    def __init__(self, out_dir, concurrent_job_limit=None):
        super(CromwellerBackendAWS, self).__init__(
            CromwellerBackendAWS._TEMPLATE)        
        config = self['backend']['providers']['local']['config']        
        config['root'] = out_dir

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit



class CromwellerBackendSLURM(dict):
    _TEMPLATE = {
        "backend": {
            "providers": {
                "slurm": {
                    "actor-factory": "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory",
                    "config": {
                        "script-epilogue": "sleep 10 && sync",
                        "concurrent-job-limit": 50,
                        "runtime-attributes": "\n          String? docker\n          String? docker_user\n          Int cpu = 1\n          Int? gpu\n          Int? time\n          Int? memory_mb\n          String? slurm_partition\n          String? slurm_account\n          String? slurm_extra_param\n          String singularity\n        ",
                        "submit": "\n          sbatch \\n          --export=ALL \\n          -J ${job_name} \\n          -D ${cwd} \\n          -o ${out} \\n          -e ${err} \\n          ${\"-t \" + time*60} \\n          -n 1 \\n          --ntasks-per-node=1 \\n          ${true=\"--cpus-per-task=\" false=\"\" defined(cpu)}${cpu} \\n          ${true=\"--mem=\" false=\"\" defined(memory_mb)}${memory_mb} \\n          ${\"-p \" + slurm_partition} \\n          ${\"--account \" + slurm_account} \\n          ${true=\"--gres gpu:\" false=\"\" defined(gpu)}${gpu} \\n          ${slurm_extra_param} \\n          --wrap \"${if defined(singularity) then '' else '/bin/bash ${script} #'} if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; singularity exec --cleanenv --home ${cwd} ${if defined(gpu) then '--nv' else ''} ${singularity} /bin/bash ${script}\"\n        ",
                        "kill": "scancel ${job_id}",
                        "exit-code-timeout-seconds": 180,
                        "check-alive": "CHK_ALIVE=$(squeue --noheader -j ${job_id}); if [ -z $CHK_ALIVE ]; then /bin/bash -c 'exit 1'; else echo $CHK_ALIVE; fi",
                        "job-id-regex": "Submitted batch job (\d+).*"
                    }
                }
            }
        }
    }

    def __init__(self, partition=None, account=None, extra_param=None):
        super(CromwellerBackendSLURM, self).__init__(
            CromwellerBackendSLURM._TEMPLATE)
        config = self['backend']['providers']['slurm']['config']
        key = 'runtime-attributes'
        
        assert(type(config[key])==str)

        if partition is not None:
            config[key] = config[key].replace(
                'String? slurm_partition\n',
                'String slurm_partition = {}\n'.format(partition))
        if account is not None:
            config[key] = config[key].replace(
                'String? slurm_account\n',
                'String slurm_account = {}\n'.format(account))
        if extra_param is not None:
            config[key] = config[key].replace(
                'String? slurm_extra_param\n',
                'String slurm_extra_param = {}\n'.format(extra_param))


class CromwellerBackendSGE(object):
    _TEMPLATE = {
        "backend": {
            "providers": {
                "sge": {
                    "actor-factory": "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory",
                    "config": {
                        "script-epilogue": "sleep 10 && sync",
                        "concurrent-job-limit": 50,
                        "runtime-attributes": "\n          String? docker\n          String? docker_user\n          String sge_pe = \"shm\"\n          Int cpu = 1\n          Int? gpu\n          Int? time\n          Int? memory_mb\n          String? sge_queue\n          String? sge_extra_param\n          String singularity\n        ",
                        "submit": "\n          echo \"${if defined(singularity) then '' else '/bin/bash ${script} #'} if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; singularity exec --cleanenv --home ${cwd} ${if defined(gpu) then '--nv' else ''} ${singularity} /bin/bash ${script}\" | qsub \\n          -S /bin/sh \\n          -terse \\n          -b n \\n          -N ${job_name} \\n          -wd ${cwd} \\n          -o ${out} \\n          -e ${err} \\n          ${if cpu>1 then \"-pe \" + sge_pe + \" \" else \"\"}${if cpu>1 then cpu else \"\"} \\n          ${true=\"-l h_vmem=$(expr \" false=\"\" defined(memory_mb)}${memory_mb}${true=\" / \" false=\"\" defined(memory_mb)}${if defined(memory_mb) then cpu else \"\"}${true=\")m\" false=\"\" defined(memory_mb)} \\n          ${true=\"-l s_vmem=$(expr \" false=\"\" defined(memory_mb)}${memory_mb}${true=\" / \" false=\"\" defined(memory_mb)}${if defined(memory_mb) then cpu else \"\"}${true=\")m\" false=\"\" defined(memory_mb)} \\n          ${true=\"-l h_rt=\" false=\"\" defined(time)}${time}${true=\":00:00\" false=\"\" defined(time)}\\n          ${true=\"-l s_rt=\" false=\"\" defined(time)}${time}${true=\":00:00\" false=\"\" defined(time)}\\n          ${\"-q \" + sge_queue} \\n          ${\"-l gpu=\" + gpu} \\n          ${sge_extra_param} \\n          -V\n        ",
                        "exit-code-timeout-seconds": 180,
                        "kill": "qdel ${job_id}",
                        "check-alive": "qstat -j ${job_id}",
                        "job-id-regex": "(\d+)"
                    }
                }
            }
        }
    }

    def __init__(self, pe, queue=None, extra_param=None):
        super(CromwellerBackendSGE, self).__init__(
            CromwellerBackendSGE._TEMPLATE)
        config = self['backend']['providers']['sge']['config']
        key = 'runtime-attributes'
        
        assert(type(config[key])==str)

        config[key] = config[key].replace(
            'String sge_pe',
            'String sge_pe = {}\n'.format(pe))

        if queue is not None:
            config[key] = config[key].replace(
                'String? sge_queue\n',
                'String sge_queue = {}\n'.format(queue))
        if extra_param is not None:
            config[key] = config[key].replace(
                'String? sge_extra_param\n',
                'String sge_extra_param = {}\n'.format(extra_param))


class CromwellerBackendPBS(object):
    _TEMPLATE = {
        "backend": {
            "providers": {
                "pbs": {
                    "actor-factory": "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory",
                    "config": {
                        "script-epilogue": "sleep 30 && sync",
                        "concurrent-job-limit": 50,
                        "runtime-attributes": "\n          String? docker\n          String? docker_user\n          Int cpu = 1\n          Int? gpu\n          Int? time\n          Int? memory_mb\n          String? pbs_queue\n          String? pbs_extra_param\n          String singularity\n        ",
                        "submit": "\n          echo \"${if defined(singularity) then '' else '/bin/bash ${script} #'} if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; singularity exec --cleanenv --home ${cwd} ${if defined(gpu) then '--nv' else ''} ${singularity} /bin/bash ${script}\" | qsub \\n          -N ${job_name} \\n          -o ${out} \\n          -e ${err} \\n          ${true=\"-lselect=1:ncpus=\" false=\"\" defined(cpu)}${cpu}${true=\":mem=\" false=\"\" defined(memory_mb)}${memory_mb}${true=\"mb\" false=\"\" defined(memory_mb)} \\n          ${true=\"-lwalltime=\" false=\"\" defined(time)}${time}${true=\":0:0\" false=\"\" defined(time)} \\n          ${true=\"-lngpus=\" false=\"\" gpu>1}${if gpu>1 then gpu else \"\"} \\n          ${\"-q \" + pbs_queue} \\n          ${pbs_extra_param} \\n          -V\n        ",
                        "exit-code-timeout-seconds": 180,
                        "kill": "qdel ${job_id}",
                        "check-alive": "qstat -j ${job_id}",
                        "job-id-regex": "(\d+)"
                    }
                }
            }
        }
    }

    def __init__(self, queue=None, extra_param=None):
        super(CromwellerBackendPBS, self).__init__(
            CromwellerBackendPBS._TEMPLATE)
        config = self['backend']['providers']['pbs']['config']
        key = 'runtime-attributes'
        
        assert(type(config[key])==str)

        if queue is not None:
            config[key] = config[key].replace(
                'String? pbs_squeue\n',
                'String pbs_squeue = {}\n'.format(queue))
        if extra_param is not None:
            config[key] = config[key].replace(
                'String? pbs_extra_param\n',
                'String pbs_extra_param = {}\n'.format(extra_param))


def main():
    pass

if __name__ == '__main__':
    main()
