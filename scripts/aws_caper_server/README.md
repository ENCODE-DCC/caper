## Introduction

`create_instance.sh` will create a new Caper server instance on your AWS EC2 region and configure the instance for Cromwell with PostgreSQL database.


## AWS account

1. Sign up for an [AWS account](https://aws.amazon.com/account/).
2. Make sure that your account has full permission on two services (S3 and EC2).
3. Configure your AWS CLI. Enter key, secret (password) and region (**IMPORTANT**) obtained from your account's IAM.
```bash
$ aws configure
```

## VPC

1. Click on [this](
https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=GenomicsVPC&templateURL=https://aws-quickstart.s3.amazonaws.com/quickstart-aws-vpc/templates/aws-vpc.template.yaml) to create a new AWS VPC. Make sure that the region on top right corner of the console page matches with your region of interest. Click on `Next` and then `Next` again. Agree to `Capabililties`. Click on `Create stack`.
2. Choose available zones in `Availability Zones`. For example, if your region is `us-west-2`, then you will see `us-west-2a`, `us-west-2b` and  `us-west-2c`. Caper server will create job instances on selected zones.


## AWS Batch

1. Click on [this](
https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=gwfcore&templateURL=https://aws-genomics-workflows.s3.amazonaws.com/v3.0.6.1/templates/gwfcore/gwfcore-root.template.yaml) to create a new AWS Batch. Make sure that the region on top right corner of the console page matches with your region of interest. Click on `Next`.
2. There are several required parameters to be specified on this page
- `S3 Bucket name`: S3 bucket name to store your pipeline outputs. This is not a full path for the output directory. It's just bucket's name.
- `Existing Bucket?`: `True` if the above bucket already exists.
- `VPC ID`: Choose the VPC `GenomicsVPC` that you just created.
- `VPC Subnet IDs`: Choose two private subnets created with the above VPC.
- (**IMPORTANT**) `Template Root URL`: Change it to `https://caper-aws-genomics-workflows.s3-us-west-1.amazonaws.com/src/templates`.
3. Click on `Next` and then `Next` again. Agree to `Capabililties`. Click on `Create stack`.
4. Go to your [AWS Batch](https://console.aws.amazon.com/batch) and click on `Job queues` in the left sidebar. Click on `default-*`. Get ARN for your batch under the key `Queue ARN`. This ARN will be used later to create Caper server instance.


## How to create a server instance

Run without parameters to see detailed help.
```bash
$ bash create_instance.sh
```

Try with the positional arguments only first and see if it works.
```bash
$ bash create_instance.sh [INSTANCE_NAME] [AWS_REGION] [PUBLIC_SUBNET_ID] [AWS_BATCH_ARN] [KEY_PAIR_NAME] [AWS_OUT_DIR]
```

- `AWS_REGION`: Your AWS region. e.g. `us-west-2`. Make sure that it matches with `region` in your AWS credentials file `$HOME/.aws/credentials`.
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
$ sudo su
$ cd /opt/caper
$ screen -dmS caper_server bash -c "caper server > caper_server.log 2>&1"
```

## How to submit a workflow

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


## Using S3 URIs in input JSON

**VERY IMPORTANT!**

Caper localizes input files on output S3 bucket path + `./caper_tmp` if they are given as non-S3 URIs (e.g. `gs://example/ok.txt`, `http://hello,com/a.txt`, `/any/absolute/path.txt`). However if S3 URIs are given in an input JSON then Caper will not localize them and will directly pass them to Cromwell. However, Cromwell is very picky about **region** and **permission**.

First of all **PLEASE DO NOT USE ANY EXTERNAL S3 FILES OUT OF YOUR REGION**. Call-caching will not work for those external files. For example, if your Caper server resides on `us-west-2` and you want to use a Broad reference file `s3://broad-references/hg38/v0/Homo_sapiens_assembly38.dict`. All broad data are on `us-east-1` so call-caching will never work.

Another example is ENCODE portal's file. [This FASTQ file](`https://www.encodeproject.org/files/ENCFF641SFZ/`) has a public S3 URI in metadata, which is `s3://encode-public/2017/01/27/92e9bb3b-bc49-43f4-81d9-f51fbc5bb8d5/ENCFF641SFZ.fastq.gz`. All ENCODE portal's data are on `us-west-2`. Call-caching will not work other regions. It's recommended to directly use the URL of this file `https://www.encodeproject.org/files/ENCFF641SFZ/@@download/ENCFF641SFZ.fastq.gz` in input JSON.

**DO NOT USE S3 FILES ON A PRIVATE BUCKET**. Job instances will not have access to those private files even though the server instance has one (with your credentials configured with `aws configure`). For example, ENCODE portal's unreleased files are on a private bucket `s3://encode-priavte`. Jobs will always fail if you use these private files.

If S3 files in an input JSON are public in the same region then check if you have `s3:GetObjectAcl` permission on the file.
```bash
$ aws s3api get-object-acl --bucket encode-public --key 2017/01/27/92e9bb3b-bc49-43f4-81d9-f51fbc5bb8d5/ENCFF641SFZ.fastq.gz
{
    "Owner": {
        "DisplayName": "encode-data",
        "ID": "50fe8c9d2e5e9d4db8f4fd5ff68ec949de9d4ca39756c311840523f208e7591d"
    },
    "Grants": [
        {
            "Grantee": {
                "DisplayName": "encode-aws",
                "ID": "a0dd0872acae5121b64b11c694371e606e28ab2e746e180ec64a2f85709eb0cd",
                "Type": "CanonicalUser"
            },
            "Permission": "FULL_CONTROL"
        },
        {
            "Grantee": {
                "Type": "Group",
                "URI": "http://acs.amazonaws.com/groups/global/AllUsers"
            },
            "Permission": "READ"
        }
    ]
}
```
If you get `403 Permission denied` then call-caching will not work.

To avoid all permission/region problems, please use non-S3 URIs/URLs.


## References

https://docs.opendata.aws/genomics-workflows/orchestration/cromwell/cromwell-overview.html


## Troubleshooting

See [this] for troubleshooting.
