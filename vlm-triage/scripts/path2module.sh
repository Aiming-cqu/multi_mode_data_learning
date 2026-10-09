#!/bin/sh

set -eu

path="$1"
name="${path%.*}"
name="${name#*.}"
echo "${name}" | sed 's#/#.#g'
