import os

import yaml

from ..run_navie_command import run_navie_command
from .test_files_to_modules import test_files_to_modules
from .step_pretest import build_task_manager


def infer_test_directives(
    instances_path,
    instance_id,
    work_dir,
    conda_env,
    conda_path,
    log_dir,
    appmap_command,
    issue_file,
):
    tcm = build_task_manager(
        instances_path,
        instance_id,
        work_dir,
        conda_env,
        log_dir,
        conda_path,
        timeout=30,
        verbose=True,
    )
    with tcm:
        try:
            tcm.exec(
                ["bash", "-c", f"{tcm.cmd_activate} && pip install pytest-test-groups"]
            )
        except RuntimeError:
            print("Failed to install pytest-test-groups, continuing without it")

    include_pattern = "^(.*[\\/])?(tests?/.*|.*_test\\.py|.*_spec\\.py|test_.*\\.py)$"

    input_path = os.path.join(work_dir, "pretest.txt")
    output_path = os.path.join(work_dir, "pretest_context.yml")
    log_path = os.path.join(work_dir, "pretest.log")

    with open(input_path, "w") as pretest_f:
        # TODO: 5/6/24 There's no server-side support for /includepattern yet, actually.
        pretest_f.write(
            f"""@context /format=yaml /nofence /includepattern={include_pattern}
            
Search exclusively for test cases.
"""
        )

    run_navie_command(
        log_dir,
        command=appmap_command,
        context_path=issue_file,
        input_path=input_path,
        output_path=output_path,
        log_path=log_path,
    )

    print(f"[pretest] ({instance_id}) Context stored in {output_path}")

    # Load pretest context as YAML
    test_files = []
    with open(output_path, "r") as f:
        pretest_context = yaml.safe_load(f)

    # Each context item consists of directory, type, content, and location
    for item in pretest_context:
        if item["type"] != "code-snippet":
            continue

        location = item["location"]
        path = location.split(":")[0]
        if not path.endswith(".py"):
            continue
        if not "test" in path:  # TODO: Make this more robust
            continue

        directory = item["directory"]
        full_path = os.path.join(directory, path)
        relative_path = os.path.relpath(full_path, os.getcwd())
        if os.path.exists(relative_path) and relative_path not in test_files:
            test_files.append(relative_path)

    if len(test_files) == 0:
        print(f"[pretest] ({instance_id}) WARN: No relevant test files detected")
        return []

    if "django" in instance_id:
        test_files = test_files_to_modules(test_files)

    return test_files
