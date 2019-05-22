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
abort    | WF_ID or STR_LABEL |Abort a running/pending workflow on a Cromwell server
unhold   | WF_ID or STR_LABEL |Release hold of workflows on a Cromwell server
list     | WF_ID or STR_LABEL |List running/pending workflows on a Cromwell server
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

## List of parameters

We highly recommend to use a default configuration file described in the section [Configuration file](#configuration-file). Note that both dash (`-`) and underscore (`_`) are allowed for key names in a configuration file.

* Basic parameters that are similar to Cromwell.

	**Cmd. line**|**Description**
	:-----|:-----
	--inputs, -i|Workflow inputs JSON file
	--options, -o|Workflow options JSON file
	--labels, -l|Workflow labels JSON file
	--imports, -p|Zip file of imported subworkflows
	--metadata-output, -m|Path for output metadata JSON file (for `run` mode only)

* Caper's special parameters. You can define a docker/singularity image to run your workflow with.

	**Cmd. line**|**Description**
	:-----|:-----
	--str-label, -s|Caper's special label for a workflow. This will be used to identify a workflow submitted by Caper
	--docker|Docker image URI for a WDL
	--singularity|Singaularity image URI for a WDL
	--use-docker|Use docker image for all tasks in a workflow by adding docker URI into docker runtime-attribute
	--use-singularity|Use singularity image for all tasks in a workflow

* Choose a default backend. Use `--deepcopy` to recursively auto-copy data files in your input JSON file. All data files will be automatically transferred to a target local/remote storage corresponding to a chosen backend. Make sure that you correctly configure temporary directories for source/target storages (`--tmp-dir`, `--tmp-gcs-bucket` and `--tmp-s3-bucket`).

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	backend|-b, --backend|local|Caper's built-in backend to run a workflow. Supported backends: `local`, `gcp`, `aws`, `slurm`, `sge` and `pbs`. Make sure to configure for chosen backend
	hold|--hold| |Put a hold on a workflow when submitted to a Cromwell server
	deepcopy|--deepcopy| |Deepcopy input files to corresponding file local/remote storage
	deepcopy-ext|--deepcopy-ext|json,<br>tsv|Comma-separated list of file extensions to be deepcopied. Supported exts: .json, .tsv  and .csv.
	format|--format, -f|id,status,<br>name,<br>str_label,<br>submission|Comma-separated list of items to be shown for `list` subcommand. Supported formats: `id` (workflow UUID), `status`, `name` (WDL basename), `str\_label` (Caper's special string label), `submission`, `start`, `end`

* Local backend settings

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	out-dir|--out-dir|`$CWD`|Output directory for local backend
	tmp-dir|--tmp-dir|`$CWD/caper\_tmp`|Tmp. directory for local backend

* Google Cloud Platform backend settings

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	gcp-prj|--gcp-prj|Google Cloud project
	out-gcs-bucket|--out-gcs-bucket|Output GCS bucket for GC backend
	tmp-gcs-bucket|--tmp-gcs-bucket|Tmp. GCS bucket for GC backend

* AWS backend settings

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	aws-batch-arn|--aws-batch-arn|ARN for AWS Batch
	aws-region|--aws-region|AWS region (e.g. us-west-1)
	out-s3-bucket|--out-s3-bucket|Output S3 bucket for AWS backend
	tmp-s3-bucket|--tmp-s3-bucket|Tmp. S3 bucket for AWS backend
	use-gsutil-over-aws-s3|--use-gsutil-over-aws-s3|Use `gsutil` instead of `aws s3` even for S3 buckets

* Private URLs settings. This is useful, particularly for [ENCODE portal](https://www.encodeproject.org/), to use private URLs (`http(s)://`) in your input JSON.

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	http-user|--http-user|HTTP Auth username to download data from private URLs
	http-password|--http-password|HTTP Auth password to download data from private URLs

* MySQL settings. Run a MySQL server with [shell scripts](/mysql) we provide and make Cromwell server connect to it instead of using its in-memory database. This is useful when you need to re-use outputs from previous failed workflows when you resume them.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	mysql-db-ip|--mysql-db-ip|localhost|MySQL DB IP address
	mysql-db-port|--mysql-db-port|3306|MySQL DB port
	mysql-db-user|--mysql-db-user|cromwell|MySQL DB username
	mysql-db-password|--mysql-db-password|cromwell|MySQL DB password

* Cromwell server settings. IP address and port for a Cromwell server.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	ip|--ip|localhost|Cromwell server IP address or hostname
	port|--port|8000|Cromwell server port
	cromwell|--cromwell|[cromwell-40.jar](https://github.com/broadinstitute/cromwell/releases/download/40/cromwell-40.jar)|Path or URL for Cromwell JAR file
	max-concurrent-tasks|--max-concurrent-tasks|1000|Maximum number of concurrent tasks
	max-concurrent-workflows|--max-concurrent-workflows|40|Maximum number of concurrent workflows
	disable-call-caching|--disable-call-caching| |Disable Cromwell's call-caching (re-using outputs)
	backend-file|--backend-file| |Custom Cromwell backend conf file. This will override Caper's built-in backends

* SLURM backend settings. This is useful for Stanford Clusters (Sherlock, SCG). Define `--slurm-partition` for Sherlock and `--slurm-account` for SCG.

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	slurm-partition|--slurm-partition|SLURM partition
	slurm-account|--slurm-account|SLURM account
	slurm-extra-param|--slurm-extra-param|Extra parameters for SLURM `sbatch` command

* SGE backend settings. Make sure to have a parallel environment configured on your system. Ask your admin to add it if not exists.

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	sge-pe|--sge-pe|SGE parallel environment. Check with `qconf -spl`
	sge-queue|--sge-queue|SGE queue to submit tasks. Check with `qconf -sql`
	slurm-extra-param|--slurm-extra-param|Extra parameters for SGE `qsub` command

* PBS backend settings.

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	pbs-queue|--pbs-queue|PBS queue to submit tasks.
	pbs-extra-param|--pbs-extra-param|Extra parameters for PBS `qsub` command


## Built-in backends

We highly recommend to use a default configuration file explained in the section [Configuration file](#configuration-file).

There are six built-in backends for Caper. Each backend must run on its designated storage. To use cloud backends (`gcp` and `aws`) and corresponding cloud storages (`gcs` and `s3`), you must install cloud platform's CLIs ([`gsutil`](https://cloud.google.com/storage/docs/gsutil_install) and [`aws`](https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html)). You also need to configure these CLIs for authentication. See configuration instructions for [GCP](docs/conf_gcp.md) and [AWS](docs/conf_aws.md) for details. Define required parameters in command line arguments or in a configuration file.

| Backend | Description          | Storage | Required parameters                                                     |
|---------|----------------------|---------|-------------------------------------------------------------------------|
|gcp    |Google Cloud Platform | gcs   | --gcp-prj, --out-gcs-bucket, --tmp-gcs-bucket                     |
|aws    |AWS                   | s3    | --aws-batch-arn, --aws-region, --out-s3-bucket, --tmp-s3-bucket |
|Local  |Default local backend | local | --out-dir, --tmp-dir                                                |
|slurm  |local SLURM backend   | local | --out-dir, --tmp-dir, --slurm-partition or --slurm-account      |
|sge    |local SGE backend     | local | --out-dir, --tmp-dir, --sge-pe                                    |
|pds    |local PBS backend     | local | --out-dir, --tmp-dir                                                |


## MySQL server

We provide [shell scripts](mysql/) to run a MySQL server in a container with docker/singularity. Once you have a running MySQL server, define MySQL-related parameters in Caper to attach it to a Cromwell server. One of the advantages of using MySQL server is to use Cromwell's [call-caching](https://cromwell.readthedocs.io/en/develop/Configuring/#call-caching) to re-use outputs from previous successful tasks. You can simply restart failed workflows with the same command line you used to start them.

1) docker

	Run the following command line. `PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` and `CONTAINER_NAME` are optional. MySQL server will run in background.

	```bash
	$ bash mysql/run_mysql_server_docker.sh [DB_DIR] [PORT] [MYSQL_USER] [MYSQL_PASSWORD] [CONTAINER_NAME]
	```

	A general usage is:
	```bash
	Usage: ./run_mysql_server_docker.sh [DB_DIR] [PORT] [MYSQL_USER] [MYSQL_PASSWORD] [CONTAINER_NAME]

	Example: run_mysql_server_docker.sh ~/cromwell_data_dir 3307

	[DB_DIR]: This directory will be mapped to /var/lib/mysql inside a container
	[PORT] (optional): MySQL database port for docker host (default: 3306)
	[MYSQL_USER] (optional): MySQL username (default: cromwell)
	[MYSQL_PASSWORD] (optional): MySQL password (default: cromwell)
	[CONTAINER_NAME] (optional): MySQL container name (default: mysql_cromwell)
	```

	If you see any conflict in `PORT` and `CONTAINER_NAME`:
	```bash
	docker: Error response from daemon: Conflict. The container name "/mysql_cromwell" is already in use by container 0584ec7affed0555a4ecbd2ed86a345c542b3c60993960408e72e6ea803cb97e. You have to remove (or rename) that container to be able to reuse that name..
	```

	Then remove a conflicting container and try with different port and container name.
	```bash
	$ docker stop [CONTAINER_NAME]  # you can also use a container ID found in the above cmd
	$ docker rm [CONTAINER_NAME]
	```

	To stop/kill a running MySQL server,
	```bash
	$ docker ps  # find your MySQL docker container
	$ docker stop [CONTAINER_NAME]  # you can also use a container ID found in the above cmd
	$ docker rm [CONTAINER_NAME]
	```

	If you see the following authentication error:
	```bash
	Caused by: java.sql.SQLException: Access denied for user 'cromwell'@'localhost' (using password: YES)
	```

	Then try to remove a volume for MySQL's docker container. See [this](https://github.com/docker-library/mariadb/issues/62#issuecomment-366933805) for details.
	```bash
	$ docker volume ls  # find [VOLUME_ID] for your container
	$ docker volume rm [VOLUME_ID]
	```

2) Singularity

	Run the following command line. `PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` and `CONTAINER_NAME` are optional. MySQL server will run in background.

	```bash
	$ bash mysql/run_mysql_server_singularity.sh [DB_DIR] [PORT] [MYSQL_USER] [MYSQL_PASSWORD] [CONTAINER_NAME]
	```

	A general usage is:
	```bash
	Usage: ./run_mysql_server_singularity.sh [DB_DIR] [PORT] [MYSQL_USER] [MYSQL_PASSWORD] [CONTAINER_NAME]

	Example: run_mysql_server_singularity.sh ~/cromwell_data_dir 3307

	[DB_DIR]: This directory will be mapped to /var/lib/mysql inside a container
	[PORT] (optional): MySQL database port for singularity host (default: 3306)
	[MYSQL_USER] (optional): MySQL username (default: cromwell)
	[MYSQL_PASSWORD] (optional): MySQL password (default: cromwell)
	[CONTAINER_NAME] (optional): MySQL container name (default: mysql_cromwell)
	```

	If you see any conflict in `PORT` and `CONTAINER_NAME`, then remove a conflicting container and try with different port and container name.
	```bash
	$ singularity instance list
	$ singularity instance stop [CONTAINER_NAME]
	```

	To stop/kill a running MySQL server,
	```bash
	$ singularity instance list  # find your MySQL singularity container
	$ singularity instance stop [CONTAINER_NAME]
	```

## HPC clusters

For users on Stanford HPC clusters (Sherlock and SCG). We recommend to run a MySQL server and run a Cromwell server attached to it. Set up a configuration file like the following.

```bash
[defaults]

# define your SLURM partition for Sherlock
slurm-partition=

# define your SLURM account for SCG
slurm-account=

# for both cluster, define a temporary directory
# all temporary files will be stored here
# scratch directory is recommended
# do not use /tmp
tmp-dir=

# for both cluster, define a output directory
# actual pipeline outputs will be stored here
out-dir=

# MySQL database settings
# default port is 3306 but if it's already taken
# use a different port
mysql-db-port=3307
```

Run a MySQL database server in a singularity container. If you are running it for the first time, make an empty directory for `DB_DIR`. `PORT` is optional but match it with that in a configuration file.
```bash
$ run_mysql_server_singularity.sh [DB_DIR] [PORT]
```

Run a Cromwell server.
> **WARNING**: Make sure to keep the SSH session alive where a Cromwell server runs on.

```bash
$ caper server
```

Submit a workflow to it instead of `sbatch`ing it. `STR_LABEL` will be useful to find your workflows.
```bash
$ caper submit [WDL] -i [INPUT_JSON] -s [STR_LABEL]
```

Monitor your workflows. Find by `STR_LABEL` or `WF_ID` (UUID). Wildcard search (`*` and `?`) is available.
```bash
$ caper list [WF_ID or STR_LABEL]
```

## Output directory organizer

Cromwell's raw outputs are not organized. PIP install `croo`. Please read through `croo`'s [README](https://github.com/ENCODE-DCC/croo).
```bash
$ pip install croo
```

Use `croo` to organize outputs. For `METADATA_JSON`, find a `metadata.json` for your workflow in Caper's output directory. It is stored on `[CAPER_OUT_DIR]/[WDL_NAME]/[WF_ID]/metadata.json`. You need an [output definition JSON file](https://github.com/ENCODE-DCC/croo#output-definition-json-file) for your WDL. Find [examples](https://github.com/ENCODE-DCC/croo/tree/master/examples) for ENCODE ATAC/ChIP-seq pipelines. 
```bash
$ croo [METADATA_JSON] --out-def-json [OUT_DEF_JSON]
```

## Temporary directory

There are four types of storages. Each storage except for URL has its own temporary directory/bucket defined by the following parameters. 

| Storage | URI(s)       | Command line parameter    |
|---------|--------------|---------------------------|
| local | Path         | --tmp-dir               |
| gcs   | gs://      | --tmp-gcs-bucket        |
| s3    | s3://      | --tmp-s3-bucket         |
| url   | http(s):// | not available (read-only) |

## Output directory

Output directories are defined similarly as temporary ones. Those are actual output directories (called `cromwell_root`, which is `cromwell-executions/` by default) where Cromwell's output are actually written to.

| Storage | URI(s)       | Command line parameter    |
|---------|--------------|---------------------------|
| local | Path         | --out-dir               |
| gcs   | gs://      | --out-gcs-bucket        |
| s3    | s3://      | --out-s3-bucket         |
| url   | http(s):// | not available (read-only) |

Workflow's final output file `metadata.json` will be written to each workflow's directory (with workflow UUID) under this output directory.

### Inter-storage transfer

Inter-storage transfer is done by keeping source's directory structure and appending to target storage temporary directory. For example of the following temporary directory settings for each backend,

| Storage | Command line parameters                              |
|---------|------------------------------------------------------|
| local | --tmp-dir /scratch/user/caper_tmp             |
| gcs   | --tmp-gcs-bucket gs://my_gcs_bucket/caper_tmp |
| s3    | --tmp-s3-bucket s3://my_s3_bucket/caper_tmp   |

A local file `/home/user/a/b/c/hello.gz` can be copied (on demand) to 

| Storage | Command line parameters                                      |
|---------|--------------------------------------------------------------|
| gcs   | gs://my_gcs_bucket/caper_tmp/home/user/a/b/c/hello.gz |
| s3    | s3://my_s3_bucket/caper_tmp/home/user/a/b/c/hello.gz  |

File transfer is done by using the following command lines using various CLIs:

* `gsutil -q cp -n [SRC] [TARGET]`
* `aws s3 cp --only-show-errors [SRC] [TARGET]`
* `curl -RL -f -C - [URL_SRC] -o [TARGET]`
* `curl -RL -f [URL_SRC] | gsutil -q cp -n - [TARGET]`

> **WARNING**: Caper does not ensure a fail-safe file transfer when it's interrupted by user or system. Also, there can be race conditions if multiple users try to access/copy files. This will be later addressed in the future release. Until then DO NOT interrupt file transfer until you see the following `copying done` message.

Example:
```
[CaperURI] copying from gcs to local, src: gs://encode-pipeline-test-runs/test_wdl_imports/main.wdl
[CaperURI] copying done, target: /srv/scratch/leepc12/caper_tmp_dir/encode-pipeline-test-runs/test_wdl_imports/main.wdl
```

### Security

> **WARNING**: Please keep your local temporary directory **SECURE**. Caper writes temporary files (`backend.conf`, `inputs.json`, `workflow_opts.json` and `labels.json`) for Cromwell on `local` temporary directory defined by `--tmp-dir`. The following sensitive information can be exposed on these directories.

| Sensitve information               | Temporary filename   |
|------------------------------------|----------------------|
| MySQL database username            | backend.conf       |
| MySQL database password            | backend.conf       |
| AWS Batch ARN                      | backend.conf       |
| Google Cloud Platform project name | backend.conf       |
| SLURM account name                 | workflow_opts.json |
| SLURM partition name               | workflow_opts.json` |

> **WARNING**: Also, please keep other temporary directories **SECURE** too. Your data files defined in your input JSON file can be recursively transferred to any of these temporary directories according to your target backend defined by `-b` or `--backend`.

## WDL customization

> **Optional**: Add the following comments to your WDL then Caper will be able to find an appropriate container image for your WDL. Then you don't have to define them in command line arguments everytime you run a pipeline.

```bash
#CAPER singularity [SINGULARITY_IMAGE_URI: e.g. docker://ubuntu:latest or shub://SUI-HPC/mysql]
#CAPER docker [DOCKER_IMAGE_URI: e.g. ubuntu:latest]
```

## Requirements

* [gsutil](https://cloud.google.com/storage/docs/gsutil_install): Run the followings to configure gsutil:
	```bash
	$ gcloud auth login --no-launch-browser
	$ gcloud auth application-default --no-launch-browser
	```

* [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html): Run the followings to configure AWS CLI:
	```bash
	$ aws configure
	```
