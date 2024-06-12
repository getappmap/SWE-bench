import os

from .log import log_command


def run_navie_command(
    log_dir,
    command,
    output_path,
    log_path,
    context_path=None,
    input_path=None,
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

    # TODO: Add token limit option, e.g. --ai-option tokenLimit=4000
    # TODO: Check input_path and context_path to determine file sizes.
    #       If the file sizes overflow a desired context limit, figure out how to 
    #       prune them in some way.


    # Build the command
    cmd = f"{command} navie --log-navie"
    if input_path:
        cmd += f" -i {input_path}"
    if context_path:
        cmd += f" -c {context_path}"
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
