from appmap.solve.steps.step_pretest import build_task_manager
from swebench.harness.constants import MAP_REPO_TO_TEST_FRAMEWORK


def step_posttest(
    log_dir,
    work_dir,
    instances_path,
    instance_id,
    conda_path,
    conda_env,
    test_files,
):
    test_files_str = ", ".join(test_files)
    print(
        f"[posttest] ({instance_id}) Running posttest for {instance_id}: {test_files_str}"
    )

    task_manager = build_task_manager(
        instances_path,
        instance_id,
        work_dir,
        conda_env,
        log_dir,
        conda_path,
        timeout=30,
        verbose=True,
    )

    instance = task_manager.instance
    test_cmd = MAP_REPO_TO_TEST_FRAMEWORK[instance["repo"]]
    print(
        f"[posttest] ({instance_id}) Test command for {instance['repo']} is {test_cmd}"
    )

    test_command = f"{task_manager.cmd_activate} && {test_cmd} "

    failed_files = []
    for test_file in test_files:
        print(
            f"[posttest] ({instance_id}) Running test command: {test_command} {test_file}"
        )
        timeout = False
        try:
            test_output = task_manager.exec(
                ["bash", "-c", f"{test_command} {test_file}"],
                timeout=task_manager.timeout,
                check=False,
            )
        except TimeoutError:
            timeout = True
            print(
                f"[posttest] ({instance_id}) Test command timed out: {test_command} {test_file}"
            )
            failed_files.append(test_file)
            continue

        if test_output.returncode == 0:
            print(f"[posttest] ({instance_id}) Tests passed")
        else:
            if not timeout:
                print(
                    f"[posttest] ({instance_id}) Test command failed: {test_command} {test_file}"
                )
            print(
                f"[posttest] ({instance_id}) Review {task_manager.log_file} for more information"
            )
            failed_files.append(test_file)

    return failed_files
