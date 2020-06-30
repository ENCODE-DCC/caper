import time

from caper.nb_subproc_thread import NBSubprocThread

SH_CONTENTS = """#!/bin/bash

NUM=$1
if [ -z "$NUM" ]
then
  NUM=10
fi

echo $NUM

# NUM kitties (1 kitty per sec)
for i in $(seq 1 $NUM)
do
  echo "hello kitty $i."
  sleep 1
done

exit 10
"""


def on_stdout(stdout):
    print('captured stdout:', stdout)
    assert stdout.endswith('\n')


def on_poll(cnt):
    print('polling count:', cnt)


def test_nb_subproc_thread(tmp_path):
    sh = tmp_path / 'test.sh'
    sh.write_text(SH_CONTENTS)

    th = NBSubprocThread(
        args=['bash', str(sh)], on_poll=on_poll, on_stdout=on_stdout, poll_interval=0.1
    )
    assert not th.is_alive()
    th.start()
    assert th.is_alive()
    # rc is None while running
    assert th.rc is None
    th.join()
    assert th.rc == 10


def test_nb_subproc_thread_stopped(tmp_path):
    sh = tmp_path / 'test.sh'
    sh.write_text(SH_CONTENTS)

    th = NBSubprocThread(args=['bash', str(sh)], on_stdout=on_stdout)
    th.start()
    time.sleep(3)
    th.stop()
    assert th.is_alive()
    th.join()
    assert not th.is_alive()
    # rc is None if terminated
    assert th.rc is None
    # subprocess is terminated until it reaches kitty 4 (4 sec > 3 sec).
    assert 'hello kitty 4' not in th.stdout


def test_nb_subproc_thread_nonzero_rc(tmp_path):
    th = NBSubprocThread(args=['cat', 'asdfasf'], on_stdout=on_stdout)
    th.start()
    th.join()
    print(th.rc, th.stdout)
    assert th.rc == 1
    # check if stderr is redirected to stdout and it's captured
    assert 'asdfasf' in th.stdout
