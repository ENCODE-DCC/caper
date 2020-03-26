## Important features of Caper

* **Similar CLI**: Caper has a similar CLI as Cromwell.

* **Built-in backends**: You don't need your own backend configuration file. Caper provides built-in backends.

* **Automatic transfer between local/cloud storages**: You can use URIs (e.g. `gs://`, `http(s)://` and `s3://`) instead of paths in a command line arguments, also in your input JSON file. Files associated with these URIs will be automatically transfered to a specified temporary directory on a target remote storage.

* **Deepcopy for input JSON file**: Recursively copy all data files in (`.json`, `.tsv` and `.csv`) to a target remote storage. It's activate by default. Use `--no-deepcopy` to disable this feature.

* **Docker/Singularity integration**: You can run a WDL workflow in a specifed docker/singularity container.

* **MySQL database integration**: Caper provide shell scripts to run a MySQL database server in a docker/singularity container. Using Caper with those databases will allow you to use Cromwell's [call-caching](https://cromwell.readthedocs.io/en/develop/Configuring/#call-caching) to re-use outputs from previous successful tasks. This will be useful to resume a failed workflow where it left off.

* **One configuration file for all**: You may not want to repeat writing same command line parameters for every pipeline run. Define parameters in a configuration file at `~/.caper/default.conf`.

* **One server for six backends**: Built-in backends allow you to submit pipelines to any local/remote backend specified with `-b` or `--backend`.

* **Cluster engine support**: SLURM, SGE and PBS are currently supported locally.

* **Easy workflow management**: Find all workflows submitted to a Cromwell server by workflow IDs (UUIDs) or `str_label` (special label for a workflow submitted by Caper `submit` and `run`). You can define multiple keywords with wildcards (`*` and `?`) to search for matching workflows. Abort, release hold, retrieve metadata JSON for them.

* **Automatic subworkflow packing**: Caper automatically creates an archive (`imports.zip`) of all imports and send it to Cromwell server/run.

* **Special label** (`str_label`): You have a string label, specified with `-s` or `--str-label`, for your workflow so that you can search for your workflow by this label instead of Cromwell's workflow UUID (e.g. `f12526cb-7ed8-4bfa-8e2e-a463e94a61d0`).


## Usage

There are 7 subcommands available for Caper. Except for `run` other subcommands work with a running Caper server, which can be started with `server` subcommand. `server` does not require a positional argument. `WF_ID` (workflow ID) is a UUID generated from Cromwell to identify a workflow. `STR_LABEL` is Caper's special string label to be used to identify a workflow.

**Subcommand**|**Positional args** | **Description**
:--------|:-----|:-----
init   | PLATFORM |Generate a default configuration file for a specified PLATFORM
server   |      |Run a Cromwell server with built-in backends
run      | WDL  |Run a single workflow (not recommened for multiple workflows)
submit   | WDL  |Submit a workflow to a Cromwell server
abort    | WF_ID or STR_LABEL |Abort submitted workflows on a Cromwell server
unhold   | WF_ID or STR_LABEL |Release hold of workflows on a Cromwell server
list     | WF_ID or STR_LABEL |List submitted workflows on a Cromwell server
metadata | WF_ID or STR_LABEL |Retrieve metadata JSONs for workflows
debug, troubleshoot | WF_ID, STR_LABEL or<br>METADATA_JSON_FILE |Analyze reason for errors

* `init`: To initialize Caper on a given platform. This command also downloads Cromwell/Womtool JARs so that Caper can work completely offline with local data files.

	**Platform**|**Description**
	:--------|:-----
	sherlock | Stanford Sherlock cluster (SLURM)
	scg | Stanford SCG cluster (SLURM)
	gcp | Google Cloud Platform
	aws | Amazon Web Service
	local | General local computer
	sge | HPC with Sun GridEngine cluster engine
	pbs | HPC with PBS cluster engine
	slurm | HPC with SLURM cluster engine

