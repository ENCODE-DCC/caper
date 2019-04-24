#!/usr/bin/env python
"""
Cromweller backend
"""

import json
from copy import deepcopy
from pyhocon import ConfigFactory, HOCONConverter

from cromweller_uri import CromwellerURI
from logged_bash_cli import bash_run_cmd


class CromwellerBackends(object):
    """CromwellerBackend manager

    This manager initializes the following backend stanzas,
    which are defined in "backend" {} in a Cromwell's backend
    file:
        1) local: local backend
        2) gc: Google Cloud backend (optional)
        3) aws: AWS backend (optional)
        4) slurm: SLURM (optional)
        5) sge: SGE (optional)
        6) pbs: PBS (optional)

    Also, it initializes the following common non-backend stanzas:
        a) common: base backend
        b) mysql: connect to MySQL (optional)
    """

    RE_PATTERN_CONF_HEADER = '^[\s]*include\s'
    BACKEND_CONF_HEADER = 'include required(classpath("application"))\n'
    DEFAULT_BACKEND = 'local'

    def __init__(self, args):
        """Parses parameters from argparse and then initializes backend
        configuration dict and convert it to HOCON string
        """

        def merge_dict(a, b, path=None):
            """Merge b into a recursively. This mutates a and overwrites
            items in b on a for conflicts.            

            Ref: https://stackoverflow.com/questions/7204805/dictionaries-of-dictionaries-merge/7205107#7205107                
            """
            if path is None: path = []
            for key in b:
                if key in a:
                    if isinstance(a[key], dict) and isinstance(b[key], dict):
                        merge_dict(a[key], b[key], path + [str(key)])
                    elif a[key] == b[key]:
                        pass
                    else:
                        a[key] = b[key]
                else:
                    a[key] = b[key]

        # init backend dict
        self._backend_dict = {}

        # local backend
        merge_dict(self._backend_dict, CromwellerBackendLocal(
            out_dir=args.get('out_dir'),
            concurrent_job_limit=args.get('num_concurrent_tasks')))

        # GC
        if args.get('gc_project') and args.get('gc_project is not None'):
            merge_dict(self._backend_dict, CromwellerBackendGC(
                gc_project=args.get('gc_project'),
                out_gcs_bucket=args.get('out_gcs_bucket'),
                concurrent_job_limit=args.get('num_concurrent_tasks')))

        # AWS
        if args.get('aws_batch_arn') and args.get('aws_region'):
            merge_dict(self._backend_dict, CromwellerBackendAWS(
                aws_batch_arn=args.get('aws_batch_arn'),
                aws_region=args.get('aws_region'),
                concurrent_job_limit=args.get('num_concurrent_tasks')))

        # SLURM
        merge_dict(self._backend_dict, CromwellerBackendSLURM(
            partition=args.get('slurm_partition'),
            account=args.get('slurm_account'),
            extra_param=args.get('slurm_extra_param'),
            concurrent_job_limit=args.get('num_concurrent_tasks')))

        # SGE
        merge_dict(self._backend_dict, CromwellerBackendSGE(
            pe=args.get('sge_pe'),
            queue=args.get('sge_queue'),
            extra_param=args.get('sge_extra_param'),
            concurrent_job_limit=args.get('num_concurrent_tasks')))

        # PBS
        merge_dict(self._backend_dict, CromwellerBackendPBS(
            queue=args.get('pbs_queue'),
            extra_param=args.get('pbs_extra_param'),
            concurrent_job_limit=args.get('num_concurrent_tasks')))

        # MySQL is optional
        if args.get('mysql_db_user') and args.get('mysql_db_password'):
            merge_dict(self._backend_dict, CromwellerBackendMySQL(
                ip=args.get('mysql_db_ip'),
                port=args.get('mysql_db_port'),
                user=args.get('mysql_db_user'),
                password=args.get('mysql_db_password')))

        # set header for conf ("include ...")
        assert(CromwellerBackends.BACKEND_CONF_HEADER.endswith('\n'))
        lines_header = [CromwellerBackends.BACKEND_CONF_HEADER]

        # override with user-specified backend.conf if exists
        if args.get('backend_conf') is not None:
            lines_wo_header = []

            with open(args.get('backend_conf'), 'r') as fp:
                for line in fp.readlines():
                    # find header and exclude
                    if re.findall(CromwellerBackends.RE_PATTERN_CONF_HEADER, line):
                        if not line in lines_header:
                            lines_header.append(line)
                    else:
                        lines_wo_header.append(line)

            # parse HOCON to JSON to dict
            c = ConfigFactory.parse_string(''.join(lines_wo_header))
            j = HOCONConverter.to_json(c)
            d = json.loads(j)
            # apply to backend conf
            merge_dict(self._backend_dict, d)

        # use default backend (local) if not specified
        if args.get('backend') is not None:
            self._backend_dict['backend']['default'] = args.get('backend')
        else:
            self._backend_dict['backend']['default'] = CromwellerBackends.DEFAULT_BACKEND

        # dict to HOCON (excluding header)
        self._backend_hocon = ConfigFactory.from_dict(self._backend_dict)
        # write header to HOCON string
        self._backend_str = ''.join(lines_header)
        # convert HOCON to string
        self._backend_str += HOCONConverter.to_hocon(self._backend_hocon)

        # save string as a final backend.conf file passed to cromwell.jar

    def get_backend_str(self):
        return self._backend_str


