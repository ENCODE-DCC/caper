# Caper

Caper (Cromwell Assisted Pipeline ExecutoR) is a wrapper Python package for [Cromwell](https://github.com/broadinstitute/cromwell/).

## Introduction

Caper is based on Unix and cloud platform CLIs (`curl`, `gsutil` and `aws`) and provides easier way of running Cromwell server/run modes by automatically composing necessary input files for Cromwell. Also, Caper supports easy automatic file transfer between local/cloud storages (local path, `s3://`, `gs://` and `http(s)://`). You can use these URIs in input JSON file or for a WDL file itself.

## Features

* **Similar CLI**: Caper has a similar CLI as Cromwell.

* **Built-in backends**: You don't need your own backend configuration file. Caper provides built-in backends.

* **Automatic transfer between local/cloud storages**: You can use URIs (e.g. `gs://`, `http(s)://` and `s3://`) instead of paths in a command line arguments, also in your input JSON file. Files associated with these URIs will be automatically transfered to a specified temporary directory on a target remote storage.

* **Deepcopy for input JSON file**: Recursively copy all data files in (`.json`, `.tsv` and `.csv`) to a target remote storage. Use `--deepcopy` for this feature.

* **Docker/Singularity integration**: You can run a WDL workflow in a specifed docker/singularity container.

* **MySQL database integration**: Caper defaults to use Cromwell's built-in HyperSQL DB to store metadata of all workflows. However, we also provide shell scripts to run a MySQL database server in a docker/singularity container. Using Caper with those databases will allow you to use Cromwell's [call-caching](https://cromwell.readthedocs.io/en/develop/Configuring/#call-caching) to re-use outputs from previous successful tasks. This will be useful to resume a failed workflow where it left off.

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
run      | WDL  |Run a single workflow (not recommened for multiple workflows)
submit   | WDL  |Submit a workflow to a Cromwell server
abort    | WF_ID or STR_LABEL |Abort submitted workflows on a Cromwell server
unhold   | WF_ID or STR_LABEL |Release hold of workflows on a Cromwell server
list     | WF_ID or STR_LABEL |List submitted workflows on a Cromwell server
metadata | WF_ID or STR_LABEL |Retrieve metadata JSONs for workflows
troubleshoot | WF_ID, STR_LABEL or<br>METADATA_JSON_FILE |Analyze reason for errors

* `run`: To run a single workflow. A string label `-s` is optional and useful for other subcommands to indentify a workflow.

	```bash
	$ caper run [WDL] -i [INPUT_JSON] -s [STR_LABEL]
	```

	> **WARNING**: If you try to run multiple workflows at the same time then you will see a DB connection error message since multiple Caper instances will try to lock the same DB file `~/.caper/default_file_db`. Use a server-based [MySQL database](DETAILS.md/#mysql-server) instead or disable connection to DB with `--no-file-db` but you will not be able to take advantage of [Cromwell's call-caching](https://cromwell.readthedocs.io/en/develop/Configuring/#call-caching) to re-use outputs from previous workflows. We recomend to use `server` and `submit` for multiple concurrent workflows.

	```bash
	[error] Failed to instantiate Cromwell System. Shutting down Cromwell.
	java.sql.SQLTransientConnectionException: db - Connection is not available, request timed out after 3000ms.
	```

* `server`: To start a server.

	```bash
	$ caper server
	```

* `submit`: To submit a workflow to a server. Define a string label for submitted workflow with `-s`. It is optional but useful for other subcommands to indentify a workflow.

	```bash
	$ caper submit [WDL] -i [INPUT_JSON] -s [STR_LABEL]
	```

* `list`: To show a list of all workflows submitted to a cromwell server. Wildcard search with using `*` and `?` is allowed for such label for the following subcommands with `STR_LABEL`. 

	```bash
	$ caper list [WF_ID or STR_LABEL]
	```

* `troubleshoot`: To analyze reasons for workflow failures. You can specify failed workflow's metadata JSON file or workflow IDs and labels. Wildcard search with using `*` and `?` is allowed for string labels.

	```bash
	$ caper troubleshoot [WF_ID, STR_LABEL or METADATA_JSON_FILE]
	```

* Other subcommands: Other subcommands work similar to `list`. It does a corresponding action for matched workflows.


## Configuration file

Caper automatically creates a default configuration file at `~/.caper/default.conf`. Such configruation file comes with all available parameters commented out. You can uncomment/define any parameter to activate it.

You can avoid repeatedly defining same parameters in your command line arguments by using a configuration file. For example, you can define `out-dir` and `tmp-dir` in your configuration file instead of defining them in command line arguments.
```
$ caper run [WDL] --out-dir [LOCAL_OUT_DIR] --tmp-dir [LOCAL_TMP_DIR]
```

Equivalent settings in a configuration file.
```
[defaults]

out-dir=[LOCAL_OUT_DIR]
tmp-dir=[LOCAL_TMP_DIR]
```

## Initialize it

Run Caper without parameters to generate a default configuration file.
```bash
$ caper
```

## Database

Caper defaults to use Cromwell's built-in HyperSQL file database located at `~/.caper/default_file_db`. You can change default database file path prefix in a default configuration file (`~/.caper/default.conf`). Setting up a database is important for Caper to re-use outputs from previous failed/succeeded workflows.
```
file-db=[YOUR_FILE_DB_PATH_PREFIX]
```

You can also use your own MySQL database if you [configure MySQL for Caper](DETAILS.md/#mysql-server).

## Singularity

Caper supports Singularity for its local built-in backend (`local`, `slurm`, `sge` and `pbs`). Tasks in a workflow will run inside a container and outputs will be pulled out to a host from it at the end of each task. Or you can add `--use-singularity` to use a [Singularity image URI defined in your WDL as a comment](DETAILS.md/#wdl-customization).

```bash
$ caper run [WDL] -i [INPUT_JSON] --singularity [SINGULARITY_IMAGE_URI]
```

Define a cache directory where local Singularity images will be built. You can also define an environment variable `SINGULARITY_CACHEDIR`.
```
singularity-cachedir=[SINGULARITY_CACHEDIR]
```

Singularity image will be built first before running a workflow to prevent mutiple tasks from competing to write on the same local image file. If you don't define it, every task in a workflow will try to repeatedly build a local Singularity image on their temporary directory. 


## Docker

Caper supports Docker for its non-HPC backends (`local`, `aws` and `gcp`). 

> **WARNING**: AWS and GCP backends will not work without a Docker image URI defined in a WDL file or specified with `--docker`. You can skip adding `--use-docker` since Caper will try to find it in your WDL first.

Tasks in a workflow will run inside a container and outputs will be pulled out to a host from it at the end of each task. Or you can add `--use-docker` to use a [Docker image URI defined in your WDL as a comment](DETAILS.md/#wdl-customization).

```bash
$ caper run [WDL] -i [INPUT_JSON] --docker [DOCKER_IMAGE_URI]
```

## Conda

Activate your `CONDA_ENV` before running Caper (both for `run` and `server` modes).
```bash
$ conda activate [COND_ENV]
```

## How to run it

According to your chosen backend, define the following parameters in your default configuration file (`~/.caper/default.conf`).

* Local
	```
	# if you want to run your workflow in a Singularity container
	singularity-cachedir=[SINGULARITY_CACHEDIR]

	# directory to store all outputs
	out-dir=[LOCAL_OUT_DIR]

	# temporary directory for Caper
	# lots of temporary files will be created and stored here
	# e.g. backend.conf, workflow_opts.json, input.json, labels.json
	# don't use /tmp
	tmp-dir=[LOCAL_TMP_DIR]
	```

* Google Cloud Platform (GCP): Install [gsutil](https://cloud.google.com/storage/docs/gsutil_install). [Configure for gcloud and gsutil](docs/conf_gcp.md).

	```
	# specify default backend as gcp
	backend=gcp

	# your project name on Google Cloud platform
	gcp-prj=YOUR_PRJ_NAME

	# directory to store all outputs
	out-gcs-bucket=gs://YOUR_OUTPUT_ROOT_BUCKET/ANY/WHERE

	# temporary bucket directory for Caper
	tmp-gcs-bucket=gs://YOUR_TEMP_BUCKET/SOME/WHERE
	```

* AWS: Install [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html). [Configure for AWS](docs/conf_aws.md).

	```
	# specify default backend as aws
	backend=aws

	# ARN for your AWS Batch
	aws-batch-arn=ARN_FOR_YOUR_AWS_BATCH

	# directory to store all outputs
	out-s3-bucket=s3://YOUR_OUTPUT_ROOT_BUCKET/ANY/WHERE

	# temporary bucket directory for Caper
	tmp-s3-bucket=s3://YOUR_TEMP_BUCKET/SOME/WHERE
	```

* SLURM
	```
	# specify default backend as slurm
	backend=slurm

	# if you want to run your workflow in a Singularity container
	singularity-cachedir=[SINGULARITY_CACHEDIR]

	# directory to store all outputs
	out-dir=[LOCAL_OUT_DIR]

	# temporary directory for Caper
	# don't use /tmp
	tmp-dir=[LOCAL_TMP_DIR]

	# SLURM partition if required (e.g. on Stanford Sherlock)
	slurm-partition=[YOUR_PARTITION]

	# SLURM account if required (e.g. on Stanford SCG4)
	slurm-account=[YOUR_ACCOUMT]

	# You may not need to specify the above two
	# since most SLURM clusters have default rules for partition/account

	# server mode
	# ip is an IP address or hostname of a Cromwell server
	# it's localhost by default but if you are submitting to
	# a remote Cromwell server (e.g. from login node to a compute node)
	# then take IP address of the server and write it here
	ip=localhost

	# port is 8000 by default. but if it's already taken 
	# then try other ports like 8001
	port=8000
	```

* SGE

	```
	# specify default backend as sge
	backend=sge

	# if you want to run your workflow in a Singularity container
	singularity-cachedir=[SINGULARITY_CACHEDIR]

	# directory to store all outputs
	out-dir=[LOCAL_OUT_DIR]

	# temporary directory for Caper
	# don't use /tmp
	tmp-dir=[LOCAL_TMP_DIR]

	# SGE PE
	sge-pe=[YOUR_PARALLEL_ENVIRONMENT]

	# server mode
	# ip is an IP address or hostname of a Cromwell server
	# it's localhost by default but if you are submitting to
	# a remote Cromwell server (e.g. from login node to a compute node)
	# then take IP address of the server and write it here
	ip=localhost

	# port is 8000 by default. but if it's already taken 
	# then try other ports like 8001
	port=8000
	```

Run Caper. Make sure to keep your SSH session alive.

`--deepcopy` is optional for input JSON file with remote URIs defined in it. Those URIs (`http(s)://`, `s3://`, `gs://`, ...) will be recursively copied into a target storage for a corresponding chosen backend. For example, GCS bucket (`gs://`) for GCP backend (`gcp`).

```bash
$ caper run [WDL] -i [INPUT_JSON] --deepcopy
```

Or run a Cromwell server with Caper. Make sure to keep server's SSH session alive.

```bash
$ hostname  # get IP address or hostname of a compute/login node
$ caper server
```

Then submit a workflow to the server. A TCP port `--port` are optional if you have changed the default port `8000`. Server IP address `--ip` is optional for a local server.
```bash
$ caper submit [WDL] -i [INPUT_JSON] --ip [SERVER_HOSTNAME] --port [PORT]
```

On HPCs (e.g. Stanford Sherlock and SCG), you can run Caper with a Singularity container if that is [defined inside `WDL`](DETAILS.md/#wdl-customization). For example, ENCODE [ATAC-seq](https://github.com/ENCODE-DCC/atac-seq-pipeline/blob/master/atac.wdl#L5) and [ChIP-seq](https://github.com/ENCODE-DCC/chip-seq-pipeline2/blob/master/chip.wdl#L5) pipelines.
```bash
$ caper run [WDL] -i [INPUT_JSON] --use-singularity
```

Or specify your own Singularity container.
```bash
$ caper run [WDL] -i [INPUT_JSON] --singularity [SINGULARITY_IMAGE_URI]
```

Similarly for Docker.
```bash
$ caper run [WDL] -i [INPUT_JSON] --use-docker
```

```bash
$ caper run [WDL] -i [INPUT_JSON] --docker [DOCKER_IMAGE_URI]
```

## HPCs

> **Run mode on HPCs**: We don't recommend to run Caper on a login node. Caper/Cromwell will be killed while building a local Singularity image or deepcopying remote files. Also Cromwell is a Java application which is not lightweight.

You are not submitting workflows to your cluster engine (e.g. SLURM). You are submitting Caper to the engine and Caper will work as another job manager which `will `sbatch` and `qsub` subtasks defined in WDL. So don't give Caper too much resource. one CPU, 1GB RAM and long enough walltime will be enough.

For Caper run mode, you cannot `caper run` multiple workflows with a single `--file-db` because they will try to write on the same DB file. Give each workflow a different `--file-db`. `--file-db` is important when you want to resume your failed workflows and automatically re-use outputs from previous workflows.

1) SLURM: 1 cpu, 2GB of RAM and 7 days of walltime. `--partition` (e.g. Stanford Sherlock) and `--account` (e.g. Stanford SCG) are optional and depend on your cluster's SLURM configuration.

	```bash
	$ sbatch -n 1 --mem 2G -t 7-0 --partition [YOUR_SLURM_PARTITON] --account [YOUR_SLURM_ACCOUNT] --wrap "caper run [WDL] -i [INPUT_JSON] [YOUR_CAPER_RUN_EXTRA_PARAMS] --file-db [YOUR_FILE_DB]"
	```

2) SGE: 1 cpu, 2GB of RAM and 7 days of walltime.

	```bash
	$ echo "caper run [WDL] -i [INPUT_JSON] [YOUR_CAPER_RUN_EXTRA_PARAMS] --file-db [YOUR_FILE_DB]" | qsub -l h_rt=144:00:00 -l h_vmem=2G
	```

> **Server/client mode on HPCs**: We recommend to run a server on a non-login node with at least one CPU, 2GB RAM and long enough walltime. Take IP address of your compute node and update your default configuration file with it. If there is any conflicting port, then change port in your configuration file. If default port 8000 is already taken the try with another port.

For Caper server mode, you can submit multiple workflows with a single `--file-db`.

1) SLURM: 1 cpu, 2GB of RAM and 7 days of walltime. `--partition` (e.g. Stanford Sherlock) and `--account` (e.g. Stanford SCG) are optional and depend on your cluster's SLURM configuration.

	```bash
	$ sbatch -n 1 --mem 2G -t 7-0 --partition [YOUR_SLURM_PARTITON] --account [YOUR_SLURM_ACCOUNT] --wrap "caper server --port 8000 [YOUR_CAPER_SERVER_EXTRA_PARAMS]"

	# get hostname of Cromwell server 
	$ squeue -u $USER
	```

	For example on Stanford Sherlock. Hostname is `sh-102-32` for this example.
	```bash
	[leepc12@sh-ln07 login ~]$ sbatch -n 1 --mem 3G -t 7-0 -p akundaje -o ~/caper_server.o -e ~/caper_server.e --wrap "caper server --port 8000"
	Submitted batch job 44439486

	[leepc12@sh-ln07 login ~]$ squeue -u $USER
             JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)
          44439486  akundaje     wrap  leepc12  R       2:34      1 sh-102-32
	```

2) SGE: 1 cpu, 2GB of RAM and 7 days of walltime.

	```bash
	$ echo "caper server --port 8000 [YOUR_CAPER_SERVER_EXTRA_PARAMS] --file-db [YOUR_FILE_DB]" | qsub -l h_rt=144:00:00 -l h_vmem=2G

	# get hostname of Cromwell server 
	$ qstat
	```

Submit workflows to the server.
```bash
$ caper submit [WDL] -i [INPUT_JSPN] -s [ANY_LABEL_FOR_WORKFLOW] --ip [SERVER_HOSTNAME] --port 8000
```


# DETAILS

See [details](DETAILS.md).
