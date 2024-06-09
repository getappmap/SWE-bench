from swebench.harness.constants import MAP_REPO_TO_TEST_FRAMEWORK

from ..run_command import run_command
from .step_pretest import build_task_manager


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

    # Run the diff command
    diff_command = f"git diff"
    file_diff = run_command(log_dir, diff_command, fail_on_error=True)
    print(f"[posttest] ({instance_id}) Current project diff:")
    print(file_diff)

    with build_task_manager(
        instances_path,
        instance_id,
        work_dir,
        conda_env,
        log_dir,
        conda_path,
        timeout=30,
        verbose=True,
    ) as task_manager:
        instance = task_manager.instance
        test_cmd = MAP_REPO_TO_TEST_FRAMEWORK[instance["repo"]]
        print(
            f"[posttest] ({instance_id}) Test command for {instance['repo']} is {test_cmd}"
        )

        test_command = f"{task_manager.cmd_activate} && {test_cmd} "
        test_files_str = " ".join(test_files)

        print(
            f"[posttest] ({instance_id}) Running test command: {test_command} {test_files_str}"
        )
        timeout = False
        try:
            test_output = task_manager.exec(
                ["bash", "-c", f"{test_command} {test_files_str}"],
                timeout=task_manager.timeout,
                check=False,
            )
        except TimeoutError:
            timeout = True
            print(
                f"[posttest] ({instance_id}) Test command timed out: {test_command} {test_files_str}"
            )

        if test_output.returncode == 0:
            print(f"[posttest] ({instance_id}) Tests passed")
            return True
        else:
            if not timeout:
                print(
                    f"[posttest] ({instance_id}) Test command failed: {test_command} {test_files_str}"
                )
            print(
                f"[posttest] ({instance_id}) Review {task_manager.log_file} for more information"
            )
            return False
