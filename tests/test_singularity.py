import json
import os
from textwrap import dedent

from caper.singularity import Singularity

UBUNTU_18_04_3 = (
    'ubuntu@sha256:d1d454df0f579c6be4d8161d227462d69e163a8ff9d20a847533989cf0c94d90'
)
UBUNTU_18_04_3_LAST_HASH_TAR_GZ = (
    'sha256:6001e1789921cf851f6fb2e5fe05be70f482fe9c2286f66892fe5a3bc404569c.tar.gz'
)


def test_build_local_image(tmp_path):
    """Singularity class works with Singularity CLI.
    Make sure to have such CLI installed on your system.

    Make sure to unset env var SINGULARITY_CACHEDIR before running pytest.

    This test will build a local Singularity image, which is consist of
    multiple docker layer (hash) files (tar.gz).
    This test will check one of the hashes.
    """
    singularity = Singularity(
        singularity_image='docker://' + UBUNTU_18_04_3,
        singularity_cachedir=str(tmp_path),
    )
    singularity.build_local_image()

    hash_file = str(tmp_path / 'docker' / UBUNTU_18_04_3_LAST_HASH_TAR_GZ)
    assert os.path.exists(hash_file)


def test_find_bindpath(tmp_path):
    """Parse input JSON file to recursively get all the files defined in it.
    For found local abspaths, find common root directories for those.

    This is necessary for singularity to bind paths (similar to mounting directories
    in docker).

    Input JSON file has one TSV file and this file will be recursively visited by
    Singularilty.find_bindpath().
    """
    tsv = tmp_path / 'test.tsv'
    tsv_contents = dedent(
        """\
        file1\t/1/2/3/4.txt
        file2\t/1/5/6/7.txt
        file3\t/a/t/c.txt
    """
    )
    tsv.write_text(tsv_contents)

    inputs = tmp_path / 'inputs.json'
    inputs_dict = {
        'test.input_tsv': str(tsv),
        'test.input': '/a/b/c/d.txt',
        'test.input2': '/a/b/e.txt',
        'test.input3': '/f/g/h.txt',
        'test.input4': '/s/x/y/s/d/e/s/.txt',
    }
    inputs.write_text(json.dumps(inputs_dict, indent=4))

    # test with two different levels
    bindpaths_5 = Singularity.find_bindpath(str(inputs), 5).split(',')
    assert sorted(bindpaths_5) == sorted(
        [
            '/1/2/3',
            '/1/5/6',
            '/a/b',
            '/a/t',
            '/f/g',
            '/s/x/y/s',
            '/'.join(str(tmp_path).split('/')[:5]),
        ]
    )

    bindpaths_2 = Singularity.find_bindpath(str(inputs), 2).split(',')
    assert sorted(bindpaths_2) == sorted(
        ['/1', '/a', '/f', '/s', '/'.join(str(tmp_path).split('/')[:2])]
    )
