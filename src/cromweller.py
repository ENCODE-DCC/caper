#!/usr/bin/env python
"""
Cromweller: Cromwell/WDL wrapper python script
    for multiple backends (local, gc, aws)

(Optional)
Add the following comments to your WDL script to specify container images
that Cromweller will use for your WDL.

Example:
#CROMWELLER docker quay.io/encode-dcc/atac-seq-pipeline:v1.1.7.2
#CROMWELLER singularity docker://quay.io/encode-dcc/atac-seq-pipeline:v1.1.7.2
"""

import argparse
import configparser
import os
import sys
from cromweller_backend import CromwellerBackends
from cromweller_uri import CromwellerURI
from logged_bash_cli import bash_run_cmd
import pyhocon


class CromwellerArgParser(object):
    """Argument parser for Cromweller
    """
    DEFAULT_CROMWELLER_CONF = '~/.cromweller/default.conf'
    DEFAULT_CROMWELL_JAR = 'https://github.com/broadinstitute/cromwell/releases/download/38/cromwell-38.jar'
    DEFAULT_MYSQL_DB_IP = 'localhost'
    DEFAULT_MYSQL_DB_PORT = 3306
    DEFAULT_NUM_CONCURRENT_WORKFLOWS = 40
    DEFAULT_NUM_CONCURRENT_TASKS = 1000
    DEFAULT_SERVER_PORT = 8000
    DEFAULT_SERVER_IP = 'localhost'

    @staticmethod
    def parse_arguments():
        """Cromweller CLI.
        """
        conf_parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            add_help=False
            )
        conf_parser.add_argument('-c', '--conf',
            help='Specify config file',
            metavar='FILE',
            default=CromwellerArgParser.DEFAULT_CROMWELLER_CONF)
        known_args, remaining_argv = conf_parser.parse_known_args()

        # read conf file if it exists
        defaults = {}
        if known_args.conf and os.path.exists(known_args.conf):
            config = configparser.ConfigParser()
            config.read([known_args.conf])
            defaults.update(dict(config.items("defaults")))

        parser = argparse.ArgumentParser(parents=[conf_parser])
        subparser = parser.add_subparsers(dest='action')

        # run, server, submit 
        parent_backend = argparse.ArgumentParser(add_help=False)
        parent_backend.add_argument('-b', '--backend',
            help='Backend to run a workflow')

        # run, server
        parent_host = argparse.ArgumentParser(add_help=False)

        group_mysql = parent_host.add_argument_group(
            title='MySQL arguments')
        group_mysql.add_argument('--mysql-db-ip',
            default=CromwellerArgParser.DEFAULT_MYSQL_DB_IP,
            help='MySQL Database IP address (e.g. localhost)')
        group_mysql.add_argument('--mysql-db-port',
            default=CromwellerArgParser.DEFAULT_MYSQL_DB_PORT,
            help='MySQL Database TCP/IP port (e.g. 3306)')
        group_mysql.add_argument('--mysql-db-user',
            help='MySQL Database username')
        group_mysql.add_argument('--mysql-db-password',
            help='MySQL Database password')

        group_cromwell = parent_host.add_argument_group(
            title='Cromwell settings')
        group_cromwell.add_argument('--cromwell',
            default=CromwellerArgParser.DEFAULT_CROMWELL_JAR,
            help='Path or URL for Cromwell JAR file')
        group_cromwell.add_argument('--num-concurrent-tasks',
            default=CromwellerArgParser.DEFAULT_NUM_CONCURRENT_TASKS,
            help='Number of concurrent tasks. '
                '"config.concurrent-job-limit" in Cromwell backend configuration '
                'for each backend')
        group_cromwell.add_argument('--num-concurrent-workflows',
            default=CromwellerArgParser.DEFAULT_NUM_CONCURRENT_WORKFLOWS,
            help='Number of concurrent workflows. '
                '"system.max-concurrent-workflows" in backend configuration')
        group_cromwell.add_argument('--use-call-caching',
            action='store_true',
            help='Use Cromwell\'s call caching, which re-uses outputs from previous workflows. '
                'Make sure to configure MySQL correctly to use this feature')
        group_cromwell.add_argument('--backend-conf',
            help='Custom Cromwell backend configuration file to override all')

        group_local = parent_host.add_argument_group(
            title='local backend arguments')
        group_local.add_argument('--out-dir',
            default='.',
            help='Output directory for local backend')
        group_local.add_argument('--tmp-dir',
            help='Temporary directory for local backend')

        group_gc = parent_host.add_argument_group(
            title='GC backend arguments')
        group_gc.add_argument('--gc-project',
            help='GC project')
        group_gc.add_argument('--out-gcs-bucket',
            help='Output GCS bucket for GC backend')
        group_gc.add_argument('--tmp-gcs-bucket',
            help='Temporary GCS bucket for GC backend')

        group_aws = parent_host.add_argument_group(
            title='AWS backend arguments')
        group_aws.add_argument('--aws-batch-arn',
            help='ARN for AWS Batch')
        group_aws.add_argument('--aws-region',
            help='AWS region (e.g. us-west-1)')
        group_aws.add_argument('--out-s3-bucket',
            help='Output S3 bucket for AWS backend')
        group_aws.add_argument('--tmp-s3-bucket',
            help='Temporary S3 bucket for AWS backend')
        group_aws.add_argument('--use-gsutil-over-aws-s3',
            action='store_true',
            help='Use gsutil instead of aws s3 CLI even for S3 buckets.')

        # run, submit
        parent_submit = argparse.ArgumentParser(add_help=False)

        parent_submit.add_argument('wdl',
            help='Path or URL for WDL script')
        parent_submit.add_argument('-i', '--inputs',
            help='Workflow inputs JSON file')
        parent_submit.add_argument('-o', '--options',
            help='Workflow options JSON file')

        group_dep = parent_submit.add_argument_group(
            title='dependency resolver for all backends',
            description='Cloud-based backends (gc and aws) will only use Docker '
                'so that "--docker URI_FOR_DOCKER_IMG" must be specified '
                'in the command line argument or as a comment "#CROMWELLER '
                'docker URI_FOR_DOCKER_IMG" in a WDL file')
        group_dep.add_argument('--docker',
            help='URI for Docker image (e.g. ubuntu:latest)')

        group_dep_local = parent_submit.add_argument_group(
            title='dependency resolver for local backend',
            description='Singularity is for local backend only. Other backends '
                '(gc and aws) will use Docker. '
                'Local backend defaults not to use any container-based methods. '
                'Activate --use-singularity or --use-docker to use one of them')
        group_dep_local.add_argument('--singularity',
            help='URI or path for Singularity image '
                '(e.g. ~/.singularity/ubuntu-latest.simg, '
                'docker://ubuntu:latest, shub://vsoch/hello-world)')
        group_dep_local.add_argument('--use-singularity',
            help='Use Singularity to resolve dependency for local backend.',
            action='store_true')
        group_dep_local.add_argument('--use-docker',
            help='Use Singularity to resolve dependency for local backend.',
            action='store_true')

        group_slurm = parent_submit.add_argument_group('SLURM arguments')
        group_slurm.add_argument('--slurm-partition',
            help='SLURM partition')
        group_slurm.add_argument('--slurm-account',
            help='SLURM account')
        group_slurm.add_argument('--slurm-extra-param',
            help='SLURM extra parameters. Must be double-quoted')

        group_sge = parent_submit.add_argument_group('SGE arguments')
        group_sge.add_argument('--sge-pe',
            help='SGE parallel environment. Check with "qconf -spl"')
        group_sge.add_argument('--sge-queue',
            help='SGE queue. Check with "qconf -sql"')
        group_sge.add_argument('--sge-extra-param',
            help='SGE extra parameters. Must be double-quoted')

        group_pbs = parent_submit.add_argument_group('PBS arguments')
        group_pbs.add_argument('--pbs-queue',
            help='PBS queue')
        group_pbs.add_argument('--pbs-extra-param',
            help='PBS extra parameters. Must be double-quoted')

        # list, cancel
        parent_wf_id = argparse.ArgumentParser(add_help=False)
        parent_wf_id.add_argument('-w', '--workflow-ids',
            nargs='+',
            help='Workflow IDs')

        # submit, list, cancel
        parent_label = argparse.ArgumentParser(add_help=False)
        parent_label.add_argument('-l', '--labels',
            nargs='+',
            help='Labels')

        parent_server_client = argparse.ArgumentParser(add_help=False)
        parent_server_client.add_argument('--server-port',
            default=CromwellerArgParser.DEFAULT_SERVER_PORT,
            help='Port for Cromweller server')
        parent_client = argparse.ArgumentParser(add_help=False)
        parent_client.add_argument('--server-ip',
            default=CromwellerArgParser.DEFAULT_SERVER_IP,
            help='IP address for Cromweller server')

        p_run = subparser.add_parser('run',
            help='Run a single workflow without server',
            parents=[parent_submit, parent_host, parent_backend])
        p_server = subparser.add_parser('server',
            help='Run a Cromwell server',
            parents=[parent_server_client, parent_host, parent_backend])
        p_submit = subparser.add_parser('submit',
            help='Submit a workflow to a Cromwell server',
            parents=[parent_server_client, parent_client, parent_submit, parent_label,
                parent_backend])
        p_cancel = subparser.add_parser('cancel',
            help='Cancel a workflow running on a Cromwell server',
            parents=[parent_server_client, parent_client, parent_wf_id, parent_label])
        p_list = subparser.add_parser('list',
            help='List workflows running on a Cromwell server',
            parents=[parent_server_client, parent_client, parent_wf_id, parent_label])

        for p in [p_run, p_server, p_submit, p_cancel, p_list]:
            p.set_defaults(**defaults)

        if len(sys.argv[1:])==0:
            parser.print_help()        
            parser.exit()
        # parse all args
        args = parser.parse_args(remaining_argv)
        # return dict version of args
        return vars(args)


