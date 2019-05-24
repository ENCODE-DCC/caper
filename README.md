# Caper

Caper (Cromwell Assisted Pipeline ExecutoR) is a wrapper Python package for [Cromwell](https://github.com/broadinstitute/cromwell/).

## Introduction

Caper is based on Unix and cloud platform CLIs (`curl`, `gsutil` and `aws`) and provides easier way of running Cromwell server/run modes by automatically composing necessary input files for Cromwell. Also, Caper supports easy automatic file transfer between local/cloud storages (local path, `s3://`, `gs://` and `http(s)://`). You can use these URIs in input JSON file or for a WDL file itself.

## Features

* **Similar CLI**: Caper has a similar CLI as Cromwell.

* **Built-in backends**: You don't need your own backend configuration file. Caper provides built-in backends.

* **Automatic transfer between local/cloud storages**: You can use URIs (e.g. `gs://`, `http://` and `s3://`) instead of paths in a command line arguments, also in your input JSON file. Files associated with these URIs will be automatically transfered to a specified temporary directory on a target remote storage.

* **Deepcopy for input JSON file**: Recursively copy all data files in (`.json`, `.tsv` and `.csv`) to a target remote storage.

* **Docker/Singularity integration**: You can run a WDL workflow in a specifed docker/singularity container.

* **MySQL database integration**: We provide shell scripts to run a MySQL database server in a docker/singularity container. Using Caper with MySQL database will allow you to use Cromwell's [call-caching](https://cromwell.readthedocs.io/en/develop/Configuring/#call-caching) to re-use outputs from previous successful tasks. This will be useful to resume a failed workflow where it left off.

* **One configuration file for all**: You may not want to repeat writing same command line parameters for every pipeline run. Define parameters in a configuration file at `~/.caper/default.conf`.

* **One server for six backends**: Built-in backends allow you to submit pipelines to any local/remote backend specified with `-b` or `--backend`.

* **Cluster engine support**: SLURM, SGE and PBS are currently supported locally.

* **Easy workflow management**: Find all workflows submitted to a Cromwell server by workflow IDs (UUIDs) or `str_label` (special label for a workflow submitted by Caper `submit` and `run`). You can define multiple keywords with wildcards (`*` and `?`) to search for matching workflows. Abort, release hold, retrieve metadata JSON for them.

* **Automatic subworkflow packing**: Caper automatically creates an archive (`imports.zip`) of all imports and send it to Cromwell server/run.

* **Special label** (`str_label`): You have a string label, specified with `-s` or `--str-label`, for your workflow so that you can search for your workflow by this label instead of Cromwell's workflow UUID (e.g. `f12526cb-7ed8-4bfa-8e2e-a463e94a61d0`).

## Installation

Make sure that you have `python3`(> 3.4.1) installed on your system. Use `pip` to install Caper.
```bash
$ pip install caper
```

Or `git clone` this repo and manually add `bin/` to your environment variable `PATH` in your BASH startup scripts (`~/.bashrc`).

```bash
$ git clone https://github.com/ENCODE-DCC/caper
$ echo "export PATH=\"\$PATH:$PWD/caper/bin\"" >> ~/.bashrc
```

## Usage

There are 7 subcommands available for Caper. Except for `run` other subcommands work with a running Cromwell server, which can be started with `server` subcommand. `server` does not require a positional argument. `WF_ID` (workflow ID) is a UUID generated from Cromwell to identify a workflow. `STR_LABEL` is Caper's special string label to be used to identify a workflow.

**Subcommand**|**Positional args** | **Description**
:--------|:-----|:-----
server   |      |Run a Cromwell server with built-in backends
run      | WDL  |Run a single workflow
submit   | WDL  |Submit a workflow to a Cromwell server
abort    | WF_ID or STR_LABEL |Abort submitted workflows on a Cromwell server
unhold   | WF_ID or STR_LABEL |Release hold of workflows on a Cromwell server
list     | WF_ID or STR_LABEL |List submitted workflows on a Cromwell server
metadata | WF_ID or STR_LABEL |Retrieve metadata JSONs for workflows

Examples:

* `run`: To run a single workflow. Add `--hold` to put an hold to submitted workflows.

	```bash
	$ caper run [WDL] -i [INPUT_JSON]
	```

* `server`: To start a server

	```bash
	$ caper server
	```

* `submit`: To submit a workflow to a server. `-s` is optional but useful for other subcommands to find submitted workflow with matching string label.

	```bash
	$ caper submit [WDL] -i [INPUT_JSON] -s [STR_LABEL]
	```

* `list`: To show list of all workflows submitted to a cromwell server. Wildcard search with using `*` and `?` is allowed for such label for the following subcommands with `STR_LABEL`. 

	```bash
	$ caper list [WF_ID or STR_LABEL]
	```

* Other subcommands: Other subcommands work similar to `list`. It does a corresponding action for matched workflows.


## Configuration file

Caper automatically creates a default configuration file at `~/.caper/default.conf`. Such configruation file comes with all available parameters commented out. You can uncomment/define any parameter to activate it.

You can avoid repeatedly defining same parameters in your command line arguments by using a configuration file. For example, you can define `out_dir` and `tmp_dir` in your configuration file instead of defining them in command line arguments.
```
$ caper run [WDL] --out-dir [LOCAL_OUT_DIR] --tmp-dir [LOCAL_TMP_DIR]
```

Equivalent settings in a configuration file.
```
[defaults]

out-dir=[LOCAL_OUT_DIR]
tmp-dir=[LOCAL_TMP_DIR]
```

## Before running it

Run Caper to generate a default configuration file.

```bash
$ caper
```

## How to run it on a local computer

Define two important parameters in your default configuration file (`~/.caper/default.json`).
```
# directory to store all outputs
out-dir=[LOCAL_OUT_DIR]

# temporary directory for Caper
# lots of temporary files will be created and stored here
# e.g. backend.conf, workflow_opts.json, input.json, labels.json
# don't use /tmp
tmp-dir=[LOCAL_TMP_DIR]
```

Run Caper. `--deepcopy` is optional for remote (http://, gs://, s3://, ...)  `INPUT_JSON` file.
```bash
$ caper run [WDL] -i [INPUT_JSON] --deepcopy
```

## How to run it on Google Cloud Platform (GCP)

Install [gsutil](https://cloud.google.com/storage/docs/gsutil_install). [Configure for gcloud and gsutil](docs/conf_gcp).

Define three important parameters in your default configuration file (`~/.caper/default.json`).
```
# your project name on Google Cloud platform
gcp-prj=YOUR_PRJ_NAME

# directory to store all outputs
out-gcs-bucket=gs://YOUR_OUTPUT_ROOT_BUCKET/ANY/WHERE

# temporary bucket directory for Caper
tmp-gcs-bucket=gs://YOUR_TEMP_BUCKET/SOME/WHERE
```

Run Caper. `--deepcopy` is optional for remote (local, http://, s3://, ...)  `INPUT_JSON` file.
```bash
$ caper run [WDL] -i [INPUT_JSON] --backend gcp --deepcopy
```

## How to run it on AWS

Install [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html). [Configure for AWS](docs/conf_aws).

Define three important parameters in your default configuration file (`~/.caper/default.json`).
```
# ARN for your AWS Batch
aws-batch-arn=ARN_FOR_YOUR_AWS_BATCH

# directory to store all outputs
out-s3-bucket=s3://YOUR_OUTPUT_ROOT_BUCKET/ANY/WHERE

# temporary bucket directory for Caper
tmp-s3-bucket=s3://YOUR_TEMP_BUCKET/SOME/WHERE
```

Run Caper. `--deepcopy` is optional for remote (http://, gs://, local, ...)  `INPUT_JSON` file.
```bash
$ caper run [WDL] -i [INPUT_JSON] --backend aws --deepcopy
```


## How to run it on SLURM cluster

Define five important parameters in your default configuration file (`~/.caper/default.json`).
```
# directory to store all outputs
out-dir=[LOCAL_OUT_DIR]

# temporary directory for Caper
# lots of temporary files will be created and stored here
# e.g. backend.conf, workflow_opts.json, input.json, labels.json
# don't use /tmp
tmp-dir=[LOCAL_TMP_DIR]

# SLURM partition if required (e.g. on Stanford Sherlock)
slurm-partition=YOUR_PARTITION

# SLURM account if required (e.g. on Stanford SCG4)
slurm-account=YOUR_ACCOUMT

# You may not need to specify the above two
# since most SLURM clusters have default rules for partition/account

# server mode
# port is 8000 by default. but if it's already taken 
# then try other ports like 8001
port=8000
```

Run Caper. `--deepcopy` is optional for remote (http://, gs://, s3://, ...) `INPUT_JSON` file.
```bash
$ caper run [WDL] -i [INPUT_JSON] --backend slurm --deepcopy
```

Or run a Cromwell server with Caper. Make sure to keep server's SSH session alive. If there is any conflicting port. Change port in your default configuration file.
```bash
$ caper server
```

On HPC cluster with Singularity installed, run Caper with a Singularity container if that is [defined inside `WDL`](DETAILS.md/#wdl-customization).
```bash
$ caper run [WDL] -i [INPUT_JSON] --backend slurm --deepcopy --use-singularity
```

Or specify your own Singularity container.
```bash
$ caper run [WDL] -i [INPUT_JSON] --backend slurm --deepcopy --singularity [YOUR_SINGULARITY_IMAGE]
```

Then submit pipelines to the server.
```bash
$ caper submit [WDL] -i [INPUT_JSON] --deepcopy -p [PORT]
```

## How to run it on SGE cluster

Define four important parameters in your default configuration file (`~/.caper/default.json`).
```
# directory to store all outputs
out-dir=[LOCAL_OUT_DIR]

# temporary directory for Caper
# lots of temporary files will be created and stored here
# e.g. backend.conf, workflow_opts.json, input.json, labels.json
# don't use /tmp
tmp-dir=[LOCAL_TMP_DIR]

# SGE PE
sge-pe=YOUR_PARALLEL_ENVIRONMENT

# server mode
# port is 8000 by default. but if it's already taken 
# then try other ports like 8001
port=8000
```

Run Caper. `--deepcopy` is optional for remote (http://, gs://, s3://, ...)  `INPUT_JSON` file.
```bash
$ caper run [WDL] -i [INPUT_JSON] --backend sge --deepcopy
```

Or run a Cromwell server with Caper. Make sure to keep server's SSH session alive. If there is any conflicting port. Change port in your default configuration file (`~/.caper/default.json`).
```bash
$ caper server
```

Then submit pipelines to the server.
```bash
$ caper submit [WDL] -i [INPUT_JSON] --deepcopy -p [PORT]
```

## How to resume a failed workflow

You need to set up a [MySQL database server](DETAILS.md/#mysql-server) to use Cromwell's call-caching feature, which allows a failed workflow to start from where it left off. Use the same command line that you used to start a workflow then Caper will automatically skip tasks that are already done successfully.

Make sure you have Docker or Singularity installed on your system. Singularity does not require super-user privilege to be installed.

Configure for MySQL DB in a default configuration file `~/.caper/default.conf`.
```
# MySQL DB port
# try other port if already taken
mysql-db-port=3307
```

`DB_DIR` is a directory to be used as a DB storage. Create an empty directory if it's for the first time. `DB_PORT` is a MySQL DB port. If there is any conflict use other ports.

1) Docker

	```bash
	$ run_mysql_server_docker.sh [DB_DIR] [DB_PORT]
	```

2) Singularity

	```bash
	$ run_mysql_server_singularity.sh [DB_DIR] [DB_PORT]
	```

## Using Conda?

Just activate your `CONDA_ENV` before running Caper (both for `run` and `server` modes).
```bash
$ conda activate [COND_ENV]
```

# DETAILS

See [details](DETAILS.md).
