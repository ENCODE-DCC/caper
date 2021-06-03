[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![CircleCI](https://circleci.com/gh/ENCODE-DCC/caper.svg?style=svg)](https://circleci.com/gh/ENCODE-DCC/caper)

# Caper

Caper (Cromwell Assisted Pipeline ExecutoR) is a wrapper Python package for [Cromwell](https://github.com/broadinstitute/cromwell/).

## Introduction

Caper is based on Unix and cloud platform CLIs (`curl`, `gsutil` and `aws`) and provides easier way of running Cromwell server/run modes by automatically composing necessary input files for Cromwell. Also, Caper supports easy automatic file transfer between local/cloud storages (local path, `s3://`, `gs://` and `http(s)://`). You can use these URIs in input JSON file or for a WDL file itself.

## Installation

1) Make sure that you have Java (>= 1.8) installed on your system.

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
	$ caper
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
	gcp | Google Cloud Platform.
	aws | Amazon Web Service.
	sherlock | Stanford Sherlock (based on `slurm` backend).
	scg | Stanford SCG (based on `slurm` backend).

6) Edit `~/.caper/default.conf`. Find instruction for each parameter in the following table.
	> **IMPORTANT**: DO NOT LEAVE ANY PARAMETERS UNDEFINED OR CAPER WILL NOT WORK CORRECTLY.

	**Parameter**|**Description**
	:--------|:-----
	local-loc-dir | **IMPORTANT**: DO NOT USE `/tmp`. This is a working directory to store all important intermediate files for Caper. This directory is also used to store big cached files for localization of remote files. e.g. to run pipelines locally with remote files (`gs://`, `s3://`, `http://`, ...) copies of such files are stored here.
	slurm-partition | SLURM partition. Define only if required by a cluster. You must define it for Stanford Sherlock.
	slurm-account | SLURM partition. Define only if required by a cluster. You must define it for Stanford SCG.
	sge-pe | Parallel environment of SGE. Find one with `$ qconf -spl` or ask you admin to add one if not exists.
	aws-batch-arn | ARN for AWS Batch.
	aws-region | AWS region (e.g. us-west-1)
	aws-out-dir | Output bucket path for AWS. This should start with `s3://`.
	gcp-prj | Google Cloud Platform Project
	gcp-out-dir | Output bucket path for Google Cloud Platform. This should start with `gs://`.

7) To use Caper on Google Cloud Platform (GCP), we provide a shell script to create a Caper server instance on Google Cloud.
See [this](scripts/gcp_caper_server/README.md) for details.

8) To use Caper on Amazon Web Service (AWS), we provide a shell script to create a Caper server instance on AWS.
See [this](scripts/aws_caper_server/README.md) for details.


## Output directory

> **IMPORTANT**: Unless you are running Caper on cloud platforms (`aws`, `gcp`) and `--local-out-dir` is not explicitly defined, all outputs will be written to a current working directory where you run `caper run` or `caper server`.

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

> **IMPORTANT**: DO NOT INSTALL CAPER, CONDA AND PIPELINE'S WDL ON `$SCRATCH` OR `$OAK` STORAGES. You will see `Segmentation Fault` errors. Install these executables (Caper, Conda, WDL, ...) on `$HOME` OR `$PI_HOME`. You can still use `$OAK` for input data (e.g. FASTQs defined in your input JSON file) but not for outputs, which means that you should not run Caper on `$OAK`. `$SCRATCH` and `$PI_SCRATCH` are okay for both input and output data so run Caper on them. Running Croo to organize outputs into `$OAK` is okay.

Submit a Caper leader job (`caper run`) to SLURM. For a partition `-p [SLURM_PARTITON]`, make sure that you use the same SLURM partition (`slurm-partition` in `~/.caper/default.conf`) as defined in Caper's configuration file. `-J [JOB_NAME]` is to identify Caper's leader job for each workflow. Make a separate directory for each workflow output will be written to each directory.

```bash
$ # DO NOT RUN THIS ON OAK STORAGE!
$ # conda activate here if required
$ cd [OUTPUT_DIR]  # make a separate directory for each workflow.
$ sbatch -p [SLURM_PARTITON] -J [JOB_NAME] --export=ALL --mem 3G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON]"
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
$ sbatch -A [SLURM_ACCOUNT] -J [JOB_NAME] --export=ALL --mem 3G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON]"
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
$ sbatch -A [SLURM_ACCOUNT] -p [SLURM_PARTITON] -J [JOB_NAME] --export=ALL --mem 3G -t 4-0 --wrap "caper run [WDL] -i [INPUT_JSON]"
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
$ echo "caper run [WDL] -i [INPUT_JSON]" | qsub -V -N [JOB_NAME] -l h_rt=144:00:00 -l h_vmem=3G
```

A Caper leader job will `qsub` lots of sub-tasks to SGE so `qstat` will be mixed up with a leader job and its children jobs. It will be more convenient to filter out children jobs.
```
$ qstat | grep -v cromwell
```

## Running pipelines on cloud platforms (GCP and AWS)

Create a small leader instance on your GCP project/AWS region. Follow above installation instruction to install `Java`, Caper and Docker.

> **IMPORTANT**: It's **STRONGLY** recommended to attach/mount a persistent disk/EBS volume with enough space to it. Caper's call-caching file DB grows quickly to reach 10 GB, which is a default size for most small instances.

Also, make sure that `local-loc-dir` in `~/.caper/default.conf` points to a directory on a large disk. All intermediate files and big cached files for inter-storage transfer will be stored there.

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

Submit a workflow to the server. All pipeline outputs will be written to `gcp-out-dir` (for GCP) or `aws-out-dir` (for AWS) in defined `~/.caper/default.conf`.
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

## Running pipelines on a custom backend

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

Look for a file defined with a Java parameter `-Dconfig.file` and find a backend of interest (`slurm` in this example) in the file.
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

> **WARINING**: Using this type of metadata database is **NOT RECOMMENDED**. It's unstable and fragile.

Define file DB parameters in `~/.caper/default.conf`.

```
db=file
file-db=/YOUR/FILE/DB/PATH/PREFIX
```

This file DB is genereted on your working directory by default. Its default filename prefix is `caper_file_db.[INPUT_JSON_BASENAME_WO_EXT]`. A DB is consist of multiple files and directories with the same filename prefix.

Unless you explicitly define `file-db` in your configuration file `~/.caper/default.conf` this file DB name will depend on your input JSON filename. Therefore, you can simply resume a failed workflow with the same command line used for starting a new pipeline.


# DETAILS

See [details](DETAILS.md).


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
