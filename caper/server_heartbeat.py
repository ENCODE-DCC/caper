import logging
import time
from autouri import AutoURI
from threading import Thread


logger = logging.getLogger(__name__)


class ServerHeartbeat:
    DEFAULT_HEARTBEAT_TIMEOUT_MS = 120000
    DEFAULT_INTERVAL_UPDATE_HEARTBEAT_SEC = 60.0

    def __init__(
            self,
            heartbeat_file,
            heartbeat_timeout=DEFAULT_HEARTBEAT_TIMEOUT_MS,
            interval_update_heartbeat=DEFAULT_INTERVAL_UPDATE_HEARTBEAT_SEC):
        """Server heartbeat to share store server's hostname/port with clients.

        Args:
            hearrbeat_file:
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

        self._stop_heartbeat_thread = True
        self._th_heartbeat = None

    def start_write_thread(self, port, hostname=None):
        """Starts a thread that writes hostname/port of a server
        on a heartbeat file.
        
        Args:
            port:
                This port will be written to a heartbeat file.
            hostname:
                Optional hostname to be written to heartbeat file.
                socket.gethostname() will be used if not defined.
        """
        self._stop_heartbeat_thread = False

        logger.info('Server heartbeat thread started.')
        self._th_heartbeat = Thread(
            target=ServerHeartbeat.__write_to_file(port, hostname))
        self._th_heartbeat.start()
        return self._th_heartbeat

    def end_write_thread(self):
        self._stop_heartbeat_thread = True
        if self._th_heartbeat is not None:
            self._th_heartbeat.join()
            self._th_heartbeat = None
            logger.info('Server heartbeat thread ended.')

    def __write_to_file(self, port, hostname=None):
        if not hostname:
            hostname = socket.gethostname()
        while True:
            try:
                logger.info(
                    'Writing heartbeat: {hostname}, {port}'.format(
                        hostname=hostname,
                        port=port))
                AutoURI(self._heartbeat_file).write(
                    '{hostname}:{port}'.format(
                        hostname=hostname,
                        port=self.port))
            except:
                logger.error(
                    'Failed to write to a heartbeat_file. {f}'.format(
                        f=self._heartbeat_file))
            cnt = 0
            while cnt < self._interval_update_heartbeat:
                cnt += 1
                if self._stop_heartbeat_thread:
                    break
                time.sleep(1)
            if self._stop_heartbeat_thread:
                break

    def read_from_file(self):
        """Read from heartbeat file.
        If a heartbeat file is not fresh (mtime difference < timeout)
        then None is returned.

        Returns:
            Tuple of (hostname, port)
        """
        try:
            u = AutoURI(self._heartbeat_file)
            if (time.time() - u.mtime) * 1000.0 < self._heartbeat_timeout:
                hostname, port = u.read().strip('\n').split(':')
                return hostname, port
        except:
            logger.warning(
                'Failed to read from a heartbeat file. {f}'.format(
                    f=self._heartbeat_file))

        return None
