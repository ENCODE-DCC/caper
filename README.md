# Caper

Caper (Cromwell Assisted Pipeline ExecutoR) is a wrapper Python package for [Cromwell](https://github.com/broadinstitute/cromwell/).

## Introduction

Caper is based on Unix and cloud platform CLIs (`curl`, `gsutil` and `aws`) and provides easier way of running Cromwell server/run modes by automatically composing necessary input files for Cromwell. Also, Caper supports easy automatic file transfer between local/cloud storages (local path, `s3://`, `gs://` and `http(s)://`). You can use these URIs in input JSON file or for a WDL file itself.

## Installation

1) Make sure that you have Java (>= 1.8) installed on your system.

	```bash
	$ java -version
	```

2) Make sure that you have `python3`(> 3.4.1) installed on your system. Use `pip` to install Caper.

	```bash
	$ pip install caper
	```

	If `pip` doesn't work then `git clone` this repo and manually add `bin/` to your environment variable `PATH` in your BASH startup scripts (`~/.bashrc`).

	```bash
	$ git clone https://github.com/ENCODE-DCC/caper
	$ echo "export PATH=\"\$PATH:$PWD/caper/bin\"" >> ~/.bashrc
	```

3) Test-run Caper.

	```bash
	$ caper
	```

4) If you see an error message like `caper: command not found` then add the following line to the bottom of `~/.bashrc` and re-login.

	```bash
	export PATH=$PATH:~/.local/bin
	```

5) Choose a platform from the following table and initialize Caper. This will create a default Caper configuration file `~/.caper/default.conf`, which have only required parameters for each platform. There are special platforms for Stanford Sherlock/SCG users.
	```bash
	$ caper init [PLATFORM]
	```

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

6) Edit `~/.caper/default.conf` according to your chosen platform. Find instruction for each item in the following table.
	> **IMPORTANT**: ONCE YOU HAVE INITIALIZED THE CONFIGURATION FILE `~/.caper/default.conf` WITH YOUR CHOSEN PLATFORM, THEN IT WILL HAVE ONLY REQUIRED PARAMETERS FOR THE CHOSEN PLATFORM. DO NOT LEAVE ANY PARAMETERS UNDEFINED OR CAPER WILL NOT WORK CORRECTLY.

	**Parameter**|**Description**
	:--------|:-----
	tmp-dir | **IMPORTANT**: A directory to store all cached files for inter-storage file transfer. DO NOT USE `/tmp`.
	slurm-partition | SLURM partition. Define only if required by a cluster. You must define it for Stanford Sherlock.
	slurm-account | SLURM partition. Define only if required by a cluster. You must define it for Stanford SCG.
	sge-pe | Parallel environment of SGE. Find one with `$ qconf -spl` or ask you admin to add one if not exists.
	aws-batch-arn | ARN for AWS Batch.
	aws-region | AWS region (e.g. us-west-1)
	out-s3-bucket | Output bucket path for AWS. This should start with `s3://`.
	gcp-prj | Google Cloud Platform Project
	out-gcs-bucket | Output bucket path for Google Cloud Platform. This should start with `gs://`.
	file-db | Path for file DB to use Cromwell's call-caching (re-using previous workflow's output).

7) To use Caper on Google Cloud Platform (GCP), [configure for GCP](docs/conf_gcp.md). To use Caper on Amazon Web Service (AWS), [configure for AWS](docs/conf_aws.md).

## Output directory

> **IMPORTANT**: Unless you are running Caper on cloud platforms (`aws`, `gcp`) and `--out-dir` is not explicitly defined, all outputs will be written to a current working directory where you run `caper run` or `caper server`.

Therefore, change directory first and run Caper there.

```bash
$ cd [OUTPUT_DIR]
```

## Activating Conda environment

If you want to use your Conda environment for Caper, then activate your Conda environment right before running/submitting `caper run` or `caper server`.
```bash
$ conda activate [PIPELINE_CONDA_ENV] 
$ caper run ...
$ sbatch ... --wrap "caper run ..."
```

## Running pipelines on Stanford Sherlock

Submit a Caper leader job (`caper run`) to SLURM. For a partition `-p [SLURM_PARTITON]`, make sure that you use the same SLURM partition (`slurm-partition` in `~/.caper/default.conf`) as defined in Caper's configuration file. `-J [JOB_NAME]` is to identify Caper's leader job for each workflow. Make a separate directory for each workflow output will be written to each directory.

```bash
$ # conda activate here if required
$ cd [OUTPUT_DIR]  # make a separate directory for each workflow.
$ sbatch -p [SLURM_PARTITON] -J [JOB_NAME] --export=ALL --mem 2G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON]"
```

A Caper leader job will `sbatch` lots of sub-tasks to SLURM so `squeue` will be mixed up with a leader job and its children jobs. It will be more convenient to filter out children jobs.
```
$ squeue -u $USER | grep -v cromwell
```


## Running pipelines on Stanford SCG

Submit a Caper leader job for `caper run` to SLURM. For a SLURM account `-A [SLURM_ACCOUNT]` (this can be different from your own account, talk to your PI or admin), make sure that you use the same SLURM account (`slurm-account` in `~/.caper/default.conf`) as defined in Caper's configuration file. `-J [JOB_NAME]` is to identify Caper's leader job for each workflow. Make a separate directory for each workflow output will be written to each directory.

