#!/bin/bash

# find project root directory
PROJECT_ROOT=$(git rev-parse --show-toplevel)
# add it to python path
export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH

if [ -z "$1" ]; then
    echo "Usage: $0 <instances_path_or_name>"
    exit 1
fi

python $PROJECT_ROOT/appmap/make_appmaps.py \
    --instances_path "$1" \
    --log_dir "appmap_logs" \
    --appmap_archive_dir appmaps \
    --temp_dir "/tmp/swe-appmaps" \
    --num_workers 1 \
    --verbose \
    --path_conda $(conda info --base)
