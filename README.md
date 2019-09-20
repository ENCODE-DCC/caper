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

Test-run Caper. This will also auto-generate a default configuration file for Caper (`~/.caper/default.conf`).
```
$ caper
```

If you see an error message like `command unknown` then add the following line to the bottom of `~/.bashrc` and re-login.
```
export PATH=$PATH:~/.local/bin
```

## Configuration for Amazon Web Service (AWS)

[Configure for AWS](docs/conf_aws.md) first. Create a small instance on AWS. SSH to it and Install Caper there. Edit/create `~/.caper/default.conf` like the following. Remove everything else from it. Define AWS Batch ARN `awd-batch-arn`, AWS region `aws-region` and an output bucket address `out-s3-bucket`. A file-based Cromwell database grows quickly to reach several GBs. Define `file-db` as a path on a mounted large file system.
```
[defaults]
backend=aws
#file-db=[PATH_FOR_CROMWELL_METADATA_DB]
#tmp-dir=[TMP_DIR_FOR_INTER_STORAGE_FILE_TRANSFER]
aws-batch-arn=[ARN_FOR_YOUR_AWS_BATCH]
aws-region=[YOUR_AWS_REGION]
out-s3-bucket=s3://[YOUR_OUTPUT_ROOT_BUCKET]/[ANY]/[WHERE]

1) Caper run mode (for a single workflow)
	```
	$ caper submit [WDL] -i [INPUT_JSON]
	```

2) Caper server/client mode (for multiple workflows)
	Run a caper server. Use `screen`, `tmux` or `nohup` to keep this session alive.
	```
	$ caper server
	```
	Open another SSH session and submit a workflow to the server.
	```
	$ caper submit [WDL] -i [INPUT_JSON]
	```

## Configuration for Google Cloud Platform (GCP)

[Configure for gcloud and gsutil](docs/conf_gcp.md). Create a small instance on your project. SSH to it and Install Caper there. Edit/create `~/.caper/default.conf` like the following. Remove everything else from it. Define Google Cloud Platform Project `gcp-prj` and an output bucket address `out-gcs-bucket`.
```
[defaults]
backend=gcp
gcp-prj=[YOUR_GCP_PROJECT_NAME]
out-gcs-bucket=gs://[YOUR_OUTPUT_ROOT_BUCKET]/[ANY]/[WHERE]
```

## Configuration for general computer

1) Edit `~/.caper/default.conf` like the following. Remove everything else from it.
2) Define an output directory `out-dir`.
```
[defaults]
backend=local
out-dir=[YOUR_OUTPUT_DIRECTORY]
```

## Configuration for Stanford Sherlock
1) Edit `~/.caper/default.conf` like the following. Remove everything else from it.
2) Define an output directory `out-dir` and SLURM partition `slurm-partition`.
```
[defaults]
backend=slurm
slurm-partition=[SHERLOCK_SLURM_PARTITION]
out-dir=[YOUR_OUTPUT_DIRECTORY]
```

## Configuration for Stanford SCG
1) Edit `~/.caper/default.conf` like the following. Remove everything else from it.
2) Define an output directory `out-dir` and SLURM account `slurm-account`.
```
[defaults]
backend=slurm
slurm-account=[SCG_SLURM_ACCOUNT]
out-dir=[YOUR_OUTPUT_DIRECTORY]
```

## Configuration for general SGE clusters

Edit `~/.caper/default.conf` like the following. Remove everything else from it. Define an output directory `out-dir`. Uncomment/define SGE queue settings according to your cluster's policy.
```
[defaults]
backend=slurm
sge-pe=[YOUR_PARALLEL_ENVIRONMENT]
#sge-queue=[YOUR_SGE_QUEUE]
out-dir=[YOUR_OUTPUT_DIRECTORY]

port=8010
```

Run Caper. Make sure to keep your SSH session alive.

Deepcopy is activate by default and URIs (`http(s)://`, `s3://`, `gs://`, ...) in your input JSON will be recursively copied into a target storage for a corresponding chosen backend. For example, GCS bucket (`gs://`) for GCP backend (`gcp`).

