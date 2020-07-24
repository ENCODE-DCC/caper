## Introduction

`create_instance.sh` will create an instance on Google Cloud Compute Engine in Google your project and configure the instance for Caper with PostgreSQL database and Google Cloud Life Sciences API (`v2beta`).

Google Cloud Life Sciences API is a new API replacing the old deprecating Genomics API (`v2alpha1`). It requires `--gcp-region` to be defined correctly. Check [supported regions](https://cloud.google.com/life-sciences/docs/concepts/locations) for the new API.

## Requirements

Make sure that `gcloud` (Google Cloud SDK CLI) is installed on your system.

Enable the following APIs on your Google Cloud console.
* Compute Engine API
* Google Cloud Storage (DO NOT click on "Create credentials")
* Google Cloud Storage JSON API
* Life Sciences API

Prepare a service account with enough permission to Google Compute Engine and Google Cloud Storage. Generate a secret key JSON from it and keep it locally on your computer.

>**WARNING**: Such secret JSON file is a master key for important resources on your project. Keep it secure at your own risk. This file will be used for Caper so that it will be trasnferred to the created instance at `/opt/caper/service_account_key.json` visible to all users on the instance.

## How to create an instance

Run without arguments to see detailed help. Some optional arguments are very important depending on your region/zone. e.g. `--gcp-region` (for Life Sciences API) and `--zone` (for instance creation). These regional parameters default to US central region/zones.
```bash
$ ./create_instance.sh
```

However, this script is designed to work well with default arguments. Try with positional arguments only first and see if it works.
```bash
$ ./create_instance.sh [INSTANCE_NAME] [PROJECT_NAME] [GCP_SERVICE_ACCOUNT_KEY_JSON_FILE] [GCP_OUT_DIR]
```

Allow several minutes for the instance to finish up installing Caper and dependencies.

## How to run/stop/restart Caper server

Once the instance is created. It is recommended to make a new screen so that `caper server` runs inside it without interruption. On the screen, change directory to Caper directory and run `caper server`. You can monitor Cromwell's log on `/opt/caper/cromwell.out`.
```bash
$ sudo su
$ screen -RD caper_server
# on the screen
$ cd /opt/caper
$ caper server
```

To stop a Caper server, open the screen with the same command line used for creating one. Then press CTRL+C just one time. **DO NOT TYPE IT MULTIPLE TIMES**. This will prevent a graceful shutdown of Cromwell, which can corrupt a metadata DB.
```bash
$ sudo su
$ screen -RD caper_server
# hit CTRL+C just one time
```

To change any parameters for Caper server/client, edit `/opt/caper/default.conf`. This file is shard among all users including `root`.

## How to submit a workflow (IMPORTANT!)

Check if `caper list` works without any network errors.
```bash
$ caper list
```

Caper will localize big data files (URLs and URIs) on a GCS bucket directory `--gcp-loc-dir`, which defaults to `[GCP_OUT_DIR]/.caper_tmp/` if not defined. e.g. your FASTQs and reference genome data defined in an input JSON.
