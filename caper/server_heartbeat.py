import logging
import socket
import time
from threading import Thread

from autouri import AutoURI

logger = logging.getLogger(__name__)


class ServerHeartbeatTimeoutError(Exception):
    pass


class ServerHeartbeat:
    DEFAULT_SERVER_HEARTBEAT_FILE = '~/.caper/default_server_heartbeat'
    DEFAULT_HEARTBEAT_TIMEOUT_MS = 120000
    DEFAULT_INTERVAL_UPDATE_HEARTBEAT_SEC = 60.0

    def __init__(
        self,
        heartbeat_file=DEFAULT_SERVER_HEARTBEAT_FILE,
        heartbeat_timeout=DEFAULT_HEARTBEAT_TIMEOUT_MS,
        interval_update_heartbeat=DEFAULT_INTERVAL_UPDATE_HEARTBEAT_SEC,
    ):
        """Server heartbeat to share store server's hostname/port with clients.

        Args:
            heartbeat_file:
                Server writes hostname/port on this file.
                Client reads hostname/port from this file.
            heartbeat_timeout:
                Expiration period for a heartbeat file (in milliseconds).
                Client will use a heartbeat file only if it is fresh (within timeout).
            interval_update_heartbeat:
                Period for updtaing a heartbeat file (in seconds).
        """
        self._heartbeat_file = heartbeat_file
        self._heartbeat_timeout = heartbeat_timeout
        self._interval_update_heartbeat = interval_update_heartbeat

        self._stop_it = False
        self._thread = None

    def start(self, port, hostname=None):
        """Starts a thread that writes hostname/port of a server
        on a heartbeat file.

        Args:
            port:
                This port will be written to a heartbeat file.
            hostname:
                Optional hostname to be written to heartbeat file.
                socket.gethostname() will be used if not defined.
        """
        self._thread = Thread(target=self._write_to_file, args=(port, hostname))
        self._thread.start()
        return self._thread

    def is_alive(self):
        return self._thread.is_alive() if self._thread else False

    def stop(self):
        self._stop_it = True

        if self._thread:
            self._thread.join()

    def read(self, raise_timeout=False):
        """Read from heartbeat file.
        If a heartbeat file is not fresh (mtime difference < timeout)
        then None is returned.

        Returns:
            Tuple of (hostname, port)
        """
        try:
            u = AutoURI(self._heartbeat_file)
            if (time.time() - u.mtime) * 1000.0 > self._heartbeat_timeout:
                raise ServerHeartbeatTimeoutError
            else:
                hostname, port = u.read().strip('\n').split(':')
                logger.info(
                    'Reading hostname/port from a heartbeat file. {h}:{p}'.format(
                        h=hostname, p=port
                    )
                )
                return hostname, int(port)

        except ServerHeartbeatTimeoutError:
            logger.error(
                'Found a heartbeat file but it has been expired (> timeout)'
                '. {f}'.format(f=self._heartbeat_file)
            )
            if raise_timeout:
                raise

        except Exception:
            logger.error(
                'Failed to read from a heartbeat file. {f}'.format(
                    f=self._heartbeat_file
                )
            )

    def _write_to_file(self, port, hostname=None):
        if not hostname:
            hostname = socket.gethostname()

        logger.info('Server heartbeat thread started.')

        while True:
            try:
                logger.debug(
                    'Writing heartbeat: {hostname}, {port}'.format(
                        hostname=hostname, port=port
                    )
                )
                AutoURI(self._heartbeat_file).write(
                    '{hostname}:{port}'.format(hostname=hostname, port=port)
                )
            except Exception:
                logger.error(
                    'Failed to write to a heartbeat_file. {f}'.format(
                        f=self._heartbeat_file
                    )
                )
            cnt = 0
            while cnt < self._interval_update_heartbeat:
                cnt += 1
                if self._stop_it:
                    break
                time.sleep(1)
            if self._stop_it:
                break

        logger.info('Server heartbeat thread ended.')
