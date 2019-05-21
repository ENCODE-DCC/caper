# Caper

Caper (Cromwell Assisted Pipeline ExecutoR) is a wrapper Python package for [Cromwell](https://github.com/broadinstitute/cromwell/).

## Introduction

Caper is based on Unix and cloud platform CLIs (`wget`, `curl`, `gsutil` and `aws`) and provides easier way of running Cromwell server/run modes by automatically composing necessary input files for Cromwell. Also, Caper supports easy automatic file transfer between local/cloud storages (local path, `s3://`, `gs://` and `http(s)://`). You can use these URIs in input JSON file or for a WDL file itself.

## Features

* **Similar CLI**: Caper has a similar CLI as Cromwell.
* **Built-in backends**: You don't need your own backend configuration file. Caper provides built-in backends.
* **Automatic transfer between local/cloud storages**: You can use URIs (e.g. `gs://`, `http://` and `s3://) instead of paths in a command line arguments, also in your input JSON file. Files associated with these URIs will be automatically transfered to a specified temporary directory on a target remote storage.
* **Deepcopy for input JSON file**: Recursively copy all data files in (`.json`, `.tsv` and `.csv`) to a target remote storage.
* **Docker/Singularity integration**: You can run a WDL workflow in a specifed docker/singularity container.
* **MySQL database integration**: We provides shells scripts to run MySQL database in a docker/singularity container. Using Caper with MySQL database will allow you to use Cromwell's [call-caching](https://cromwell.readthedocs.io/en/develop/Configuring/#call-caching) to re-use outputs from previous successful tasks.
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

## Configuration file

`Caper` automatically creates a default configuration file at `~/.caper/default.conf`. Such configruation file comes with all available parameters commented out. You can uncomment/define any parameter to activate it.

You can avoid repeatedly defining same parameters in your command line arguments by using a configuration file. For example, you can define `out_dir` and `tmp_dir` in your configuration file instead of defining them in command line arguments.
```
$ caper run your.wdl --out-dir [LOCAL_OUT_DIR] --tmp-dir [LOCAL_TMP_DIR]
```

Equivalent settings in a configuration file.
```
[defaults]
out-dir=[LOCAL_OUT_DIR]
tmp-dir=[LOCAL_TMP_DIR]
```

## List of parameters

We highly recommend to use a default configuration file explained in the section [Configuration file](#configuration-file). Note that both dash (`-`) and underscore (`_`) are allowed for key names in a configuration file.

**Cmd. line arg.**|**Description**
:-----:|:-----:
--inputs, -i|Workflow inputs JSON file
--options, -o|Workflow options JSON file
--labels, -l|Workflow labels JSON file
--imports, -p|Zip file of imported subworkflows

**Cmd. line arg.**|**Description**
:-----:|:-----:
--str-label, -s|Caper's special label for a workflow. This will be used to identify a workflow submitted by Caper
--docker|Docker image URI for a WDL
--singularity|Singaularity image URI for a WDL
--use-docker|Use docker image for all tasks in a workflow by adding docker URI into docker runtime-attribute
--use-singularity|Use singularity image for all tasks in a workflow

**Conf. file**|**Cmd. line arg.**|**Default**|**Description**
:-----:|:-----:|:-----:|:-----:
backend|-b, --backend|local|Caper's built-in backend to run a workflow. Supported backends: `local`, `gcp`, `aws`, `slurm`, `sge` and `pbs`. Make sure to configure for chosen backend
hold|--hold| |Put a hold on a workflow when submitted to a Cromwell server
deepcopy|--deepcopy| |Deepcopy input files to corresponding file local/remote storage
deepcopy-ext|--deepcopy-ext|json,tsv|Comma-separated list of file extensions to be deepcopied. Supported exts: .json, .tsv  and .csv.
format|--format, -f|id,status,name,str\_label,submission|Comma-separated list of items to be shown for `list` subcommand. Supported formats: `id` (workflow UUID), `status`, `name` (WDL basename), `str\_label` (Caper's special string label), `submission`, `start`, `end`

**Conf. file**|**Cmd. line arg.**|**Default**|**Description**
:-----:|:-----:|:-----:|:-----:
out-dir|--out-dir|`$CWD`|Output directory for local backend
tmp-dir|--tmp-dir|`$CWD/caper\_tmp`|Tmp. directory for local backend

**Conf. file**|**Cmd. line arg.**|**Description**
:-----:|:-----:|:-----:
gcp-prj|--gcp-prj|Google Cloud project
out-gcs-bucket|--out-gcs-bucket|Output GCS bucket for GC backend
tmp-gcs-bucket|--tmp-gcs-bucket|Tmp. GCS bucket for GC backend

**Conf. file**|**Cmd. line arg.**|**Description**
:-----:|:-----:|:-----:
aws-batch-arn|--aws-batch-arn|ARN for AWS Batch
aws-region|--aws-region|AWS region (e.g. us-west-1)
out-s3-bucket|--out-s3-bucket|Output S3 bucket for AWS backend
tmp-s3-bucket|--tmp-s3-bucket|Tmp. S3 bucket for AWS backend
use-gsutil-over-aws-s3|--use-gsutil-over-aws-s3|Use `gsutil` instead of `aws s3` even for S3 buckets

**Conf. file**|**Cmd. line arg.**|**Description**
:-----:|:-----:|:-----:
http-user|--http-user|HTTP Auth username to download data from private URLs
http-password|--http-password|HTTP Auth password to download data from private URLs

**Conf. file**|**Cmd. line arg.**|**Default**|**Description**
:-----:|:-----:|:-----:|:-----:
mysql-db-ip|--mysql-db-ip|localhost|MySQL DB IP address
mysql-db-port|--mysql-db-port|3306|MySQL DB port
mysql-db-user|--mysql-db-user|cromwell|MySQL DB username
mysql-db-password|--mysql-db-password|cromwell|MySQL DB password

**Conf. file**|**Cmd. line arg.**|**Default**|**Description**
:-----:|:-----:|:-----:|:-----:
ip|--ip|localhost|Cromwell server IP address or hostname
port|--port|8000|Cromwell server port
cromwell|--cromwell|[cromwell-40.jar](https://github.com/broadinstitute/cromwell/releases/download/40/cromwell-40.jar)|Path or URL for Cromwell JAR file
max-concurrent-tasks|--max-concurrent-tasks|1000|Maximum number of concurrent tasks
max-concurrent-workflows|--max-concurrent-workflows|40|Maximum number of concurrent workflows
disable-call-caching|--disable-call-caching| |Disable Cromwell's call-caching (re-using outputs)
backend-file|--backend-file| |Custom Cromwell backend conf file. This will override Caper's built-in backends

**Conf. file**|**Cmd. line arg.**|**Description**
:-----:|:-----:|:-----:
slurm-partition|--slurm-partition|SLURM partition
slurm-account|--slurm-account|SLURM account
slurm-extra-param|--slurm-extra-param|Extra parameters for SLURM `sbatch` command

**Conf. file**|**Cmd. line arg.**|**Description**
:-----:|:-----:|:-----:
sge-pe|--sge-pe|SGE parallel environment. Check with `qconf -spl`
sge-queue|--sge-queue|SGE queue to submit tasks. Check with `qconf -sql`
slurm-extra-param|--slurm-extra-param|Extra parameters for SGE `qsub` command

**Conf. file**|**Cmd. line arg.**|**Description**
:-----:|:-----:|:-----:
pbs-queue|--pbs-queue|PBS queue to submit tasks.
pbs-extra-param|--pbs-extra-param|Extra parameters for PBS `qsub` command

## How to configure for each backend

We highly recommend to use a default configuration file explained in the section [Configuration file](#configuration-file).

There are six backends supported by Caper. Each backend must run on its designated storage. To use cloud backends (`gcp` and `aws`) and corresponding cloud storages (`gcs` and `s3`), you must install cloud platform's CLIs ([`gsutil`](https://cloud.google.com/storage/docs/gsutil_install) and [`aws`](https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html)). You also need to configure these CLIs for authentication. See configuration instructions for [GCP](docs/conf_gcp.md) and [AWS](docs/conf_aws.md) for details.

| Backend | Description          | Storage | Required parameters                                                     |
|---------|----------------------|---------|-------------------------------------------------------------------------|
|`gcp`    |Google Cloud Platform | `gcs`   | `--gcp-prj`, `--out-gcs-bucket`, `--tmp-gcs-bucket`                     |
|`aws`    |AWS                   | `s3`    | `--aws-batch-arn`, `--aws-region`, `--out-s3-bucket`, `--tmp-s3-bucket` |
|`Local`  |Default local backend | `local` | `--out-dir`, `--tmp-dir`                                                |
|`slurm`  |local SLURM backend   | `local` | `--out-dir`, `--tmp-dir`, `--slurm-partition` or `--slurm-account`      |
|`sge`    |local SGE backend     | `local` | `--out-dir`, `--tmp-dir`, `--sge-pe`                                    |
|`pds`    |local PBS backend     | `local` | `--out-dir`, `--tmp-dir`                                                |

* Google Cloud Platform (`gcp`): Make sure that you already configured `gcloud` and `gsutil` correctly and passed authentication for them (e.g. `gcloud auth login`). You need to define `--gcp-prj`, `--out-gcs-bucket` and `--tmp-gcs-bucket` in your command line arguments or in your configuration file.
	```
	$ caper run my.wdl -b gcp --gcp-prj [GOOGLE_PRJ_NAME] --out-gcs-bucket [GS_OUT_DIR] --tmp-gcs-bucket [GS_TMP_DIR]
	```

* AWS (`aws`)Make sure that you already configured `aws` correctly and passed authentication for them (e.g. `aws configure`). You need to define `--aws-batch-arn`, `--aws-region`, `--out-s3-bucket` and `--tmp-s3-bucket` in your command line arguments or in your configuration file.
	```
	$ caper run my.wdl -b aws --aws-batch-arn [AWS_BATCH_ARN] --aws-region [AWS_REGION] --out-s3-bucket [S3_OUT_DIR] --tmp-s3-bucket [S3_TMP_DIR]
	```

* All local backends (`Local`, `slurm`, `sge` and `pbs`): You need to define `--out-dir` and `--tmp-dir` in your command line arguments or in your configuration file.
	```
	$ caper run my.wdl -b [BACKEND] --out-dir [OUT_DIR] --tmp-dir [TMP_DIR]
	```

* SLURM backend (`slurm`): You need to define `--slurm-account` or `--slurm-partition` in your command line arguments or in your configuration file.

	> **WARNING: If your SLURM cluster does not require you to specify a partition or an account then skip them.
	```
	$ caper run my.wdl -b slurm --slurm-account [YOUR_SLURM_ACCOUNT] --slurm-partition [YOUR_SLURM_PARTITON]
	```

* SGE backend (`sge`): You need to define `--sge-pe` in your command line arguments or in your configuration file.
	
	> **WARNING: If you don't have a parallel environment (PE) then ask your SGE admin to add one.
	```
	$ caper run my.wdl -b sge --sge-pe [YOUR_PE]
	```

* PBS backend (`pbs`): There are no required parameters for PBS backend.
	```
	$ caper run my.wdl -b pbs
	```

## Temporary directory

There are four types of storages. Each storage except for URL has its own temporary directory/bucket defined by the following parameters. 

| Storage | URI(s)       | Command line parameter    |
|---------|--------------|---------------------------|
| `local` | Path         | `--tmp-dir`               |
| `gcs`   | `gs://`      | `--tmp-gcs-bucket`        |
| `s3`    | `s3://`      | `--tmp-s3-bucket`         |
| `url`   | `http(s)://` | not available (read-only) |

## Output directory

Output directories are defined similarly as temporary ones. Those are actual output directories (called `cromwell_root`, which is `cromwell-executions/` by default) where Cromwell's output are actually written to.

| Storage | URI(s)       | Command line parameter    |
|---------|--------------|---------------------------|
| `local` | Path         | `--out-dir`               |
| `gcs`   | `gs://`      | `--out-gcs-bucket`        |
| `s3`    | `s3://`      | `--out-s3-bucket`         |
| `url`   | `http(s)://` | not available (read-only) |

Workflow's final output file `metadata.json` will be written to each workflow's directory (with workflow UUID) under this output directory.

### Inter-storage transfer

Inter-storage transfer is done by keeping source's directory structure and appending to target storage temporary directory. For example of the following temporary directory settings for each backend,

| Storage | Command line parameters                              |
|---------|------------------------------------------------------|
| `local` | `--tmp-dir /scratch/user/caper_tmp`             |
| `gcs`   | `--tmp-gcs-bucket gs://my_gcs_bucket/caper_tmp` |
| `s3`    | `--tmp-s3-bucket s3://my_s3_bucket/caper_tmp`   |

A local file `/home/user/a/b/c/hello.gz` can be copied (on demand) to 

| Storage | Command line parameters                                      |
|---------|--------------------------------------------------------------|
| `gcs`   | `gs://my_gcs_bucket/caper_tmp/home/user/a/b/c/hello.gz` |
| `s3`    | `s3://my_s3_bucket/caper_tmp/home/user/a/b/c/hello.gz`  |

File transfer is done by using the following command lines using various CLIs:

* `gsutil -q cp -n [SRC] [TARGET]`
* `aws s3 cp '--only-show-errors' [SRC] [TARGET]`
* `wget --no-check-certificate -qc [URL_SRC] -O [LOCAL_TARGET]`
* `curl -f [URL_SRC] | gsutil -q cp -n - [TARGET]`

> **WARNING**: Caper does not ensure a fail-safe file transfer when it's interrupted by user or system. Also, there can be race conditions if multiple users try to access/copy files. This will be later addressed in the future release. Until then DO NOT interrupt file transfer until you see the following `copying done` message.

Example:
```
[CaperURI] copying from gcs to local, src: gs://encode-pipeline-test-runs/test_wdl_imports/main.wdl
[CaperURI] copying done, target: /srv/scratch/leepc12/caper_tmp_dir/encode-pipeline-test-runs/test_wdl_imports/main.wdl
```

### Working with private URLs

To have access to password-protected (HTTP Auth) private URLs, provide username and password in command line arguments (`--http-user` and `--http-password`) or in a configuration file.
```
$ caper run http://password.protected.server.com/my.wdl -i http://password.protected.server.com/my.inputs.json --http-user [HTTP_USERNAME] --http-password [HTTP_PASSWORD] 
```

### Security

> **WARNING**: Please keep your local temporary directory **SECURE**. Caper writes temporary files (`backend.conf`, `inputs.json`, `workflow_opts.json` and `labels.json`) for Cromwell on `local` temporary directory defined by `--tmp-dir`. The following sensitive information can be exposed on these directories.

| Sensitve information               | Temporary filename   |
|------------------------------------|----------------------|
| MySQL database username            | `backend.conf`       |
| MySQL database password            | `backend.conf`       |
| AWS Batch ARN                      | `backend.conf`       |
| Google Cloud Platform project name | `backend.conf`       |
| SLURM account name                 | `workflow_opts.json` |
| SLURM partition name               | `workflow_opts.json` |

> **WARNING**: Also, please keep other temporary directories **SECURE** too. Your data files defined in your input JSON file can be recursively transferred to any of these temporary directories according to your target backend defined by `-b` or `--backend`.

## WDL customization

> **Optional**: Add the following comments to your WDL then Caper will be able to find an appropriate container image for your WDL. Then you don't have to define them in command line arguments everytime you run a pipeline.

```bash
#CAPER singularity docker://ubuntu:latest
#CAPER docker ubuntu:latest
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

## Running a MySQL server with Docker

We provide [a shell script](mysql/run_mysql_server_docker.sh) to run a MySQL server with docker. Run the following command line. `[PORT]`, `[MYSQL_USER]`, `[MYSQL_PASSWORD]` and `[CONTAINER_NAME]` are optional. MySQL server will run in background.

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

If you see any conflict in `[PORT]` and `[CONTAINER_NAME]`:
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

## Running a MySQL server with Singularity

We provide [a shell script](mysql/run_mysql_server_singularity.sh) to run a MySQL server with singularity. Run the following command line. `[PORT]`, `[MYSQL_USER]`, `[MYSQL_PASSWORD]` and `[CONTAINER_NAME]` are optional. MySQL server will run in background.

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

If you see any conflict in `[PORT]` and `[CONTAINER_NAME]`, then remove a conflicting container and try with different port and container name.
```bash
$ singularity instance list
$ singularity instance stop [CONTAINER_NAME]
```

To stop/kill a running MySQL server,
```bash
$ singularity instance list  # find your MySQL singularity container
$ singularity instance stop [CONTAINER_NAME]
```
