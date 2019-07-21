# Caper

Caper (Cromwell Assisted Pipeline ExecutoR) is a wrapper Python package for [Cromwell](https://github.com/broadinstitute/cromwell/).

## Introduction

Caper is based on Unix and cloud platform CLIs (`curl`, `gsutil` and `aws`) and provides easier way of running Cromwell server/run modes by automatically composing necessary input files for Cromwell. Also, Caper supports easy automatic file transfer between local/cloud storages (local path, `s3://`, `gs://` and `http(s)://`). You can use these URIs in input JSON file or for a WDL file itself.

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

There are 7 subcommands available for Caper. Except for `run` other subcommands work with a running Caper server, which can be started with `server` subcommand. `server` does not require a positional argument. `WF_ID` (workflow ID) is a UUID generated from Cromwell to identify a workflow. `STR_LABEL` is Caper's special string label to be used to identify a workflow.

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
	$ caper run [WDL] -i [INPUT_JSON]
	```

	> **WARNING**: If you try to run multiple workflows at the same time then you will see a `db - Connection is not available` error message since multiple Caper instances will try to lock the same DB file `~/.caper/default_file_db`.

	```bash
	java.sql.SQLTransientConnectionException: db - Connection is not available, request timed out after 3000ms.
	```

	> **WORKAROUND**: Define a different DB file per run with `--file-db`. Or start a caper server and submit multiple workflows to it so that the DB file is taken by one caper server only. Or use a server-based [MySQL database](DETAILS.md/#mysql-server) instead or disable connection to DB with `--no-file-db` or `-n` but you will not be able to use [Cromwell's call-caching](https://cromwell.readthedocs.io/en/develop/Configuring/#call-caching) to re-use outputs from previous workflows.

* `server`: To start a server. You can define a server port with `--port`. Use a different port for each server for multiple servers. If you don't use a default port (`8000`). Then define `--port` for all client subcommands like `submit`, `list` and `troubleshoot`. If you run a server on a different IP address or hostname, then define it with `--ip` for all client subcomands like `submit`.

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

Run Caper without parameters to generate a default configuration file.
```bash
$ caper
```

Caper automatically creates a default configuration file at `~/.caper/default.conf`. Such configruation file comes with all available parameters commented out. You can uncomment/define any parameter to activate it.

You can avoid repeatedly defining same parameters in your command line arguments. For example, you can define `out-dir` and `tmp-dir` in your configuration file instead of defining them in command line arguments.
```
$ caper run [WDL] --out-dir [LOCAL_OUT_DIR] --tmp-dir [LOCAL_TMP_DIR]
```

Equivalent settings in a configuration file.
```
[defaults]

out-dir=[LOCAL_OUT_DIR]
tmp-dir=[LOCAL_TMP_DIR]
```

## Minimum required parameters

An auto-generated default configuration has a `Minimum required parameters` section on top. Other parameters in other sections are optional and most users will not be interested in them. If you don't see this section then remove existing default configuration file and regenerate it.

Edit your configuration file (`~/.caper/default.conf` by default) and uncomment/define parameters for your preferred backend.
```
[defaults]

############ Minimum required parameters
## Please read through carefully

## Define file DB to use Cromwell's call-caching
## Call-caching is important for restarting failed workflows
## File DB can only be accessed by one caper process (caper run or server)
## i.e. you cannot run multiple caper run with one file DB
## For such case, we recommend to use caper server and submit multiple workflows to it
## You can disable file DB with '--no-file-db' or '-n'
#file-db=~/.caper/default_file_db

## Define to use 'caper server' and all client subcommands like 'caper submit'
## This is not required for 'caper run'
#port=8000

## Define default backend (local, gcp, aws, slurm, sge, pbs)
#backend=local

## Define output directory if you want to run pipelines locally
#out-dir=

## Define if you want to run pipelines on Google Cloud Platform
#gcp-prj=encode-dcc-1016
#out-gcs-bucket=gs://encode-pipeline-test-runs/project1/caper_out

## Define if you want to run pipelines on AWS
#aws-batch-arn=arn:....
#aws-region=us-west-1
#out-s3-bucket=s3://encode-pipeline-test-runs/project1/caper_out

## Define if you want to run pipelines on SLURM
## Define partition or account or both according to your cluster's requirements
## For example, Stanford requires a partition and SCG requires an account.
#slurm-partition=akundaje
#slurm-account=akundaje

## Define if you want to run pipelines on SGE
#sge-pe=shm

## Define if your SGE cluster requires a queue
#sge-queue=q

## Define if your PBS cluster requires a queue
#pbs-queue=q
```

> **RECOMMENDATION**: Instead of using a default configuration file at `~/.caper/default.conf`, you can specify your own configuration file with `caper -c`. This is useful when you want to manage a configuration file per project (e.g. use a different file DB `--file-db` per project to prevent locking).
```
$ caper -c [YOUR_CONF_FILE_FOR_PROJECT_1] ...
```

## Running workflows on GCP/AWS backends

Cloud backends (AWS and GCP) write outputs on corresponding storage buckets (s3 and gcs). Caper internally uses cloud CLIs `gsutil` and `aws`. Therefore, make sure that these CLIs are installed and configured correctly.

> **WARNING**: On GCP backend you can deploy a workflow from your local computer. However due to AWS security reasons, you cannot do it on AWS backend. You need to spin up a AWS instance on AWS Console and configure for `aws` on the instance and run Caper there.

1) Google Cloud Platform (GCP): Install [gsutil](https://cloud.google.com/storage/docs/gsutil_install). [Configure for gcloud and gsutil](docs/conf_gcp.md).

2) AWS: [Configure for AWS](docs/conf_aws.md) first.

## Deepcopy (auto inter-storage transfer)

`--deepcopy` allows Caper to **RECURSIVELY** copy files defined in your input JSON into your target backend's temporary storage. For example, Cromwell cannot read directly from URLs in an [input JSON file](https://github.com/ENCODE-DCC/atac-seq-pipeline/blob/master/examples/caper/ENCSR356KRQ_subsampled.json), but Caper with `--deepcopy` makes copies of these URLs on your backend's temporary directory (e.g. `--tmp-dir` for `local`, `--tmp-gcs-bucket` for `gcp`) and pass them to Cromwell.

## How to manage configuration file per project

It is useful to have a configuration file per project. For example of two projects.

We want to run pipelines locally for project-1, run a server with `caper -c project_1.conf server` and submit a workflow with `caper -c project_1.conf submit [WDL] ...` or run a single workflow `caper -c project_1.conf run [WDL] ...`.
```
[defaults]
file-db=~/.caper/file_db_project_1
port=8000
backend=local
out-dir=/scratch/user/caper_out_project_1
```

We want to run pipelines on Google Cloud Platform for project-2. Run a server with `caper -c project_2.conf server` and submit a workflow with `caper -c project_2.conf submit [WDL] ...` or run a single workflow `caper -c project_2.conf run [WDL] ...`.
```
[defaults]
file-db=~/.caper/file_db_project_2
port=8001
backend=gcp
gcp-prj=YOUR_GCP_PRJ_NAME
out-gcs-bucket=gs://caper_out_project_2
```

Then you will see no conflict in file DBs and network ports (`8000` vs. `8001`) between two projects.


## How to run it

According to your chosen backend, define the following parameters in your default configuration file (`~/.caper/default.conf`).

* Local
	```
	backend=local
	out-dir=[LOCAL_OUT_DIR]

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

* Google Cloud Platform (GCP): Install [gsutil](https://cloud.google.com/storage/docs/gsutil_install). [Configure for gcloud and gsutil](docs/conf_gcp.md).
	```
	backend=gcp
	gcp-prj=YOUR_PRJ_NAME
	out-gcs-bucket=gs://YOUR_OUTPUT_ROOT_BUCKET/ANY/WHERE
	```

* AWS: [Configure for AWS](docs/conf_aws.md) first.
	```
	backend=aws
	aws-batch-arn=ARN_FOR_YOUR_AWS_BATCH
	aws-region=YOUR_AWS_REGION
	out-s3-bucket=s3://YOUR_OUTPUT_ROOT_BUCKET/ANY/WHERE
	```

* SLURM
	```
	backend=slurm
	out-dir=[LOCAL_OUT_DIR]

	# SLURM partition if required (e.g. on Stanford Sherlock)
	slurm-partition=[YOUR_PARTITION]

	# SLURM account if required (e.g. on Stanford SCG4)
	slurm-account=[YOUR_ACCOUMT]

	ip=localhost
	port=8000
	```

* SGE

	```
	backend=sge
	out-dir=[LOCAL_OUT_DIR]

	# SGE PE (if you don't have it, ask your admin to create one)
	sge-pe=[YOUR_PARALLEL_ENVIRONMENT]

	# SGE queue if required
	sge-queue=[YOUR_SGE_QUEUE]

	ip=localhost
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

Install Java locally or load cluster's Java module.
```bash
$ module load java
```

You are not submitting workflows to your cluster engine (e.g. SLURM). You are submitting Caper to the engine and Caper will work as another job manager which `will `sbatch` and `qsub` subtasks defined in WDL. So don't give Caper too much resource. one CPU, 1GB RAM and long enough walltime will be enough.

For Caper run mode, you cannot `caper run` multiple workflows with a single `--file-db` because they will try to write on the same DB file. Give each workflow a different `--file-db`. `--file-db` is important when you want to resume your failed workflows and automatically re-use outputs from previous workflows.

1) SLURM: 1 cpu, 2GB of RAM and 7 days of walltime. `--partition` (e.g. Stanford Sherlock) and `--account` (e.g. Stanford SCG) are optional and depend on your cluster's SLURM configuration.

	```bash
	$ sbatch --export=ALL -n 1 --mem 2G -t 7-0 --partition [YOUR_SLURM_PARTITON] --account [YOUR_SLURM_ACCOUNT] --wrap "caper run [WDL] -i [INPUT_JSON] [YOUR_CAPER_RUN_EXTRA_PARAMS] --file-db [YOUR_FILE_DB]"
	```

2) SGE: 1 cpu, 2GB of RAM and 7 days of walltime.

	```bash
	$ echo "caper run [WDL] -i [INPUT_JSON] [YOUR_CAPER_RUN_EXTRA_PARAMS] --file-db [YOUR_FILE_DB]" | qsub -l h_rt=144:00:00 -l h_vmem=2G
	```

