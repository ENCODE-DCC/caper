import logging
import os
import shutil
import socket
from subprocess import PIPE, STDOUT, CalledProcessError, Popen
from tempfile import TemporaryDirectory

from autouri import AbsPath, AutoURI

from .cromwell_metadata import CromwellMetadata
from .cromwell_workflow_monitor import CromwellWorkflowMonitor

logger = logging.getLogger(__name__)


class Cromwell(object):
    """Wraps Cromwell/Womtool.
    """

    DEFAULT_CROMWELL = 'https://github.com/broadinstitute/cromwell/releases/download/47/cromwell-47.jar'
    DEFAULT_WOMTOOL = (
        'https://github.com/broadinstitute/cromwell/releases/download/47/womtool-47.jar'
    )
    DEFAULT_CROMWELL_INSTALL_DIR = '~/.caper/cromwell_jar'
    DEFAULT_WOMTOOL_INSTALL_DIR = '~/.caper/womtool_jar'
    DEFAULT_JAVA_HEAP_CROMWELL_SERVER = '10G'
    DEFAULT_JAVA_HEAP_CROMWELL_RUN = '3G'
    DEFAULT_JAVA_HEAP_WOMTOOL = '1G'
    DEFAULT_SERVER_PORT = 8000
    USER_INTERRUPT_WARNING = '\n********** DO NOT CTRL+C MULTIPLE TIMES **********\n'
    LOCALHOST = 'localhost'

    def __init__(
        self,
        cromwell=DEFAULT_CROMWELL,
        womtool=DEFAULT_WOMTOOL,
        cromwell_install_dir=DEFAULT_CROMWELL_INSTALL_DIR,
        womtool_install_dir=DEFAULT_WOMTOOL_INSTALL_DIR,
        java_heap_cromwell_server=DEFAULT_JAVA_HEAP_CROMWELL_SERVER,
        java_heap_cromwell_run=DEFAULT_JAVA_HEAP_CROMWELL_RUN,
        java_heap_womtool=DEFAULT_JAVA_HEAP_WOMTOOL,
        server_port=DEFAULT_SERVER_PORT,
        server_hostname=None,
        server_heartbeat=None,
        debug=False,
    ):
        """
        Args:
            cromwell:
            server_hostname:
                Server hostname. If defined heartbeat file will be written
                with this hostname instead of socket.gethostname().
            server_heartbeat:
                ServerHeartbeat object.
        """
        self._cromwell = cromwell
        self._womtool = womtool
        self._java_heap_cromwell_server = java_heap_cromwell_server
        self._java_heap_cromwell_run = java_heap_cromwell_run
        self._java_heap_womtool = java_heap_womtool
        self._server_port = server_port
        self._server_hostname = (
            server_hostname if server_hostname else socket.gethostname()
        )
        self._server_heartbeat = server_heartbeat

        u_cromwell_install_dir = AbsPath(cromwell_install_dir)
        if not u_cromwell_install_dir.is_valid:
            raise ValueError(
                'crommwell_install_dir is not a valid absolute '
                'path. {path}'.format(path=cromwell_install_dir)
            )
        self._cromwell_install_dir = u_cromwell_install_dir.uri

        u_womtool_install_dir = AbsPath(womtool_install_dir)
        if not u_womtool_install_dir.is_valid:
            raise ValueError(
                'womtool_install_dir is not a valid absolute '
                'path. {path}'.format(path=womtool_install_dir)
            )
        self._womtool_install_dir = u_womtool_install_dir.uri

        self._debug = debug

    def validate(self, wdl, inputs=None, imports=None):
        """Validate WDL/inputs/imports using Womtool.

        Returns:
            rc:
                Womtool's return code.
        """
        self.install_womtool()

        u_wdl = AutoURI(wdl)
        if not u_wdl.exists:
            raise FileNotFoundError(
                'WDL file does not exist. wdl={wdl}'.format(wdl=wdl)
            )
        if inputs:
            u_inputs = AutoURI(inputs)
            if not u_inputs.exists:
                raise FileNotFoundError(
                    'Inputs JSON defined but does not exist. i={i}'.format(i=inputs)
                )

        with TemporaryDirectory() as tmp_d:
            if imports:
                u_imports = AutoURI(imports)
                if not u_imports.exists:
                    raise FileNotFoundError(
                        'Imports file defined but does not exist. i={i}'.format(
                            i=imports
                        )
                    )
                wdl_ = os.path.join(tmp_d, u_wdl.basename)
                u_wdl.cp(wdl_)
                shutil.unpack_archive(imports, tmp_d)
            else:
                wdl_ = u_wdl.localize_on(tmp_d)

            cmd = [
                'java',
                '-Xmx{heap}'.format(heap=self._java_heap_womtool),
                '-jar',
                '-DLOG_LEVEL={lvl}'.format(lvl='DEBUG' if self._debug else 'INFO'),
                self._womtool,
                'validate',
                wdl_,
            ]
            if inputs:
                cmd += ['-i', inputs]

            logger.info('Validating WDL/inputs/imports with Womtool...')
            p = Popen(cmd, stdout=PIPE, stderr=PIPE)
            stdout, stderr = p.communicate()
            rc = p.returncode

            if rc:
                logger.error(
                    'RC={rc}\nSTDOUT={o}\nSTDERR={e}'
                    'Womtool validation failed.'.format(rc=rc, o=stdout, e=stderr)
                )
            else:
                logger.info('Womtool validation passed.')

        return rc

    def run(
        self,
        wdl,
        backend_conf=None,
        inputs=None,
        options=None,
        imports=None,
        labels=None,
        metadata=None,
        fileobj_stdout=None,
        dry_run=False,
        callback_status_change=None,
    ):
        """Run Cromwell run mode (java -jar cromwell.jar run).

        Args:
            backend_conf:
                backend.conf file (-Dconfig.file=)
            inputs:
                input JSON file (-i)
            options:
                workflow options JSON file (-o)
            imports:
                imports.zip file (-p)
            labels:
                labels file (-l)
            metadata:
                output metadata JSON file (-m)
            dry_run:
                Dry run
            fileobj_stdout:
                File-like object to print Cromwell's STDOUT to.
                STDERR is redirected to STDOUT.
            callback_status_change:
                Not implemnted yet.
                Callback function called while polling.
                This function should take 5 args
                    workflow_id:
                        UUID of a workflow
                    workflow_new_status:
                        New status for a workflow. None if no change.
                    task_id:
                        Tuple (task_name, shard_idx) to identify workflow's task.
                    task_new_status:
                        New status for a task, None if no change.
                    metadata:
                        metadata (dict) of a workflow.
        Returns:
            return code:
                Cromwell's return code. -1 if dry-run.
            metadata_file:
                Metadata file URI. None if Cromwell failed.
        """
        self.install_cromwell()

        # LOG_LEVEL must be >=INFO to catch workflow ID from STDOUT
        cmd = [
            'java',
            '-Xmx{}'.format(self._java_heap_cromwell_run),
            '-XX:ParallelGCThreads=1',
            '-jar',
            '-DLOG_LEVEL={lvl}'.format(lvl='DEBUG' if self._debug else 'INFO'),
            '-DLOG_MODE=standard',
        ]

        if backend_conf:
            cmd += ['-Dconfig.file={}'.format(backend_conf)]
        cmd += [self._cromwell, 'run', wdl]
        if inputs:
            cmd += ['-i', inputs]
        if options:
            cmd += ['-o', options]
        if labels:
            cmd += ['-l', labels]
        if imports:
            cmd += ['-p', imports]
        if metadata:
            cmd += ['-m', metadata]

        logger.info('run: {cmd}'.format(cmd=' '.join(cmd)))
        rc = -1
        if dry_run:
            return rc
        try:
            wm = CromwellWorkflowMonitor(
                callback_status_change=callback_status_change, is_server=False
            )

            p = Popen(cmd, stdout=PIPE, stderr=STDOUT)
            while True:
                stdout = p.stdout.readline().decode()
                if fileobj_stdout:
                    fileobj_stdout.write(stdout)
                    fileobj_stdout.flush()

                wm.update(stdout)
                if p.poll() is not None:
                    break
            rc = p.poll()

        except CalledProcessError as e:
            rc = e.returncode
        except KeyboardInterrupt:
            logger.error(Cromwell.USER_INTERRUPT_WARNING)
        finally:
            p.terminate()

        if metadata:
            metadata_file = CromwellMetadata(metadata).write_on_workflow_root()
        else:
            metadata_file = None

        return rc, metadata_file

    def server(
        self,
        backend_conf=None,
        fileobj_stdout=None,
        embed_subworkflow=False,
        dry_run=False,
        callback_status_change=None,
    ):
        """Run Cromwell server mode (java -jar cromwell.jar server).

        Args:
            backend_conf:
                backend.conf file for Cromwell's Java parameter
                "-Dconfig.file=".
            fileobj_stdout:
                File object to write Cromwell's STDOUT on.
                STDERR is redirected to STDOUT.
            embed_subworkflow:
                This class basically stores/updates metadata.JSON file on
                each workflow's root directory whenever there is status change
                of workflow (or it's tasks).
                This flag ensures that any subworkflow's metadata JSON will be
                embedded in main (this) workflow's metadata JSON.
                This is to mimic behavior of Cromwell run mode's -m parameter.
            dry_run:
                Dry run.
            callback_status_change:
                (Not implemented yet)
                Callback function called while polling.
                function should take 5 args
                    workflow_id:
                        UUID of a workflow
                    workflow_new_status:
                        New status for a workflow. None if no change.
                    task_id:
                        Tuple (task_name, shard_idx) to identify workflow's task.
                    task_new_status:
                        New status for a task, None if no change.
                    metadata:
                        metadata (dict) of a workflow.
        Returns:
            return code:
                Cromwell's return code. -1 if dry-run.
        """
        self.install_cromwell()

        # check if port is open
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((Cromwell.LOCALHOST, self._server_port))
        if not result:
            raise ValueError(
                'Server port {} is already taken. '
                'Try with a different port'.format(self._server_port)
            )

        # LOG_LEVEL must be >=INFO to catch workflow ID from STDOUT
        cmd = [
            'java',
            '-Xmx{}'.format(self._java_heap_cromwell_server),
            '-XX:ParallelGCThreads=1',
            '-jar',
            '-DLOG_LEVEL={lvl}'.format(lvl='DEBUG' if self._debug else 'INFO'),
            '-DLOG_MODE=standard',
        ]
        if backend_conf:
            cmd += ['-Dconfig.file={}'.format(backend_conf)]

        cmd += [self._cromwell, 'server']
        logger.info('cmd: {cmd}'.format(cmd=cmd))

        rc = -1
        if dry_run:
            return rc
        try:
            wm = CromwellWorkflowMonitor(
                server_port=self._server_port,
                is_server=True,
                embed_subworkflow=embed_subworkflow,
                callback_status_change=callback_status_change,
            )
            init_server = False

            p = Popen(cmd, stdout=PIPE, stderr=STDOUT)
            while True:
                stdout = p.stdout.readline().decode()
                if fileobj_stdout:
                    fileobj_stdout.write(stdout)
                    fileobj_stdout.flush()

                wm.update(stdout)
                if not init_server and wm.is_server_started():
                    if self._server_heartbeat:
                        self._server_heartbeat.run(
                            port=self._server_port, hostname=self._server_hostname
                        )
                    init_server = True
                if p.poll() is not None:
                    break
            rc = p.poll()

        except CalledProcessError as e:
            rc = e.returncode
        except KeyboardInterrupt:
            logger.error(Cromwell.USER_INTERRUPT_WARNING)
        finally:
            if self._server_heartbeat:
                self._server_heartbeat.stop()
            p.terminate()

        return rc

    def install_cromwell(self):
        self._cromwell = Cromwell.__install_file(
            self._cromwell, self._cromwell_install_dir, 'Cromwell JAR'
        )
        return self._cromwell

    def install_womtool(self):
        self._womtool = Cromwell.__install_file(
            self._womtool, self._womtool_install_dir, 'Womtool JAR'
        )
        return self._womtool

    @staticmethod
    def __install_file(f, install_dir, label):
        u = AutoURI(f)
        if isinstance(u, AbsPath):
            return u.uri
        logger.info('Installing {label}... {f}'.format(label=label, f=f))
        path = os.path.join(os.path.expanduser(install_dir), u.basename)
        return u.cp(path)
