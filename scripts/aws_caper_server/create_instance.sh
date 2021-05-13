#!/bin/bash
set -eo pipefail

if [[ $# -lt 1 ]]; then
  echo "Automated shell script to create Caper server instance with PostgreSQL on AWS."
  echo
  echo "Usage: ./create_instance.sh [INSTANCE_NAME] [AWS_REGION] [PUBLIC_SUBNET_ID] "
  echo "                            [AWS_BATCH_ARN] [KEY_PAIR_NAME] [AWS_OUT_DIR]"
  echo "                            <OPTIONAL_ARGUMENTS>"
  echo
  echo "Positional arguments:"
  echo "  [INSTANCE_NAME]: New instance's name (tag)."
  echo "  [AWS_REGION]: Region for AWS. us-east-1 by default."
  echo "  [PUBLIC_SUBNET_ID]: Public subnet ID. ID of \"Public subnet 1A\" under your VPC. e.g. subnet-0d9e1116acXXXXXXX."
  echo "  [AWS_BATCH_ARN]: AWS Batch Queue's ARN. --aws-batch-arn in Caper. Choose a default queue. e.g. arn:aws:batch:us-east-1:..."
  echo "  [KEY_PAIR_NAME]: AWS EC2 key pair name."
  echo "  [AWS_OUT_DIR]: s3:// bucket dir path for outputs. --aws-out-dir in Caper."
  echo
  echo "Optional arguments for Caper:"
  echo "  -l, --aws-loc-dir: s3:// bucket dir path for localization."
  echo "  --postgresql-db-ip: localhost by default."
  echo "  --postgresql-db-port: 5432 by default."
  echo "  --postgresql-db-user: cromwell by default."
  echo "  --postgresql-db-password: cromwell by default."
  echo "  --postgresql-db-name: cromwell by default."
  echo
  echo "Optional arguments for instance creation (gcloud compute instances create):"
  echo "  -i, --instance-type: Instance type. t2.xlarge by default."
  echo "  -b, --boot-disk-size: Boot disk size in GB. DO NOT USE ANY SIZE UNIT."
  echo "  --boot-disk-device-name: Boot disk type. /dev/sda1 by default."
  echo "  --ami-name-search-query: Operating system for the image. \"Ubuntu 18.04 LTS\" by default. Caper server requires Ubuntu/Debian based OS. Check https://docs.aws.amazon.com/opsworks/latest/userguide/workinginstances-os.html"
  echo

  if [[ $# -lt 6 ]]; then
    echo "Define all positional arguments."
  fi
  exit 1
fi

# parse opt args first.
POSITIONAL=()
while [[ $# -gt 0 ]]; do
  key="$1"
  case $key in
    -l|--aws-loc-dir)
      AWS_LOC_DIR="$2"
      shift
      shift
      ;;
    --postgresql-db-ip)
      POSTGRESQL_DB_IP="$2"
      shift
      shift
      ;;
    --postgresql-db-port)
      POSTGRESQL_DB_PORT="$2"
      shift
      shift
      ;;
    --postgresql-db-user)
      POSTGRESQL_DB_USER="$2"
      shift
      shift
      ;;
    --postgresql-db-password)
      POSTGRESQL_DB_PASSWORD="$2"
      shift
      shift
      ;;
    --postgresql-db-name)
      POSTGRESQL_DB_NAME="$2"
      shift
      shift
      ;;
    -i|--instance-type)
      INSTANCE_TYPE="$2"
      shift
      shift
      ;;
    -b|--boot-disk-size)
      BOOT_DISK_SIZE="$2"
      shift
      shift
      ;;
    --boot-disk-device-name)
      BOOT_DISK_DEVICE_NAME="$2"
      shift
      shift
      ;;
    --ami-name-search-query)
      AMI_NAME_SEARCH_QUERY="$2"
      shift
      shift
      ;;
    -*)
      echo "Wrong parameter: $1."
      shift
      exit 1
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

# restore pos args.
set -- "${POSITIONAL[@]}"

# parse pos args.
INSTANCE_NAME="$1"
AWS_REGION="$2"
PUBLIC_SUBNET_ID="$3"
AWS_BATCH_ARN="$4"
KEY_PAIR_NAME="$5"
AWS_OUT_DIR="$6"

