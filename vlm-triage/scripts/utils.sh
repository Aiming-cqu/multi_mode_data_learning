#!/bin/sh

cleanup() # [signal] [code]
{
	signal=${1:-0} # numeric
	code=${2:-0} # numeric
	if [ ${signal} -eq 0 ] # numeric
	then
		wait
	else
		set -x
		while true
		do
			tasks="$(pgrep -P $$)" || break # numeric
			kill -${signal} ${tasks} && \
					sleep 3 && kill -15 ${tasks} && \
					sleep 3 && kill -9 ${tasks} || true # numeric # multi
		done
	fi
	exit ${code} # numeric
}
