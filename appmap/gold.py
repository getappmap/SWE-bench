import argparse
import json
import os
import re
import sys
import random
from pathlib import Path
from textwrap import dedent

from datasets import Dataset

from data import load_data
from filelock import FileLock


def output_results(instance, output_file, patch_data):
    instance["model_patch"] = patch_data["patch"] if patch_data is not None else None
    instance["model_name_or_path"] = "gold"
    with FileLock(f"{output_file}.lock"):
        with open(output_file, "a+") as f:
            f.write(json.dumps(instance) + "\n")

def split_runner_instances(
    instances: list, num_runners: int, runner_index: int
) -> list:
    """
    Split a list of instances into multiple groups based on the number of runners and the index of the runner.

    Args:
        instances (list): List of instances
        num_runners (int): Number of runners
        runner_index (int): Index of the runner
    Returns:
        list: List of instances for the given runner index
    """
    instances_per_runner = len(instances) // num_runners
    remainder = len(instances) % num_runners
    if runner_index == 0:
        # Lucky index 0 gets all the remainder instances
        return instances[: instances_per_runner + remainder]
    else:
        start_index = instances_per_runner * runner_index + remainder
        end_index = start_index + instances_per_runner
        return instances[start_index:end_index]

def write_instances(instances: Dataset, args):
    instance_set_path = None
    if args.instance_set:
        instance_set_path = (
            Path(__file__).parent / "instance_sets" / f"{args.instance_set}.txt"
        )
        with open(instance_set_path) as f:
            print(f"Using instance set: {instance_set_path}")
            instance_set = list(map(str.strip, f))
            instances = [
                instance
                for instance in instances
                if instance["instance_id"] in instance_set
            ]
    if args.filter:
        print(f"Filtering instances by regex: {args.filter}")
        pattern = re.compile(args.filter)
        instances = [instance for instance in instances if pattern.search(instance["instance_id"])]

    if args.num_runners > 1:
        # Shuffle the instances to ensure one worker doesn't get stuck with all the
        # long-running projects
        random.Random(args.seed).shuffle(instances)
        print(f"Splitting {len(instances)} instances across {args.num_runners} runners")
        instances = split_runner_instances(
            instances, args.num_runners, args.runner_index
        )
        print(f"{len(instances)} instances scheduled for this runner:")
        for instance in instances:
            print(f"- {instance['instance_id']}")

    if len(instances) == 0:
        print(
            f"No instances selected (instance set: {instance_set_path}, filter: {args.filter})"
        )
        sys.exit(1)

    for instance in instances:
        output_results(instance, args.output, instance)


def main(args):
    dataset = load_data(args.instances_path, args.split)
    write_instances(list(dataset), args)


appmap_finder = None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        epilog=dedent(
            """
                      The full set of instances is specified by --instances. A subset can be
                      selected by
                        --instance_set. That subset will be filtered further by --filter.
                       """
        )
    )

    parser.add_argument(
        "--instances_path",
        "--instances",
        type=str,
        help="path or huggingface name of task instances dataset",
        default="princeton-nlp/SWE-bench_Lite",
    )
    parser.add_argument(
        "--split", type=str, default="test", help="Dataset split to use"
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="(Optional) Filter to apply to task instances",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="predictions.jsonl",
        help="Path to output predictions",
    )
    parser.add_argument(
        "--instance_set", type=str, help="(Optional) Name of instance set"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="(Optional) Random seed for shuffling instances",
    )
    parser.add_argument(
        "--num_runners",
        type=int,
        default=1,
        help="Number of runners to split the workload across",
    )
    parser.add_argument(
        "--runner_index",
        type=int,
        default=0,
        help="Index of the runner to use",
    )
    args = parser.parse_args()
    main(args)