class CromwellerBackendCommon(dict):
    """Dict of common stanzas for all Cromweller backends
    """
    TEMPLATE = {
        "backend": {
            "default": "local"
        },
        "webservice" : {
            "port" : 8000
        },
        "services": {
            "LoadController": {
                "class": "cromwell.services.loadcontroller.impl.LoadControllerServiceActor",
                "config": {
                    # due to issues on stanford sherlock/scg
                    "control-frequency": "21474834 seconds"
                }
            }
        },
        "system": {
            "abort-jobs-on-terminate": True,
            "graceful-server-shutdown": True,
            "max-concurrent-workflows" : 40
        },
        "call-caching": {
            "enabled": False,
            "invalidate-bad-cache-results": True
        }
    }

    def __init__(self,
        port=None,
        use_call_caching=None,
        max_concurrent_workflows=None):

        super(CromwellerBackendCommon, self).__init__(
            CromwellerBackendCommon.TEMPLATE)

        if port is not None:
            self['webservice']['port'] = port
        if use_call_caching is not None:
            self['call-caching']['enabled'] = use_call_caching
        if use_call_caching is not None:
            self['system']['max-concurrent-workflows'] = max_concurrent_workflows
        

class CromwellerBackendMySQL(dict):
    """Backend for MySQL
    """
    TEMPLATE = {
        "database": {
            "profile": "slick.jdbc.MySQLProfile$",
            "db": {
                "url": "jdbc:mysql://localhost:3306/cromwell_db?allowPublicKeyRetrieval=true&useSSL=false&rewriteBatchedStatements=true",
                "user": "cromwell",
                "password": "cromwell",
                "driver": "com.mysql.jdbc.Driver" 
            }
        }
    }

    def __init__(self,
        ip,
        port,
        user,
        password):

        super(CromwellerBackendMySQL, self).__init__(
            CromwellerBackendMySQL.TEMPLATE)

        db = ['database']['db']
        db['user'] = user
        db['password'] = password
        db['url'] = db['url'].replace('localhost:3306',
            '{ip}:{port}'.format(ip, port))
        

