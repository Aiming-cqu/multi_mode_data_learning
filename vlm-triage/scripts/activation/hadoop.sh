#!/bin/sh

test -z "${PROJECT_ROOT}" && echo '❗️ PROJECT_ROOT not set' && exit 1

export HADOOP_HOME="${PROJECT_ROOT}/third-party/hadoop-2.7.2-5546"
export HADOOP_CONF_DIR="${HADOOP_HOME}/etc/hadoop"
export SPARK_HOME="${PROJECT_ROOT}/third-party/spark-3.2.0-110-bin"

test -d "${HADOOP_HOME}" || echo "❗️ HADOOP_HOME directory not exists: ${HADOOP_HOME}"
test -d "${SPARK_HOME}" || echo "❗️ SPARK_HOME directory not exists: ${SPARK_HOME}"
