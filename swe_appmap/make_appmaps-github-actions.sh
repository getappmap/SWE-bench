#!/bin/bash

# find project root directory
PROJECT_ROOT=$(git rev-parse --show-toplevel)
# add it to python path
export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH

INSTANCES="princeton-nlp/SWE-bench"

python $PROJECT_ROOT/swe_appmap/make_appmaps.py \
    --instances_path "$INSTANCES" \
    --log_dir "appmap_logs" \
    --appmap_archive_dir appmaps \
    --temp_dir "/tmp/swe-appmaps" \
    --num_workers 1 \
    --verbose \
    --path_conda $(conda info --base) \
    --appmap_bin /usr/local/bin/appmap \
    "$@"
