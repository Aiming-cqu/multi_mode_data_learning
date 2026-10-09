#!/bin/sh
test -z "${PIXI_PROJECT_ROOT}" && exec pixi run -- sh "$0" "$@"
#!/usr/bin/env -S pixi run -- sh

set -eu

test -z "${PROJECT_ROOT}" && echo '❗️ PROJECT_ROOT required to be set' && exit 1

unset PIXI_PROJECT_ROOT

cleanup_vllm()
{
    # WORKAROUND: Pixi deno_task_shell blocks signals， so we have to kill vllm manually
    while true
    do
        tasks="$(pgrep -P $$) $(pgrep vllm)" || break # numeric
        kill -2 ${tasks} && \
                sleep 5 && kill -15 ${tasks} 2>/dev/null && \
                sleep 5 && kill -9 ${tasks} 2>/dev/null || true # numeric # multi
    done
}

trap "cleanup_vllm" 2 # SIGINT
trap "cleanup_vllm" 15 # SIGTERM

FAILED_LIST=''
PASSED_LIST_PING=''
PASSED_LIST_COMPLETION=''

for script_path in "${PROJECT_ROOT}/scripts/model-serving/"*.sh
do
    cleanup_vllm

    echo ''

    script_name="$(basename "${script_path}")"
    echo "Testing ${script_name} ..."

    log_path="${PROJECT_ROOT}/logs/test-${script_name%.*}.log"
	echo "Log path: ${log_path}"

    # Start the script in background, capture output
    sh "${script_path}" >"${log_path}" 2>&1 & script_pid=$!
    echo "Started ${script_name} with PID ${script_pid}"

    # tail -f "${log_path}" & tail_pid=$!

    ping_pass=0
    while true
    do
        if curl -sf "http://localhost:8030/ping"
        then
            ping_pass=1
            break
        elif kill -0 ${script_pid} 2>/dev/null
        then
            sleep 1
        else
            break
        fi
    done

    if [ ${ping_pass} -eq 0 ]
    then
        FAILED_LIST="${FAILED_LIST}${script_name}\n"
        echo "Failed: ${script_name}\n"
        tail -n 30 "${log_path}"
        continue
    fi

    completion_pass=0
    printf "Testing completion endpoint...\n\n"
    if curl -X POST "http://localhost:8030/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d '{"model": "0", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}' \
        --max-time 30 -w '\n'
    then
        completion_pass=1
        PASSED_LIST_COMPLETION="${PASSED_LIST_COMPLETION}${script_name}\n"
    else
        PASSED_LIST_PING="${PASSED_LIST_PING}${script_name}\n"
    fi

    # Extract key info from log
    log_model_loading=$(grep "Model loading took" "${log_path}" | head -1)
    log_encoder_cache=$(grep "Encoder cache will be initialized with a budget of" "${log_path}" | head -1)
    log_available_kv_cache=$(grep "Available KV cache memory" "${log_path}" | head -1)
    log_padding_layers=$(grep "Add.*padding layers" "${log_path}" | head -1)
    log_kv_cache_size=$(grep "GPU KV cache size" "${log_path}" | head -1)
    log_concurrency=$(grep "Maximum concurrency" "${log_path}" | head -1)
    printf "\nMemory Metrics:\n# %s\n# %s\n# %s\n# %s\n# %s\n# %s\n" \
        "${log_model_loading}" "${log_encoder_cache}" "${log_available_kv_cache}" \
        "${log_padding_layers}" "${log_kv_cache_size}" "${log_concurrency}"

done

cleanup_vllm

# Summary
echo ""
echo "Summary:"
echo "Failed:"
echo "${FAILED_LIST}"
echo "Ping Passed (Completion Failed):"
echo "${PASSED_LIST_PING}"
echo "Completion Passed:"
echo "${PASSED_LIST_COMPLETION}"
echo ""