> **Server/client mode on HPCs**: We recommend to run a server on a non-login node with at least one CPU, 2GB RAM and long enough walltime. Take IP address of your compute node and update your default configuration file with it. If there is any conflicting port, then change port in your configuration file. If default port 8000 is already taken the try with another port.

For Caper server mode, you can submit multiple workflows with a single `--file-db`.

1) SLURM: 1 cpu, 12GB of RAM and 7 days of walltime. `--partition` (e.g. Stanford Sherlock) and `--account` (e.g. Stanford SCG) are optional and depend on your cluster's SLURM configuration.

	```bash
	$ sbatch --export=ALL -n 1 --mem 10G -t 7-0 --partition [YOUR_SLURM_PARTITON] --account [YOUR_SLURM_ACCOUNT] --wrap "caper server --port 8000 [YOUR_CAPER_SERVER_EXTRA_PARAMS]"

	# get hostname of Cromwell server 
	$ squeue -u $USER
	```

	For example on Stanford Sherlock. Hostname is `sh-102-32` for this example.
	```bash
	[leepc12@sh-ln07 login ~]$ sbatch --export=ALL -n 1 --mem 10G -t 7-0 -p akundaje -o ~/caper_server.o -e ~/caper_server.e --wrap "caper server --port 8000"
	Submitted batch job 44439486

	[leepc12@sh-ln07 login ~]$ squeue -u $USER
             JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)
          44439486  akundaje     wrap  leepc12  R       2:34      1 sh-102-32
	```

2) SGE: 1 cpu, 2GB of RAM and 7 days of walltime.

	```bash
	$ echo "caper server --port 8000 [YOUR_CAPER_SERVER_EXTRA_PARAMS] --file-db [YOUR_FILE_DB]" | qsub -l h_rt=144:00:00 -l h_vmem=10G

	# get hostname of Cromwell server 
	$ qstat
	```

Submit workflows to the server.
```bash
$ caper submit [WDL] -i [INPUT_JSPN] -s [ANY_LABEL_FOR_WORKFLOW] --ip [SERVER_HOSTNAME] --port 8000
```


# DETAILS

See [details](DETAILS.md).
