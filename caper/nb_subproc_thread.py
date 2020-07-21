import logging
import time
from queue import Empty, Queue
from subprocess import PIPE, STDOUT, CalledProcessError, Popen
from threading import Thread

logger = logging.getLogger(__name__)


class NBSubprocThread(Thread):
    DEFAULT_POLL_INTERVAL_SEC = 0.01

    def __init__(
        self,
        args,
        cwd=None,
        stdin=None,
        on_poll=None,
        on_stdout=None,
        on_finish=None,
        poll_interval=DEFAULT_POLL_INTERVAL_SEC,
        quiet=False,
    ):
        """Non-blocking STDOUT streaming for subprocess.Popen.
        Note that STDERR is always redirected to STDOUT.

        This class makes a daemonized thread for nonblocking
        streaming of STDOUT/STDERR.

        Note that return value of callback functions are updated
        for the following properties:
            - status:
                updated with return value of on_poll, on_stdout
            - returnvalue:
                updated with return value of on_finish

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
                Return value is used for updating property status.
            on_stdout:
                Callback on every non-empty STDOUT line
                (ending with backslash n).
                You can use this to print out STDOUT as well.
                Return value is used for updating property status.
                This callback function should take one argument:
                    - stdout (string):
                        New incoming STDOUT line string including backslash n.
            on_finish:
                Callback on terminating/completing a thread.
                Return value is used for updating property returnvalue.
            poll_interval (float):
                Polling interval in seconds.
            quiet:
                No logging.
        """
        super().__init__(
            target=self._popen, args=(args, cwd, stdin, on_poll, on_stdout, on_finish)
        )
        self._poll_interval = poll_interval
        self._quiet = quiet

        self._stdout_list = []
        self._returncode = None
        self._stop_it = False
        self._status = None
        self._returnvalule = None

    @property
    def stdout(self):
        return ''.join(self._stdout_list)

    @property
    def returncode(self):
        """Returns subprocess.Popen.returncode.
        None if not completed or any general Exception occurs.
        """
        return self._returncode

    @property
    def status(self):
        """Updated with return value of on_poll() for every polling.
        Also updated with return value of on_stdout() for every new stdout.
        """
        return self._status

    @property
    def returnvalue(self):
        """Updated with return value of on_finish()
        which is called when a thread is terminated.
        None if thread is still running so that on_finish() has not been called yet.
        This works like an actual return value of the function ran inside a thread.
        """
        return self._returnvalule

    def stop(self):
        """Subprocess will be teminated after next polling.
        """
        self._stop_it = True

    def _popen(
        self, args, cwd=None, stdin=None, on_poll=None, on_stdout=None, on_finish=None
    ):
        """Wrapper for subprocess.Popen.
        stdout/stderr is fixed at subprocess.PIPE/subprocess.STDOUT.
        i.e. STDERR is always redirected to STDOUT.
        This thread also has a child thread for non-blocking-streaming of
        STDOUT.

        Queue implementation for non-blocking STDOUT streaming:
        https://stackoverflow.com/a/4896288
        """

        def enqueue_stdout(stdout, q):
            for line in iter(stdout.readline, b''):
                q.put(line)
            stdout.close()

        self._stop_it = False

        try:
            p = Popen(args, stdout=PIPE, stderr=STDOUT, cwd=cwd, stdin=stdin)
            q = Queue()
            thread_stdout = Thread(target=enqueue_stdout, args=(p.stdout, q))
            thread_stdout.daemon = True
            thread_stdout.start()

            while True:
                try:
                    stdout = q.get_nowait().decode()
                    if stdout:
                        self._stdout_list.append(stdout)
                        if on_stdout:
                            self._status = on_stdout(stdout)
                except Empty:
                    pass
                if on_poll:
                    self._status = on_poll()
                if p.poll() is not None:
                    self._returncode = p.poll()
                    break
                if self._stop_it:
                    break
                time.sleep(self._poll_interval)

            if not self._quiet:
                if self._stop_it:
                    logger.info(
                        'Stopped subprocess. prev_status={s}'.format(s=self._status)
                    )

        except CalledProcessError as e:
            self._returncode = e.returncode
            if not self._quiet:
                logger.error(e)
        finally:
            p.terminate()

        if on_finish:
            self._returnvalule = on_finish()

        if not self._quiet:
            if self._returncode:
                logger.error(
                    'Subprocess failed. returncode={rc}'.format(rc=self._returncode)
                )
            else:
                logger.info('Subprocess finished successfully.')
