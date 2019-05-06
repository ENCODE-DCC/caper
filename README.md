# Cromweller

Cromweller is a wrapper Python package for [Cromwell](https://github.com/broadinstitute/cromwell/).

## Introduction

Cromweller is based on Unix and cloud platform CLIs (`wget`, `curl`, `gsutil` and `aws`) and provides easier way of running Cromwell server/run by automatically composing necessary input files for Cromwell. Also, Cromweller supports easy automatic file transfer between local/cloud storages (local path, `s3://`, `gs://` and `http(s)://`). You can use these URIs in input JSON file or for a WDL file itself.

## Features

* **Similar CLI**: Cromweller has a similar command line interface as Cromwell.

	For run mode,
	```bash
	$ cromweller run my.wdl -i input.json -o workflow.opts.json -l labels.json -p imports.zip
	```
	For server mode,
	```bash
	$ cromweller server
	```

* **Built-in backends**: You don't need your own backend configuration file. Cromweller provides the following built-in backends. You can still use your own backend file with `--backend-file`. Configuration in this file will override anything defined in built-in ones.

	| Backend | Description           |
	|---------|-----------------------|
	| `Local` | Default local backend |
	| `gcp`   | Google Cloud Platform |
	| `aws`   | Amazon Web Service    |
	| `slurm` | SLURM                 |
	| `sge`   | Sun GridEngine        |
	| `pbs`   | PBS                   |

* **Automatic transfer between local/cloud storages**: For example, the following command line works. Such auto-transfer is done magically by correctly defining [temporary directory](#temporary-storage) for each stroage.
	```bash
	$ cromweller run gs://some/where/my.wdl -i s3://over/here/input.json
	```

* **Deepcopy for input JSON file**: You may want to have all data files defined in your input JSON file automatically transferred to a target remote storage. Deepcopying is allowed for several text file extensions (`.json`, `.tsv` and `.csv`). Any string value with absolute path/URI in your input JSON will be recursively copied to a target backend storage. For example of the above command.

	```bash
	$ cromweller run gs://some/where/my.wdl -i s3://over/here/input.json --deepcopy -b gcp
	```
	Let's say that you specified a target backend as `gcp` (Google Clooud Platform) then corresponding target storage will be `gs://` (Google Cloud Storage) and your input JSON (`s3://over/here/input.json`) looks like the following:
	```json
	{
		"txt_file": "s3://over/here/info.json",
		"big_file": "http://your.server.com/big.bigwig",
		"hello" : {
			"world" : ["gs://some/where/hello.tsv"]
		}
	}
	```
	Then Cromweller looks at all files with extensions `.json` and `.tsv` first and recursively transfer all files defined in it to a target storage. If those files are already on a target storage then transfer will be skipped. If anything is updated to those text file then Cromwellers make a copy of that file on the same directory with a suffix `.gcs`. For example, Cromweller makes a copy of `s3://over/here/info.json` as `s3://over/here/info.gcs.json`.

	All other files with an absolute path/URI (`http://your.server.com/big.bigwig`) will be transferred to your [temporary directory](#temporary-directory) on `gs://`.

* **Docker/Singularity integration**: You can define a container image (Docker or Singularity) to run all tasks in a WDL workflow. Simply define it in command line arguments or directly in your WDL as [comments](#wdl-customization). Then `docker` or `singularity` attribute will be added to `runtime {}` section of all of tasks in a WDL so that Cromwell runs in a Docker mode or Singularity mode.
	```bash
	$ cromweller run http://my.web.server.com/my.wdl --singularity docker://ubuntu:latest
	$ cromweller submit s3://over/there/your.wdl --docker ubuntu:latest
	```
* **MySQL database integration**: You can spin up a Cromwell server with your own port (`8000` by default) with the following simple command line. This works for `run` mode too.
	```bash
	$ cromweller server --port 8001	
	```
	You can also connect to a remote/local MySQL database. 
	```bash
	$ cromweller server --mysql-db-ip 4.3.2.1 --mysql-db-port 3307 --mysql-db-user cromwell --mysql-db-password some-secret-key
	```	
	You can also submit a workflow to a remote Cromwell server (`localhost` by default).
	```bash
	$ cromweller submit --ip 1.2.3.4 --port 8001 your.wdl ...
	```
	> **WARNING**: Before running a Cromwell server. See [security warnings](https://cromwell.readthedocs.io/en/develop/developers/Security/).

* **One configuration file for all**: You may not want to repeat writing the same command line parameters for every pipeline run. Define them in a configuration file at `~/.cromweller/default.conf` and forget about it.

* **One server for six backends**: Once authentication/configuration for cloud CLIs (`gcloud` and `aws`) are correctly set up, then your Cromwell server can submit job to any backend specified with `-b` or `--backend`.
	```bash
	$ cromweller submit -b gcp s3://maybe/here/your.wdl
	```
	```bash
	$ cromweller submit -b aws gs://maybe/there/my.wdl
	```

* **Cluster engine support**: SLURM, SGE and PBS are currently supported. To run a Cromwell server directly submitting/monitoring jobs to SLURM. Make sure to keep your server process alive by using `nohup`, `screen` or `tmux`.

	You can specify default backend for your Cromwell server.
	```bash
	$ cromweller server -b slurm
	```
	Submit to the Cromwell server instead of running `sbatch`. This workflow will run on a `slurm` backend.
	```bash
	$ cromweller submit your.wdl -i your.inputs.json
	```
	You can also directly `sbatch` Cromweller. Use `Local` mode.
	```bash
	$ sbatch cromweller run -b Local your.wdl
	```

* **Easy workflow management**: Find all workflows submitted to a Cromwell server by workflow IDs (UUIDs) or `str_label` (special label for a workflow submitted by Cromweller `submit` and `run`). You can define multiple keywords with wildcards (`*` and `?`) to search for matching workflows. Abort, release hold, retrieve metadata JSON for them.

	Example:
	```bash
	$ cromweller list
	id      status  name    str_label       submission
	f12526cb-7ed8-4bfa-8e2e-a463e94a61d0    Succeeded       test_cromweller_uri     None    2019-05-04T17:56:30.173-07:00
	66dbb4a5-2077-4db8-bc83-6a5d36495037    Aborted test_cromweller_uri     None    2019-05-04T17:55:12.902-07:00
	9a29f2ef-9c89-460c-9ebe-ab174eff135f    Succeeded       sub_c.c None    None
	970b3640-ccdd-4b5a-82b3-f4a32252e95a    Succeeded       sub_a.a None    None
	0787a2b8-49a0-4acb-b6b3-338c697f1d90    Succeeded       main    None    2019-05-04T17:53:28.045-07:00
	5917a17d-3156-41c7-93d9-545d8cdde3c0    Failed  None    None    2019-05-04T17:51:17.239-07:00	
	```

	```bash
	$ cromweller abort 66dbb4a5-2077-4db8-bc83-6a5d3649503 test_cromweller_uri
	```

	```bash
	$ cromweller metadata 0787a2b8-49a0-4acb-b6b3-338c697f1d90 970b3640-ccdd-4b5a-82b3-f4a32252e95a
	```

* **Automatic subworkflow packing**: Cromweller automatically creates an archive (`imports.zip`) of all imports and send it to Cromwell server/run.

	For example, your WDL and its imports are n a Google Cloud Storage bucket.
	```bash
	gs://every/where/main.wdl
	gs://every/where/a/b/c/d.wdl
	gs://every/where/e/f/g.wdl
	```

	`main.wdl` looks like the following:
	```python
	import "a/b/c/d.wdl" as sub_d
	import "e/f/g.wdl" as sub_g
	import "http://some.where.com/z.wdl" as sub_z	
	```

	If you run `gs://every/where/main.wdl` then Cromweller looks `gs://every/where/a/b/c/d.wdl` and `gs://every/where/e/f/g.wdl` and pack them as a ZIP file and send it to Cromwell server/run. You don't need to add such ZIP file as `-p` or `--imports` in the command line.
	```bash
	$ cromweller run gs://every/where/main.wdl
	```

	You can still use your own ZIP file as `-p` in the command line arguments then Cromweller's automatic subworkflow packing will be disabled.

## Usage

```bash
usage: cromweller.py [-h] [-c FILE]
                     {run,server,submit,abort,unhold,list,metadata} ...

positional arguments:
  {run,server,submit,abort,unhold,list,metadata}
    run                 Run a single workflow without server
    server              Run a Cromwell server
    submit              Submit a workflow to a Cromwell server
    abort               Abort running/pending workflows on a Cromwell server
    unhold              Release hold of workflows on a Cromwell server
    list                List running/pending workflows on a Cromwell server
    metadata            Retrieve metadata JSON for workflows from a Cromwell
                        server

optional arguments:
  -h, --help            show this help message and exit
  -c FILE, --conf FILE  Specify config file
```

## Installation

We will add PIP installation later. Until then git clone it and manually add `cromweller` to your environment variable `PATH` in your BASH startup scripts (`~/.bashrc`).

```bash
$ git clone https://github.com/ENCODE-DCC/cromweller
$ echo "export PATH=\"\$PATH:$PWD/cromweller\"" >> ~/.bashrc
```

## Configuration file

You can avoid repeatedly defining the same parameters in your command line arguments by using a configuration file. For example, you can define `out_dir` and `tmp_dir` in your configuration file instead of defining them in command line arguments.
```
$ cromweller run your.wdl --out-dir [LOCAL_OUT_DIR] --tmp-dir [LOCAL_TMP_DIR]
```

Equivalent settings in a configuration file. Make sure to replace dashes (`-`) with underscores (`_`).
```
[defaults]
out_dir=[LOCAL_OUT_DIR]
tmp_dir=[LOCAL_TMP_DIR]
```

Run with a configuration file.
```
$ cromweller -c [YOUR_CONF_FILE] run your.wdl
```

You can also have a default configuration file at `~/.cromweller/default.conf`. Cromweller will try to find this path first and if it exists then will automatically use it as a default configuration file.

We provide an example configuration file `default.conf`.

Create Cromweller's directory on your `HOME`. Copy the example configuration file (`default.conf`) to it. Uncomment any parameter to activate and define it.
```
$ mkdir -p ~/.cromweller
$ cd cromweller  # make sure that you are on Cromweller's git directory
$ cp default.conf ~/.cromweller
```

## How to configure for each backend

We recommend to use a default configuration file explained in the section [Configuration file](#configuration-file).

There are six backends supported by Cromweller. Each backend must run on its designated storage. To use cloud backends (`gcp` and `aws`) and corresponding cloud storages (`gcs` and `s3`), you must install cloud platform's CLIs ([`gsutil`](https://cloud.google.com/storage/docs/gsutil_install) and [`aws`](https://docs.aws.amazon.com/cli/latest/userguide/install-linux.html)). You also need to configure these CLIs for authentication. See configuration instructions for [GCP](docs/conf_gcp.md) and [AWS](docs/conf_aws.md) for details.

| Backend | Description          | Storage | Required parameters                                                     |
|---------|----------------------|---------|-------------------------------------------------------------------------|
|`gcp`    |Google Cloud Platform | `gcs`   | `--gcp-prj`, `--out-gcs-bucket`, `--tmp-gcs-bucket`                     |
|`aws`    |AWS                   | `s3`    | `--aws-batch-arn`, `--aws-region`, `--out-s3-bucket`, `--tmp-s3-bucket` |
|`Local`  |Default local backend | `local` | `--out-dir`, `--tmp-dir`                                                |
|`slurm`  |local SLURM backend   | `local` | `--out-dir`, `--tmp-dir`, `--slurm-partition` or `--slurm-account`      |
|`sge`    |local SGE backend     | `local` | `--out-dir`, `--tmp-dir`, `--sge-pe`                                    |
|`pds`    |local PBS backend     | `local` | `--out-dir`, `--tmp-dir`                                                |

### Google Cloud Platform (`gcp`)

Make sure that you already configured `gcloud` and `gsutil` correctly and passed authentication for them (e.g. `gcloud auth login`). You need to define `--gcp-prj`, `--out-gcs-bucket` and `--tmp-gcs-bucket` in your command line arguments or in your configuration file.
```
$ cromweller run my.wdl -b gcp --gcp-prj [GOOGLE_PRJ_NAME] --out-gcs-bucket [GS_OUT_DIR] --tmp-gcs-bucket [GS_TMP_DIR]
```

### Google Cloud Platform (`gcp`)

Make sure that you already configured `aws` correctly and passed authentication for them (e.g. `aws configure`). You need to define `--aws-batch-arn`, `--aws-region`, `--out-s3-bucket` and `--tmp-s3-bucket` in your command line arguments or in your configuration file.
```
$ cromweller run my.wdl -b aws --aws-batch-arn [AWS_BATCH_ARN] --aws-region [AWS_REGION] --out-s3-bucket [S3_OUT_DIR] --tmp-s3-bucket [S3_TMP_DIR]
```

### All local backends (`Local`, `slurm`, `sge` and `pbs`)

You need to define `--out-dir` and `--tmp-dir` in your command line arguments or in your configuration file.
```
$ cromweller run my.wdl -b [BACKEND] --out-dir [OUT_DIR] --tmp-dir [TMP_DIR]
```

### SLURM backend (`slurm`)

You need to define `--slurm-account` or `--slurm-partition` in your command line arguments or in your configuration file.
> **WARNING: If your SLURM cluster does not require you to specify a partition or an account then skip them.
```
$ cromweller run my.wdl -b slurm --slurm-account [YOUR_SLURM_ACCOUNT] --slurm-partition [YOUR_SLURM_PARTITON]
```

### SGE backend (`sge`)

You need to define `--sge-pe` in your command line arguments or in your configuration file.
> **WARNING: If you don't have a parallel environment (PE) then ask your SGE admin to add one.
```
$ cromweller run my.wdl -b sge --sge-pe [YOUR_PE]
```

### PBS backend (`pbs`)

There are no required parameters for PBS backend.
```
$ cromweller run my.wdl -b pbs
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
| `local` | `--tmp-dir /scratch/user/cromweller_tmp`             |
| `gcs`   | `--tmp-gcs-bucket gs://my_gcs_bucket/cromweller_tmp` |
| `s3`    | `--tmp-s3-bucket s3://my_s3_bucket/cromweller_tmp`   |

A local file `/home/user/a/b/c/hello.gz` can be copied (on demand) to 

| Storage | Command line parameters                                      |
|---------|--------------------------------------------------------------|
| `gcs`   | `gs://my_gcs_bucket/cromweller_tmp/home/user/a/b/c/hello.gz` |
| `s3`    | `s3://my_s3_bucket/cromweller_tmp/home/user/a/b/c/hello.gz`  |

File transfer is done by using the following command lines using various CLIs:

* `gsutil -q cp -n [SRC] [TARGET]`
* `aws s3 cp '--only-show-errors' [SRC] [TARGET]`
* `wget --no-check-certificate -qc [URL_SRC] -O [LOCAL_TARGET]`
* `curl -f [URL_SRC] | gsutil -q cp -n - [TARGET]`

> **WARNING**: Cromweller does not ensure a fail-safe file transfer when it's interrupted by user or system. Also, there can be race conditions if multiple users try to access/copy files. This will be later addressed in the future release. Until then DO NOT interrupt file transfer until you see the following `copying done` message.

Example:
```
[CromwellerURI] copying from gcs to local, src: gs://encode-pipeline-test-runs/test_wdl_imports/main.wdl
[CromwellerURI] copying done, target: /srv/scratch/leepc12/cromweller_tmp_dir/encode-pipeline-test-runs/test_wdl_imports/main.wdl
```

### Security

> **WARNING**: Please keep your local temporary directory **SECURE**. Cromweller writes temporary files (`backend.conf`, `inputs.json`, `workflow_opts.json` and `labels.json`) for Cromwell on `local` temporary directory defined by `--tmp-dir`. The following sensitive information can be exposed on these directories.

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

> **Optional**: Add the following comments to your WDL then Cromweller will be able to find an appropriate container image for your WDL. Then you don't have to define them in command line arguments everytime you run a pipeline.

```bash
#CROMWELLER singularity docker://ubuntu:latest
#CROMWELLER docker ubuntu:latest
```

## Requirements

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
