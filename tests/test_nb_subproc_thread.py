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


def on_poll():
    print('polling')


def on_finish():
    return 'done'


def test_nb_subproc_thread(tmp_path):
    sh = tmp_path / 'test.sh'
    sh.write_text(SH_CONTENTS)

    th = NBSubprocThread(
        args=['bash', str(sh)],
        on_poll=on_poll,
        on_stdout=on_stdout,
        on_finish=on_finish,
        poll_interval=0.1,
    )
    assert th.returnvalue is None
    assert not th.is_alive()
    th.start()
    assert th.is_alive()
    # rc is None while running
    assert th.returncode is None
    th.join()
    assert th.returncode == 10
    assert th.returnvalue == 'done'


def test_nb_subproc_thread_stopped(tmp_path):
    sh = tmp_path / 'test.sh'
    sh.write_text(SH_CONTENTS)

    th = NBSubprocThread(args=['bash', str(sh)], on_stdout=on_stdout)
    th.start()
    time.sleep(2)
    assert th.is_alive()
    th.stop()
    th.join()
    assert not th.is_alive()
    # rc is None if terminated
    assert th.returncode is None
    # subprocess is terminated until it reaches kitty 4 (4 sec > 2 sec).
    assert 'hello kitty 4' not in th.stdout


def test_nb_subproc_thread_nonzero_rc(tmp_path):
    th = NBSubprocThread(args=['cat', 'asdfasf'], on_stdout=on_stdout)
    th.start()
    th.join()
    print(th.returncode, th.stdout)
    assert th.returncode == 1
    # check if stderr is redirected to stdout and it's captured
    assert 'asdfasf' in th.stdout