# set defaults for opt args. (caper)
if [[ -z "$AWS_LOC_DIR" ]]; then
  AWS_LOC_DIR="$AWS_OUT_DIR"/.caper_tmp
fi
if [[ -z "$AWS_REGION" ]]; then
  AWS_REGION=us-east-1
fi
if [[ -z "$POSTGRESQL_DB_IP" ]]; then
  POSTGRESQL_DB_IP=localhost
fi
if [[ -z "$POSTGRESQL_DB_PORT" ]]; then
  POSTGRESQL_DB_PORT=5432
fi
if [[ -z "$POSTGRESQL_DB_USER" ]]; then
  POSTGRESQL_DB_USER=cromwell
fi
if [[ -z "$POSTGRESQL_DB_PASSWORD" ]]; then
  POSTGRESQL_DB_PASSWORD=cromwell
fi
if [[ -z "$POSTGRESQL_DB_NAME" ]]; then
  POSTGRESQL_DB_NAME=cromwell
fi

# set defaults for opt args.
if [[ -z "$INSTANCE_TYPE" ]]; then
  INSTANCE_TYPE=t2.xlarge
fi
if [[ -z "$BOOT_DISK_SIZE" ]]; then
  BOOT_DISK_SIZE=150
fi
if [[ -z "$BOOT_DISK_DEVICE_NAME" ]]; then
  BOOT_DISK_DEVICE_NAME="/dev/sda1"
fi
if [[ -z "$AMI_NAME_SEARCH_QUERY" ]]; then
  AMI_NAME_SEARCH_QUERY="ubuntu/images/hvm-ssd/ubuntu-bionic-18.04-amd64*"
fi

# validate all args.
if [[ "$PUBLIC_SUBNET_ID" != subnet-* ]]; then
  echo "[PUBLIC_SUBNET_ID] should start with subnet-."
  exit 1
fi
if [[ "$AWS_BATCH_ARN" != arn* ]]; then
  echo "[AWS_BATCH_ARN] is not valid."
  exit 1
