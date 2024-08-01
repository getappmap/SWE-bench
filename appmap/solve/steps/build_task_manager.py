from appmap.data import load_data
from swebench.harness.context_manager import TaskEnvContextManager


import os


def build_task_manager(
    instances_path,
    instance_id,
    testbed,
    conda_env,
    log_dir,
    conda_path,
    timeout,
    verbose,
):
    testbed = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
    dev_dataset = load_data(instances_path, "dev")
    test_dataset = load_data(instances_path, "test")

    instance = next(
        (inst for inst in test_dataset if inst["instance_id"] == instance_id), None
    )
    if not instance:
        instance = next(
            (inst for inst in dev_dataset if inst["instance_id"] == instance_id), None
        )

    if not instance:
        raise ValueError(
            f"Could not find instance {instance_id} in dev or test datasets of {instances_path}"
        )

    return TaskEnvContextManager(
        instance,
        testbed,
        conda_env,
        log_dir,
        conda_path=conda_path,
        timeout=timeout,
        verbose=verbose,
    )
