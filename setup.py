import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='caper',
    version='1.0.0',
    python_requires='>=3.6',
    scripts=[
        'bin/caper',
        'bin/run_mysql_server_docker.sh',
        'bin/run_mysql_server_singularity.sh',
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
        'requests',
        'pyopenssl',
        'autouri>=0.1.2.1',
        'miniwdl',
    ],
)