```bash
$ caper run [WDL] -i [INPUT_JSON]
```

Or run a Cromwell server with Caper. Make sure to keep server's SSH session alive.

```bash
$ caper server
```

Then submit a workflow to the server.
```bash
$ caper submit [WDL] -i [INPUT_JSON]
```

On HPCs (e.g. Stanford Sherlock and SCG), you can run Caper with a Singularity container if that is [defined inside `WDL`](DETAILS.md/#wdl-customization). For example, ENCODE [ATAC-seq](https://github.com/ENCODE-DCC/atac-seq-pipeline/blob/master/atac.wdl#L5) and [ChIP-seq](https://github.com/ENCODE-DCC/chip-seq-pipeline2/blob/master/chip.wdl#L5) pipelines.
```bash
$ caper run [WDL] -i [INPUT_JSON] --singularity
```

Or specify your own Singularity container.
```bash
$ caper run [WDL] -i [INPUT_JSON] --singularity [YOUR_OWN_SINGULARITY_IMAGE_URI]
```

Similarly for Docker.
```bash
$ caper run [WDL] -i [INPUT_JSON] --docker
```

```bash
$ caper run [WDL] -i [INPUT_JSON] --docker [YOUR_OWN_DOCKER_IMAGE_URI]
```

## HPCs

> **Run mode on HPCs**: We don't recommend to run Caper on a login node. Caper/Cromwell will be killed while building a local Singularity image or deepcopying remote files. Also Cromwell is a Java application which is not lightweight.

Install Java and Singularity locally or load cluster's Java module.
```bash
$ module load java
$ module load singularity
```

You are not submitting workflows to your cluster engine (e.g. SLURM). You are submitting Caper to the engine and Caper will work as another job manager which `will `sbatch` and `qsub` subtasks defined in WDL. So don't give Caper too much resource. one CPU, 1GB RAM and long enough walltime will be enough.

For Caper run mode, you cannot `caper run` multiple workflows with a single `--file-db` because they will try to write on the same DB file. Give each workflow a different `--file-db`. `--file-db` is important when you want to resume your failed workflows and automatically re-use outputs from previous workflows.

1) SLURM: 1 cpu, 2GB of RAM and 7 days of walltime. You may need to define a partition of an account according to your cluster's SLURM configuration. Then define them for `sbatch` (not for `caper`).

	```bash
	$ sbatch --export=ALL -n 1 --mem 2G -t 7-0 --wrap "caper run [WDL] -i [INPUT_JSON]"
	```

2) SGE: 1 cpu, 2GB of RAM and 7 days of walltime.

	```bash
	$ echo "caper run [WDL] -i [INPUT_JSON]" | qsub -l h_rt=144:00:00 -l h_vmem=2G
	```

> **Server/client mode on HPCs**: We recommend to run a server on a non-login node with at least one CPU, 2GB RAM and long enough walltime. Take IP address of your compute node and update your default configuration file with it. If there is any conflicting port, then change port in your configuration file. If default port 8000 is already taken the try with another port.

For Caper server mode, you can submit multiple workflows with a single `--file-db`.

1) SLURM: 1 cpu, 12GB of RAM and 7 days of walltime. You may need to define a partition `-p` of an account `--account` according to your cluster's SLURM configuration. Then define them for `sbatch` (not for `caper`).

	```bash
	$ sbatch --export=ALL -n 1 --mem 10G -t 7-0 --wrap "caper server"

	# get hostname of Cromwell server 
	$ squeue -u $USER
	```

	For example on Stanford Sherlock. Hostname is `sh-102-32` for this example.
	```bash
	[leepc12@sh-ln07 login ~]$ sbatch --export=ALL -n 1 --mem 10G -t 7-0 -p akundaje -o ~/caper_server.o -e ~/caper_server.e --wrap "caper server"
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
$ caper submit [WDL] -i [INPUT_JSPN] --ip [SERVER_HOSTNAME]
```

# DETAILS

See [details](DETAILS.md).
