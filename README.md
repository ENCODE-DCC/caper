[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![CircleCI](https://circleci.com/gh/ENCODE-DCC/caper.svg?style=svg)](https://circleci.com/gh/ENCODE-DCC/caper)

# Caper

Caper (Cromwell Assisted Pipeline ExecutoR) is a wrapper Python package for [Cromwell](https://github.com/broadinstitute/cromwell/).

## Introduction

Caper wraps Cromwell to run pipelines on multiple platforms like GCP (Google Cloud Platform), AWS (Amazon Web Service) and HPCs like SLURM, SGE, PBS/Torque and LSF. It provides easier way of running Cromwell server/run modes by automatically composing necessary input files for Cromwell. Caper can run each task on a specified environment (Docker, Singularity or Conda). Also, Caper automatically localizes all files (keeping their directory structure) defined in your input JSON and command line according to the specified backend. For example, if your chosen backend is GCP and files in your input JSON are on S3 buckets (or even URLs) then Caper automatically transfers `s3://` and `http(s)://` files to a specified `gs://` bucket directory. Supported URIs are `s3://`, `gs://`, `http(s)://` and local absolute paths. You can use such URIs either in CLI and input JSON. Private URIs are also accessible if you authenticate using cloud platform CLIs like `gcloud auth`, `aws configure` and using `~/.netrc` for URLs.


## Installation for Google Cloud Platform and AWS

See [this](scripts/gcp_caper_server/README.md) for details.


## Installation for AWS

See [this](scripts/aws_caper_server/README.md) for details.


## Installation

1) Make sure that you have Java (>= 11) and Python>=3.6 installed on your system and `pip` to install Caper.

	```bash
	$ pip install caper
	```

2) If you see an error message like `caper: command not found` then add the following line to the bottom of `~/.bashrc` and re-login.

	```bash
	export PATH=$PATH:~/.local/bin
	```

3) Choose a backend from the following table and initialize Caper. This will create a default Caper configuration file `~/.caper/default.conf`, which have only required parameters for each backend. `caper init` will also install Cromwell/Womtool JARs on `~/.caper/`. Downloading those files can take up to 10 minutes. Once they are installed, Caper can completely work offline with local data files.

	**Backend**|**Description**
	:--------|:-----
	local | local computer without cluster engine.
	slurm | SLURM cluster.
	sge | Sun GridEngine cluster.
	pbs | PBS cluster.
	lsf | LSF cluster.
	sherlock | Stanford Sherlock (based on `slurm` backend).
	scg | Stanford SCG (based on `slurm` backend).

	```bash
	$ caper init [BACKEND]
	```

4) Edit `~/.caper/default.conf` and follow instructions in there. **DO NOT LEAVE ANY PARAMETERS UNDEFINED OR CAPER WILL NOT WORK CORRECTLY**


## Docker, Singularity and Conda

For local backends (`local`, `slurm`, `sge`, `pbs` and `lsf`), you can use `--docker`, `--singularity` or `--conda` to run WDL tasks in a pipeline within one of these environment. For example, `caper run ... --singularity docker://ubuntu:latest` will run each task within a Singularity image built from a docker image `ubuntu:latest`. These parameters can also be used as flags. If used as a flag, Caper will try to find a default docker/singularity/conda in WDL. e.g. All ENCODE pipelines have default docker/singularity images defined within WDL's meta section (under key `caper_docker` or `default_docker`).

> **IMPORTANT**: Docker/singularity/conda defined in Caper's configuration file or in CLI (`--docker`, `--singularity` and `--conda`) will be overriden by those defined in WDL task's `runtime`. We provide these parameters to define default/base environment for a pipeline, not to override on WDL task's `runtime`.

For Conda users, make sure that you have installed pipeline's Conda environments before running pipelines. Caper only knows Conda environment's name. You don't need to activate any Conda environment before running a pipeline since Caper will internally run `conda run -n ENV_NAME COMMANDS` for each task.

Take a look at the following examples:
```bash
$ caper run test.wdl --docker # can be used as a flag too, Caper will find docker image from WDL if defined
$ caper run test.wdl --singularity docker://ubuntu:latest
$ caper submit test.wdl --conda your_conda_env_name # running caper server is required
```
An environemnt defined here will be overriden by those defined in WDL task's `runtime`. Therefore, think of this as a base/default environment for your pipeline. You can define per-task environment in each WDL task's `runtime`.

For cloud backends (`gcp` and `aws`), you always need to use `--docker` (can be skipped). Caper will automatically try to find a base docker image defined in your WDL. For other pipelines, define a base docker image in Caper's CLI or directly in each WDL task's `runtime`.


## Singularity and Docker Hub pull limit

