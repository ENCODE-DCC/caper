#!/bin/bash
set -e

if [ $# -lt 1 ]; then
  echo "Usage: ./run_mysql_server_singularity.sh [DB_DIR] [PORT] \
[MYSQL_USER] [MYSQL_PASSWORD] [CONTAINER_NAME]"
  echo
  echo "Example: run_mysql_server_singularity.sh ~/cromwell_data_dir 3307"
  echo
  echo "[DB_DIR]: This directory will be mapped to '/var/lib/mysql' inside a container"
  echo "[PORT] (optional): MySQL database port for singularity host (default: 3306)"
  echo "[MYSQL_USER] (optional): MySQL username (default: cromwell)"
  echo "[MYSQL_PASSWORD] (optional): MySQL password (default: cromwell)"
  echo "[CONTAINER_NAME] (optional): MySQL container name (default: mysql_cromwell)"
  echo
  exit 1
fi

# check if DB_DIR exists
if [ ! -d "$1" ]; then
  echo "[DB_DIR] ($1) doesn't exists."
  exit 1
fi
DB_DIR=$(cd $(dirname $1) && pwd -P)/$(basename $1)

# check if PORT taken
if [ $# -gt 1 ]; then PORT=$2; else PORT=3306; fi
if [ ! -z "$(netstat -tulpn 2>/dev/null | grep LISTEN | grep \:${PORT})" ]; then
  echo "[PORT] (${PORT}) already taken."
  exit 1
fi

if [ $# -gt 2 ]; then MYSQL_USER=$3; else MYSQL_USER=cromwell; fi
if [ $# -gt 3 ]; then MYSQL_PASSWORD=$4; else MYSQL_PASSWORD=cromwell; fi
if [ $# -gt 4 ]; then CONTAINER_NAME=$5; else CONTAINER_NAME=mysql_cromwell; fi
CROMWELL_DB=cromwell_db

RAND_STR=$(date | md5sum | awk '{print $1}')

TMP_MYSQLD=${HOME}/.run_mysql_server_singularity/${RAND_STR}/mysqld
TMP_CNF_FILE=${HOME}/.my.cnf
TMP_ROOT_PW_SQL_FILE=${HOME}/.mysqlrootpw

mkdir -p ${TMP_MYSQLD}

cat > ${TMP_CNF_FILE} << EOM
[mysqld]
innodb_use_native_aio=0
init-file=${HOME}/.mysqlrootpw
port=${PORT}

[client]
user=root
password='my-secret-pw'
EOM

cat > ${TMP_ROOT_PW_SQL_FILE} << EOM
SET PASSWORD FOR 'root'@'localhost' = PASSWORD('my-secret-pw');
EOM

singularity instance start \
--bind ${HOME} \
--bind ${DB_DIR}:/var/lib/mysql \
--bind ${TMP_MYSQLD}:/var/run/mysqld \
shub://ISU-HPC/mysql ${CONTAINER_NAME}

INIT_SQL="CREATE DATABASE ${CROMWELL_DB}; CREATE USER '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON ${CROMWELL_DB}.* TO '${MYSQL_USER}'@'%' WITH GRANT OPTION;"

singularity run instance://${CONTAINER_NAME}
echo "Creating user ${MYSQL_USER}"
sleep 10

singularity exec instance://${CONTAINER_NAME} mysql -e "${INIT_SQL}" || true

echo "All done. You can ignore any error messages occurred when creating a user."
