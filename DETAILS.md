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
hpc submit| WDL  | Submit a Caper leader job to HPC's job engine
hpc list|        | List all Caper leader jobs
hpc abort | JOB_ID | Abort a Caper leader job. This will cascade kill all child jobs.

* `init`: To initialize Caper on a given platform. This command also downloads Cromwell/Womtool JARs so that Caper can work completely offline with local data files.

	**Platform**|**Description**
	:--------|:-----
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

Deepcopy allows Caper to **RECURSIVELY** copy files defined in your input JSON into your target backend's temporary storage. For example, Cromwell cannot read directly from URLs in an [input JSON file](https://github.com/ENCODE-DCC/atac-seq-pipeline/blob/master/examples/caper/ENCSR356KRQ_subsampled.json), but Caper makes copies of these URLs on your backend's temporary directory (e.g. `--local-loc-dir` for `local`, `--gcp-loc-dir` for `gcp`) and pass them to Cromwell.

## How to manage configuration file per project

It is useful to have a configuration file per project. For example of two projects.

We want to run pipelines locally for project-1, run a server with `caper -c project_1.conf server` and submit a workflow with `caper -c project_1.conf submit [WDL] ...` or run a single workflow `caper -c project_1.conf run [WDL] ...`.
```
db=file
file-db=~/.caper/file_db_project_1
port=8000
backend=local
local-out-dir=/scratch/user/caper_out_project_1
```

We want to run pipelines on Google Cloud Platform for project-2. Run a server with `caper -c project_2.conf server` and submit a workflow with `caper -c project_2.conf submit [WDL] ...` or run a single workflow `caper -c project_2.conf run [WDL] ...`.
```
db=file
file-db=~/.caper/file_db_project_2
port=8001
backend=gcp
gcp-prj=YOUR_GCP_PRJ_NAME
gcp-out-dir=gs://caper_out_project_2
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
	--docker|Docker image URI for a WDL. You can also use this as a flag to use Docker image defined in your WDL's `meta` section under the key `default_docker`. THIS WILL BE OVERRIDEN BY `docker` DEFINED IN EACH TASK's `runtime`.
	--singularity|Singularity image URI for a WDL. You can also use this as a flag to use Singularity image defined in your WDL's `meta` section under the key `default_singularity`. THIS WILL BE OVERRIDEN BY `singularity` DEFINED IN EACH TASK's `runtime`.
	--conda|Conda environment name to run a WDL task. You can also use this as a flag to use Conda environment defined in your WDL's `meta` section under the key `default_conda`. THIS WILL BE OVERRIDEN BY `conda` DEFINED IN EACH TASK's `runtime`.
	--db|Metadata DB type (file: not recommended, mysql: recommended, in-memory: no metadata DB)
	--file-db, -d|File-based metadata DB for Cromwell's built-in HyperSQL database (UNSTABLE)
	--db-timeout|Milliseconds to wait for DB connection (default: 30000)
	--java-heap-server|Java heap memory for caper server (default: 10G)
	--disable-auto-write-metadata| Disable auto update/retrieval/writing of `metadata.json` on workflow's output directory.
	--java-heap-run|Java heap memory for caper run (default: 3G)
	--show-subworkflow|Include subworkflow in `caper list` search query. **WARNING**: If there are too many subworkflows, then you will see HTTP 503 error (service unavaiable) or Caper/Cromwell server can crash.

* Choose a default backend. Deepcopy is enabled by default. All data files will be automatically transferred to a target local/remote storage corresponding to a chosen backend. Make sure that you correctly configure temporary directories for source/target storages (`--local-loc-dir`, `--gcp-loc-dir` and `--aws-loc-dir`). To disable this feature use `--no-deepcopy`.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	backend|-b, --backend|local|Caper's built-in backend to run a workflow. Supported backends: `local`, `gcp`, `aws`, `slurm`, `sge` and `pbs`. Make sure to configure for chosen backend
	hold|--hold| |Put a hold on a workflow when submitted to a Cromwell server
	no-deepcopy|--no-deepcopy| |Disable deepcopy (copying files defined in an input JSON to corresponding file local/remote storage)
	format|--format, -f|id,status,<br>name,<br>str_label,<br>submission|Comma-separated list of items to be shown for `list` subcommand. Supported formats: `id` (workflow UUID), `status`, `name` (WDL basename), `str\_label` (Caper's special string label), `parent` (parent's workflow UUID: `None` if not subworkflow), `submission`, `start`, `end`
	hide-result-before|--hide-result-before| | Datetime string to hide old workflows submitted before it. This is based on a simple string comparison (sorting). (e.g. 2019-06-13, 2019-06-13T10:07)

* Special parameter for a direct transfer between S3 and GCS buckets

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	use-gsutil-for-s3|--use-gsutil-for-s3|Use `gsutil` for direct transfer between S3 and GCS buckets. Otherwise Caper streams file transfer through local machine for S3 <-> GCS. Make sure that `gsutil` is installed and authentication for both GCS and S3 is done on shell environment level.

* Local backend settings

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	local-out-dir, out-dir|--local-out-dir, --out-dir|`$CWD`|Output directory for local backend
	local-loc-dir, tmp-dir|--local-loc-dir, --tmp-dir|`$CWD/caper\_tmp`|Tmp. directory for localization on local backend

* Google Cloud Platform backend settings

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	gcp-prj|--gcp-prj|Google Cloud project
	use-google-cloud-life-sciences|--use-google-cloud-life-sciences|Use Google Cloud Life Sciences API instead of (deprecated) Genomics API
	gcp-zones|--gcp-zones|Comma-delimited Google Cloud Platform zones to provision worker instances (e.g. us-central1-c,us-west1-b)
	gcp-out-dir, out-gcs-bucket|--gcp-out-dir, --out-gcs-bucket|Output `gs://` directory for GC backend
	gcp-loc-dir, tmp-gcs-bucket|--gcp-loc-dir, --tmp-gcs-bucket|Tmp. directory for localization on GC backend
	gcp-call-caching-dup-strat|--gcp-call-caching-dup-strat|Call-caching duplication strategy. Choose between `copy` and `reference`. `copy` will make a copy for a new workflow, `reference` will make refer to the call-cached output of a previous workflow in `metadata.json`. Defaults to `reference`

