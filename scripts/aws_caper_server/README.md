## Introduction

`create_instance.sh` will create a new Caper server instance on your AWS EC2 region and configure the instance for Cromwell with PostgreSQL database.


## Requirements

Follow these two instructions before running the shell script.
- [Configuration for S3 storage access](../../docs/conf_aws.md#Configuration-for-S3-storage-access)
- [Configuration for AWS backend](../../docs/conf_aws.md#Configuration-for-AWS-backend)


## How to create an instance (admin)

Run without parameters to see detailed help.
```bash
$ bash create_instance.sh
```

Try with the positional arguments only first and see if it works.
```bash
$ bash create_instance.sh [INSTANCE_NAME] [AWS_REGION] [PUBLIC_SUBNET_ID] [AWS_BATCH_ARN] [KEY_PAIR_NAME] [AWS_OUT_DIR]
```

- `AWS_REGION`: Your AWS region. e.g. `us-east-1`. Make sure that it matches with `region` in your AWS credentials file `$HOME/.aws/credentials`.
- `PUBLIC_SUBNET_ID`: Click on `Services` on AWS Console and Choose `VPC`. Click on `Subnets` on the left sidebar and find `Public subnet 1` under your VPC created from the above instruction.
- `AWS_BATCH_ARN`: ARN of the AWS Batch created from the above instruction. Double-quote the whole ARN since it includes `:`.
- `KEY_PAIR_NAME`: Click on `Services` on AWS Console and Choose `EC2`. Choose `Key Pairs` on the left sidebar and create a new key pair (in `.pem` format). Take note of the key name and keep the `.pem` key file on a secure directory where you want to SSH to the instance from. You will need it later when you SSH to the instancec.
- `AWS_OUT_DIR`: Full output directory path starting with the bucket name you used in the above instruction. This directory should start with `s3://`. e.g. `s3://caper-server-out-bucket/out`.

Go to the AWS Console and Click on `Services` on AWS Console and Choose `EC2`. Click on `Instances` on the left sidebar and find the created instance. Click on the instance.

Click on `Security` and find `Security groups`. Click on the security group. Add an inbound rule. Choose type `SSH` and define CIDR for your IP range. Setting it to `0.0.0.0/0` will open the VPC to the world.

> **IMPORTANT**: It is a default security group for the VPC so use it at your own risk. It's recommended to calculate CIDR for your computer/company and use it here.

Go back to `Instances` on the console and find the server instance. Get the command line to SSH to it. Make sure that you have the `.pem` key file on your local computer.

Connect to the instance and wait until `caper -v` works. Allow 20-30 minutes for Caper installation.
```bash
$ caper -v
```

Authenticate yourself for AWS services.
```bash
$ sudo su
$ aws configure
# enter your AWS credential and region (IMPORTANT)
```

Run Caper server.
```bash
# cd to caper's main directory
$ sudo su
$ cd /opt/caper
$ screen -dmS caper_server bash -c "caper server > caper_server.log 2>&1"
```

## How to stop Caper server (admin)

On the instance, attach to the existing screen `caper_server`, stop it with Ctrl + C.
```bash
$ sudo su # log-in as root
$ screen -r caper_server # attach to the screen
# in the screen, press Ctrl + C to send SIGINT to Caper
```

## How to start Caper server (admin)

On the instance, make a new screen `caper_server`.
```bash
$ sudo su
$ cd /opt/caper
$ screen -dmS caper_server bash -c "caper server > caper_server.log 2>&1"
```

## How to submit workflow (user)

For the first log-in, authenticate yourself to get permission to read/write on the output S3 bucket. This is to localize any external URIs (defined in an input JSON) on the output S3 bucket's directory with suffix `.caper_tmp/`. Make sure that you have full permission on the output S3 bucket.
```bash
$ aws configure
# enter your AWS credential and correct region (IMPORTANT)
```

Check if `caper list` works without any network errors.
```bash
$ caper list
```

Submit a workflow.
```bash
$ caper submit [WDL] -i input.json ...
```

Caper will localize big data files on a S3 bucket directory `--aws-loc-dir` (or `aws-loc-dir` in the Caper conf file), which defaults to `[AWS_OUT_DIR]/.caper_tmp/` if not defined. e.g. your FASTQs and reference genome data defined in an input JSON.
