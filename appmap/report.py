import argparse
import csv
import json
import os

from swebench import get_model_report


def main(predictions, instances, log_dir, model, split, save_results, verbose, output):
    report = get_model_report(
        model=model,
        predictions_path=os.path.abspath(predictions),
        swe_bench_tasks=instances,
        log_dir=os.path.join(log_dir, model),
        verbose=verbose,
    )

    for k, v in report.items():
        print(f"{k}: {len(v)}")

    if save_results:
        write_csv_report(
            report,
            read_predictions(predictions),
            split,
            output,
        )


def read_predictions(predictions_path: str) -> list[dict]:
    predictions = []
    with open(predictions_path, "r") as f:
        for line in f:
            predictions.append(json.loads(line))
    return predictions


def write_csv_report(report_map, predictions: list[dict], split, output_csv_path):
    categories = [key for key in report_map.keys() if key != "no_generation"]
    # Prepare CSV headers
    headers = [
        "instance_id",
        "split",
        *categories,
        "model_patch_name",
        "model_iteration",
        "model_lint_repair",
        "model_test_repair",
    ]

    # Write to CSV
    with open(output_csv_path, "w", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()
        for instance in predictions:
            row = {
                "instance_id": instance["instance_id"],
                "split": split,
            }
            for category in categories:
                row[category] = instance["instance_id"] in report_map.get(category, [])

            row["model_patch_name"] = instance.get("model_patch_name", "")
            row["model_iteration"] = instance.get("model_iteration", "")
            row["model_lint_repair"] = instance.get("model_lint_repair", "")
            row["model_test_repair"] = instance.get("model_test_repair", "")

            writer.writerow(row)

        print(f"Wrote {len(predictions)} predictions to {output_csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--predictions",
        type=str,
        default="predictions.jsonl",
        help="Path to predictions file",
    )
    parser.add_argument(
        "--instances",
        type=str,
        help="huggingface name of task instances dataset",
        default="princeton-nlp/SWE-bench_Lite",
    )
    parser.add_argument(
        "--log_dir", type=str, help="Path to log directory", default="logs"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="navie",
        help="Name of folder containing model evaluation results (e.g. '20240402_sweagent_gpt4)",
    )
    parser.add_argument(
        "--split",
        type=str,
        default="test",
        help="Name of split to get evaluation results for (should be parent folder, e.g. 'test', 'dev')",
        choices=["test", "dev"],
    )
    parser.add_argument(
        "--save_results", default=True, action="store_true", help="Save results to file"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show intermediate messages"
    )
    parser.add_argument(
        "--output", type=str, default="results.csv", help="Path to output file"
    )
    args = parser.parse_args()
    main(**vars(args))
