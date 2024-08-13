import argparse
import os
import re
from typing import List, Tuple


def parse_cost(line: str) -> float:
    match = re.search(r"cost:\s*\$([0-9]+\.[0-9]+)", line)
    return float(match.group(1)) if match else 0.0


def scrape_log_files(log_dir: str) -> dict[str, float]:
    costs = {}
    for instance_dir in os.listdir(log_dir):
        instance_path = os.path.join(log_dir, instance_dir)
        if not os.path.isdir(instance_path):
            continue
        instance_cost = 0.0

        for subdir, _, files in os.walk(instance_path):
            for file in files:
                if file.endswith(".log"):
                    with open(os.path.join(subdir, file), "r") as f:
                        for line in f:
                            if "cost:" in line:
                                instance_cost += parse_cost(line)
        costs[instance_dir] = instance_cost
    return costs


def generate_cost_report(log_dir: str) -> Tuple[float, float, float]:
    costs = scrape_log_files(log_dir)
    total_cost = sum(costs.values())
    avg_cost = total_cost / len(costs) if costs else 0.0
    return total_cost, avg_cost, len(costs)


def main():
    parser = argparse.ArgumentParser(
        description="Generate cost report from experiment logs."
    )
    parser.add_argument(
        "--log_dir", required=True, help="Directory containing the log files."
    )
    args = parser.parse_args()

    total_cost, avg_cost, count = generate_cost_report(args.log_dir)
    print(f"Total Instances: {count}")
    print(f"Total Cost: ${total_cost:.2f}")
    print(f"Average Cost per Instance: ${avg_cost:.2f}")


if __name__ == "__main__":
    main()