* AWS backend settings

	**Conf. file**|**Cmd. line**|**Description**
	:-----|:-----|:-----
	aws-batch-arn|--aws-batch-arn|ARN for AWS Batch
	aws-region|--aws-region|AWS region (e.g. us-west-1)
	aws-out-dir, out-s3-bucket|--aws-out-dir, --out-s3-bucket|Output `s3://` directory for AWS backend
	aws-loc-dir, tmp-s3-bucket|--aws-loc-dir, --tmp-s3-bucket|Tmp. directopy for localization on AWS backend
	aws-call-caching-dup-strat|--aws-call-caching-dup-strat|Call-caching duplication strategy. Choose between `copy` and `reference`. `copy` will make a copy for a new workflow, `reference` will make refer to the call-cached output of a previous workflow in `metadata.json`. Defaults to `reference`

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

* Caper server/run parameters.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	cromwell|--cromwell|[cromwell-59.jar](https://github.com/broadinstitute/cromwell/releases/download/59/cromwell-59.jar)|Path or URL for Cromwell JAR file
	max-concurrent-tasks|--max-concurrent-tasks|1000|Maximum number of concurrent tasks
	max-concurrent-workflows|--max-concurrent-workflows|40|Maximum number of concurrent workflows
	disable-call-caching|--disable-call-caching| |Disable Cromwell's call-caching (re-using outputs)
	soft-glob-output|--soft-glob-output||Use soft-linking for globbing outputs for a filesystem that does not allow hard-linking: e.g. beeGFS.
	backend-file|--backend-file| |Custom Cromwell backend conf file. This will override Caper's built-in backends

* Caper run/submit parameters.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	max-retries|--max-retries|1|Maximum number of retries for failing tasks

* Caper server/client parameters.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	ip|--ip|localhost|Cromwell server hostname/IP address or hostname
	port|--port|8000|Cromwell server port
	no-server-heartbeat|--no-server-heartbeat||Flag to disable server heartbeat file.
	server-heartbeat-file|--server-heartbeat-file|`~/.caper/default_server_heartbeat`|Heartbeat file for Caper clients to get IP and port of a server.

* Caper run/client parameters.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	womtool|--womtool|[womtool-59.jar](https://github.com/broadinstitute/cromwell/releases/download/59/womtool-59.jar)|Path or URL for Womtool JAR file (to validate WDL/inputs).
	ignore-womtool|--ignore-womtool|False|Skip Womtool validation.
	java-heap-womtool|--java-heap-womtool|1G|Java heap memory for Womtool.

* Caper client parameters.

	**Conf. file**|**Cmd. line**|**Default**|**Description**
	:-----|:-----|:-----|:-----
	server-heartbeat-timeout|--server-heartbeat-timeout|120000|Timeout for a heartbeat file in Milliseconds.


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
|gcp    |Google Cloud Platform | gcs   | --gcp-prj, --gcp-out-dir, --gcp-loc-dir                     |
|aws    |AWS                   | s3    | --aws-batch-arn, --aws-region, --aws-out-dir, --aws-loc-dir |
|Local  |Default local backend | local | --local-out-dir, --local-loc-dir                                                |
|slurm  |local SLURM backend   | local | --local-out-dir, --local-loc-dir, --slurm-partition or --slurm-account      |
|sge    |local SGE backend     | local | --local-out-dir, --local-loc-dir, --sge-pe                                    |
|pds    |local PBS backend     | local | --local-out-dir, --local-loc-dir                                                |

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

## Working (temporary) directory

There are four types of storages. Each storage except for URL has its own working/temporary directory/uri defined by the following parameters. These directories are used for storing Caper's intermediate files and cached big data files for localization on corrsponding storages. e.g. localizing files on GCS to S3 (on --gcp-loc-dir) to run pipeline on AWS instance with GCS files.

| Storage | URI(s)       | Command line parameter    |
|---------|--------------|---------------------------|
| local | Path         | --local-loc-dir               |
| gcs   | gs://      | --gcp-loc-dir        |
| s3    | s3://      | --aws-loc-dir         |
| url   | http(s):// | not available (read-only) |

## Output directory

Output directories are defined similarly as temporary ones. Those are actual output directories (called `cromwell_root`, which is `cromwell-executions/` by default) where Cromwell's output are actually written to.

| Storage | URI(s)       | Command line parameter    |
|---------|--------------|---------------------------|
| local | Path         | --local-out-dir               |
| gcs   | gs://      | --gcp-out-dir        |
| s3    | s3://      | --aws-out-dir         |
| url   | http(s):// | not available (read-only) |

Workflow's final output file `metadata.json` will be written to each workflow's directory (with workflow UUID) under this output directory.

### Inter-storage transfer

Inter-storage transfer is done by keeping source's directory structure and appending to target storage temporary directory. For example of the following temporary directory settings for each backend,

| Storage | Command line parameters                              |
|---------|------------------------------------------------------|
| local | --local-loc-dir /scratch/user/caper_tmp             |
| gcs   | --gcp-loc-dir gs://my_gcs_bucket/caper_tmp |
| s3    | --aws-loc-dir s3://my_s3_bucket/caper_tmp   |

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

> **WARNING**: Please keep your local temporary directory **SECURE**. Caper writes temporary files (`backend.conf`, `inputs.json`, `workflow_opts.json` and `labels.json`) for Cromwell on `local` temporary directory defined by `--local-loc-dir`. The following sensitive information can be exposed on these directories.

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


## How to override Caper's built-in backend

If Caper's built-in backends don't work as expected on your clusters (e.g. due to different resource settings), then you can override built-in backends with your own configuration file (e.g. `your.backend.conf`). Caper generates a `backend.conf` for built-in backends on a temporary directory.

Find this `backend.conf` first by dry-running `caper run [WDL] --dry-run ...`. For example of a `slurm` backend:
```
$ caper run main.wdl --dry-run
2020-07-07 11:18:13,196|caper.caper_runner|INFO| Adding encode-dcc-1016 to env var GOOGLE_CLOUD_PROJECT
2020-07-07 11:18:13,197|caper.caper_base|INFO| Creating a timestamped temporary directory. /mnt/data/scratch/leepc12/test_caper_tmp/main/20200707_111813_197082
2020-07-07 11:18:13,197|caper.caper_runner|INFO| Localizing files on work_dir. /mnt/data/scratch/leepc12/test_caper_tmp/main/20200707_111813_197082
2020-07-07 11:18:13,829|caper.cromwell|INFO| Validating WDL/inputs/imports with Womtool...
2020-07-07 11:18:16,034|caper.cromwell|INFO| Womtool validation passed.
2020-07-07 11:18:16,035|caper.caper_runner|INFO| launching run: wdl=/mnt/data2/scratch/leepc12/test_wdl1_sub/main.wdl, inputs=None, backend_conf=/mnt/data/scratch/leepc12/test_caper_tmp/main/20200707_111813_197082/backend.conf
```

Find `backend_conf`, make a copy of it and edit it.

```
include required(classpath("application"))
backend {
  default = "slurm"
  providers {

  ...

    slurm {
      config {
        default-runtime-attributes {
          time = 24
        }
        concurrent-job-limit = 1000
        script-epilogue = "sleep 10 && sync"
        filesystems {
          local {
            localization = [
              "soft-link"
              "hard-link"
              "copy"
            ]
            caching {
              check-sibling-md5 = true
              duplication-strategy = [
                "soft-link"
                "hard-link"
                "copy"
              ]
              hashing-strategy = "path+modtime"
            }
          }
        }
        run-in-background = true
        runtime-attributes = """String? docker
String? docker_user
Int cpu = 1
Int? gpu
Int? time
Int? memory_mb
String? slurm_partition
String? slurm_account
String? slurm_extra_param
String? singularity
String? singularity_bindpath
String? singularity_cachedir
"""
        submit = """if [ -z \"$SINGULARITY_BINDPATH\" ]; then export SINGULARITY_BINDPATH=${singularity_bindpath}; fi; \
if [ -z \"$SINGULARITY_CACHEDIR\" ]; then export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi;

ITER=0
until [ $ITER -ge 3 ]; do
    sbatch \
        --export=ALL \
        -J ${job_name} \
        -D ${cwd} \
        -o ${out} \
        -e ${err} \
        ${'-t ' + time*60} \
        -n 1 \
        --ntasks-per-node=1 \
        ${'--cpus-per-task=' + cpu} \
        ${true="--mem=" false="" defined(memory_mb)}${memory_mb} \
        ${'-p ' + slurm_partition} \
        ${'--account ' + slurm_account} \
        ${'--gres gpu:' + gpu} \
        ${slurm_extra_param} \
        --wrap "${if !defined(singularity) then '/bin/bash ' + script
                  else
                    'singularity exec --cleanenv ' +
                    '--home ' + cwd + ' ' +
                    (if defined(gpu) then '--nv ' else '') +
                    singularity + ' /bin/bash ' + script}" \
        && break
    ITER=$[$ITER+1]
    sleep 30
done
"""
        root = "/mnt/data/scratch/leepc12/caper_out"
        exit-code-timeout-seconds = 360
        check-alive = """for ITER in 1 2 3; do
    CHK_ALIVE=$(squeue --noheader -j ${job_id} --format=%i | grep ${job_id})
    if [ -z "$CHK_ALIVE" ]; then if [ "$ITER" == 3 ]; then /bin/bash -c 'exit 1'; else sleep 30; fi; else echo $CHK_ALIVE; break; fi
done
"""
        kill = "scancel ${job_id}"
        job-id-regex = "Submitted batch job (\\d+).*"
      }
      actor-factory = "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory"
    }
  ...

}

...

````

Some part of the script (wrapped in `${}`) is written in WDL. For example, `${true="--mem=" false="" defined(memory_mb)}`, if `memory_mb` is defined it will print `--mem`). For such WDL expressions, you can use any variables defined in `runtime-attributes`.

For example, if your cluster does not allow importing all environment variables (`sbatch --export=ALL` ...)  then you can remove `--export=ALL` from the above script.

There is a retrial logic implemented in this SLURM backend. It retries submitting up to 3 times for some SLURM clusters.
```
ITER=0; until [ $ITER -ge 3 ]; do
...
ITER=$[$ITER+1]; sleep 30; done
```

Also, there is another logic to use Singularity. If `singularity` is not given, then Cromwell will run `/bin/bash ${script}` otherwise this backend will collect some Singularity specific environment variables and finally run `singularity exec --cleanenv --home ${cwd} ${singularity} /bin/bash ${script}`. `${singularity}` is a variable that has singularity image location defined in `runtime-attributes` mentioned above.
```
sbatch ... --wrap "${if defined(singularity) then '' else '/bin/bash ${script} #`} ..."
```

There are some built-in variables (`out`, `err`, `cwd`, `script`, `cpu`, `memory_mb` and `time`) in Cromwell, which are important to keep Cromwell's task running. For example, if you remove `-o ${out}` from the script and Cromwell will fail to find `stdout` on output directory, which will lead to a pipeline failure.

See more [details](https://cromwell.readthedocs.io/en/stable/Configuring/) about a backend configuration file.

Your custom `your.backend.conf` file will override on Caper's existing built-in backend, so keep modified parts (`submit` command line in this example) only in your `your.backend.conf` file.
```
backend {
  default = "slurm"
  providers {
    slurm {
        submit = """sbatch         --export=ALL         -J ${job_name}         -D ${cwd}         -o ${out}         -e ${err}         ${"-t " + time*60}         -n 1         --ntasks-per-node=1         ${true="--cpus-per-task=" false="" defined(cpu)}${cpu}         ${true="--mem=" false="" defined(memory_mb)}${memory_mb}         ${"-p " + slurm_partition}         ${"--account " + slurm_account}         ${true="--gres gpu:" false="" defined(gpu)}${gpu}         ${slurm_extra_param}         --wrap "${if defined(singularity) then '' else             '/bin/bash ${script} #'}             if [ -z \"$SINGULARITY_BINDPATH\" ]; then             export SINGULARITY_BINDPATH=${singularity_bindpath}; fi;             if [ -z \"$SINGULARITY_CACHEDIR\" ]; then             export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi;             singularity exec --cleanenv --home ${cwd}             ${if defined(gpu) then '--nv' else ''}             ${singularity} /bin/bash ${script}" && break
    ITER=$[$ITER+1]; sleep 30; done
    """
    }
  }
}
```

And then run `caper run` with your `your.backend.conf`.
```
$ caper run ... --backend-file your.backend.conf
```


## Caper server heartbeat (running multiple servers)

Caper server writes a heartbeat file (specified by `--server-heartbeat-file`) on every 120 seconds (controlled by `--server-heartbeat-timeout`). This file will contain an IP(hostname)/PORT pair of the running `caper server`.

Example heartbeat file:
```bash
$ cat ~/.caper/default_server_heartbeat
your.hostname.com:8000
```

This heartbeat file is useful when users don't want to find IP(hostname)/PORT of a running `caper server` especially when they `qsub`bed or `sbatch`ed `caper server` on their clusters. For such cases, IP (hostname of node/instance) of the server is later determined after the cluster engine starts the submitted `caper server` job and it's inconvenient for the users to find the IP (hostname) of the running server manually with `qstat` or `squeue` and add it back to Caper's configuration file `~/.caper/default.conf`.

Therefore, Caper defaults to use this heartbeat file (can be disabled by a flag `--no-server-heartbeat`). So if client-side caper functions like `caper list` and `caper metadata` finds this heartbeat file and automatically parse it to get an IP/PORT pair.

However, there can be a conflict if users want to run multiple `caper server`s on the same machine (or multiple machines sharing the same caper configuration directory `~/.caper/` and hence the same default heartbeat file). For such cases, users can disable this heartbeat feature by adding the following line to their configuration file: e.g. `~/.caper/default.conf`.
```bash
no-server-heartbeat=True
```

Then start multiple servers with different port and DB (for example of MySQL). Users should make sure that each server uses a different DB (file or MySQL server port, whatever...) since there is no point of using multiple Caper servers with the same DB. For example of MySQL, users should not forget to spin up multiple MySQL servers with different ports.

```bash
$ caper server --port 8000 --mysql-db-port 3306 ... &
$ caper server --port 8001 --mysql-db-port 3307 ... &
$ caper server --port 8002 --mysql-db-port 3308 ... &
```

Send queries to a specific server.
```bash
$ caper list --port 8000
$ caper list --port 8001
$ caper list --port 8002
```

## Metadata database

If you are not interested in resuming failed workflows skip this section.

Cromwell metadata DB is used for call-caching (re-using outputs from previous workflows). Caper>=0.6 defaults to use `in-memory` DB, whose metadata will be all lost when the Caper process stops.

In order to use call-caching, choose one of the following metadata database types with `--db` or `db=` in your Caper conf file `~/.caper/default.conf`.

1) `mysql` (**RECOMMENDED**): We provide [shell scripts](#mysql-server) to run a MySQL server without root. You need either Docker or Singularity installed on your system.

2) `postgresql` (experimental): We don't provide a method to run PostgreSQL server and initialize it correctly for Crowmell. See [this](https://cromwell.readthedocs.io/en/stable/Configuring/) for details.

3) `file` (**UNSTABLE**, not recommended): This is Cromwell's built-in [HyperSQL DB file mode](#file-database). Caper<0.6 defaulted to use it but a file DB turns out to be very unstable and get corrupted easily.

## MySQL database

We provide [shell scripts](bin/run_mysql_server_docker.sh) to run a MySQL server in a container with docker/singularity. Once you have a running MySQL server, add the followings to Caper's conf file `~/.caper/default.conf`. You may need to change the port number if it conflicts.

```
db=mysql
mysql-db-port=3306
```

1) docker

	Ask your admin to add you to the `docker` group or if you are root then install Docker, create a group `docker` and add yourself to the group `docker`.

	```bash
	$ sudo apt-get install docker.io
	$ sudo groupadd docker
	$ sudo usermod -aG docker $USER
	```

	**RE-LOGIN** and check if Docker `hello-world` works.

	```bash
	$ docker run hello-world
	```

	Run the following command line. `PORT` and `CONTAINER_NAME` are optional. MySQL server will run in background.

	```bash
	$ run_mysql_server_docker.sh [DB_DIR] [PORT]
	```

	If you see any conflict in `PORT` or `CONTAINER_NAME`, then try with higher `PORT` or different `CONTAINER_NAME` (`mysql_cromwell` by default).

	Example conflict in `PORT`. Try with `3307` or higher.
	```
	[PORT] (3306) already taken.
	```

	Example conflict in `CONTAINER_NAME`. Try with `mysql_cromwell2`.
	```bash
	docker: Error response from daemon: Conflict. The container name "/mysql_cromwell" is already in use by container 0584ec7affed0555a4ecbd2ed86a345c542b3c60993960408e72e6ea803cb97e. You have to remove (or rename) that container to be able to reuse that name..
	```

	Check if MySQL server is running.
	```bash
	$ docker ps  # find your MySQL docker container
	```

	To stop/kill a running MySQL server,
	```bash
	$ docker stop [CONTAINER_NAME]  # you can also use a container ID found in the above cmd
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

	Run the following command line. `PORT` and `CONTAINER_NAME` are optional. MySQL server will run in background as a Singularity instance.

	```bash
	$ run_mysql_server_singularity.sh [DB_DIR] [PORT] [CONTAINER_NAME]
	```

	If you see any conflict in `PORT` or `CONTAINER_NAME`, then try with higher `PORT` or different `CONTAINER_NAME` (`mysql_cromwell` by default).

	Example conflict in `PORT`. Try with `3307` or higher.
	```
	[PORT] (3306) already taken.
	```

	Example conflict in `CONTAINER_NAME`. Try with `mysql_cromwell2`.
	```
	ERROR: A daemon process is already running with this name: mysql_cromwell
	ABORT: Aborting with RETVAL=255
	```

	To stop/kill a running MySQL server.
	```bash
	$ singularity instance list  # find your MySQL singularity container
	$ singularity instance stop [CONTAINER_NAME]
	```

## PostgreSQL database

Add the followings to Caper's conf file `~/.caper/default.conf`. You may need to change the port number if it conflicts.
```
db=postgresql
postgresql-db-port=5432
```

You do not need superuser privilege to make your own database once you have PostgreSQL installed on your system. Ask your admin to install it.

Make sure to match `DB_PORT`, `DB_NAME`, `DB_USER` and `DB_PASSWORD` with Caper's parameters `--postgresql-db-port`, `--postgresql-db-name`, `--postgresql-db-user`, and `--postgresql-db-password`. You can also define them in  `~/.caper/default.conf`.

```bash
# make sure to match those variables with corresponding Caper's parameters.
$ DB_PORT=5432
$ DB_NAME=cromwell
$ DB_USER=cromwell
$ DB_PASSWORD=cromwell

# initialize PostgreSQL server with a specific data path
# actual data will be stored on directory $DB_FILE_PATH
$ DB_FILE_PATH=my_postgres
$ initdb -D $DB_FILE_PATH -U $USER

# start PostgreSQL server with a specific port
$ DB_LOG_FILE=pg.log
$ pg_ctl -D $DB_FILE_PATH -o "-F -p $DB_PORT" -l $DB_LOG_FILE start

# create DB for Cromwell
$ createdb $DB_NAME

# add extension for Cromwell
$ psql -d $DB_NAME -c "create extension lo;"

# make a role (user)
$ psql -d $DB_NAME -c "create role $DB_USER with superuser login password $DB_PASSWORD"
```


## File database

Caper defaults to use file database to store workflow's metadata. Such metadata database is necessary for restarting a workflow from where it left off (Cromwell's call-caching feature). Default database location is on `local_out_dir` in the configuration file `~/.caper/default.conf` or CWD where you run Caper run/server command line. Its default filename prefix is `caper-db_[WDL_BASENAME].[INPUT_JSON_BASENAME]`. Therefore,
unless you explicitly define `file-db` in your configuration file you can simply resume a failed workflow with the same command line used for starting a new pipeline.

File database cannot be accessed with multiple processes. So defining `file-db` in  `~/.caper/default.conf` can result in DB connection timeout error. Define `file-db` in  `~/.caper/default.conf` only when you run a Caper server (with `caper server`) and submit workflows to it.
```
db=file
file-db=/YOUR/FILE/DB/PATH/PREFIX
```


## Profiling/monitoring resources on Google Cloud

A workflow ran with Caper>=1.2.0 on `gcp` backend has a monitoring log (`monitoring.log`) by default on each task's execution directory. This log file includes useful resources data on an instance like used memory, used disk space and total cpu percentage.

`caper gcp_monitor` recursively parses such monitoring log files and show statistics of them in a tab-separated table. `caper gcp_monitor` can take `metadata.json` file URI or a workflow ID if there is a running `caper server`. `--json-format` is optional to print out detailed outputs in a JSON format.

```bash
$ caper gcp_monitor METADATA_JSON_FILE_OR_WORKFLOW_ID ... --json-format
```

For further analysis on resource data, use `caper gcp_res_analysis`. `--plot-pdf` is optional to make a multipage PDF file with scatter plots.
```bash
$ caper gcp_res_analysis METADATA_JSON_FILE_OR_WORKFLOW_ID ... --plot-pdf [PLOT_PDF_PATH]
```

Define task's input file variables to limit analysis on specific tasks and input variables. Use `--in-file-vars-def-json` to define it.
 Example JSON files can be found at the following URLs:
- ENCODE ATAC-seq pipeline: [Result JSON](https://storage.googleapis.com/caper-data/gcp_resource_analysis/in_file_vars_json/atac.json)
- ENCODE ChIP-seq pipeline: [Result JSON](https://storage.googleapis.com/caper-data/gcp_resource_analysis/in_file_vars_json/chip.json)

Example plots:
- ENCODE ATAC-seq pipeline: [Plot PDF](https://storage.googleapis.com/caper-data/gcp_resource_analysis/example_plot/atac.pdf)


## Singularity and Docker Hub pull limit

If you provide a Singularity image based on docker `docker://` then Caper will locally build a temporary Singularity image (`*.sif`) under `SINGULARITY_CACHEDIR` (defaulting to `~/.singularity/cache` if not defined). However, Singularity will blindly pull from DockerHub to quickly reach [a daily pull limit](https://www.docker.com/increase-rate-limits). It's recommended to use Singularity images from `shub://` (Singularity Hub) or `library://` (Sylabs Cloud).



## How to customize resource parameters for HPCs

Each HPC backend (`slurm`, `sge`, `pbs` and `lsf`) has its own resource parameter. e.g. `slurm-resource-param`. Find it in Caper's configuration file (`~/.caper/default.conf`) and edit it. For example, the default resource parameter for SLURM looks like the following:
```
slurm-resource-param=-n 1 --ntasks-per-node=1 --cpus-per-task=${cpu} ${if defined(memory_mb) then "--mem=" else ""}${memory_mb}${if defined(memory_mb) then "M" else ""} ${if defined(time) then "--time=" else ""}${time*60} ${if defined(gpu) then "--gres=gpu:" else ""}${gpu}
```
This should be a one-liner with WDL syntax allowed in `${}` notation. i.e. Cromwell's built-in resource variables like `cpu`(number of cores for a task), `memory_mb`(total amount of memory for a task in MB), `time`(walltime for a task in hour) and `gpu`(name of gpu unit or number of gpus) in `${}`. See https://github.com/openwdl/wdl/blob/main/versions/1.0/SPEC.md for WDL syntax. This line will be formatted with actual resource values by Cromwell and then passed to the submission command such as `sbatch` and `qsub`.

Note that Cromwell's implicit type conversion (`WomLong` to `String`) seems to be buggy for `WomLong` type memory variables such as `memory_mb` and `memory_gb`. So be careful about using the `+` operator between `WomLong` and other types (`String`, even `Int`). For example, `${"--mem=" + memory_mb}` will not work since `memory_mb` is `WomLong` type. Use `${"if defined(memory_mb) then "--mem=" else ""}{memory_mb}${"if defined(memory_mb) then "mb " else " "}` instead. See https://github.com/broadinstitute/cromwell/issues/4659 for details.
