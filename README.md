> **CRITICAL**: Caper has been updated to use [Autouri](https://github.com/ENCODE-DCC/autouri) instead of its own localization module. If you are upgrading from old Caper < 0.8. Upgrade Caper with the following commands. If it doesn't work remove Caper `pip uninstall caper` and clean-install it `pip install caper`.
```bash
$ pip install caper --upgrade
```

> **IMPORTANT**: If you use `--use-gsutil-for-s3` then you need to update your `gsutil`. This flag allows a direct transfer between `gs://` and `s3://`. This requires `gsutil` >= 4.47. See this [issue](https://github.com/GoogleCloudPlatform/gsutil/issues/935) for details.
```bash
$ pip install gsutil --upgrade
```

**IMPORATNT**: A new flag `--soft-glob-output` is added to use soft-linking for globbing outputs. Use it for `caper server/run` (not for `caper submit`) on a filesystem that does not allow hard-linking: e.g. beeGFS.

**IMPORATNT**: Caper defaults back to **NOT** use a file-based metadata DB, which means no call-caching (re-using outputs from previous workflows) by default.

**IMPORATNT**: Even if you still want to use a file-based DB (`--db file` and `--file-db [DB_PATH]`), metadata DB generated from Caper<0.6 (with Cromwell-42) is not compatible with metadata DB generated from Caper>=0.6 (with Cromwell-47). Refer to [this doc](https://github.com/broadinstitute/cromwell/releases/tag/43) for such migration.

See [this](#metadata-database) for details about metadata DB. Define a DB type with `db=` in your conf `~/.caper/default.conf` to use a metadata DB.

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

5) Choose a platform from the following table and initialize Caper. This will create a default Caper configuration file `~/.caper/default.conf`, which have only required parameters for each platform. There are special platforms for Stanford Sherlock/SCG users. This will also install Cromwell/Womtool JARs on `~/.caper`. Downloading those files can take up to 10 minutes. Once they are installed, Caper can completely work offline with local data files.

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

## Running pipelines on a custom backend

If Caper's built-in backends don't work as expected on your clusters (e.g. due to different resource settings), then you can override built-in backends with your own configuration file (e.g. `your.backend.conf`). Caper generates a `backend.conf` for built-in backends on a temporary directory.

Find this `backend.conf` first by dry-running `caper run [WDL] --dry-run ...`. For example of a `slurm` backend:
```
$ caper run toy.wdl --dry-run --backend slurm
[Caper] Validating WDL/input JSON with womtool...
Picked up _JAVA_OPTIONS: -Xms256M -Xmx4024M -XX:ParallelGCThreads=1
Success!
[Caper] cmd:  ['java', '-Xmx3G', '-XX:ParallelGCThreads=1', '-DLOG_LEVEL=INFO', '-DLOG_MODE=standard', '-jar', '-Dconfig.file=/mnt/data/scratch/leepc12/caper_out/.caper_tmp/toy/20200309_151256_331283/backend.conf', '/users/leepc12/.caper/cromwell_jar/cromwell-47.jar', 'run', '/mnt/data2/scratch/leepc12/test_caper_refac/toy.wdl', '-i', '/mnt/data/scratch/leepc12/caper_out/.caper_tmp/toy/20200309_151256_331283/inputs.json', '-o', '/mnt/data/scratch/leepc12/caper_out/.caper_tmp/toy/20200309_151256_331283/workflow_opts.json', '-l', '/mnt/data/scratch/leepc12/caper_out/.caper_tmp/toy/20200309_151256_331283/labels.json', '-m', '/mnt/data/scratch/leepc12/caper_out/.caper_tmp/toy/20200309_151256_331283/metadata.json']
```

Look for a file defined with a Java parameter `-Dconfig.file` and find a backend of interest (`slurm` in this example) in the file.
```
include required(classpath("application"))
backend {
  default = "slurm"
  providers {

  ...

    slurm {
      actor-factory = "cromwell.backend.impl.sfs.config.ConfigBackendLifecycleActorFactory"
      config {
        default-runtime-attributes {
          time = 24
        }
        concurrent-job-limit = 1000
        script-epilogue = "sleep 10 && sync"
        root = "/mnt/data/scratch/leepc12/caper_out"
        runtime-attributes = """
        String? docker
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
        submit = """ITER=0; until [ $ITER -ge 3 ]; do
        sbatch         --export=ALL         -J ${job_name}         -D ${cwd}         -o ${out}         -e ${err}         ${"-t " + time*60}         -n 1         --ntasks-per-node=1         ${true="--cpus-per-task=" false="" defined(cpu)}${cpu}         ${true="--mem=" false="" defined(memory_mb)}${memory_mb}         ${"-p " + slurm_partition}         ${"--account " + slurm_account}         ${true="--gres gpu:" false="" defined(gpu)}${gpu}         ${slurm_extra_param}         --wrap "${if defined(singularity) then '' else             '/bin/bash ${script} #'}             if [ -z \"$SINGULARITY_BINDPATH\" ]; then             export SINGULARITY_BINDPATH=${singularity_bindpath}; fi;             if [ -z \"$SINGULARITY_CACHEDIR\" ]; then             export SINGULARITY_CACHEDIR=${singularity_cachedir}; fi;             singularity exec --cleanenv --home ${cwd}             ${if defined(gpu) then '--nv' else ''}             ${singularity} /bin/bash ${script}" && break
    ITER=$[$ITER+1]; sleep 30; done
    """
        kill = "scancel ${job_id}"
        exit-code-timeout-seconds = 360
        check-alive = "for ITER in 1 2 3; do CHK_ALIVE=$(squeue --noheader -j ${job_id} --format=%i | grep ${job_id}); if [ -z \"$CHK_ALIVE\" ]; then if [ \"$ITER\" == 3 ]; then /bin/bash -c 'exit 1'; else sleep 30; fi; else echo $CHK_ALIVE; break; fi; done"
        job-id-regex = "Submitted batch job (\\d+).*"
      }
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
kadru.stanford.edu:8000
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

	> **IMPORTANT**: File DBs generated from Caper>=0.6 and Caper<0.6 are not compatible with each other. See [release note of Cromwell-43](https://github.com/broadinstitute/cromwell/releases/tag/43) for details and how to migrate if required.

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
