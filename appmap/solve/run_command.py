import subprocess

from log import log_command


def run_command(log_dir, command, fail_on_error=True):
    log_command(log_dir, command)

    result = subprocess.run(command, shell=True, capture_output=True)
    if result.returncode != 0 and fail_on_error:
        raise RuntimeError(f"Failed to execute command {command}")

    return result.stdout.decode()