If you provide a Singularity image based on docker `docker://` then Caper will locally build a temporary Singularity image (`*.sif`) under `SINGULARITY_CACHEDIR` (defaulting to `~/.singularity/cache` if not defined). However, Singularity will blindly pull from DockerHub to quickly reach [a daily pull limit](https://www.docker.com/increase-rate-limits). It's recommended to use Singularity images from `shub://` (Singularity Hub) or `library://` (Sylabs Cloud).


## Important notes for Conda users

Since Caper>=2.0 you don't have to activate Conda environment before running pipelines. Caper will internally run `conda run -n ENV_NAME /bin/bash script.sh`. Just make sure that you correctly installed given pipeline's Conda environment(s).


## Important notes for Stanford HPC (Sherlock and SCG) users

**DO NOT INSTALL CAPER, CONDA AND PIPELINE'S WDL ON `$SCRATCH` OR `$OAK` STORAGES**. You will see `Segmentation Fault` errors. Install these executables (Caper, Conda, WDL, ...) on `$HOME` OR `$PI_HOME`. You can still use `$OAK` for input data (e.g. FASTQs defined in your input JSON file) but not for outputs, which means that you should not run Caper on `$OAK`. `$SCRATCH` and `$PI_SCRATCH` are okay for both input and output data so run Caper on them. Running Croo to organize outputs into `$OAK` is okay.


## Running pipelines on HPCs

Use `--singularity` or `--conda` in CLI to run a pipeline inside Singularity image or Conda environment. Most HPCs do not allow docker. For example, submit `caper run ... --singularity` as a leader job (with long walltime and not-very-big resources like 2 cpus and 5GB of RAM). Then Caper's leader job itself will submit its child jobs to the job engine so that both leader and child jobs can be found with `squeue` or `qstat`.

Here are some example command lines to submit Caper as a leader job. Make sure that you correctly configured Caper with `caper init` and filled all parameters in the conf file `~/.caper/default.conf`.

There are extra parameters `--db file --file-db [METADATA_DB_PATH_FOR_CALL_CACHING]` to use call-caching (restarting workflows by re-using previous outputs). If you want to restart a failed workflow then use the same metadata DB path then pipeline will start from where it left off. It will actually start over but will reuse (soft-link) previous outputs.

```bash
# make a separate directory for each workflow.
$ cd [OUTPUT_DIR]

# Example for Stanford Sherlock
$ sbatch -p [SLURM_PARTITON] -J [WORKFLOW_NAME] --export=ALL --mem 5G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON] --singularity --db file --file-db [METADATA_DB_PATH_FOR_CALL_CACHING]"

# Example for Stanford SCG
$ sbatch -A [SLURM_ACCOUNT] -J [WORKFLOW_NAME] --export=ALL --mem 5G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON] --singularity --db file --file-db [METADATA_DB_PATH_FOR_CALL_CACHING]"

# Example for General SLURM cluster
$ sbatch -A [SLURM_ACCOUNT_IF_NEEDED] -p [SLURM_PARTITON_IF_NEEDED] -J [WORKFLOW_NAME] --export=ALL --mem 5G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON] --singularity --db file --file-db [METADATA_DB_PATH_FOR_CALL_CACHING]"

# Example for SGE
$ echo "caper run [WDL] -i [INPUT_JSON] --conda --db file --file-db [METADATA_DB_PATH_FOR_CALL_CACHING]" | qsub -V -N [JOB_NAME] -l h_rt=144:00:00 -l h_vmem=3G

# Check status of leader job
$ squeue -u $USER | grep -v [WORKFLOW_NAME]

# Kill the leader job then Caper will gracefully shutdown to kill its children.
$ scancel [LEADER_JOB_ID]
```


## How to customize resource parameters for HPCs

Each HPC backend (`slurm`, `sge`, `pbs` and `lsf`) has its own resource parameter. e.g. `slurm-resource-param`. Find it in Caper's configuration file (`~/.caper/default.conf`) and edit it. For example, the default resource parameter for SLURM looks like the following:
```
slurm-resource-param=-n 1 --ntasks-per-node=1 --cpus-per-task=${cpu} ${if defined(memory_mb) then "--mem=" else ""}${memory_mb}${if defined(memory_mb) then "M" else ""} ${if defined(time) then "--time=" else ""}${time*60} ${if defined(gpu) then "--gres=gpu:" else ""}${gpu}
```
This should be a one-liner with WDL syntax allowed in `${}` notation. i.e. Cromwell's built-in resource variables like `cpu`(number of cores for a task), `memory_mb`(total amount of memory for a task in MB), `time`(walltime for a task in hour) and `gpu`(name of gpu unit or number of gpus) in `${}`. See https://github.com/openwdl/wdl/blob/main/versions/1.0/SPEC.md for WDL syntax. This line will be formatted with actual resource values by Cromwell and then passed to the submission command such as `sbatch` and `qsub`.

Note that Cromwell's implicit type conversion (`WomLong` to `String`) seems to be buggy for `WomLong` type memory variables such as `memory_mb` and `memory_gb`. So be careful about using the `+` operator between `WomLong` and other types (`String`, even `Int`). For example, `${"--mem=" + memory_mb}` will not work since `memory_mb` is `WomLong` type. Use `${"if defined(memory_mb) then "--mem=" else ""}{memory_mb}${"if defined(memory_mb) then "mb " else " "}` instead. See https://github.com/broadinstitute/cromwell/issues/4659 for details.


# DETAILS

See [details](DETAILS.md).
