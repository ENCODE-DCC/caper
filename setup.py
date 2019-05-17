import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='caper',  
    version='0.1',
    scripts=['caper','src/caper.py'] ,
    author="Jin Lee",
    author_email="leepc12@gmail.com",
    description="Cromwell Assisted Pipeline ExecutoR",
    long_description="Cromwell/WDL wrapper utility based on Unix/cloud platform CLIs",
    long_description_content_type="text/markdown",
    url="https://github.com/ENCODE-DCC/caper",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
)
