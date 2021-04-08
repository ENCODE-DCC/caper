import os
import re
from pathlib import Path

import setuptools

META_PATH = Path('caper', '__init__.py')
HERE = os.path.abspath(os.path.dirname(__file__))


def read(*parts):
    """
    Build an absolute path from *parts* and and return the contents of the
    resulting file.  Assume UTF-8 encoding.
    """
    with Path(HERE, *parts).open(encoding='utf-8') as f:
        return f.read()


META_FILE = read(META_PATH)


def find_meta(meta):
    """
    Extract __*meta*__ from META_FILE.
    """
    meta_match = re.search(
        r"^__{meta}__ = ['\"]([^'\"]*)['\"]".format(meta=meta), META_FILE, re.M
    )
    if meta_match:
        return meta_match.group(1)
    raise


with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='caper',
    version=find_meta('version'),
    python_requires='>=3.6',
    scripts=[
        'bin/caper',
        'bin/run_mysql_server_docker.sh',
        'bin/run_mysql_server_singularity.sh',
        'scripts/gcp_caper_server/create_instance.sh',
    ],
    author='Jin Lee',
    author_email='leepc12@gmail.com',
    description='Cromwell Assisted Pipeline ExecutoR',
    long_description='https://github.com/ENCODE-DCC/caper',
    long_description_content_type='text/markdown',
    url='https://github.com/ENCODE-DCC/caper',
    packages=setuptools.find_packages(exclude=['mysql*', 'docs']),
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
    ],
    install_requires=[
        'pyhocon>=0.3.53',
        'requests>=2.20',
        'pyopenssl',
        'autouri>=0.2.4',
        'miniwdl>=0.7.0',
        'humanfriendly',
        'numpy>=1.8.2',
        'pandas>=1.0',
        'scikit-learn>=0.19.2',
        'matplotlib>=1.5',
        'six>=1.13.0',
    ],
)
