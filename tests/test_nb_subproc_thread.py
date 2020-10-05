import time

from caper.nb_subproc_thread import NBSubprocThread

SH_CONTENTS = """#!/bin/bash

echoerr() { echo "$@" 1>&2; }

NUM=$1
if [ -z "$NUM" ]
then
  NUM=10
fi

echo $NUM

# NUM kitties (1 kitty per sec)
for i in $(seq 1 $NUM)
do
  echo "hello kitty $i-1. (STDOUT)"
  sleep 0.25
  echoerr "hello kitty $i-1. (STDERR)"
  sleep 0.25
  echoerr "hello kitty $i-2. (STDERR)"
  sleep 0.25
  echo "hello kitty $i-2. (STDOUT)"
  sleep 0.25
done

exit 10
"""


def on_stdout(stdout):
    print('captured stdout:', stdout)
    assert stdout.endswith('\n')


def on_stderr(stderr):
    print('captured stderr:', stderr)
    assert stderr.endswith('\n')


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
        on_stderr=on_stderr,
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
    assert 'hello kitty 4' not in th.stderr


def test_nb_subproc_thread_nonzero_rc(tmp_path):
    for i in range(100):
        test_str = 'asdfasf-{i}-zxcv'.format(i=i)

        th = NBSubprocThread(
            args=['cat', test_str], on_stdout=on_stdout, on_stderr=on_stderr
        )
        th.start()
        th.join()
        assert th.returncode == 1
        assert 'cat: {s}: No such file or directory\n'.format(s=test_str) in th.stderr
        assert th.stdout == ''

        th = NBSubprocThread(args=['ls', test_str], on_stderr=on_stderr)
        th.start()
        th.join()
        assert th.returncode == 2
        assert (
            "ls: cannot access '{s}': No such file or directory\n".format(s=test_str)
            in th.stderr
        )
        assert th.stdout == ''

        th = NBSubprocThread(args=['java', test_str], on_stderr=on_stderr)
        th.start()
        th.join()
        assert th.returncode == 1
        assert (
            'Error: Could not find or load main class {s}\n'.format(s=test_str)
            in th.stderr
        )
        assert th.stdout == ''
