import subprocess


def run_command(command, fail_on_error=True):
    print(f"Executing command: {command}")

    result = subprocess.run(command, shell=True, capture_output=True)
    if result.returncode != 0 and fail_on_error:
        raise RuntimeError(f"Failed to execute command {command}")

    return result.stdout.decode()
