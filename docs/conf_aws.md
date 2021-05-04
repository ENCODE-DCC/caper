## Configuration for S3 storage access

1. Sign up for an [AWS account](https://aws.amazon.com/account/).

2. Make sure that your account has permission on two services (S3 and EC2).
- Admin: full permission on both EC2 and output S3 bucket.
- User: read/write permission on the output S3 bucket.

3. Configure your AWS CLI. Enter key and password obtained from your account's IAM.
```bash
$ aws configure
```

## Configuration for AWS backend

Please follow the above instruction for S3 storage access.

1. Click on [this](
https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=GenomicsVPC&templateURL=https://aws-quickstart.s3.amazonaws.com/quickstart-aws-vpc/templates/aws-vpc.template.yaml) to create a new AWS VPC. Make sure that the region on top right corner of the console page matches with your region of interest. Click on `Next` and then `Next` again. Agree to `Capabililties`. Click on `Create stack`.

2. Choose all available zones in `Availability Zones`. For example, if your region is `us-east-2`, then you will see `us-east-2a`, `us-east-2b` and  `us-east-2c`. Choose all.

3. Click on [this](https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=gwfcore&templateURL=https://aws-genomics-workflows.s3.amazonaws.com/src/templates/gwfcore/gwfcore-root.template.yaml) to create a new AWS Batch. Make sure that the region on top right corner of the console page matches with your region of interest. Click on `Next`.

4. There are several required parameters to be specified on this page
- `S3 Bucket name`: S3 bucket name to store your pipeline outputs. This is not a full path for the output directory. It's just bucket's name.
- `Existing Bucket?`: `True` if the above bucket already exists.
- `VPC ID`: Choose the VPC `GenomicsVPC` that you just created.
- `VPC Subnet IDs`: Choose two private subnets created with the above VPC.
- (**IMPORTANT**) `Template Root URL`: `https://caper-aws-genomics-workflows.s3-us-west-1.amazonaws.com/src/templates`.

5. Click on `Next` and then `Next` again. Agree to `Capabililties`. Click on `Create stack`.

6. Go to your [AWS Batch](https://console.aws.amazon.com/batch) and click on `Job queues` in the left sidebar. Click on `default-*`. Get ARN for your batch under the key `Queue ARN`. This ARN will be used later to create Caper server instance.



## References

https://docs.opendata.aws/genomics-workflows/orchestration/cromwell/cromwell-overview/
