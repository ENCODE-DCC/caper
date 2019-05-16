#!/bin/bash
set -e

if [ $# -lt 1 ]; then
  echo "Usage: ./run_mysql_server_docker.sh [DB_DIR] [PORT] \
[MYSQL_USER] [MYSQL_PASSWORD] [CONTAINER_NAME]"
  echo
  echo "Example: run_mysql_server_docker.sh ~/cromwell_data_dir 3307"
  echo
  echo "[DB_DIR]: This directory will be mapped to '/var/lib/mysql' inside a container"
  echo "[PORT] (optional): MySQL database port for docker host (default: 3306)"
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

INIT_SQL="""
CREATE USER '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON ${CROMWELL_DB}.* TO '${MYSQL_USER}'@'%' WITH GRANT OPTION;
"""
RAND_STR=$(date | md5sum | awk '{print $1}')
TMP_INIT_DIR=${HOME}/.run_mysql_server_docker/${RAND_STR}
TMP_INIT_FILE=${TMP_INIT_DIR}/init_cromwell_user.sql

mkdir -p ${TMP_INIT_DIR}
echo ${INIT_SQL} > ${TMP_INIT_FILE}

echo "SECURITY WARNING: Your MySQL DB username/password can be exposed in \
${TMP_INIT_FILE}"

docker run --detach --name ${CONTAINER_NAME} \
-v ${DB_DIR}:/var/lib/mysql \
-v ${TMP_INIT_DIR}:/docker-entrypoint-initdb.d \
-e MYSQL_ROOT_PASSWORD=${MYSQL_PASSWORD} \
-e MYSQL_DATABASE=${CROMWELL_DB} \
--publish ${PORT}:3306 mysql

echo "All done."
