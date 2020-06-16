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
                This callback function should take one argument:
                    - stdout (string):
                        New incoming STDOUT line string including backslash n.
            on_terminate:
                Callback on terminating a thread.
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

    @property
    def stdout(self):
        return self._stdout

    @property
    def rc(self):
        return self._rc

    def stop(self):
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
                        on_stdout(stdout)
                except Empty:
                    pass
                except KeyboardInterrupt:
                    raise
                if on_poll:
                    on_poll(cnt)
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
        finally:
            p.terminate()

        if on_terminate:
            on_terminate()