```bash
$ # conda activate here if required
$ cd [OUTPUT_DIR]  # make a separate directory for each workflow
$ sbatch -A [SLURM_ACCOUNT] -J [JOB_NAME] --export=ALL --mem 2G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON]"
```

A Caper leader job will `sbatch` lots of sub-tasks to SLURM so `squeue` will be mixed up with a leader job and its children jobs. It will be more convenient to filter out children jobs.
```
$ squeue -u $USER | grep -v cromwell
```

## Running pipelines on SLURM clusters

Submit a Caper leader job for `caper run` to SLURM. Define or skip a SLURM account `-A [SLURM_ACCOUNT]` or a SLURM partition `-p [SLURM_PARTITON]` according to your SLURM's configuration. Make sure that those parameters match with whatever defined (`slurm-account` or `slurm-partition` in `~/.caper/default.conf`) in Caper's configuration file. `-J [JOB_NAME]` is to identify Caper's leader job for each workflow. Make a separate directory for each workflow output will be written to each directory.

```bash
$ # conda activate here if required
$ cd [OUTPUT_DIR]  # make a separate directory for each workflow
$ sbatch -A [SLURM_ACCOUNT] -p [SLURM_PARTITON] -J [JOB_NAME] --export=ALL --mem 2G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON]"
```

A Caper leader job will `sbatch` lots of sub-tasks to SLURM so `squeue` will be mixed up with a leader job and its children jobs. It will be more convenient to filter out children jobs.
```
$ squeue -u $USER | grep -v cromwell
```

## Running pipelines on SGE clusters

Submit a Caper leader job for `caper run` to SGE. `-N [JOB_NAME]` is to identify Caper's leader job for each workflow. Make a separate directory for each workflow output will be written to each directory.
```bash
$ # conda activate here if required
$ cd [OUTPUT_DIR]  # make a separate directory for each workflow
$ echo "caper run [WDL] -i [INPUT_JSON]" | qsub -V -N [JOB_NAME] -l h_rt=144:00:00 -l h_vmem=2G
```

A Caper leader job will `qsub` lots of sub-tasks to SGE so `qstat` will be mixed up with a leader job and its children jobs. It will be more convenient to filter out children jobs.
```
$ qstat | grep -v cromwell
```

## Running pipelines on cloud platforms (GCP and AWS)

Create a small leader instance on your GCP project/AWS region. Follow above installation instruction to install `Java`, Caper and Docker.

> **IMPORTANT**: It's **STRONGLY** recommended to attach/mount a persistent disk/EBS volume with enough space to it. Caper's call-caching file DB grows quickly to reach 10 GB, which is a default size for most small instances.

Also, make sure that `tmp-dir` in `~/.caper/default.conf` points to a directory on a large disk. All intermediate files and big cached files for inter-storage transfer will be stored there.

Mount a persistent disk and change directory into it. A **BIG** DB file to enable Cromwell's call-caching (re-using previous failed workflow's outputs) will be generated on this current working directory.
```bash
$ cd /mnt/[MOUNTED_DISK]/[OUTPUT_DIR]
```

Make a screen to keep the session alive. Use the same command line to reattach to it.
```bash
$ screen -RD caper_server
```

Run a server on a screen. Detach from the screen (`Ctrl+A` and then `d`).
```bash
$ caper server
```

Submit a workflow to the server. All pipeline outputs will be written to `out-gcs-bucket` (for GCP) or `out-s3-bucket` (for AWS) in defined `~/.caper/default.conf`.
```bash
$ caper submit [WDL] -i [INPUT_JSON]
```

Monitor your workflows.
```
$ caper list
```

## Running pipelines on general computers

Make a separate directory for each workflow.
```bash
$ # conda activate here if required
$ cd [OUTPUT_DIR]  # make a separate directory for each workflow
$ caper run [WDL] -i [INPUT_JSON]
```

## File DB and resuming failed workflows

Caper defaults to use a file DB, which will grow quickly to reach several GBs, to store metadata for outputs of previous workflows. This metadata DB is used for call-caching (re-using outputs from previous workflows) of Cromwell. You can disable it with `--no-file-db` or `-n` but it's strongly recommended to use one.

This file DB is genereted on your working directory by default. Its default filename prefix is `caper_file_db.[INPUT_JSON_BASENAME_WO_EXT]`. A DB is consist of multiple files and directories with the same filename prefix.

Unless you explicitly define `file-db` in your configuration file `~/.caper/default.conf` this file DB name will depend on your input JSON filename. Therefore, you can simply resume a failed workflow with the same command line used for starting a new pipeline.

For example, assume that you have run your pipeline with the following command line. Then you will see a bunch of files/directories (`caper_file_db.input1*`) generated for a DB.
```bash
$ caper run /atac-seq-pipeline/atac.wdl -i input1.json
```

Unfortunately your pipeline failed and you corrected your input JSON but didn't change its filename. Then simply re-run with the same command line to restart from where it left off.
```bash
$ caper run /atac-seq-pipeline/atac.wdl -i input1.json
```

However, if you have changed input JSON filename then explicitly define previous failed workflow's file DB prefix with `--file-db` or `-d`.
```bash
$ caper run /atac-seq-pipeline/atac.wdl -i input1.json --file-db caper_file_db.input1
```

You can also define `file-db` in your configuration file `~/.caper/default.conf` and use it for all workflows. But please note that you can only run a single workflow at the same time with `caper run` since this will take a sole control on this DB file.

You can also use an external MySQL database to avoid only-one-DB-connection issue. See details section for it.

# DETAILS

See [details](DETAILS.md).
