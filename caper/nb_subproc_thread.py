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
        on_terminate=None,
        poll_interval=DEFAULT_POLL_INTERVAL_SEC,
    ):
        """Non-blocking STDOUT streaming for subprocess.Popen.
        Note that STDERR is always redirected to STDOUT.

        This class makes two threads (main and sub).
        Main thread for subprocess.Popen, sub thread for nb-streaming STDOUT.

        Note that return value of callback functions are used for status or return
        value (property status, ret) of this thread itself.

        Return value of on_poll and on_std_out are used to update property status.
        Return value of on_terminate is used to update property ret.

        These are useful to check status of the thread and get the final return
        value of the function that this thread runs.

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
                This callback function should take one argument:
                    - iter (int):
                        Number of iterations for polling.
            on_stdout:
                Callback on every non-empty STDOUT line (ending with backslash n).
                You can use this to print out STDOUT as well.
                Return value will replace
                This callback function should take one argument:
                    - stdout (string):
                        New incoming STDOUT line string including backslash n.
            on_terminate:
                Callback on terminating a thread.
                Note that return value of this function will be the final return
                value (property ret) of this thread after it is done (joined).
            poll_interval (float):
                Polling interval in seconds.
        """
        super().__init__(
            target=self._popen,
            args=(args, cwd, stdin, on_poll, on_stdout, on_terminate),
        )
        self._poll_interval = poll_interval
        self._stdout = ''
        self._rc = None
        self._stop_it = False
        self._status = None
        self._ret = None

    @property
    def stdout(self):
        return self._stdout

    @property
    def rc(self):
        """Returns:
            -1 if CalledProcessError occurs
            -2 if any other general exception (Exception) occurs
            Otherwise returncode code of shell command line args will be returned.
        """
        return self._rc

    @property
    def status(self):
        """Updated with return value of on_poll() for every polling.
        Also updated with returnv alue of on_stdout() for every stdout (full line(s)).
        """
        return self._status

    @property
    def ret(self):
        """Return value updated with return value of on_terminate()
        None if thread is not done.
        """
        return self._ret

    def stop(self):
        """Subprocess will be teminated after next polling.
        """
        self._stop_it = True

    def _popen(
        self,
        args,
        cwd=None,
        stdin=None,
        on_poll=None,
        on_stdout=None,
        on_terminate=None,
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

        try:
            p = Popen(args, stdout=PIPE, stderr=STDOUT, cwd=cwd, stdin=stdin)
            q = Queue()
            th_q = Thread(target=enqueue_stdout, args=(p.stdout, q))
            th_q.daemon = True
            th_q.start()

            cnt = 0
            while True:
                if self._stop_it:
                    break
                try:
                    b = q.get_nowait()
                    stdout = b.decode()
                    self._stdout += stdout
                    if on_stdout:
                        self._status = on_stdout(stdout)
                except Empty:
                    pass
                except KeyboardInterrupt:
                    raise
                if on_poll:
                    self._status = on_poll(cnt)
                if p.poll() is not None:
                    break
                time.sleep(self._poll_interval)
                cnt += 1

            if self._stop_it:
                self._rc = -1
            else:
                self._rc = p.poll()

        except CalledProcessError as e:
            self._rc = e.returncode
        except Exception as e:
            self._rc = -2
            logging.error(e)
        finally:
            p.terminate()

        if on_terminate:
            self._ret = on_terminate()
