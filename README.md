# Cromweller
Cromwell wrapper based on Unix and cloud platform CLIs (`wget`, `curl`, `gsutil` and `aws s3`).

# Installation
Use `pip` to install it.

```bash
$ pip install cromweller
```

# Usage

```bash
usage: cromweller.py [-h] [-c FILE]
                     {run,server,submit,abort,list,metadata} ...

positional arguments:
  {run,server,submit,abort,list,metadata}
    run                 Run a single workflow without server
    server              Run a Cromwell server
    submit              Submit a workflow to a Cromwell server
    abort               Abort workflows running/pending on a Cromwell server
    list                List workflows running/pending on a Cromwell server
    metadata            Retrieve metadata JSON for a workflow from a Cromwell
                        server

optional arguments:
  -h, --help            show this help message and exit
  -c FILE, --conf FILE  Specify config file
```

# Requirements

* `python` >= 3.3, `java` >= 1.8, `pip3`, `wget` and `curl`
	Debian:
	```bash
	$ sudo apt-get install python3 jre-default python3-pip wget curl
	```
	Others:
	```bash
	$ sudo yum install python3 java-1.8.0-openjdk sudo yum install epel-release wget curl
	```

* python dependencies: `pyhocon`, `requests` and `datetime`
	```bash
	$ pip3 install pyhocon requests datetime
	```

* [gsutil](https://cloud.google.com/storage/docs/gsutil_install): Run the followings to configure gsutil:
	```bash
	$ gcloud auth login --no-launch-browser
	$ gcloud auth application-default --no-launch-browser
	```

* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html): Run the followings to configure AWS CLI:
	```bash
	$ aws configure
	```

## Python compatibility
`python` >= 3.3 due to `time.perf_counter()` and `os.path.makedirs(exist_ok=True)`.

# Cromwell

Cromweller is a wrapper for Cromwell and internally runs Cromwell server/run mode.

## Security

Before running a Cromwell server. See [this](https://cromwell.readthedocs.io/en/develop/developers/Security/) for details.