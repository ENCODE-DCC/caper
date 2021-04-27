## Configuration for S3 storage access

1. Sign up for an [AWS account](https://aws.amazon.com/account/).
2. Configure your AWS CLI. Enter key and password obtained from your account's IAM.
    ```bash
      $ aws configure
    ```

## Configuration for AWS backend (`aws`)

Please follow the above instruction for S3 storage access.

1. Click on [this](
https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=GenomicsVPC&templateURL=https://aws-quickstart.s3.amazonaws.com/quickstart-aws-vpc/templates/aws-vpc.template.yaml) to create a new AWS VPC. Make sure that the region on top right corner of the console page matches with your region of interest. Click on `Next` and then `Next` again. Agree to `Capabililties`. Click on `Create stack`.

2. Choose all available zones in `Availability Zones`. For example, if your region is `us-east-2`, then you will see `us-east-2a`, `us-east-2b` and  `us-east-2c`. Choose all.

3. Click on [this](https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=gwfcore&templateURL=https://aws-genomics-workflows.s3.amazonaws.com/src/templates/gwfcore/gwfcore-root.template.yaml) to create a new AWS Batch. Make sure that the region on top right corner of the console page matches with your region of interest. Click on `Next`.

4. There are several required parameters to be specified on this page
- `S3 Bucket name`: S3 bucket name to store outputs. This is not a full path for the output directory. It's just bucket's name.
- `Existing Bucket?`: `True` if the above bucket already exists.
- `VPC ID`: Choose the VPC `GenomicsVPC` that you just created.
- `VPC Subnet IDs`: Choose two private subnets created with the above VPC.
- `Template Root URL`: `https://caper-aws-genomics-workflows.s3-us-west-1.amazonaws.com/src/templates`.

5. Click on `Next` and then `Next` again. Agree to `Capabililties`. Click on `Create stack`.

6. Go to your [AWS Batch](https://console.aws.amazon.com/batch) and click on `Job queues` in the left sidebar.

7. Click on `default-*`. Get ARN for your batch under the key `Queue ARN`. Write this to Caper's confiugration file at `~/.caper/default.conf`. Also, specify the AWS region you are working on. Remove trailing letters like `a` and `b` from the region string.
  ```bash
  aws-batch-arn=[YOUR_AWS_BATCH_ARN]
  # example: us-east-1
  aws-region=[YOUR_REGION]
  ```

8. Go back to your [Amazon AWS EC2 console](https://console.aws.amazon.com/ec2).
9. Generate a key pair (`.pem`) to SSH into the server instance later.
10. Click on `Instances` in the left sidebar and then lick on `Launch instance`.
11. Choose the first AMI (Amazon Linux 2 AMI) or Ubuntu 18. Choose `t3.large`. and click on `Review and launch`.
12. Click on `3. Configure Instance` in the top middle of the page.
13. For `Network`, choose VPC generated (not a default one) from above steps. This VPC name will include your stack name in it.
14. Choose your key in Security settings.
15. Click on `Review and Launch` in the bottom right of the page and then click on `Launch` in the bottom right of the page.

Now SSH to your instance (with the `.pem` key file generated during step 3). In your instance, run the following:

```bash
$ sudo yum install -y python3 java git curl
$ pip3 install caper
```

Now you are ready to run Caper on an AWS instance. Specify backend `-b` as `aws`.
```bash
$ caper run [WDL] -i [INPUT_JSON] -b aws
```

Or, run a server and submit jobs to the server with `caper submit`.
```bash
$ caper server -b aws
```

## References

https://docs.opendata.aws/genomics-workflows/orchestration/cromwell/cromwell-overview/
