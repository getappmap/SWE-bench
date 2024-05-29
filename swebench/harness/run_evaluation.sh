#!/bin/bash

# find project root directory
PROJECT_ROOT=$(git rev-parse --show-toplevel)
# add it to python path
export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH

SCENARIO="$1"
SCENARIO_DIR=/experiments/experiments/evaluation/lite/$SCENARIO

PREDICTIONS=$SCENARIO_DIR/all_preds.jsonl
if ! [ -f "$PREDICTIONS" ]; then
    echo "Error: predictions path $PREDICTIONS not found"
    exit 1
fi

TASKS="princeton-nlp/SWE-bench_Lite"
if [ -z "$TASKS" ]; then
    echo "Error: SWE-Bench tasks not provided"
    exit 1
fi

LOG_DIR=$SCENARIO_DIR/logs

python $PROJECT_ROOT/swebench/harness/run_evaluation.py \
    --predictions_path "$PREDICTIONS" \
    --swe_bench_tasks "$TASKS" \
    --log_dir "$LOG_DIR" \
    --flat \
    --testbed /mnt \
    --skip_existing \
    --timeout 900 \
    --verbose \
    --num_processes 8 \
    --path_conda $(conda info --base)
