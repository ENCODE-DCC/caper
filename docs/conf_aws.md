## Configuration for S3 storage access

1. Sign up for an [AWS account](https://aws.amazon.com/account/).
2. Configure your AWS CLI. Enter key and password obtained from your account's IAM.
    ```bash
      $ aws configure
    ```

## Configuration for AWS backend (`aws`)

1. Follow the above instruction for S3 storage access
2. Follow [this instruction](https://docs.opendata.aws/genomics-workflows/orchestration/cromwell/cromwell-overview/).

Unfortunately, the above instruction does not work currently. Hope Cromwell developers fix it soon. Until it's fixed, follow the below steps.

> **WARNING**: This is just a workaround and any batch actions taken will NOT BE ROLLED BACK. That means, you will see automatically generated objects with random names in your AWS IAM and AWS Batch.

1. Open a web browser and authenticate yourself on [Amazon AWS EC2 console](https://console.aws.amazon.com/ec2).
2. Choose your region in the top right corner of the page.
3. Click on "Key pairs" in the left side bar and Create a key pair. This will be later used to create an AWS instance for cromwell server.
4. Click on [this](https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=Cromwell&templateURL=https://s3.amazonaws.com/aws-genomics-workflows/templates/cromwell/cromwell-aio.template.yaml)
5. Click on "Next" in the bottom right of the page.
6. Specify your own "Stack name" and "S3 Bucket Name". "S3 Bucket Name" should not include `s3://` and it should not exist because it will be automatically created. Choose a key pair generated in step 3) for "EC2 Key Pair Name". Choose "AvailabilityZones". Click on "Next" in the bottom right of the page.
7. Expand "Stack create options" in the bottom of the page. Disable "Rollback on failure". Click on "Next".
8. Agree to "Capabilities" (two checkboxes). Click on "Create stack".
9. Stack batch jobs will fail. But it's okay.
10. Go to your [AWS Batch](https://console.aws.amazon.com/batch).
11. Click on "Job queues" in the left sidebar.
12. Click on "default-*". Get ARN for your batch under the key "Queue ARN". Write this to Caper's confiugration file at `~/.caper/default.conf`. Also, specify AWS region you got from step 2). Remove trailing letters like `a` and `b` from the region string.

	```bash
	aws-batch-arn=[PASTE_YOUR_ARN_HERE]
	aws-region=us-east-1
	```

13. Go back to your [Amazon AWS EC2 console](https://console.aws.amazon.com/ec2).
14. Click on "Instances" in the left sidebar.
15. Click on "Launch instance".
16. Choose the first AMI (Amazon Linux 2 AMI). Choose "t3.large". and click on "Review and launch"
17. Click on "3. Configure Instance" in the top middle of the page.
18. For "Network", choose VPC generated (not a default one) from above steps. This VPC name will include your stack name in it.
19. For "IAM role", choose IAM role generated (not a default one) from above steps. This IAM role name will include your stack name in it.
20. Click on "Review and Launch" in the bottom right of the page.
21. Click on "Launch" in the bottom right of the page.

Now SSH to your instance (with the `.pem` key file generated during step 3). In your instance, run the following:

```bash
$ sudo yum install -y python3 java git curl
$ pip3 install caper3
```

Now you are ready to run Caper on an AWS instance. Specify backend `-b` as `aws`.

```bash
$ caper run [WDL] -i [INPUT_JSON] -b aws
```

```bash
$ caper server -b aws
```