fi
if [[ "$AWS_OUT_DIR" != s3://* ]]; then
  echo "[AWS_OUT_DIR] should be a S3 bucket path starting with s3://."
  exit 1
fi
if [[ "$AWS_LOC_DIR" != s3://* ]]; then
  echo "-l, --aws-loc-dir should be a S3 bucket path starting with s3://."
  exit 1
fi
if [[ -z "$KEY_PAIR_NAME" ]]; then
  echo "[KEY_PAIR_NAME] is not valid."
  exit 1
fi
if [[ "$POSTGRESQL_DB_IP" == localhost && "$POSTGRESQL_DB_PORT" != 5432 ]]; then
  echo "--postgresql-db-port should be 5432 for locally installed PostgreSQL (--postgresql-db-ip localhost)."
  exit 1
fi

# constants for files/params on instance.
AWS_AUTH_SH="/etc/profile.d/aws-auth.sh"
CAPER_CONF_DIR=/opt/caper
ROOT_CAPER_CONF_DIR=/root/.caper
GLOBAL_CAPER_CONF_FILE="$CAPER_CONF_DIR/default.conf"

# prepend more init commands to the startup-script
STARTUP_SCRIPT="""#!/bin/bash
### install gsutil
sudo apt-get install google-cloud-sdk

### update apt and install and packages
sudo apt-get update
sudo apt-get -y install screen python3 python3-pip default-jre postgresql postgresql-contrib

### install gsutil
sudo apt-get -y install apt-transport-https ca-certificates gnupg
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
sudo apt-get update
sudo apt-get -y install google-cloud-sdk

### make caper's work directory
sudo mkdir -p $CAPER_CONF_DIR
sudo chmod 777 -R $CAPER_CONF_DIR
sudo setfacl -d -m u::rwX $CAPER_CONF_DIR
sudo setfacl -d -m g::rwX $CAPER_CONF_DIR
sudo setfacl -d -m o::rwX $CAPER_CONF_DIR

### make caper's out/localization directory
sudo mkdir -p $CAPER_CONF_DIR/local_loc_dir $CAPER_CONF_DIR/local_out_dir

### make caper conf file
cat <<EOF > $GLOBAL_CAPER_CONF_FILE
# caper
backend=aws
no-server-heartbeat=True
# cromwell
max-concurrent-workflows=300
max-concurrent-tasks=1000
# local backend
local-out-dir=$CAPER_CONF_DIR/local_out_dir
local-loc-dir=$CAPER_CONF_DIR/local_loc_dir
# aws backend
aws-batch-arn=$AWS_BATCH_ARN
aws-region=$AWS_REGION
aws-out-dir=$AWS_OUT_DIR
aws-loc-dir=$AWS_LOC_DIR
# metadata DB
db=postgresql
postgresql-db-ip=$POSTGRESQL_DB_IP
postgresql-db-port=$POSTGRESQL_DB_PORT
postgresql-db-user=$POSTGRESQL_DB_USER
postgresql-db-password=$POSTGRESQL_DB_PASSWORD
postgresql-db-name=$POSTGRESQL_DB_NAME
EOF
sudo chmod +r $GLOBAL_CAPER_CONF_FILE

### soft-link conf file for root
sudo mkdir -p $ROOT_CAPER_CONF_DIR
sudo ln -s $GLOBAL_CAPER_CONF_FILE $ROOT_CAPER_CONF_DIR

### caper conf shared with all users
sudo touch $AWS_AUTH_SH
echo \"mkdir -p ~/.caper\" >> $AWS_AUTH_SH
echo \"ln -s /opt/caper/default.conf ~/.caper/ 2> /dev/null | true\" >> $AWS_AUTH_SH
"""

# append more init commands to the startup-script
STARTUP_SCRIPT="""$STARTUP_SCRIPT
### init PostgreSQL for Cromwell
sudo -u postgres createuser root -s
sudo createdb $POSTGRESQL_DB_NAME
sudo psql -d $POSTGRESQL_DB_NAME -c \"create extension lo;\"
sudo psql -d $POSTGRESQL_DB_NAME -c \"create role $POSTGRESQL_DB_USER with superuser login password '$POSTGRESQL_DB_PASSWORD'\"

### upgrade pip and install caper croo
sudo python3 -m pip install --upgrade pip
sudo -H pip3 install --ignore-installed PyYAML
sudo pip install caper croo
"""

echo "$(date): Making a temporary startup script..."
echo "$STARTUP_SCRIPT" > tmp_startup_script.sh

# find the most recent AMI matching the name search query
# https://gist.github.com/vancluever/7676b4dafa97826ef0e9
echo "$(date): Searching for AMI with name matching \"${AMI_NAME_SEARCH_QUERY}\" in region ${AWS_REGION}..."
AMI=$(aws --region "${AWS_REGION}" ec2 describe-images --filters "Name=name,Values=${AMI_NAME_SEARCH_QUERY}" --query 'sort_by(Images,&CreationDate)[-1].ImageId')
AMI="${AMI%\"}"
AMI="${AMI#\"}"
echo "$(date): Found AMI: ${AMI}"

echo "$(date): Creating an instance..."
aws ec2 --region "${AWS_REGION}" run-instances \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${INSTANCE_NAME}}]" \
  --image-id "${AMI}" \
  --subnet-id "${PUBLIC_SUBNET_ID}" \
  --key-name "${KEY_PAIR_NAME}" \
  --block-device-mappings "DeviceName=${BOOT_DISK_DEVICE_NAME},Ebs={VolumeSize=${BOOT_DISK_SIZE}}" \
  --instance-type "${INSTANCE_TYPE}" \
  --user-data "file://tmp_startup_script.sh"
echo "$(date): Created an instance successfully."

echo "$(date): Deleting the temporary startup script..."
rm -f tmp_startup_script.sh

echo "$(date): Please allow 20-30 minutes for the startup script installing/configuring Caper."
echo "$(date): Run \"caper -v\" to check it's installed."
echo "$(date): Run \"aws configure\" as root so that Cromwell can use your AWS credentials to create instances and write outputs on the bucket."
