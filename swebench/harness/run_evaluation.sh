#!/bin/bash

# find project root directory
PROJECT_ROOT=$(git rev-parse --show-toplevel)
# add it to python path
export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH

# get predictions path from the first argument
# (error if not provided)
if [ -z "$1" ]; then
    echo "Error: predictions path not provided"
    exit 1
fi
PREDICTIONS="$1"

# get SWE-Bench tasks from the second argument
# (error if not provided)
if [ -z "$2" ]; then
    echo "Error: SWE-Bench tasks not provided"
    exit 1
fi
TASKS="$2"

LOG_DIR="$PROJECT_ROOT/eval_logs/"

python $PROJECT_ROOT/swebench/harness/run_evaluation.py \
    --predictions_path "$PREDICTIONS" \
    --swe_bench_tasks "$TASKS" \
    --log_dir "$LOG_DIR" \
    --testbed /tmp \
    --skip_existing \
    --timeout 900 \
    --verbose \
    --num_processes 1 \
    --path_conda /home/divide/opt/miniconda3/
