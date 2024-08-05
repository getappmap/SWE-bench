import os

from filelock import FileLock


def log_command(dir, command):
    command_lock_file = os.path.join(dir, "command.lock")
    command_log_file = os.path.join(dir, "command.log")

    with FileLock(command_lock_file):
        with open(command_log_file, "a+") as f:
            f.write(command + "\n")


def log_lint(dir, file, lint_messages):
    lint_lock_file = os.path.join(dir, "lint.lock")
    lint_log_file = os.path.join(dir, "lint.log")

    with FileLock(lint_lock_file):
        with open(lint_log_file, "a+") as f:
            f.writelines("\n".join([file, "-" * len(file), lint_messages, "\n"]))


def log_diff(dir, file, diff):
    diff_lock_file = os.path.join(dir, "diff.lock")
    diff_log_file = os.path.join(dir, "diff.log")

    with FileLock(diff_lock_file):
        with open(diff_log_file, "a+") as f:
            f.writelines("\n".join([file, "-" * len(file), diff, "\n"]))