class Cromweller(object):
    """Cromwell/WDL wrapper
    """

    def __init__(self, args):
        # keep args dict
        self._args = args
        # init all backends
        self._backend_conf = CromwellerBackends(args)

    def run(self):
        pass

    def server(self):
        pass

    def submit(self):
        pass

    def cancel(self):
        pass

    def list(self):
        pass

        
        

    # def __create_backend_file(self, args):
    #     # use _backend_json and _mysql_json (if mysql options are defined)
    #     # convert JSON to HOCONF
    #     self._backend_file = CromwellerURI('backend.conf').get_local_file()

    # def __get_workflow_opts_json(self):
    #     return CromwellerURI('workflow_opts.json').get_local_file()

    # def server(self):
    #     metadata_json = ''
    #     cmd = 'java -jar -Dconfig.file={backend_file} {cromwell_jar} '
    #     cmd += 'server {wdl} {input_param} -o {workflow_opts_json} '
    #     cmd += '-m {metadata}'
    #     cmd.format(
    #         backend_file = self._backend_file,
    #         cromwell_jar = self._comrwell_jar,
    #         wdl = self._wdl,
    #         input_param = '-i {}'.format(self._input_json_file)
    #             if self._input_json_file else '',
    #         workflow_opts_json = self.__get_workflow_opts_json(),
    #         metadata = metadata_json)
    #     bash_run_cmd(cmd)

    #     bash_
    #     p = subprocess.Popen(cmd)
    #     try:
    #         # run mode        
    #         # p.wait()
    #         # move_metadata()
    #         # parse_metadata()

    #         # server mode
    #         # uuid = new_uuid()
    #         # label_json = { 'cromweller-workflow-uuid' : uuid }        
    #         rc = None
    #         while rc is None:
    #             time.sleep(5)
    #             # GET: get list of all workflows
    #             # check if metadata.json exists
    #             # GET: find by uuid
    #             rc = p.poll()
    #         # move_metadata()
    #         # parse_metadata()

    #     except KeyboardInterrupt:
    #         try:
    #            p.terminate()
    #         except OSError:
    #            raise
    #         p.wait()

    # def run(self):
    #     pass

    # def list(self):
    #     pass

def main():
    # parse args. note that args is a dict
    args = CromwellerArgParser.parse_arguments()

    # init cromweller
    c = Cromweller(args)

    

if __name__ == '__main__':
    sys.exit(main())




"""
DEV NOTE
cromwell is desinged to monitor rc (return code) file, which is generated/controlled
in ${script}, so if singularity does not run it due to some problems in singuarlity's
internal settings then rc file is not generated.
this can result in hanging of a cromwell process.
setting the below parameter enables monitoring by 'check-alive'.
it will take about 'exit-code-timeout-seconds' x 3 time to detect failure.

        # cromwell responds only to non-zero exit code from 'check-alive',
        # but 'squeue -j [JOB_ID]' returns zero exit code even when job is not found
        # workaround to exit with 1 (like SGE's qstat -j [JOB_ID] does) for such cases.

exit-code-timeout-seconds = 180

'export PYTHONNOUSERSITE='
'unset PYTHONPATH'
"""