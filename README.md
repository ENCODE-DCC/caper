[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![CircleCI](https://circleci.com/gh/ENCODE-DCC/caper.svg?style=svg)](https://circleci.com/gh/ENCODE-DCC/caper)

# Caper

Caper (Cromwell Assisted Pipeline ExecutoR) is a wrapper Python package for [Cromwell](https://github.com/broadinstitute/cromwell/).

## Introduction

Caper wraps Cromwell to run pipelines on multiple platforms like GCP (Google Cloud Platform), AWS (Amazon Web Service) and HPCs like SLURM, SGE, PBS/Torque and LSF. It provides easier way of running Cromwell server/run modes by automatically composing necessary input files for Cromwell. Also, Caper can run each task on a specified environment (Docker, Singularity or Conda). Caper automatically localizes all files defined in your input JSON according to the specified backend. For example, if your chosen backend is GCP and files in your input JSON are on S3 buckets (or even URLs) then Caper automatically transfers `s3://` and `http(s)://` files to a specified `gs://` bucket directory. Supported URIs are `s3://`, `gs://`, `http(s)://` and local absolute paths. Private URIs are also accessible if you authenticate using cloud platform CLIs like `gcloud auth`, `aws configure` and using `~/.netrc` for URLs.

## Installation

1) Make sure that you have Java (>= 11) installed on your system.

	```bash
	$ java -version
	```

2) Make sure that you have `python >= 3.6` installed on your system. Use `pip` to install Caper. If you use a pipeline with its own Conda environment then activate the environment first. i.e. installing Caper inside the environment.

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
	$ caper -v
	```

4) If you see an error message like `caper: command not found` then add the following line to the bottom of `~/.bashrc` and re-login.

	```bash
	export PATH=$PATH:~/.local/bin
	```

5) Choose a backend from the following table and initialize Caper. This will create a default Caper configuration file `~/.caper/default.conf`, which have only required parameters for each backend. There are special options (`sherlock` and `scg`) for Stanford Sherlock/SCG users. `caper init` will also install Cromwell/Womtool JARs on `~/.caper/`. Downloading those files can take up to 10 minutes. Once they are installed, Caper can completely work offline with local data files.

	```bash
	$ caper init [BACKEND]
	```

	**Backend**|**Description**
	:--------|:-----
	local | General local computer.
	slurm | HPC with SLURM cluster engine.
	sge | HPC with Sun GridEngine cluster engine.
	pbs | HPC with PBS cluster engine.
  lsf | HPC with LSF cluster engine.
	sherlock | Stanford Sherlock (based on `slurm` backend).
	scg | Stanford SCG (based on `slurm` backend).
  gcp | Google Cloud Platform. See scripts/gcp_caper_server/README.md instead of running `caper init gcp`.
  aws | Amazon Web Service. See scripts/aws_caper_server/README.md instead of running `caper init aws`.

6) Edit `~/.caper/default.conf`. **DO NOT LEAVE ANY PARAMETERS UNDEFINED OR CAPER WILL NOT WORK CORRECTLY**


## Output directory

> **IMPORTANT**: Unless you are running Caper on cloud platforms (`aws`, `gcp`) and `--local-out-dir` is not explicitly defined, all outputs will be written to a current working directory where you run `caper run` or `caper server`.

Therefore, change directory first and run Caper there.

```bash
$ cd [OUTPUT_DIR]
```

## Docker, Singularity and Conda

For local backends (`local`, `slurm`, `sge`, `pbs` and `lsf`), you can use `--docker`, `--singularity` or `--conda` to run pipelines within one of these environment. For example, `caper run ... --singularity docker://ubuntu:latest` will run each task within a Singularity image built from a docker image `ubuntu:latest`. These parameters can also be used as flags. If used as a flag, Caper will try to find a default docker/singularity/conda in WDL. e.g. All ENCODE pipelines have default docker images defined within WDL's meta section (under key `caper_docker` or `default_docker`).

For Conda users, make sure that you have installed pipeline's Conda environments before running pipelines. Caper only knows Conda environment's name to run a task on.

For Singularity users, if you provide a Singularity image based on docker `docker://` then Caper will locally build a temporary Singularity image (`*.sif`) under `SINGULARITY_CACHEDIR` (defaulting to `~/.singularity/cache` if not defined). It's synchronized for all tasks, which means that one task will build the image and others will wait and use the built image later. Building can take some time according to the size of the original docker image.


Take a look at the following examples:
```bash
$ caper run test.wdl --docker # can be used as a flag too, Caper will find docker image from WDL if defined
$ caper run test.wdl --singularity docker://ubuntu:latest
$ caper submit test.wdl --conda your_conda_env_name
```
An environemnt defined here will be overriden by those defined in WDL task's `runtime`. Therefore, think of this as a base/default environment for your pipeline. You can define per-task environment in each WDL task's `runtime`.

For cloud backends (`gcp` and `aws`), you always need to use `--docker` (can be skipped). Caper will automatically try to find a base docker image defined in your WDL. For other pipelines, define a base docker image in Caper's CLI or directly in each WDL task's `runtime`.


## Important notes for Conda users

Since Caper>=2.0 you don't have to activate Conda environment before running pipelines. Caper will internally run `conda run -n ENV_NAME /bin/bash script.sh`. Just make sure that you correctly installed given pipeline's Conda environment(s).


## Important notes for Stanford HPC (Sherlock and SCG) users

DO NOT INSTALL CAPER, CONDA AND PIPELINE'S WDL ON `$SCRATCH` OR `$OAK` STORAGES. You will see `Segmentation Fault` errors. Install these executables (Caper, Conda, WDL, ...) on `$HOME` OR `$PI_HOME`. You can still use `$OAK` for input data (e.g. FASTQs defined in your input JSON file) but not for outputs, which means that you should not run Caper on `$OAK`. `$SCRATCH` and `$PI_SCRATCH` are okay for both input and output data so run Caper on them. Running Croo to organize outputs into `$OAK` is okay.


## Running pipelines on HPCs

In order to run a pipeline inside Singularity image or Conda environment use `--singularity` or `--conda` since most HPCs do not allow docker. For example, submit `caper run ... --singularity` as a leader job (with long walltime and enough resources like 1-2 cpus and 4GB of RAM). Then Caper's leader job itself will submit its child jobs to the job engine so that both leader and child jobs can be found with `squeue` or `qstat`.

Here are some example command lines to submit Caper as a leader job. Make sure that you correctly configured Caper with `caper init` and filled all parameters in the conf file `~/.caper/default.conf`.
```bash
# make a separate directory for each workflow.
$ cd [OUTPUT_DIR]

# Example for Stanford Sherlock
$ sbatch -p [SLURM_PARTITON] -J [WORKFLOW_NAME] --export=ALL --mem 4G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON] --singularity --db file --file-db [METADATA_DB_PATH_FOR_CALL_CACHING]"

# Example for Stanford SCG
$ sbatch -A [SLURM_ACCOUNT] -J [WORKFLOW_NAME] --export=ALL --mem 3G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON] --singularity --db file --file-db [METADATA_DB_PATH_FOR_CALL_CACHING]"

# Example for General SLURM cluster
$ sbatch -A [SLURM_ACCOUNT] -p [SLURM_PARTITON] -J [WORKFLOW_NAME] --export=ALL --mem 3G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON] --singularity --db file --file-db [METADATA_DB_PATH_FOR_CALL_CACHING]"

# Example for SGE
$ echo "caper run [WDL] -i [INPUT_JSON] --singularity --db file --file-db [METADATA_DB_PATH_FOR_CALL_CACHING]" | qsub -V -N [JOB_NAME] -l h_rt=144:00:00 -l h_vmem=3G

# Check status of leader/child jobs
$ squeue -u $USER | grep -v cromwell
```

## Running pipelines on cloud platforms (GCP and AWS)

Follow these instructions for [GCP](scripts/gcp_caper_server/README.md) and [AWS](scripts/aws_caper_server/README.md).


## Running pipelines on a local machine

Make a separate directory for each workflow. Caper maximizes parallelization (depending on the task tree of a given WDL). So make sure that your local machine has enough resources to run it. You can control number of concurrent tasks in a pipeline. For example, serialize all tasks with `--max-concurrent-tasks 1`.

```bash
$ cd [OUTPUT_DIR]  # make a separate directory for each workflow
$ caper run [WDL] -i [INPUT_JSON] --docker
```


## How to configure resource parameters for HPCs

Each HPC backend (`slurm`, `sge`, `pbs` and `lsf`) has its own resource parameter. Find it in Caper's configuration file (`~/.caper/default.conf`) and edit it. For example, the default resource parameter for SLURM looks like the following:
```
slurm-resource-parameter=-n 1 --ntasks-per-node=1 --cpus-per-task=${cpu} ${if defined(memory_mb) then "--mem=" else ""}${memory_mb}${if defined(memory_mb) then "M" else ""} ${if defined(time) then "--time=" else ""}${time*60} ${if defined(gpu) then "--gres=gpu:" else ""}${gpu}
```
This should be a one-liner and WDL syntax and Cromwell's built-in resource variables like `cpu`(number of cores for a task), `memory_mb`(total amount of memory for a task in MB), `time`(walltime for a task in hour) and `gpu`(name of gpu unit or number of gpus) are allowed in `${}` notation. See https://github.com/openwdl/wdl/blob/main/versions/1.0/SPEC.md for WDL syntax.

Note that Cromwell's implicit type conversion (`WomLong` to `String`) seems to be buggy for `WomLong` type memory variables such as `memory_mb` and `memory_gb`. So be careful about using the `+` operator between `WomLong` and other types (`String`, even `Int`). For example, `${"--mem=" + memory_mb}` will not work since `memory_mb` is `WomLong` type. Use `${"if defined(memory_mb) then "--mem=" else ""}{memory_mb}${"if defined(memory_mb) then "mb " else " "}`. See https://github.com/broadinstitute/cromwell/issues/4659 for details.


# DETAILS

See [details](DETAILS.md).
