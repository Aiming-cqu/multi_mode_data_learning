#!/bin/sh

WEBUI_PORT=4316
OTLP_GRPC_PORT=4317
OTLP_HTTP_PORT=4318

app="${1:-hyperdx}"

DOCKER_ARGS="${DOCKER_ARGS--d}"

case "${app}" in
  aspire-dashboard)
    docker run ${DOCKER_ARGS} --name aspire-dashboard \
      -p ${WEBUI_PORT}:18888 \
      -p ${OTLP_GRPC_PORT}:18889 \
      -p ${OTLP_HTTP_PORT}:18890 \
      -e DASHBOARD__TELEMETRYLIMITS__MAXLOGCOUNT=1000000 \
      -e DASHBOARD__TELEMETRYLIMITS__MAXMETRICSCOUNT=1000000 \
      -e DASHBOARD__TELEMETRYLIMITS__MAXTRACECOUNT=1000000 \
      mcr.microsoft.com/dotnet/aspire-dashboard
    ;;
  grafana-lgtm)
    docker run ${DOCKER_ARGS} --name grafana-lgtm \
      -p ${WEBUI_PORT}:3000 \
      -p ${OTLP_GRPC_PORT}:${OTLP_GRPC_PORT} \
      -p ${OTLP_HTTP_PORT}:${OTLP_HTTP_PORT} \
      grafana/otel-lgtm
    ;;
  hyperdx)
    docker run ${DOCKER_ARGS} --name hyperdx \
      -p ${WEBUI_PORT}:8080 \
      -p ${OTLP_GRPC_PORT}:${OTLP_GRPC_PORT} \
      -p ${OTLP_HTTP_PORT}:${OTLP_HTTP_PORT} \
      -p 8123:8123 \
      -e AUTH_DISABLED="true" \
      docker.io/hyperdx/hyperdx-local
    ;;
  jaeger)
    docker run ${DOCKER_ARGS} --name jaeger \
      -p ${WEBUI_PORT}:16686 \
      -p ${OTLP_GRPC_PORT}:${OTLP_GRPC_PORT} \
      -p ${OTLP_HTTP_PORT}:${OTLP_HTTP_PORT} \
      jaegertracing/all-in-one
    ;;
  openlit)
    # ADMIN_EMAIL="user@openlit.io"
    # ADMIN_PASSWORD="REDACTED"
    data_dir="${HOME}/.openlit/client/data"
    mkdir -p "${data_dir}"/
    docker run ${DOCKER_ARGS} --name clickhouse-24.4.1 \
      -p 8123:8123 \
      -p 9000:9000 \
      -v /var/log/:/var/log/ \
      -e CLICKHOUSE_USER="you@company.com" \
      -e CLICKHOUSE_PASSWORD="REDACTED" \
      clickhouse/clickhouse-server:24.4.1
    docker run ${DOCKER_ARGS} --name openlit \
      -p ${WEBUI_PORT}:3000 \
      -p ${OTLP_GRPC_PORT}:${OTLP_GRPC_PORT} \
      -p ${OTLP_HTTP_PORT}:${OTLP_HTTP_PORT} \
      -v "${data_dir}"/:/app/client/data/ \
      -e INIT_DB_HOST="127.0.0.1" \
      -e INIT_DB_PORT=8123 \
      -e INIT_DB_USERNAME="you@company.com" \
      -e INIT_DB_PASSWORD="REDACTED" \
      -e SQLITE_DATABASE_URL="file:/app/client/data/data.db" \
      ghcr.io/openlit/openlit
    ;;
  signoz)
    docker run ${DOCKER_ARGS} --name signoz \
      -p ${WEBUI_PORT}:8080 \
      -p ${OTLP_GRPC_PORT}:${OTLP_GRPC_PORT} \
      -p ${OTLP_HTTP_PORT}:${OTLP_HTTP_PORT} \
      -p 8123:8123 \
      -v signoz_db_application:/var/lib/signoz \
      -v signoz_db_telemetry:/var/lib/clickhouse \
      -e SIGNOZ_ADMIN_NAME="Admin" \
      -e SIGNOZ_ADMIN_EMAIL="you@company.com" \
      -e SIGNOZ_ADMIN_PASSWORD="REDACTED" \
      -e SIGNOZ_TELEMETRY_ENABLED="false" \
      ghcr.io/aetherall/signoz-standalone:latest
    ;;
  *)
    echo "Unknown service: ${app}"
    echo "Available services: aspire-dashboard, grafana-lgtm, hyperdx, jaeger, openlit, signoz"
    exit 1
    ;;
esac