* `run`: To run a single workflow. A string label `-s` is optional and useful for other subcommands to indentify a workflow.

	```bash
	$ caper run [WDL] -i [INPUT_JSON]
	```

	> **WARNING**: If you use a file DB (`--file-db`) and try to run multiple workflows at the same time then you will see a `db - Connection is not available` error message since multiple Caper instances will try to lock the same DB file `~/.caper/default_file_db`.

	```bash
	java.sql.SQLTransientConnectionException: db - Connection is not available, request timed out after 3000ms.
	```

	> **WORKAROUND**: Define a different DB file per run with `--file-db`. Or start a caper server and submit multiple workflows to it so that the DB file is taken by one caper server only. Or use a server-based [MySQL database](DETAILS.md/#mysql-server) instead.

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

* `debug` or `troubleshoot`: To analyze reasons for workflow failures. You can specify failed workflow's metadata JSON file or workflow IDs and labels. Wildcard search with using `*` and `?` is allowed for string labels.

	```bash
	$ caper debug [WF_ID, STR_LABEL or METADATA_JSON_FILE]
	```

* Other subcommands: Other subcommands work similar to `list`. It does a corresponding action for matched workflows.

## Deepcopy (auto inter-storage transfer)

> **IMPORTANT**: `--deepcopy` has been deprecated and it's activated by default. You can disable it with `--no-deepcopy`.

Deepcopy allows Caper to **RECURSIVELY** copy files defined in your input JSON into your target backend's temporary storage. For example, Cromwell cannot read directly from URLs in an [input JSON file](https://github.com/ENCODE-DCC/atac-seq-pipeline/blob/master/examples/caper/ENCSR356KRQ_subsampled.json), but Caper makes copies of these URLs on your backend's temporary directory (e.g. `--tmp-dir` for `local`, `--tmp-gcs-bucket` for `gcp`) and pass them to Cromwell.

## How to manage configuration file per project

It is useful to have a configuration file per project. For example of two projects.

We want to run pipelines locally for project-1, run a server with `caper -c project_1.conf server` and submit a workflow with `caper -c project_1.conf submit [WDL] ...` or run a single workflow `caper -c project_1.conf run [WDL] ...`.
```
db=file
file-db=~/.caper/file_db_project_1
port=8000
backend=local
out-dir=/scratch/user/caper_out_project_1
```

We want to run pipelines on Google Cloud Platform for project-2. Run a server with `caper -c project_2.conf server` and submit a workflow with `caper -c project_2.conf submit [WDL] ...` or run a single workflow `caper -c project_2.conf run [WDL] ...`.
```
db=file
file-db=~/.caper/file_db_project_2
port=8001
backend=gcp
gcp-prj=YOUR_GCP_PRJ_NAME
out-gcs-bucket=gs://caper_out_project_2
```

Then you will see no conflict in file DBs and network ports (`8000` vs. `8001`) between two projects.



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
	--dry-run|Caper generates all temporary files but does not take any action.
	--str-label, -s|Caper's special label for a workflow. This will be used to identify a workflow submitted by Caper
	--docker|Docker image URI for a WDL. You can also use this as a flag. You can also use this as a flag to use Docker image defined in your WDL as a special comment `#CAPER docker [IMAGE]`.
	--singularity|Singularity image URI for a WDL. You can also use this as a flag to use Singularity image defined in your WDL as a special comment `#CAPER singularity [IMAGE]`.
	--no-build-singularity|Local singularity image will not be built before running/submitting a workflow
	--singularity-cachedir|Singularity image URI for a WDL
	--db|Metadata DB type (file: not recommended, mysql: recommended, in-memory: no metadata DB)
	--file-db, -d|File-based metadata DB for Cromwell's built-in HyperSQL database (UNSTABLE)
	--db-timeout|Milliseconds to wait for DB connection (default: 30000)
	--java-heap-server|Java heap memory for caper server (default: 10G)
	--java-heap-run|Java heap memory for caper run (default: 3G)

* Choose a default backend. Deepcopy is enabled by default. All data files will be automatically transferred to a target local/remote storage corresponding to a chosen backend. Make sure that you correctly configure temporary directories for source/target storages (`--tmp-dir`, `--tmp-gcs-bucket` and `--tmp-s3-bucket`). To disable this feature use `--no-deepcopy`.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	backend|-b, --backend|local|Caper's built-in backend to run a workflow. Supported backends: `local`, `gcp`, `aws`, `slurm`, `sge` and `pbs`. Make sure to configure for chosen backend
	hold|--hold| |Put a hold on a workflow when submitted to a Cromwell server
	no-deepcopy|--no-deepcopy| |Disable deepcopy (copying files defined in an input JSON to corresponding file local/remote storage)
	format|--format, -f|id,status,<br>name,<br>str_label,<br>submission|Comma-separated list of items to be shown for `list` subcommand. Supported formats: `id` (workflow UUID), `status`, `name` (WDL basename), `str\_label` (Caper's special string label), `submission`, `start`, `end`
	hide-result-before|--hide-result-before| | Datetime string to hide old workflows submitted before it. This is based on a simple string sorting. (e.g. 2019-06-13, 2019-06-13T10:07)

	DEPRECATED OLD PARAMETERS:

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	deepcopy-ext|--deepcopy-ext|json,<br>tsv|DEPRECATED. Caper defaults to use deepcopy for JSON, TSV and CSV.

* Local backend settings

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	out-dir|--out-dir|`$CWD`|Output directory for local backend
	tmp-dir|--tmp-dir|`$CWD/caper\_tmp`|Tmp. directory for local backend

* Google Cloud Platform backend settings

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	gcp-prj|--gcp-prj|Google Cloud project
	gcp-zone|--gcp-zones|Comma-delimited Google Cloud Platform zones to provision worker instances (e.g. us-central1-c,us-west1-b)
	out-gcs-bucket|--out-gcs-bucket|Output GCS bucket for GC backend
	tmp-gcs-bucket|--tmp-gcs-bucket|Tmp. GCS bucket for GC backend

* AWS backend settings

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	aws-batch-arn|--aws-batch-arn|ARN for AWS Batch
	aws-region|--aws-region|AWS region (e.g. us-west-1)
	out-s3-bucket|--out-s3-bucket|Output S3 bucket for AWS backend
	tmp-s3-bucket|--tmp-s3-bucket|Tmp. S3 bucket for AWS backend
	use-gsutil-for-s3|--use-gsutil-for-s3|Use `gsutil` for direct transfer between S3 and GCS buckets. Otherwise Caper streams file transfer through local machine.

	DEPREACTED OLD PARAMETERS:

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	use-gsutil-over-aws-s3|--use-gsutil-over-aws-s3|DEPREACTED.

* Private URLs settings
	Caper defaults to use `~/.netrc` file to get access to private URLs. This is useful, particularly for [ENCODE portal](https://www.encodeproject.org/), for using private URLs (`http(s)://`) directly in your input JSON.

	DEPREACTED OLD PARAMETERS.

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	http-user|--http-user|DEPRECATED
	http-password|--http-password|DEPRECATED
	use-netrc|--use-netrc|DEPRECATED

* MySQL settings. Run a MySQL server with [shell scripts](/mysql) we provide and make Cromwell server connect to it instead of using its in-memory database. This is useful when you need to re-use outputs from previous failed workflows when you resume them.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	mysql-db-ip|--mysql-db-ip|localhost|(Optional) MySQL DB IP address
	mysql-db-port|--mysql-db-port|3306|MySQL DB port
	mysql-db-user|--mysql-db-user|cromwell|(Optional) MySQL DB username
	mysql-db-password|--mysql-db-password|cromwell|(Optional) MySQL DB password
	mysql-db-name|--mysql-db-name|cromwell|(Optional) MySQL DB name for Cromwell

* PostgreSQL settings.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	postgresql-db-ip|--postgresql-db-ip|localhost|(Optional) PostgreSQL DB IP address
	postgresql-db-port|--postgresql-db-port|3306|PostgreSQL DB port
	postgresql-db-user|--postgresql-db-user|cromwell|(Optional) PostgreSQL DB username
	postgresql-db-password|--postgresql-db-password|cromwell|(Optional) PostgreSQL DB password
	postgresql-db-name|--postgresql-db-name|cromwell|(Optional) PostgreSQL DB name for Cromwell

* Cromwell server settings. IP address and port for a Cromwell server.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	ip|--ip|localhost|Cromwell server IP address or hostname
	port|--port|8000|Cromwell server port
	no-server-heartbeat|--no-server-heartbeat||Flag to disable server heartbeat file.
	server-heartbeat-file|--server-heartbeat-file|`~/.caper/default_server_heartbeat`|Heartbeat file for Caper clients to get IP and port of a server.
	server-heartbeat-timeout|--server-heartbeat-timeout|120000|Timeout for a heartbeat file in Milliseconds.

	cromwell|--cromwell|[cromwell-40.jar](https://github.com/broadinstitute/cromwell/releases/download/40/cromwell-40.jar)|Path or URL for Cromwell JAR file
	max-concurrent-tasks|--max-concurrent-tasks|1000|Maximum number of concurrent tasks
	max-concurrent-workflows|--max-concurrent-workflows|40|Maximum number of concurrent workflows
	max-retries|--max-retries|1|Maximum number of retries for failing tasks
	disable-call-caching|--disable-call-caching| |Disable Cromwell's call-caching (re-using outputs)
	soft-glob-output|--soft-glob-output||Use soft-linking for globbing outputs for a filesystem that does not allow hard-linking: e.g. beeGFS.
	backend-file|--backend-file| |Custom Cromwell backend conf file. This will override Caper's built-in backends

* Troubleshoot parameters for `caper troubleshoot` subcommand.

	**Cmd. line**|**Description**
	:-----|:-----
	--show-completed-task|Show completed tasks when troubleshooting

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

You can also use your own MySQL database if you [configure MySQL for Caper](DETAILS.md/#mysql-server).

## Singularity

Caper supports Singularity for its local built-in backend (`local`, `slurm`, `sge` and `pbs`). Tasks in a workflow will run inside a container and outputs will be pulled out to a host from it at the end of each task. You need to add `--singularity` to use your own Singularity image. `SINGULARITY_IMAGE_URI` is **OPTIONAL**. You can omit it then Caper will try to find a [Singularity image URI defined in your WDL as a comment](DETAILS.md/#wdl-customization).

```bash
$ caper run [WDL] -i [INPUT_JSON] --singularity [SINGULARITY_IMAGE_URI_OR_LEAVE_IT_BLANK]
```

Define a cache directory where local Singularity images will be built. You can also define an environment variable `SINGULARITY_CACHEDIR`.
```
singularity-cachedir=[SINGULARITY_CACHEDIR]
```

Singularity image will be built first before running a workflow to prevent mutiple tasks from competing to write on the same local image file. If you don't define it, every task in a workflow will try to repeatedly build a local Singularity image on their temporary directory. 


## Docker

Caper supports Docker for its non-HPC backends (`local`, `aws` and `gcp`). 

> **WARNING**: For `aws` and `gcp` backends Caper will try to find a [Docker image URI defined in your WDL as a comment](DETAILS.md/#wdl-customization) even if `--docker` is not explicitly defined.

Tasks in a workflow will run inside a container and outputs will be pulled out to a host from it at the end of each task. `DOCKER_IMAGE_URI` is **OPTIONAL**. If it's not defined then Caper will try to find a [Docker image URI defined in your WDL as a comment](DETAILS.md/#wdl-customization).

```bash
$ caper run [WDL] -i [INPUT_JSON] --docker [DOCKER_IMAGE_URI_OR_LEAVE_IT_BLANK]
```

## Conda

Activate your `CONDA_ENV` before running Caper (both for `run` and `server` modes).
```bash
$ conda activate [COND_ENV]
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
| PostgreSQL database username            | backend.conf       |
| PostgreSQL database password            | backend.conf       |
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
