#!/bin/sh

test -z "${PROJECT_ROOT}" && echo '❗️ PROJECT_ROOT not set' && exit 1

export OTEL_ENDPOINT="${OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces"
export OTEL_EXPORTER='otlp_http'
export LITELLM_DROP_PARAMS=1
export LITELLM_LOG='INFO'
export LITELLM_LOG_FILE="${PROJECT_ROOT}/logs/litellm.log"
# export DEFAULT_NUM_WORKERS_LITELLM_PROXY=4
