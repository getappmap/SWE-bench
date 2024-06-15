import argparse
from datetime import datetime
import json
import os
import re
import shutil
import sys

from swebench.metrics.report import get_model_report


def validate_environment():
    # Check if unidiff, seaborn and matplotlib are installed (they're required for reports).
    try:
        import unidiff, seaborn, matplotlib
    except Exception as e:
        print(f"Error while verifying requirements: {e}")
        print(
            "Note: unidiff, seaborn and matplotlib are required for generating reports."
        )
        exit(1)


def read_jsonl(file_path):
    with open(file_path, "r") as f:
        return [json.loads(line.strip()) for line in f]


def write_jsonl(data, file_path):
    with open(file_path, "w") as f:
        for entry in data:
            f.write(json.dumps(entry) + "\n")


def process_predictions(predictions_path, model_name, target_directory):
    predictions = read_jsonl(predictions_path)
    processed_predictions = []
    for prediction in predictions:
        processed_entry = {
            "instance_id": prediction["instance_id"],
            "model_patch": prediction["model_patch"],
            "model_name_or_path": model_name,
        }
        processed_predictions.append(processed_entry)

    output_path = os.path.join(target_directory, "all_preds.jsonl")
    write_jsonl(processed_predictions, output_path)
    return len(predictions)


MODEL_RE = re.compile("- Evaluation Model: .*?\n")


def process_logs(log_dir, model_name, date, target_directory):
    target_log_dir = os.path.join(target_directory, "logs")
    os.makedirs(target_log_dir, exist_ok=True)

    for log_fname in os.listdir(log_dir):
        if log_fname.endswith(".eval.log"):
            instance_id = log_fname.split(".")[0]
            new_log_fname = f"{instance_id}.{date}_{model_name}.eval.log"
            with open(os.path.join(log_dir, log_fname), "r") as log_file:
                log_content = MODEL_RE.sub(
                    f"- Evaluation Model: {model_name}\n", log_file.read()
                )
            with open(os.path.join(target_log_dir, new_log_fname), "w") as new_log_file:
                new_log_file.write(log_content)
    return target_log_dir


def copy_solve_logs(solve_dir, target_directory):
    target_solve_dir = os.path.join(target_directory, "solve_steps")
    shutil.copytree(solve_dir, target_solve_dir, dirs_exist_ok=True)


def generate_reports(experiments, split, model):
    os.chdir(os.path.join(experiments, "analysis"))
    sys.path.append(os.getcwd())
    import get_results

    get_results.main(model, split, True)


def main():
    parser = argparse.ArgumentParser(
        description="Process experiment results with a given model name"
    )
    parser.add_argument(
        "--results", required=True, help="Path to the results directory"
    )
    parser.add_argument("--model_name", required=True, help="Model name")
    parser.add_argument(
        "--dataset",
        required=True,
        help="Dataset name (full or lite)",
        type=str,
        choices=["full", "lite"],
    )
    parser.add_argument(
        "--experiments",
        required=True,
        help="Path to experiments repository",
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y%m%d"),
        help="Date for the output directory (default: current date)",
    )
    args = parser.parse_args()

    split = {"full": "test", "lite": "lite"}[args.dataset]

    date = args.date
    target_directory = os.path.abspath(
        os.path.join(args.experiments, "evaluation", split, f"{date}_{args.model_name}")
    )
    os.makedirs(target_directory, exist_ok=True)

    predictions = os.path.join(args.results, "predictions.jsonl")
    eval_logs = os.path.join(args.results, "logs", "navie")
    solve_logs = os.path.join(args.results, "logs", "solve")

    count = process_predictions(predictions, args.model_name, target_directory)
    process_logs(eval_logs, args.model_name, date, target_directory)
    shutil.copytree(
        solve_logs, os.path.join(target_directory, "solve_steps"), dirs_exist_ok=True
    )
    print(f"Processed results ({count}) written to {target_directory}.")
    os.makedirs(os.path.join(target_directory, "results"), exist_ok=True)
    generate_reports(args.experiments, split, f"{date}_{args.model_name}")
    print(f"Reports generated. Remember to add a README to {target_directory}")

if __name__ == "__main__":
    validate_environment()
    main()
