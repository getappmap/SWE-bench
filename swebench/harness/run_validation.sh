#!/usr/bin/env bash

# find project root directory
PROJECT_ROOT=$(git rev-parse --show-toplevel)
# add it to python path
export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH

if [ -z "$1" ]; then
    echo "Usage: $0 <instances_path_or_name>"
    exit 1
fi

instance_path="$1"; shift

python $PROJECT_ROOT/swebench/harness/engine_validation.py \
    --instances_path "$instance_path" \
    --log_dir "validate_logs" \
    --temp_dir "/tmp/swe-validate" \
    --num_workers 1 \
    --verbose \
    --path_conda $(conda info --base) \
    "$@"
