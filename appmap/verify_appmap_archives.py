import os
import sys
from appmap.archive import ArchiveFinder
from swebench.collect.make_lite.get_unique_repo_versions import load_dataset


def load_repo_versions_from_dataset(dataset_path):
    dataset_name, split_name = (
        dataset_path.split(":") if ":" in dataset_path else (dataset_path, None)
    )

    dataset = load_dataset(dataset_name)

    repo_versions = {}
    for split in dataset.keys():
        if split_name and split_name != split:
            continue
        for instance in dataset[split]:
            if not "version" in instance or len(instance["version"]) == 0:
                continue
            repo_version = f'{instance["repo"].split("/")[-1]}-{instance["version"]}'
            repo_versions[repo_version] = repo_versions.get(repo_version, 0) + 1

    return repo_versions


def verify_appmap_archives(repo_versions, appmap_dir):
    archive_finder = ArchiveFinder(appmap_dir)
    missing_archives = []

    for repo_version, count in repo_versions.items():
        archive = archive_finder.find_archive(repo_version)
        if archive is None:
            missing_archives.append((repo_version, count))

    return missing_archives


def main(dataset_path, appmap_dir):
    repo_versions = load_repo_versions_from_dataset(dataset_path)
    missing_archives = verify_appmap_archives(repo_versions, appmap_dir)

    if missing_archives:
        print(
            "Missing appmap archives for the following repo-versions (sorted by instance count):"
        )
        for repo_version, count in sorted(
            missing_archives, key=lambda x: x[1], reverse=True
        ):
            print(f"{repo_version}: {count} instances")
        # Print total count
        sum_count = sum(count for _, count in missing_archives)
        print(f"Total: {sum_count} instances")
    else:
        print("All appmap archives are available.")


if __name__ == "__main__":
    dataset_path = "princeton-nlp/SWE-bench_Lite"
    if len(sys.argv) > 1:
        dataset_path = sys.argv[1]
    split = None
    appmap_dir = None
    if len(sys.argv) > 2:
        appmap_dir = os.path.abspath(sys.argv[2])
    main(dataset_path, appmap_dir)
