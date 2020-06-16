import socket
import time

import pytest

from caper.server_heartbeat import ServerHeartbeat, ServerHeartbeatTimeoutError


def test_server_heartbeat(tmp_path):
    """All methods will be tested here.
    This willl test 3 things:
        - can read from file
        - can get hostname of this machine
        - can ignore old file (> heartbeat_timeout of 5 sec)
    """
    hb_file = tmp_path / 'hb_file'

    hb = ServerHeartbeat(heartbeat_file=str(hb_file), heartbeat_timeout=5000)

    # before starting write thread
    # it should return None
    assert hb.read() is None

    try:
        hb.start(port=9999)

        time.sleep(1)
        assert hb.read() == (socket.gethostname(), 9999)
    finally:
        hb.stop()

    # after timeout
    time.sleep(5)
    assert hb.read() is None

    with pytest.raises(ServerHeartbeatTimeoutError):
        hb.read(raise_timeout=True)
