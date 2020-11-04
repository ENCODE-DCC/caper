import logging
import time
from signal import SIGTERM
from subprocess import PIPE, Popen
from threading import Thread

logger = logging.getLogger(__name__)


def is_fileobj_open(fileobj):
    return fileobj and not getattr(fileobj, 'closed', False)


class NBSubprocThread(Thread):
    DEFAULT_POLL_INTERVAL_SEC = 0.01
    DEFAULT_SUBPROCESS_NAME = 'Subprocess'
    DEFAULT_STOP_SIGNAL = SIGTERM

    def __init__(
        self,
        args,
        cwd=None,
        stdin=None,
        on_poll=None,
        on_stdout=None,
        on_stderr=None,
        on_finish=None,
        poll_interval=DEFAULT_POLL_INTERVAL_SEC,
        quiet=False,
        subprocess_name=DEFAULT_SUBPROCESS_NAME,
    ):
        """Non-blocking STDOUT/STDERR streaming for subprocess.Popen().

        This class makes two daemonized threads for nonblocking
        streaming of STDOUT/STDERR.

        Note that return value of callback functions are updated
        for the following properties:
            - status:
                Updated with return value of on_poll, on_stdout, on_stderr.
                If return value is None then no update.
            - returnvalue:
                Updated with return value of on_finish.
                If return value is None then no update.

        This is useful to check status of the thread and
        get the final return value of the function that this class
        actually runs.

        Args:
            args:
                List of command line arguments.
            cwd:
                subprocess.Popen's cwd.
            stdin:
                subprocess.Popen's stdin.
                Note that subprocess.Popen's stdout/stderr is fixed
                at subprocess.PIPE/subprocess.STDOUT.
            on_poll:
                Callback on every polling.
                If return value is not None then it is used for updating property `status`.
            on_stdout:
                Callback on every non-empty STDOUT line.
                If return value is not None then it is used for updating property `status`.
                This callback function should take one argument:
                    - stdout (str):
                        New incoming STDOUT line string with trailing newline (backslash n).
            on_stderr:
                Callback on every non-empty STDERR line.
                If return value is not None then it is used for updating property `status`.
                This callback function should take one argument:
                    - stderr (str):
                        New incoming STDERR line string with trailing newline (backslash n).
            on_finish:
                Callback on terminating/completing a thread.
                If return value is not None then it is used for updating property `returnvalue`.
            poll_interval (float):
                Polling interval in seconds.
            quiet:
                No logging.
            subprocess_name:
                Subprocess name for logging.
        """
        super().__init__(
            target=self._popen,
            args=(args, cwd, stdin, on_poll, on_stdout, on_stderr, on_finish),
        )
        self._poll_interval = poll_interval
        self._quiet = quiet
        self._subprocess_name = subprocess_name

        self._stdout_list = []
        self._stderr_list = []
        self._returncode = None
        self._stop_it = False
        self._stop_signal = None
        self._status = None
        self._returnvalue = None

    @property
    def stdout(self):
        return ''.join(self._stdout_list)

    @property
    def stderr(self):
        return ''.join(self._stderr_list)

    @property
    def returncode(self):
        """Returns subprocess.Popen.returncode.
        None if not completed or any general Exception occurs.
        """
        return self._returncode

    @property
    def status(self):
        """Updated with return value of on_poll() for every polling.
        Also updated with return value of on_stdout() or on_stderr()
        if their return values are not None.
        """
        return self._status

    @property
    def returnvalue(self):
        """Updated with return value of on_finish()
        which is called when a thread is terminated.
        None if thread is still running so that on_finish() has not been called yet.
        This works like an actual return value of the function ran inside a thread.
        """
        return self._returnvalue

    def stop(self, stop_signal=DEFAULT_STOP_SIGNAL, wait=False):
        """Subprocess will be teminated after next polling.

        Args:
            wait:
                Wait for a valid returncode (which is not None).
        """
        self._stop_it = True
        self._stop_signal = stop_signal
        if wait:
            if self._returncode is None:
                logger.info(
                    '{name} stopped but waiting for graceful shutdown...'.format(
                        name=self._subprocess_name
                    )
                )
            while True:
                if self._returncode is not None:
                    return
                time.sleep(self._poll_interval)

    def _popen(
        self,
        args,
        cwd=None,
        stdin=None,
        on_poll=None,
        on_stdout=None,
        on_stderr=None,
        on_finish=None,
    ):
        """Wrapper for subprocess.Popen().
        """

        def read_stdout(stdout_bytes):
            text = stdout_bytes.decode()
            if text:
                self._stdout_list.append(text)
                if on_stdout:
                    ret_on_stdout = on_stdout(text)
                    if ret_on_stdout is not None:
                        self._status = ret_on_stdout

        def read_stderr(stderr_bytes):
            text = stderr_bytes.decode()
            if text:
                self._stderr_list.append(text)
                if on_stderr:
                    ret_on_stderr = on_stderr(text)
                    if ret_on_stderr is not None:
                        self._status = ret_on_stderr

        def read_from_stdout_obj(stdout):
            if is_fileobj_open(stdout):
                for line in iter(stdout.readline, b''):
                    read_stdout(line)

        def read_from_stderr_obj(stderr):
            if is_fileobj_open(stderr):
                for line in iter(stderr.readline, b''):
                    read_stderr(line)

        self._stop_it = False

        try:
            p = Popen(args, stdout=PIPE, stderr=PIPE, cwd=cwd, stdin=stdin)
            thread_stdout = Thread(
                target=read_from_stdout_obj, args=(p.stdout,), daemon=True
            )
            thread_stderr = Thread(
                target=read_from_stderr_obj, args=(p.stderr,), daemon=True
            )
            thread_stdout.start()
            thread_stderr.start()

            while True:
                if on_poll:
                    ret_on_poll = on_poll()
                    if ret_on_poll is not None:
                        self._status = ret_on_poll
                if p.poll() is not None:
                    self._returncode = p.poll()
                    break
                if self._stop_it and self._stop_signal:
                    p.send_signal(self._stop_signal)
                    break
                time.sleep(self._poll_interval)

        except Exception as e:
            if not self._quiet:
                logger.error(e, exc_info=True)

        finally:
            stdout_bytes, stderr_bytes = p.communicate()
            read_stdout(stdout_bytes)
            read_stderr(stderr_bytes)
            self._returncode = p.returncode

        if on_finish:
            ret_on_finish = on_finish()
            if ret_on_finish is not None:
                self._returnvalue = ret_on_finish

        if not self._quiet:
            if self._returncode:
                logger.error(
                    '{name} failed. returncode={rc}'.format(
                        name=self._subprocess_name, rc=self._returncode
                    )
                )
            else:
                logger.info(
                    '{name} finished successfully.'.format(name=self._subprocess_name)
                )
