## Introduction

`create_instance.sh` will create an instance on Google Cloud Compute Engine in Google your project and configure the instance for Caper with PostgreSQL database and Google Cloud Life Sciences API (`v2beta`).

Google Cloud Life Sciences API is a new API replacing the old deprecating Genomics API (`v2alpha1`). It requires `--gcp-region` to be defined correctly. Check [supported regions](https://cloud.google.com/life-sciences/docs/concepts/locations) for the new API.

## Requirements

Make sure that `gcloud` (Google Cloud SDK CLI) is installed on your system.

Go to [APIs & Services](https://console.cloud.google.com/apis/dashboard) on your project and enable the following APIs on your Google Cloud console.
* Compute Engine API
* Cloud Storage: DO NOT click on `Create credentials`.
* Cloud Storage JSON API
* Google Cloud Life Sciences API

Go to [Service accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) on your project and create a new service account with enough permission to Compute Engine, Cloud Storage, Life Sciences API and **Service Account User** (VERY IMPORTANT). Generate a secret key JSON from it and keep it locally on your computer.

>**WARNING**: Such secret JSON file is a master key for important resources on your project. Keep it secure at your own risk. This file will be used for Caper so that it will be trasnferred to the created instance at `/opt/caper/service_account_key.json` visible to all users on the instance.

## Troubleshooting errors

If you see permission errors check if the above roles are correctly configured for your service account.

If you see PAPI errors and Google's HTTP endpoint deprecation warning. Remove Life Sciences API role from your service account and add it back.

## How to create an instance

Run without arguments to see detailed help. Some optional arguments are very important depending on your region/zone. e.g. `--gcp-region` (for Life Sciences API) and `--zone` (for instance creation). These regional parameters default to US central region/zones.
```bash
$ bash create_instance.sh
```

However, this script is designed to work well with default arguments. Try with positional arguments only first and see if it works.
```bash
$ bash create_instance.sh [INSTANCE_NAME] [PROJECT_ID] [GCP_SERVICE_ACCOUNT_KEY_JSON_FILE] [GCP_OUT_DIR]
```

Allow several minutes for the instance to finish up installing Caper and dependencies.

## How to run/stop/restart Caper server

Once the instance is created. It is recommended to make a new screen so that `caper server` runs inside it without interruption. On the screen, change directory to Caper directory and run `caper server`. You can monitor Cromwell's log on `/opt/caper/cromwell.out`.
```bash
$ sudo su
$ screen -RD caper_server
# in the screen
$ cd /opt/caper
$ caper server
```

To stop a Caper server, open the screen with the same command line used for creating one. Then press CTRL+C just one time. **DO NOT TYPE IT MULTIPLE TIMES**. This will prevent a graceful shutdown of Cromwell, which can corrupt a metadata DB.
```bash
$ sudo su
$ screen -RD caper_server
# in the screen, hit CTRL+C just one time
```

To change any parameters for Caper server/client, edit `/opt/caper/default.conf`. This file is shared among all users including `root`.

## How to submit a workflow

Check if `caper list` works without any network errors.
```bash
$ caper list
```

Submit a workflow.
```bash
$ caper submit [WDL] -i input.json ...
```

Caper will localize big data files on a GCS bucket directory `--gcp-loc-dir`, which defaults to `[GCP_OUT_DIR]/.caper_tmp/` if not defined. e.g. your FASTQs and reference genome data defined in an input JSON.


## Example

```bash
$ ./create_instance.sh xxxxxxxxxxxxx-caper-server xxxxxxxxxxxxx ~/.ssh/xxxxxxxxxxxxx-caper-server.json gs://xxxxxxxxxxxxx/caper_out --gcp-loc-dir gs://xxxxxxxxxxxxx/caper_tmp_dir --boot-disk-size 500GB
```
