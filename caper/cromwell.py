import json
import logging
import os
import shutil
import socket
import tempfile

from autouri import AbsPath, AutoURI

from .cromwell_metadata import CromwellMetadata
from .cromwell_workflow_monitor import CromwellWorkflowMonitor
from .nb_subproc_thread import NBSubprocThread, is_fileobj_open

logger = logging.getLogger(__name__)


class PortAlreadyInUseError(Exception):
    pass


def install_file(f, install_dir, label):
    """Install f locally on install_dir.
    If f is already local then skip it.
    """
    if AbsPath(f).is_valid:
        return AbsPath(f).uri
    logger.info('Installing {label}... {f}'.format(label=label, f=f))
    path = os.path.join(os.path.expanduser(install_dir), AutoURI(f).basename)
    return AutoURI(f).cp(path)


class Cromwell:
    """Wraps Cromwell/Womtool.
    """

    DEFAULT_CROMWELL = 'https://github.com/broadinstitute/cromwell/releases/download/59/cromwell-59.jar'
    DEFAULT_WOMTOOL = (
        'https://github.com/broadinstitute/cromwell/releases/download/59/womtool-59.jar'
    )
    DEFAULT_CROMWELL_INSTALL_DIR = '~/.caper/cromwell_jar'
    DEFAULT_WOMTOOL_INSTALL_DIR = '~/.caper/womtool_jar'
    DEFAULT_JAVA_HEAP_CROMWELL_SERVER = '10G'
    DEFAULT_JAVA_HEAP_CROMWELL_RUN = '4G'
    DEFAULT_JAVA_HEAP_WOMTOOL = '1G'
    DEFAULT_SERVER_PORT = 8000
    SERVER_STATUS_STARTED = 'server_started'
    LOCALHOST = 'localhost'

    def __init__(
        self,
        cromwell=DEFAULT_CROMWELL,
        womtool=DEFAULT_WOMTOOL,
        cromwell_install_dir=DEFAULT_CROMWELL_INSTALL_DIR,
        womtool_install_dir=DEFAULT_WOMTOOL_INSTALL_DIR,
    ):
        """
        Args:
            cromwell:
                Cromwell JAR path/URI/URL.
            womtool:
                Womtool JAR path/URI/URL.
            cromwell_install_dir:
                Local directory to install Cromwell JAR.
            womtool_install_dir:
                Local directory to install Womtool JAR.
        """
        self._cromwell = cromwell
        self._womtool = womtool

        if not AbsPath(cromwell_install_dir).is_valid:
            raise ValueError(
                'crommwell_install_dir is not a valid absolute '
                'path. {path}'.format(path=cromwell_install_dir)
            )
        self._cromwell_install_dir = cromwell_install_dir

        if not AbsPath(womtool_install_dir).is_valid:
            raise ValueError(
                'womtool_install_dir is not a valid absolute '
                'path. {path}'.format(path=womtool_install_dir)
            )
        self._womtool_install_dir = womtool_install_dir

    def validate(
        self,
        wdl,
        inputs=None,
        imports=None,
        cwd=None,
        java_heap_womtool=DEFAULT_JAVA_HEAP_WOMTOOL,
    ):
        """Validate WDL/inputs/imports using Womtool.

        Returns:
            valid:
                Validated or not.
        """
        self.install_womtool()

        wdl_file = AutoURI(wdl)
        if not wdl_file.exists:
            raise FileNotFoundError(
                'WDL file does not exist. wdl={wdl}'.format(wdl=wdl)
            )
        if inputs:
            if not AutoURI(inputs).exists:
                raise FileNotFoundError(
                    'Inputs JSON defined but does not exist. i={i}'.format(i=inputs)
                )

        with tempfile.TemporaryDirectory() as tmp_d:
            if imports:
                if not AutoURI(imports).exists:
                    raise FileNotFoundError(
                        'Imports file defined but does not exist. i={i}'.format(
                            i=imports
                        )
                    )
                wdl_ = os.path.join(tmp_d, wdl_file.basename)
                wdl_file.cp(wdl_)
                shutil.unpack_archive(imports, tmp_d)
            else:
                wdl_ = wdl_file.localize_on(tmp_d)

            cmd = [
                'java',
                '-Xmx{heap}'.format(heap=java_heap_womtool),
                '-jar',
                '-DLOG_LEVEL={lvl}'.format(lvl='INFO'),
                self._womtool,
                'validate',
                wdl_,
            ]
            if inputs:
                cmd += ['-i', AutoURI(inputs).localize_on(tmp_d)]

            logger.info('Validating WDL/inputs/imports with Womtool...')

            stderr = ''

            def on_stderr(s):
                nonlocal stderr
                stderr += s

            th = NBSubprocThread(cmd, cwd=tmp_d, on_stderr=on_stderr, quiet=True)
            th.start()
            th.join()

            if th.returncode:
                logger.error(
                    'RC={rc}\nSTDERR={stderr}\nWomtool validation failed.'.format(
                        rc=th.returncode, stderr=stderr
                    )
                )
                return False
            else:
                logger.info('Womtool validation passed.')
                return True

    def run(
        self,
        wdl,
        inputs=None,
        options=None,
        imports=None,
        labels=None,
        metadata=None,
        backend_conf=None,
        backend=None,
        fileobj_stdout=None,
        fileobj_troubleshoot=None,
        java_heap_cromwell_run=DEFAULT_JAVA_HEAP_CROMWELL_RUN,
        java_heap_womtool=DEFAULT_JAVA_HEAP_WOMTOOL,
        work_dir=None,
        cwd=None,
        on_status_change=None,
        dry_run=False,
    ):
        """Run Cromwell run mode (java -jar cromwell.jar run).
        This is a non-blocking function which returns a NBSubprocThread object.
        So this function itself doesn't return anything.
        However, its NBSubprocThread object has a return value which is validated
        after the thread is done (joined).
        Such return value is metadata dict, which is a final output of Cromwell run.
        You can simply get it by thread.returnvalue after thread is done.

        Args:
            inputs:.
                input JSON file (-i).
            options:
                workflow options JSON file (-o).
            imports:
                imports.zip file (-p).
            labels:
                labels file (-l).
            metadata:
                output metadata JSON file (-m).
            backend_conf:
                backend.conf file (-Dconfig.file=).
                Default backend defined in this file will be used.
                If no default backend is defined then "Local" (Cromwell's default)
                backend will be used.
            fileobj_stdout:
                File-like object to print Cromwell's STDOUT.
            fileobj_troubleshoot:
                File-like object to write auto-troubleshooting result after
                workflow is done.
            java_heap_cromwell_run:
                Java heap (java -Xmx) for Cromwell run mode.
            java_heap_womtool=DEFAULT_JAVA_HEAP_WOMTOOL,
                Java heap (java -Xmx) for Womtool validation.
            work_dir:
                Temp directory to store Cromwell's output metadata JSON file.
                Cromwell will run on "cwd". Not on this work_dir.
            cwd:
                Current working directory to run Cromwell on.
                This will be finally passed to subprocess.Popen(cwd=).
            on_status_change:
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
            dry_run:
                Dry run.
        Returns:
            th:
                Thread for Cromwell's run mode. None if dry_run.
                Notes:
                    Thread's return value (th.returnvalue)
                    is Cromwell's output metadata dict.
                    It is None if Cromwell subprocess itself didn't run,
                    If it ran but workflow failed then metadata dict is not None.
        """
        self.install_cromwell()

        if work_dir is None:
            work_dir = tempfile.mkdtemp(prefix='cromwell-run')

        # LOG_LEVEL must be >=INFO to catch workflow ID from STDOUT
        cmd = [
            'java',
            '-Xmx{}'.format(java_heap_cromwell_run),
            '-XX:ParallelGCThreads=1',
            '-jar',
            '-DLOG_LEVEL={lvl}'.format(lvl='INFO'),
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
        if metadata is None:
            metadata = os.path.join(
                work_dir, CromwellMetadata.DEFAULT_METADATA_BASENAME
            )
        cmd += ['-m', metadata]

        logger.debug('cmd: {cmd}'.format(cmd=' '.join(cmd)))
        if dry_run:
            return

        wm = CromwellWorkflowMonitor(on_status_change=on_status_change, is_server=False)

        def on_stdout(stdout):
            nonlocal wm
            nonlocal fileobj_stdout

            if is_fileobj_open(fileobj_stdout):
                fileobj_stdout.write(stdout)
                fileobj_stdout.flush()
            wm.update(stdout)

        def on_finish():
            nonlocal metadata
            nonlocal fileobj_troubleshoot

            if os.path.exists(metadata):
                json_contents = AutoURI(metadata).read()
                if json_contents:
                    metadata_dict = json.loads(json_contents)
                    cm = CromwellMetadata(metadata_dict)
                    cm.write_on_workflow_root()

                    if cm.workflow_status != 'Succeeded' and fileobj_troubleshoot:
                        # auto-troubleshoot on terminate if workflow is not successful
                        logger.info('Workflow failed. Auto-troubleshooting...')
                        cm.troubleshoot(fileobj=fileobj_troubleshoot)

                    # to make it a return value of the thread after it is done (joined)
                    return metadata_dict

        th = NBSubprocThread(
            cmd,
            cwd=cwd,
            on_stdout=on_stdout,
            on_finish=on_finish,
            subprocess_name='Cromwell',
        )
        th.start()

        return th

    def server(
        self,
        server_port=DEFAULT_SERVER_PORT,
        server_hostname=None,
        server_heartbeat=None,
        backend_conf=None,
        fileobj_stdout=None,
        embed_subworkflow=False,
        java_heap_cromwell_server=DEFAULT_JAVA_HEAP_CROMWELL_SERVER,
        auto_write_metadata=True,
        on_server_start=None,
        on_status_change=None,
        cwd=None,
        dry_run=False,
    ):
        """Run Cromwell server mode (java -jar cromwell.jar server).
        This is a non-blocking function that returns a Thread object of Cromwell server.
        Howerver, this Thread object has a property status that indicates whether
        the server is started and ready to take submissions.
        Such condition is thread.status == True.

        Args:
            server_port:
                Server port.
            server_hostname:
                Server hostname. If defined then the heartbeat file will be written
                with this hostname instead of socket.gethostname().
            server_heartbeat:
                ServerHeartbeat object to write hostname/port pair into a heartbeat file.
                Then it will be later used by CaperClient to find hostname/port of
                this server.
            backend_conf:
                backend.conf file for Cromwell's Java parameter
                "-Dconfig.file=".
                Default backend defined in this file will be used.
                If no default backend is defined then "Local" (Cromwell's default)
                backend will be used.
            fileobj_stdout:
                File object to write Cromwell's STDOUT on.
            embed_subworkflow:
                This class basically stores/updates metadata.JSON file on
                each workflow's root directory whenever there is status change
                of workflow (or its tasks).
                This flag ensures that any subworkflow's metadata JSON will be
                embedded in main (this) workflow's metadata JSON.
                This is to mimic behavior of Cromwell run mode's -m parameter.
            java_heap_cromwell_server:
                Java heap (java -Xmx) for Cromwell server mode.
            auto_write_metadata:
                Automatic retrieval/writing of metadata.json upon workflow/task's status change.
            on_server_start:
                On server start.
            on_status_change:
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
            cwd:
                This will be finally passed to subprocess.Popen(cwd=).
            dry_run:
                Dry run.
        Returns:
            th:
                Thread for Cromwell's server mode.
                Returns None if dry_run.
        """
        self.install_cromwell()

        # check if port is open
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((Cromwell.LOCALHOST, server_port))
        if not result:
            raise PortAlreadyInUseError(
                'Server port {p} is already taken. '
                'Try with a different port'.format(p=server_port)
            )

        # LOG_LEVEL must be >=INFO to catch workflow ID from STDOUT
        cmd = [
            'java',
            '-Xmx{}'.format(java_heap_cromwell_server),
            '-XX:ParallelGCThreads=1',
            '-jar',
            '-DLOG_LEVEL={lvl}'.format(lvl='INFO'),
            '-DLOG_MODE=standard',
            '-Dwebservice.port={port}'.format(port=server_port),
        ]
        if backend_conf:
            cmd += ['-Dconfig.file={}'.format(backend_conf)]
            logger.debug(
                'backend_conf contents:\n{s}'.format(s=AutoURI(backend_conf).read())
            )

        cmd += [self._cromwell, 'server']

        logger.debug('cmd: {cmd}'.format(cmd=' '.join(cmd)))
        if dry_run:
            return

        wm = CromwellWorkflowMonitor(
            server_port=server_port,
            is_server=True,
            embed_subworkflow=embed_subworkflow,
            auto_write_metadata=auto_write_metadata,
            on_server_start=on_server_start,
            on_status_change=on_status_change,
        )

        def on_stdout(stdout):
            """Returns 'server_started' when server is ready to take submissions.
            Return value of this callback function is to update .status
            of an NBSubprocThread object.
            """
            nonlocal fileobj_stdout
            nonlocal wm
            nonlocal server_heartbeat

            if is_fileobj_open(fileobj_stdout):
                fileobj_stdout.write(stdout)
                fileobj_stdout.flush()

            wm.update(stdout)
            if wm.is_server_started():
                if server_heartbeat and not server_heartbeat.is_alive():
                    server_heartbeat.start(port=server_port, hostname=server_hostname)
                return 'server_started'

        def on_finish():
            nonlocal server_heartbeat

            if server_heartbeat:
                server_heartbeat.stop()

        th = NBSubprocThread(
            cmd,
            cwd=cwd,
            on_stdout=on_stdout,
            on_finish=on_finish,
            subprocess_name='Cromwell',
        )
        th.start()

        return th

    def install_cromwell(self):
        self._cromwell = install_file(
            self._cromwell, self._cromwell_install_dir, 'Cromwell JAR'
        )
        return self._cromwell

    def install_womtool(self):
        self._womtool = install_file(
            self._womtool, self._womtool_install_dir, 'Womtool JAR'
        )
        return self._womtool
