import os

from navie.config import Config

from .log import log_command


def run_navie_command(
    log_dir,
    output_path,
    log_path,
    temperature=None,
    token_limit=None,
    context_path=None,
    input_path=None,
    prompt_path=None,
    additional_args=None,
):
    """
    Execute the navie command with specified arguments.

    :param command: Command to execute (e.g., 'navie')
    :param context_path: Path to the context file
    :param input_path: Path to the input file
    :param output_path: Path to the output file
    :param log_path: Path to the log file
    :param additional_args: Additional arguments for the command
    :return: None
    """

    # TODO: Check input_path and context_path to determine file sizes.
    #       If the file sizes overflow a desired context limit, figure out how to
    #       prune them in some way.
    command = Config.get_appmap_command()

    env = {}
    if temperature:
        env["APPMAP_NAVIE_TEMPERATURE"] = temperature
    if token_limit:
        env["APPMAP_NAVIE_TOKEN_LIMIT"] = token_limit
    env_str = " ".join([f"{k}={v}" for k, v in env.items()])

    cmd = f"{env_str} {command} navie --log-navie"
    if input_path:
        cmd += f" -i {input_path}"
    if context_path:
        cmd += f" -c {context_path}"
    if prompt_path:
        cmd += f" -p {prompt_path}"
    cmd += f" -o {output_path}"
    if additional_args:
        cmd += f" {additional_args}"
    cmd += f" > {log_path} 2>&1"

    log_command(log_dir, cmd)

    result = os.system(cmd)

    if result != 0:
        raise RuntimeError(
            f"Failed to execute command {cmd}. See {log_path} for details."
        )
