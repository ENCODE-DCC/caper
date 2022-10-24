[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![CircleCI](https://circleci.com/gh/ENCODE-DCC/caper.svg?style=svg)](https://circleci.com/gh/ENCODE-DCC/caper)


## Introduction

Caper (Cromwell Assisted Pipeline ExecutoR) is a wrapper Python package for [Cromwell](https://github.com/broadinstitute/cromwell/). Caper wraps Cromwell to run pipelines on multiple platforms like GCP (Google Cloud Platform), AWS (Amazon Web Service) and HPCs like SLURM, SGE, PBS/Torque and LSF. It provides easier way of running Cromwell server/run modes by automatically composing necessary input files for Cromwell. Caper can run each task on a specified environment (Docker, Singularity or Conda). Also, Caper automatically localizes all files (keeping their directory structure) defined in your input JSON and command line according to the specified backend. For example, if your chosen backend is GCP and files in your input JSON are on S3 buckets (or even URLs) then Caper automatically transfers `s3://` and `http(s)://` files to a specified `gs://` bucket directory. Supported URIs are `s3://`, `gs://`, `http(s)://` and local absolute paths. You can use such URIs either in CLI and input JSON. Private URIs are also accessible if you authenticate using cloud platform CLIs like `gcloud auth`, `aws configure` and using `~/.netrc` for URLs.


## Installation for Google Cloud Platform and AWS

See [this](scripts/gcp_caper_server/README.md) for details.


## Installation for AWS

See [this](scripts/aws_caper_server/README.md) for details.


## Installation for local computers and HPCs

1) Make sure that you have Java (>= 11) and Python>=3.6 installed on your system and `pip` to install Caper.

	```bash
	$ pip install caper
	```

2) If you see an error message like `caper: command not found` after installing then add the following line to the bottom of `~/.bashrc` and re-login.

	```bash
	export PATH=$PATH:~/.local/bin
	```

3) Choose a backend from the following table and initialize Caper. This will create a default Caper configuration file `~/.caper/default.conf`, which have only required parameters for each backend. `caper init` will also install Cromwell/Womtool JARs on `~/.caper/`. Downloading those files can take up to 10 minutes. Once they are installed, Caper can completely work offline with local data files.

	**Backend**|**Description**
	:--------|:-----
	local | local computer without a cluster engine
	slurm | SLURM (e.g. Stanford Sherlock and SCG)
	sge | Sun GridEngine
	pbs | PBS cluster
	lsf | LSF cluster

	> **IMPORTANT**: `sherlock` and `scg` backends have been deprecated. Use `slurm` backend instead and following instruction comments in the configuration file.

	```bash
	$ caper init [BACKEND]
	```

4) Edit `~/.caper/default.conf` and follow instructions in there. **CAREFULLY READ INSTRUCTION AND DO NOT LEAVE IMPORTANT PARAMETERS UNDEFINED OR CAPER WILL NOT WORK CORRECTLY**


## Docker, Singularity and Conda

For local backends (`local`, `slurm`, `sge`, `pbs` and `lsf`), you can use `--docker`, `--singularity` or `--conda` to run WDL tasks in a pipeline within one of these environment. For example, `caper run ... --singularity docker://ubuntu:latest` will run each task within a Singularity image built from a docker image `ubuntu:latest`. These parameters can also be used as flags. If used as a flag, Caper will try to find a default docker/singularity/conda in WDL. e.g. All ENCODE pipelines have default docker/singularity images defined within WDL's meta section (under key `caper_docker` or `default_docker`).

> **IMPORTANT**: Docker/singularity/conda defined in Caper's configuration file or in CLI (`--docker`, `--singularity` and `--conda`) will be overriden by those defined in WDL task's `runtime`. We provide these parameters to define default/base environment for a pipeline, not to override on WDL task's `runtime`.

For Conda users, make sure that you have installed pipeline's Conda environments before running pipelines. Caper only knows Conda environment's name. You don't need to activate any Conda environment before running a pipeline since Caper will internally run `conda run -n ENV_NAME TASK_SHELL_SCRIPT` for each task.

Take a look at the following examples:
```bash
$ caper run test.wdl --docker # can be used as a flag too, Caper will find a docker image defined in WDL
$ caper run test.wdl --singularity docker://ubuntu:latest
$ caper hpc submit test.wdl --singularity --leader-job-name test1 # submit to job engine and use singularity defined in WDL
$ caper submit test.wdl --conda your_conda_env_name # running caper server is required
```

An environemnt defined here will be overriden by those defined in WDL task's `runtime`. Therefore, think of this as a base/default environment for your pipeline. You can define per-task docker, singularity images to override those defined in Caper's command line. For example:
```wdl
task my_task {
	...
	runtime {
		docker: "ubuntu:latest"
		singularity: "docker://ubuntu:latest"
	}
}
```

For cloud backends (`gcp` and `aws`), Caper will automatically try to find a base docker image defined in your WDL. For other pipelines, define a base docker image in Caper's CLI or directly in each WDL task's `runtime`.


## Running pipelines on HPCs

Use `--singularity` or `--conda` in CLI to run a pipeline inside Singularity image or Conda environment. Most HPCs do not allow docker. For example, `caper hpc submit ... --singularity` will submit Caper process to the job engine as a leader job. Then Caper's leader job will submit its child jobs to the job engine so that both leader and child jobs can be found with `squeue` or `qstat`.

Use `caper hpc list` to list all leader jobs. Use `caper hpc abort JOB_ID` to abort a running leader job. **DO NOT DIRECTLY CANCEL A JOB USING CLUSTER COMMAND LIKE SCANCEL OR QDEL** then only your leader job will be canceled, not all the child jobs.

Here are some example command lines to submit Caper as a leader job. Make sure that you correctly configured Caper with `caper init` and filled all parameters in the conf file `~/.caper/default.conf`.

There is an extra set of parameters `--file-db [METADATA_DB_PATH_FOR_CALL_CACHING]` to use call-caching (restarting workflows by re-using previous outputs). If you want to restart a failed workflow then use the same metadata DB path then pipeline will start from where it left off. It will actually start over but will reuse (soft-link) previous outputs.

```bash
# make a new output directory for a workflow.
$ cd [OUTPUT_DIR]

# Example with Singularity without using call-caching.
$ caper hpc submit [WDL] -i [INPUT_JSON] --singularity --leader-job-name GOOD_NAME1

# Example with Conda and using call-caching (restarting a workflow from where it left off)
# Use the same --file-db PATH for next re-run then Caper will collect and softlink previous outputs.
$ caper hpc submit [WDL] -i [INPUT_JSON] --conda --leader-job-name GOOD_NAME2 --db file --file-db [METADATA_DB_PATH] 

# List all leader jobs.
$ caper hpc list

# Check leader job's STDOUT file to monitor workflow's status.
# Example for SLURM
$ tail -f slurm-[JOB_ID].out

# Cromwell's log will be written to cromwell.out* on the same directory.
# It will be helpful for monitoring your workflow in detail.
$ ls -l cromwell.out*

# Abort a leader job (this will cascade-kill all its child jobs)
# If you directly use job engine's command like scancel or qdel then child jobs will still remain running.
$ caper hpc abort [JOB_ID]
```

## Customize resource parameters on HPCs

If default settings of Caper does not work with your HPC, then see [this document](docs/resource_param.md) to manually customize resource command line (e.g. `sbatch ... [YOUR_CUSTOM_PARAMETER]`) for your chosen backend.

# DETAILS

See [details](DETAILS.md).
