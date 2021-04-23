## Configuration for S3 storage access

1. Sign up for an [AWS account](https://aws.amazon.com/account/).
2. Configure your AWS CLI. Enter key and password obtained from your account's IAM.
    ```bash
      $ aws configure
    ```

## Configuration for AWS backend (`aws`)

Please follow the above instruction for S3 storage access.

1. Follow [this](https://aws.amazon.com/quickstart/architecture/vpc/) to create a VPC (virtual private network) and its subnets.
  - Name tag: `vpc-caper`
  - IPv4 CIDR block: `10.0.0.0/24`
2. Click on `Subnets` on the left panel. Click on `Create`. Choose the VPC that you just created.
  - Subnet name: `subnet-caper`
  - IPv4 CIDR block: `10.0.0.0/24`
3. Open a web browser and authenticate yourself on [Amazon AWS EC2 console](https://console.aws.amazon.com/ec2).
4. Choose your region in the top right corner of the page. Click on `Services` in the top left corner and Choose `EC2`.
5. Click on `Key pairs` in the left side bar and Create a key pair. This will be later used to create an AWS instance for cromwell server.
  - Name: `key-caper`
  - File format: `pem`
6. Click on [this](https://console.aws.amazon.com/cloudformation/home?#/stacks/new?stackName=Cromwell&templateURL=https://caper-data.s3.amazonaws.com/aws-genomics-workflows-dist/templates/gwfcore/gwfcore-root.template.yaml). Choose your region again in the top right corner.
7. Click on `Next` in the bottom right of the page.
8. Complete `Specify stack details` form by filling the following items:
- `Stack name`: `stack-caper`
- `S3 Bucket Name`: Output bucket name. This should not include `s3://` and it should not be an existing bucket because it will be automatically created in this stack batch.
- `VPC ID`: VPC that you just created.
- `VPC Subnet IDs`: Subnet that you just created.
- `Namespace`: `caper`
- `Artifact S3 Bucket Name`: `caper-aws-genomics-workflows`.
- `Template Root URL`: `https://caper-aws-genomics-workflows.s3.amazonaws.com/templates`.

10. Expand `Stack create options` in the bottom of the page. Disable `Rollback on failure`. Click on `Next`.
11. Agree to `Capabilities` (two checkboxes). Click on `Create stack`.

12. Stack batch jobs will fail. But it's okay.
13. Go to your [AWS Batch](https://console.aws.amazon.com/batch).
14. Click on "Job queues" in the left sidebar.
15. Click on "default-*". Get ARN for your batch under the key "Queue ARN". Write this to Caper's confiugration file at `~/.caper/default.conf`. Also, specify AWS region you got from step 2). Remove trailing letters like `a` and `b` from the region string.
	```bash
	aws-batch-arn=[PASTE_YOUR_ARN_HERE]
	# example: us-east-1
	aws-region=[YOUR_REGION]
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
$ pip3 install caper
```

Now you are ready to run Caper on an AWS instance. Specify backend `-b` as `aws`.

```bash
$ caper run [WDL] -i [INPUT_JSON] -b aws
```

```bash
$ caper server -b aws
```
