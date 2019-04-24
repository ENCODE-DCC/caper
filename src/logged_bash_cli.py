#!/usr/bin/env python
"""Bash CLI with logging.
"""

import os
import sys
import subprocess
import logging

logging.basicConfig(
    format='[%(asctime)s %(levelname)s] %(message)s',
    stream=sys.stdout)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def bash_run_cmd(cmd):
    p = subprocess.Popen(['/bin/bash','-o','pipefail'], # to catch error in pipe
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        preexec_fn=os.setsid) # to make a new process with a new PGID
    pid = p.pid
    pgid = os.getpgid(pid)
    logger.info('run_cmd: PID={}, PGID={}, CMD={}'.format(pid, pgid, cmd))
    stdout, stderr = p.communicate(cmd)
    rc = p.returncode
    err_str = 'PID={}, PGID={}, RC={}\nSTDERR={}\nSTDOUT={}'.format(pid, pgid, rc,
        stderr.strip(), stdout.strip())
    if rc:
        # kill all child processes
        try:
            os.killpg(pgid, signal.SIGKILL)
        except:
            pass
        finally:
            raise OSError(err_str)
    else:
        logger.info(err_str)

    return stdout.strip('\n')
