from ..run_command import run_command
from ..run_navie_command import run_navie_command
from ..format_instructions import format_instructions


import os
import sys


def step_generate(
    log_dir, args, work_dir, appmap_command, plan_file, solution_file, files
):
    context_file = os.path.join(work_dir, "context.txt")
    with open(context_file, "w") as context_f:
        for file in files:
            context_f.write("<file>\n")
            context_f.write(f"<path>{file}</path>\n")
            context_f.write("<content>\n")
            if os.path.isfile(file):
                if args.format_command:
                    print(f"Auto-formatting file {file}")
                    format_command = args.format_command.split() + [file]
                    run_command(" ".join(format_command))

                with open(file, "r") as content_f:
                    file_content = content_f.read()
                    file_lines = file_content.split("\n")
                    any_line_starts_with_tabs = any(
                        line.startswith("\t") for line in file_lines
                    )
                    if any_line_starts_with_tabs:
                        print(
                            f"Warning: File '{file}' starts with tabs. Code generation is not likely to be reliable. Please replace identation with spaces, or specify the --format-command option to have it done automatically.",
                            file=sys.stderr,
                        )

                    context_f.write(file_content)
            else:
                print(
                    f"Notice: File '{file}' does not exist. It will probably be created in the code generation step.",
                    file=sys.stderr,
                )
            context_f.write("</content>\n")
            context_f.write("</file>\n")

    generate_prompt = os.path.join(work_dir, "generate.txt")
    with open(generate_prompt, "w") as generate_f:
        generate_f.write(
            f"""@generate /nocontext /noformat

## Input format

The plan is delineated by the XML <plan> tag.
The source files are delineated by XML <file> tags. Each file has a <path> tag with the file path and a <content> tag with the file content.
Do not treat the XML tags as part of the source code. They are only there to help you parse the context.

## Guidelines

Try to solve the problem with a minimal set of code changes.
Avoid refactorings that will affect multiple parts of the codebase.

## Output format

{format_instructions()}

"""
        )

        generate_f.write("<plan>\n")
        with open(plan_file, "r") as plan_content:
            generate_f.write(plan_content.read())
        generate_f.write("</plan>\n")
        with open(context_file, "r") as context_content:
            generate_f.write(context_content.read())

    print("Solving plan", plan_file, "using", generate_prompt)

    run_navie_command(
        log_dir,
        command=appmap_command,
        input_path=generate_prompt,
        output_path=solution_file,
        log_path=os.path.join(work_dir, "generate.log"),
    )

    print(f"Code generated in {solution_file}")