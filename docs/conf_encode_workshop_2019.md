# Welcome to the 2019 ENCODE Users' Meeting Pipeline Workshop

## Do this before the workshop

0. Register by following instructions in the email you received with the subject "Welcome to Using ENCODE in the Cloud".

1. Open a web browser (Chrome, Safari, or Edge - Firefox is not supported) and go to [our workshop server instance on Google Cloud Platform console](https://console.cloud.google.com/compute/instancesDetail/zones/us-west1-b/instances/workshop-server?project=encode-workshop).

2. Click on the `SSH` button under `Remote Access`.  It may sake several seconds to open a connection to the server instance.
> **WARNING**: If it takes too long (>2 minutes) to log in, then switch to a "Cloud Shell" method. Click on the inverse triangle next to "SSH" button and choose "View gcloud command". Click on "RUN IN CLOUD SHELL" button in the bottom-right corner. Push Enter to execute the copied command line. Answer "Y" to the question. Push Enter twice to pass two questions.

3. Set up your server account:  Soft-link a shared configuration file.
```bash
$ mkdir -p ~/.caper && cd ~/.caper
$ ln -s /opt/code/default.conf default.conf
```

4. Authenticate yourself to get access to buckets.
```bash
$ gcloud auth login --no-launch-browser
$ gcloud auth application-default login --no-launch-browser
```

## To do together during workshop

> **WARNING**: **USERS SHOULD NOT FOLLOW THE BELOW STEPS BEFORE THE WORKSHOP**.

5. Submit a workflow to Caper server.
```bash
$ caper submit /opt/code/rna-seq-pipeline/rna-seq-pipeline.wdl -i gs://encode-workshop-samples/rna-seq-pipeline/input_workshop_example_SSD.json
# you will see the following message. make sure to remember the workflow_id
# in this example, the workflow_id is f7094621-3d38-48a6-b877-1da2b0cec931
[Caper] submit:  {'id': 'f7094621-3d38-48a6-b877-1da2b0cec931', 'status': 'Submitted'}
```

6. Make sure to remember `workflow_id` of your submitted workflow. You can monitor workflows with:
```bash
$ caper list [WORKFLOW_ID]
```

7. Once your workflow is done (marked as `Succeeded`). Retrieve a `metadata.json` with the following command:
```bash
$ caper metadata [WORKFLOW_ID] > metadata.json
```

8. Run Croo with the retrieved `metadata.json` to organized outputs on `--out-dir`.
```bash
$ croo metadata.json --out-dir gs://encode-workshop-croo/$USER --out-def-json /opt/code/rna-seq-pipeline/output_definition.json
```

9. Open a web browser and go to [Google Cloud Storage console](https://console.cloud.google.com/storage/browser/encode-workshop-croo/?project=encode-workshop&folder=true&organizationId=true).

10. Navigate to your organized output directory under your username. For example, `gs://encode-workshop-croo/[YOUR_USER_NAME]/`. Click on an HTML file then you will see a nice file table summarizing all outputs with description. Find any bigwig file in it and take a URL for it. That URL will be public so you can use it to visualize the track with your preferred genome browser (for example, you can use [this one](http://epigenomegateway.wustl.edu/legacy/)).


## Setting up a Caper server instance (ADMIN ONLY)

This example is to set up a server instance for the ENCODE workshop 2019 at Seattle. However, this example should also be helpful to set up your own server instance.

> **WARNING**: This section is for admins only. **USERS SHOULD NOT FOLLOW THE BELOW STEPS ON THE INSTANCE**.

1. Create an instance with Debian-based Linux (e.g. Ubuntu). Minimum requirements for the server is CPU >=4, Memorsy > 16GB.

2. Install softwares. Install Caper (Cromwell wrapper) and Croo (Cromwell output organizer).
```bash
$ sudo apt-get update && sudo apt-get install -y default-jdk acl python3 python3-pip git wget curl htop
$ sudo pip3 install caper croo
```

3. Clone pipeline codes and share them with users. This example will install ENCODE RNA-Seq and Demo pipelines on `/opt/code`.
```bash
$ sudo mkdir /opt/code
$ sudo chown $USER:$USER /opt/code
$ cd /opt/code
$ git clone https://github.com/ENCODE-DCC/rna-seq-pipeline
$ git clone https://github.com/ENCODE-DCC/demo-pipeline
```

4. Authenticate yourself.
```bash
$ gcloud auth login --no-launch-browser
$ gcloud auth application-default login --no-launch-browser
```

5. Create a scratch directory for Caper. Any subdirectories under `/srv/scratch` will inherit permissions from their parent directory.
```bash
$ sudo mkdir /srv/scratch
$ sudo chown $USER:$USER /srv/scratch
$ sudo chmod 777 /srv/scratch
$ sudo setfacl -d -m u::rwx /srv/scratch
$ sudo setfacl -d -m g::rwx /srv/scratch
$ sudo setfacl -d -m o::rwx /srv/scratch
```

6. Create a Caper configuration file, which will be shared with all users.
```bash
$ touch /opt/code/default.conf
```

7. Edit the shared configuration file `/opt/code/default.conf`. You can comment settings for the ENCODE workshop 2019 and uncomment/define your own `gcp-prj`, `tmp-gcs-bucket` and `out-gcs-bucket`.
```bash
[defaults]
cromwell=/opt/code/cromwell-42.jar
java-heap-server=8G

backend=gcp

out-dir=/srv/scratch/caper_out
tmp-dir=/srv/scratch/caper_tmp

#gcp-prj=[YOUR_GOOGLE_PROJECT]
gcp-prj=encode-workshop

#out-gcs-bucket=[YOUR_OUTPUT_BUCKET_FOR_CAPER]
#tmp-gcs-bucket=[YOUR_TMP_BUCKET_FOR_CAPER]
out-gcs-bucket=gs://encode-workshop-outputs/caper_out
tmp-gcs-bucket=gs://encode-workshop-outputs/caper_tmp

max-concurrent-workflows=100
```

8. Download Cromwell 42 JAR and share it with all users.
```bash
$ cd /opt/code
$ wget https://github.com/broadinstitute/cromwell/releases/download/42/cromwell-42.jar
```

9. Soft-link a shared configuration file.
```bash
$ mkdir -p ~/.caper && cd ~/.caper
$ ln -s /opt/code/default.conf default.conf
```

10. Create Caper's output bucket `gs://encode-workshop-outputs`.

11. Make the bucket public by adding a `Storage Object Viewer` role for `allUsers` to the bucket. This will allow public HTTP access to all files on the bucket, which will be used to visualize some of pipeline outputs (e.g. bigwigs) on a genome browser.

12. Give write permission to **ALL WORKSHOP PARTICIPANTS* (not for all public users). Add `Storage Object Creator` role to all participants. This is to give all participants write access to Caper tmp directory `gs://encode-workshop-outputs/caper_tmp` so that `--deepcopy` does not make duplicate files on the shared bucket. This will also give them write access to `gs://encode-workshop-outputs/croo` so that their organized outputs generates from Croo will be write on that bucket directory.

13. Run a Caper server.
```bash
$ caper server
```

14. Make all buckets public (Read access to anyone).

15. Give users the following IAM Roles:

1) For the whole project
	- Compute Engine > Compute Instance Admin (v1)
	- Compute Engine > Compute OS Login
	- Service Account > Service Account User

2) For the croo bucket (`gs://encode-workshop-croo`)
	- Storage Object Admin
