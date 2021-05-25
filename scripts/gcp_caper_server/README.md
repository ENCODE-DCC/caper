## Introduction

`create_instance.sh` will create an instance on Google Cloud Compute Engine in Google your project and configure the instance for Caper with PostgreSQL database and Google Cloud Life Sciences API (`v2beta`).

> **NOTE**: Google Cloud Life Sciences API is a new API replacing the old deprecating Genomics API (`v2alpha1`). It requires `--gcp-region` to be defined correctly. Check [supported regions](https://cloud.google.com/life-sciences/docs/concepts/locations) for the new API.

## Install Google Cloud SDK SLI

Make sure that `gcloud` (Google Cloud SDK CLI) is installed on your system.

Go to [APIs & Services](https://console.cloud.google.com/apis/dashboard) on your project and enable the following APIs on your Google Cloud console.
* Compute Engine API
* Cloud Storage: DO NOT click on `Create credentials`.
* Cloud Storage JSON API
* Google Cloud Life Sciences API

Go to [Service accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) on your project and create a new service account with the following roles:
* Compute Admin
* Storage Admin: You can skip this and individually configure permission on each bucket on the project.
* Cloud Life Sciences Admin (Cromwell's PAPI v2beta)
* **Service Account User** (VERY IMPORTANT).

Generate a secret key JSON from the service account and keep it locally on your computer.

> **WARNING**: Such secret JSON file is a master key for important resources on your project. Keep it secure at your own risk. This file will be used for Caper so that it will be trasnferred to the created instance at `/opt/caper/service_account_key.json` visible to all users on the instance.

## How to create an instance

Run without arguments to see detailed help. Some optional arguments are very important depending on your region/zone. e.g. `--gcp-region` (for provisioning worker instances of Life Sciences API) and `--zone` (for server instance creation only). These regional parameters default to US central region/zones.
```bash
$ bash create_instance.sh
```

However, this script is designed to work well with default arguments. Try with positional arguments only first and see if it works.
```bash
$ bash create_instance.sh [INSTANCE_NAME] [PROJECT_ID] [GCP_SERVICE_ACCOUNT_KEY_JSON_FILE] [GCP_OUT_DIR]
```

This script will run Caper server by user `root` in a `screen` named `caper_server` at the end the installation.


## How to stop Caper server

On the instance, attach to the existing screen `caper_server`, stop it with Ctrl + C.
```bash
$ sudo su # log-in as root
$ screen -r caper_server # attach to the screen
# in the screen, press Ctrl + C to send SIGINT to Caper
```

## How to start Caper server

On the instance, make a new screen `caper_server`.
```bash
$ cd /opt/caper
$ screen -dmS caper_server bash -c "caper server > caper_server.log 2>&1"
```

## How to submit workflow

Check if `caper list` works without any network errors.
```bash
$ caper list
```

Submit a workflow.
```bash
$ caper submit [WDL] -i input.json ...
```

Caper will localize big data files on a GCS bucket directory `--gcp-loc-dir`, which defaults to `[GCP_OUT_DIR]/.caper_tmp/` if not defined. e.g. your FASTQs and reference genome data defined in an input JSON.


## How to configure Caper

**This section is for advanced users only**. Caper tries to find a default configuration file at `~/.caper/default.conf` which is symlinked from `/opt/caper/default.conf`. `/opt/caper/default.conf` is a globally shared configuration file. Edit this file for both server/client.

Everytime a user logs in, symlinking is reset. It is controlled by `/etc/profile.d/gcp-auth.sh`.
```bash
gcloud auth activate-service-account --key-file=/opt/caper/service_account_key.json
mkdir -p ~/.caper
ln -s /opt/caper/default.conf ~/.caper/ 2> /dev/null | true
```

If users want to have their own configuration at `~/.caper/default.conf`, simply delete this symlink and make a copy of globally shared one.
```bash
$ rm ~/.caper/default.conf
$ cp /opt/caper/default.conf ~/.caper/default.conf
```


## Troubleshooting

See [this] for troubleshooting.
