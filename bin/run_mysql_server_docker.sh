#!/bin/bash
set -e

if [ $# -lt 1 ]; then
  echo "Usage: ./run_mysql_server_docker.sh [DB_DIR] [PORT] [CONTAINER_NAME] \
[MYSQL_USER] [MYSQL_PASSWORD] [MYSQL_DB_NAME]"
  echo
  echo "Example: run_mysql_server_docker.sh ~/cromwell_data_dir 3307 mysql_cromwell2"
  echo
  echo "[DB_DIR]: This directory will be mapped to '/var/lib/mysql' inside a container"
  echo "[PORT] (optional): MySQL database port for docker host (default: 3306)"
  echo "[CONTAINER_NAME] (optional): MySQL container name (default: mysql_cromwell)"
  echo "[MYSQL_USER] (optional): MySQL username (default: cromwell)"
  echo "[MYSQL_PASSWORD] (optional): MySQL password (default: cromwell)"
  echo "[MYSQL_DB_NAME] (optional): MySQL database name. Match it with Caper's --mysql-db-name (default: cromwell)"
  echo
  exit 1
fi

# check if DB_DIR exists
if [ ! -d "$1" ]; then
  echo "[DB_DIR] ($1) doesn't exists."
  exit 1
fi
DB_DIR=$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")

# check if PORT is taken
if [ $# -gt 1 ]; then PORT=$2; else PORT=3306; fi
if netstat -tulpn 2>/dev/null | grep LISTEN | grep ":${PORT}" | grep -q ^; then
  echo "[PORT] (${PORT}) already taken."
  exit 1
fi

if [ $# -gt 2 ]; then CONTAINER_NAME=$3; else CONTAINER_NAME=mysql_cromwell; fi
if [ $# -gt 3 ]; then MYSQL_USER=$4; else MYSQL_USER=cromwell; fi
if [ $# -gt 4 ]; then MYSQL_PASSWORD=$5; else MYSQL_PASSWORD=cromwell; fi
if [ $# -gt 5 ]; then MYSQL_DB_NAME=$6; else MYSQL_DB_NAME=cromwell; fi

INIT_SQL="""
CREATE USER '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON ${MYSQL_DB_NAME}.* TO '${MYSQL_USER}'@'%' WITH GRANT OPTION;
"""
RAND_STR=$(date | md5sum | awk '{print $1}')
TMP_INIT_DIR=${HOME}/.run_mysql_server_docker/${RAND_STR}
TMP_INIT_FILE=${TMP_INIT_DIR}/init_cromwell_user.sql

rm -rf "${TMP_INIT_DIR}"
mkdir -p "${TMP_INIT_DIR}"
echo "${INIT_SQL}" > "${TMP_INIT_FILE}"

echo "SECURITY WARNING: Your MySQL DB username/password can be exposed in \
${TMP_INIT_FILE}"

chown ${UID} -R "${DB_DIR}"
docker run -d --rm --user ${UID} \
--name "${CONTAINER_NAME}" \
-v "${DB_DIR}":/var/lib/mysql \
-v "${TMP_INIT_DIR}":/docker-entrypoint-initdb.d \
-e MYSQL_ROOT_PASSWORD="${MYSQL_PASSWORD}" \
-e MYSQL_DATABASE="${MYSQL_DB_NAME}" \
--publish "${PORT}":3306 mysql:5.7

echo "All done."
