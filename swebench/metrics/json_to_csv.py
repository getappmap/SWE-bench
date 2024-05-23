import json
import csv

def json_report_to_csv(report_path: str, output_csv_path: str):
    """
    Converts a JSON report to a CSV file, with each row representing an instance ID
    and columns for each category in the report (excluding "no_generation").

    Args:
        report_path (str): Path to the JSON report file.
        output_csv_path (str): Path to the output CSV file.
    """

    # Read JSON report
    with open(report_path, 'r') as json_file:
        report_map = json.load(json_file)
    
    # Get all instance_ids
    all_instance_ids = set()
    for category, instance_ids in report_map.items():
        all_instance_ids.update(instance_ids)
    
    # Prepare CSV headers
    headers = ["instance_id"] + [key for key in report_map.keys() if key != "no_generation"]

    # Write to CSV
    with open(output_csv_path, 'w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=headers)
        writer.writeheader()

        for instance_id in all_instance_ids:
            row = {"instance_id": instance_id}
            for category in headers[1:]:  # Skip 'instance_id' header
                row[category] = instance_id in report_map.get(category, [])
            writer.writerow(row)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert JSON report to CSV.")
    parser.add_argument("report_path", type=str, help="Path to the JSON report file.")
    parser.add_argument("output_csv_path", type=str, help="Path to the output CSV file.")
    args = parser.parse_args()

    json_report_to_csv(args.report_path, args.output_csv_path)