class CromwellerBackendGC(dict):
    """Dict for Cromweller backend GC
    """
    TEMPLATE = {
        "backend": {
            "providers": {
                "gc": {
                    "actor-factory": "cromwell.backend.impl.jes.JesBackendLifecycleActorFactory",
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

    def __init__(self,
        gc_project,
        out_gcs_bucket,
        concurrent_job_limit=None):

        super(CromwellerBackendGC, self).__init__(
            CromwellerBackendGC.TEMPLATE)        

        config = self['backend']['providers']['gc']['config']
        config['project'] = gc_project
        config['root'] = out_gcs_bucket
        assert(out_gcs_bucket.startswith('gs://'))

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CromwellerBackendAWS(dict):
    """Dict for Cromweller backend AWS
    """
    TEMPLATE = {
        "backend": {
            "providers": {
                "aws": {
                    "actor-factory": "cromwell.backend.impl.aws.AwsBatchBackendLifecycleActorFactory",
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

    def __init__(self,
        aws_batch_arn,
        aws_region,
        out_s3_bucket,
        concurrent_job_limit=None):

        super(CromwellerBackendAWS, self).__init__(
            CromwellerBackendAWS.TEMPLATE)

        self['aws']['region'] = aws_region
        config = self['backend']['providers']['aws']['config']
        config['default-runtime-attributes']['queueArn'] = aws_batch_arn
        config['root'] = out_s3_bucket
        assert(out_s3_bucket.startswith('s3://'))

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit


class CromwellerBackendLocal(dict):
    TEMPLATE = {
        "backend": {
            "providers": {
                "local": {
                    "actor-factory": "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes" : {                            
                        },
                        "run-in-background": True,
                        "script-epilogue": "sleep 10 && sync",
                        "concurrent-job-limit": 1000,                        
                        "runtime-attributes": "\n          Int? gpu\n          String? docker\n          String? docker_user\n          String? singularity\n        ",
                        "submit": "\n          ${if defined(singularity) then \"\" else \"/bin/bash ${script} #\"} if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; singularity exec --cleanenv --home ${cwd} ${if defined(gpu) then '--nv' else ''} ${singularity} /bin/bash ${script}\n        "
                    }
                }
            }
        }
    }

    def __init__(self,
        out_dir,
        concurrent_job_limit=None):

        super(CromwellerBackendLocal, self).__init__(
            CromwellerBackendLocal.TEMPLATE)

        config = self['backend']['providers']['local']['config']        
        config['root'] = out_dir

        if concurrent_job_limit is not None:
            config['concurrent-job-limit'] = concurrent_job_limit



class CromwellerBackendSLURM(dict):
    TEMPLATE = {
        "backend": {
            "providers": {
                "slurm": {
                    "actor-factory": "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes" : {                            
                        },
                        "script-epilogue": "sleep 10 && sync",
                        "concurrent-job-limit": 1000,
                        "runtime-attributes": "\n          String? docker\n          String? docker_user\n          Int cpu = 1\n          Int? gpu\n          Int? time\n          Int? memory_mb\n          String? slurm_partition\n          String? slurm_account\n          String? slurm_extra_param\n          String singularity\n        ",
                        "submit": "\n          sbatch \n          --export=ALL \n          -J ${job_name} \n          -D ${cwd} \n          -o ${out} \n          -e ${err} \n          ${\"-t \" + time*60} \n          -n 1 \n          --ntasks-per-node=1 \n          ${true=\"--cpus-per-task=\" false=\"\" defined(cpu)}${cpu} \n          ${true=\"--mem=\" false=\"\" defined(memory_mb)}${memory_mb} \n          ${\"-p \" + slurm_partition} \n          ${\"--account \" + slurm_account} \n          ${true=\"--gres gpu:\" false=\"\" defined(gpu)}${gpu} \n          ${slurm_extra_param} \n          --wrap \"${if defined(singularity) then '' else '/bin/bash ${script} #'} if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; singularity exec --cleanenv --home ${cwd} ${if defined(gpu) then '--nv' else ''} ${singularity} /bin/bash ${script}\"\n        ",
                        "kill": "scancel ${job_id}",
                        "exit-code-timeout-seconds": 180,
                        "check-alive": "CHK_ALIVE=$(squeue --noheader -j ${job_id}); if [ -z $CHK_ALIVE ]; then /bin/bash -c 'exit 1'; else echo $CHK_ALIVE; fi",
                        "job-id-regex": "Submitted batch job (\d+).*"
                    }
                }
            }
        }
    }

    def __init__(self,
        partition=None,
        account=None,
        extra_param=None,
        concurrent_job_limit=None):

        super(CromwellerBackendSLURM, self).__init__(
            CromwellerBackendSLURM.TEMPLATE)

        config = self['backend']['providers']['slurm']['config']
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
    TEMPLATE = {
        "backend": {
            "providers": {
                "sge": {
                    "actor-factory": "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes" : {                            
                        },
                        "script-epilogue": "sleep 10 && sync",
                        "concurrent-job-limit": 1000,
                        "runtime-attributes": "\n          String? docker\n          String? docker_user\n          String sge_pe = \"shm\"\n          Int cpu = 1\n          Int? gpu\n          Int? time\n          Int? memory_mb\n          String? sge_queue\n          String? sge_extra_param\n          String singularity\n        ",
                        "submit": "\n          echo \"${if defined(singularity) then '' else '/bin/bash ${script} #'} if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; singularity exec --cleanenv --home ${cwd} ${if defined(gpu) then '--nv' else ''} ${singularity} /bin/bash ${script}\" | qsub \n          -S /bin/sh \n          -terse \n          -b n \n          -N ${job_name} \n          -wd ${cwd} \n          -o ${out} \n          -e ${err} \n          ${if cpu>1 then \"-pe \" + sge_pe + \" \" else \"\"}${if cpu>1 then cpu else \"\"} \n          ${true=\"-l h_vmem=$(expr \" false=\"\" defined(memory_mb)}${memory_mb}${true=\" / \" false=\"\" defined(memory_mb)}${if defined(memory_mb) then cpu else \"\"}${true=\")m\" false=\"\" defined(memory_mb)} \n          ${true=\"-l s_vmem=$(expr \" false=\"\" defined(memory_mb)}${memory_mb}${true=\" / \" false=\"\" defined(memory_mb)}${if defined(memory_mb) then cpu else \"\"}${true=\")m\" false=\"\" defined(memory_mb)} \n          ${true=\"-l h_rt=\" false=\"\" defined(time)}${time}${true=\":00:00\" false=\"\" defined(time)}\n          ${true=\"-l s_rt=\" false=\"\" defined(time)}${time}${true=\":00:00\" false=\"\" defined(time)}\n          ${\"-q \" + sge_queue} \n          ${\"-l gpu=\" + gpu} \n          ${sge_extra_param} \n          -V\n        ",
                        "exit-code-timeout-seconds": 180,
                        "kill": "qdel ${job_id}",
                        "check-alive": "qstat -j ${job_id}",
                        "job-id-regex": "(\d+)"
                    }
                }
            }
        }
    }

    def __init__(self,
        pe=None,
        queue=None,
        extra_param=None,
        concurrent_job_limit=None):

        super(CromwellerBackendSGE, self).__init__(
            CromwellerBackendSGE.TEMPLATE)

        config = self['backend']['providers']['sge']['config']
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
    TEMPLATE = {
        "backend": {
            "providers": {
                "pbs": {
                    "actor-factory": "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory",
                    "config": {
                        "default-runtime-attributes" : {                            
                        },
                        "script-epilogue": "sleep 30 && sync",
                        "concurrent-job-limit": 1000,
                        "runtime-attributes": "\n          String? docker\n          String? docker_user\n          Int cpu = 1\n          Int? gpu\n          Int? time\n          Int? memory_mb\n          String? pbs_queue\n          String? pbs_extra_param\n          String singularity\n        ",
                        "submit": "\n          echo \"${if defined(singularity) then '' else '/bin/bash ${script} #'} if [ -z $SINGULARITY_BINDPATH ]; then SINGULARITY_BINDPATH=/; fi; singularity exec --cleanenv --home ${cwd} ${if defined(gpu) then '--nv' else ''} ${singularity} /bin/bash ${script}\" | qsub \n          -N ${job_name} \n          -o ${out} \n          -e ${err} \n          ${true=\"-lselect=1:ncpus=\" false=\"\" defined(cpu)}${cpu}${true=\":mem=\" false=\"\" defined(memory_mb)}${memory_mb}${true=\"mb\" false=\"\" defined(memory_mb)} \n          ${true=\"-lwalltime=\" false=\"\" defined(time)}${time}${true=\":0:0\" false=\"\" defined(time)} \n          ${true=\"-lngpus=\" false=\"\" gpu>1}${if gpu>1 then gpu else \"\"} \n          ${\"-q \" + pbs_queue} \n          ${pbs_extra_param} \n          -V\n        ",
                        "exit-code-timeout-seconds": 180,
                        "kill": "qdel ${job_id}",
                        "check-alive": "qstat -j ${job_id}",
                        "job-id-regex": "(\d+)"
                    }
                }
            }
        }
    }

    def __init__(self,
        queue=None,
        extra_param=None,
        concurrent_job_limit=None):

        super(CromwellerBackendPBS, self).__init__(
            CromwellerBackendPBS.TEMPLATE)
        config = self['backend']['providers']['pbs']['config']
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
