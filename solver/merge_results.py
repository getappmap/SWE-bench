import argparse
import glob
import json
import os
import shutil
import tarfile
from zipfile import ZipFile


def read_jsonl(file_path):
    with open(file_path, "r") as f:
        for line in f:
            yield json.loads(line)


def write_jsonl(data, file_path):
    with open(file_path, "w") as f:
        for entry in data:
            f.write(json.dumps(entry) + "\n")


def merge_predictions(predictions_files):
    print("Merging prediction files...")
    merged_predictions = {}
    for file_path in predictions_files:
        print(f"Reading {file_path}... ", end="")
        count = 0
        for entry in read_jsonl(file_path):
            instance_id = entry["instance_id"]
            merged_predictions[instance_id] = entry
            count += 1
        print(count)
    return list(merged_predictions.values())


def merge_logs(log_dirs, target_dir):
    print(f"Merging logs into {target_dir}...")
    for log_dir in log_dirs:
        for log_file in glob.glob(os.path.join(log_dir, "*")):
            print(
                f"Copying {log_file} from {log_dir} to {target_dir}{' ' * 40}",
                end="\r",
                flush=True,
            )
            shutil.copy(log_file, target_dir)
    print()


def unzip_files(zip_files, temp_dir):
    unzipped_dirs = []
    for zip_file in zip_files:
        temp_subdir = os.path.join(
            temp_dir, os.path.splitext(os.path.basename(zip_file))[0]
        )
        print(f"Extracting {zip_file} to {temp_subdir}")
        with ZipFile(zip_file, "r") as zip_ref:
            zip_ref.extractall(temp_subdir)

        unzipped_dirs.append(temp_subdir)

        # Check for the existence of a single tar.xz file in the temp directory
        tar_xz_files = [f for f in os.listdir(temp_subdir) if f.endswith(".tar.xz")]
        if len(tar_xz_files) == 0:
            pass
        elif len(tar_xz_files) == 1:
            print(f"Extracting contents from {tar_xz_files[0]}")
            tar_xz_file = tar_xz_files[0]
            tar_xz_path = os.path.join(temp_subdir, tar_xz_file)
            # Extract predictions.jsonl and logs from the tar.xz file
            print(f"Extracting contents from {tar_xz_path}")
            with tarfile.open(tar_xz_path, "r:xz") as tar:
                predictions_path = os.path.join(temp_subdir, "predictions.jsonl")
                with open(predictions_path, "wb") as f:
                    f.write(tar.extractfile("predictions.jsonl").read())

                logs_dir = os.path.join(temp_subdir, "logs")
                os.makedirs(logs_dir, exist_ok=True)
                for member in tar.getmembers():
                    if member.name.startswith("logs/"):
                        member.name = member.name[len("logs/") :]
                        tar.extract(member, path=logs_dir)
            os.remove(tar_xz_path)
        else:
            print(f"WARNING Found {len(tar_xz_files)} tar.xz files in {temp_subdir}.")

    return unzipped_dirs


def merge_directories(result_dirs, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    predictions_files = []
    navie_log_dirs = []
    solve_log_dirs = []

    for result_dir in result_dirs:
        print(f"Preparing to merge results from {result_dir}")
        predictions_files.append(os.path.join(result_dir, "predictions.jsonl"))
        navie_log_dirs.append(os.path.join(result_dir, "logs", "navie"))
        solve_log_dirs.append(os.path.join(result_dir, "logs", "solve"))

    merged_predictions = merge_predictions(predictions_files)
    merged_predictions_path = os.path.join(output_dir, "predictions.jsonl")
    print(
        f"Writing {len(merged_predictions)} merged predictions to {merged_predictions_path}"
    )
    write_jsonl(merged_predictions, merged_predictions_path)

    merged_navie_dir = os.path.join(output_dir, "logs", "navie")
    merged_solve_dir = os.path.join(output_dir, "logs", "solve")
    os.makedirs(merged_navie_dir, exist_ok=True)
    os.makedirs(merged_solve_dir, exist_ok=True)

    merge_logs(navie_log_dirs, merged_navie_dir)
    for solve_dir in solve_log_dirs:
        instances = [
            d
            for d in os.listdir(solve_dir)
            if os.path.isdir(os.path.join(solve_dir, d))
        ]
        for instance in instances:
            target_solve_instance_dir = os.path.join(merged_solve_dir, instance)
            if os.path.exists(target_solve_instance_dir):
                shutil.rmtree(target_solve_instance_dir)
            print(
                f"Copying {instance} solve log from {solve_dir} to {target_solve_instance_dir}{' ' * 40}",
                end="\r",
                flush=True,
            )
            shutil.copytree(
                os.path.join(solve_dir, instance), target_solve_instance_dir
            )
    print()
    return len(merged_predictions)


def main(result_sources, output_dir, temp_dir):
    """
    Merges results from multiple sources (directories or zip files).

    Args:
      result_sources (list[str]): List of paths to result directories or zip files containing results.
      output_dir (str): Path to the directory where merged results will be stored.
      temp_dir (str): Temporary directory for extracting zip files.
    """
    print("Starting the merge process...")
    dirs_to_merge = []
    for source in result_sources:
        if source.endswith(".zip"):
            dirs_to_merge.extend(unzip_files([source], temp_dir))
        else:
            dirs_to_merge.append(source)

    count = merge_directories(dirs_to_merge, output_dir)
    print(f"Merged results ({count} total) are written to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge results from multiple directories or zip files."
    )
    parser.add_argument(
        "result_sources",
        nargs="+",
        help="List of paths to result directories or zip files.",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Path to the directory where merged results will be stored.",
    )
    parser.add_argument(
        "--temp_dir",
        default="/tmp",
        help="Temporary directory for extracting zip files.",
    )
    args = parser.parse_args()

    main(args.result_sources, args.output_dir, args.temp_dir)
