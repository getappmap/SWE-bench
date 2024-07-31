import os

from appmap.navie.log_print import log_print

EXCLUDE_PYTHON_TESTS_PATTERN = """(\\btesting\\b|\\btest\\b|\\btests\\b|\\btest_|_test\\.py$|\\.txt$|\\.html$|\\.rst$|\\.md$)"""


class Client:
    def __init__(self, work_dir, temperature=0.0, token_limit=None, log=log_print):
        self.work_dir = work_dir
        self.temperature = temperature
        self.token_limit = token_limit
        self.log = log
        # TODO: Change me
        self.appmap_command = (
            "node /Users/kgilpin/source/appland/appmap-js/packages/cli/built/cli.js"
        )

    def ask(self, question_file, output_file, context_file=None, prompt_file=None):
        log_file = os.path.join(self.work_dir, "ask.log")
        input_file = os.path.join(self.work_dir, "ask.txt")

        with open(input_file, "w") as input_f:
            if context_file:
                input_f.write("/nocontext\n")

            with open(question_file, "r") as question_f:
                question = question_f.read()
                input_f.write(question)

        command = self._build_command(
            input_path=question_file,
            output_path=output_file,
            log_file=log_file,
            prompt_path=prompt_file,
        )
        self._execute(command, log_file)

    def terms(self, issue_file, output_file):
        log_file = os.path.join(self.work_dir, "terms.log")
        input_file = os.path.join(self.work_dir, "terms.txt")
        with open(issue_file, "r") as issue_f:
            issue_content = issue_f.read()

        with open(input_file, "w") as rewrite_f:
            rewrite_f.write(
                f"""@generate /nocontext

Generate a list of all file names, module names, class names, function names and varable names that are mentioned in the
described issue. Do not emit symbols that are part of the programming language itself. Do not emit symbols that are part
of test frameworks. Focus on library and application code only. Emit the results as a JSON list. Do not emit text, markdown, 
or explanations.

<issue>
{issue_content}
</issue>
"""
            )

        command = self._build_command(
            input_path=input_file, output_path=output_file, log_file=log_file
        )
        self._execute(command, log_file)

    def context(
        self, query_file, output_file, exclude_pattern=None, vectorize_query=True
    ):
        log_file = os.path.join(self.work_dir, "search_terms.log")

        with open(query_file, "r") as f:
            query_content = f.read()

        question = ["@context /nofence /format=yaml"]
        if not vectorize_query:
            question.append("/noterms")
        if exclude_pattern:
            question.append(f"/exclude={exclude_pattern}")

        question_file = os.path.join(self.work_dir, "context.txt")
        with open(question_file, "w") as apply_f:
            apply_f.write(
                f"""{" ".join(question)}
                        
{query_content}
"""
            )

        command = self._build_command(
            input_path=question_file, output_path=output_file, log_file=log_file
        )
        self._execute(command, log_file)

    def plan(self, issue_file, output_file, context_file=None, prompt_file=None):
        log_file = os.path.join(self.work_dir, "plan.log")
        input_file = os.path.join(self.work_dir, "plan.txt")

        with open(issue_file, "r") as issue_f:
            issue_content = issue_f.read()

        with open(input_file, "w") as plan_f:
            question = ["@plan"]
            if context_file:
                question.append("/nocontext")
            plan_f.write(
                f"""{" ".join(question)}

{issue_content}
"""
            )

        command = self._build_command(
            input_path=input_file,
            output_path=output_file,
            context_path=context_file,
            prompt_path=prompt_file,
            log_file=log_file,
        )
        self._execute(command, log_file)

    def list_files(self, plan_file, output_file):
        log_file = os.path.join(self.work_dir, "list_files.log")
        input_file = os.path.join(self.work_dir, "list_files.txt")
        if not output_file.endswith(".json"):
            self.log(
                "list-files",
                f"Expecting output file {output_file} to have extension: .json",
            )

        with open(plan_file, "r") as plan_f:
            plan_content = plan_f.read()

        with open(input_file, "w") as question_f:
            question_f.write(
                f"""@list-files /format=json /nofence
                             
{plan_content}
"""
            )

        command = self._build_command(
            input_path=input_file,
            output_path=output_file,
            log_file=log_file,
        )
        self._execute(command, log_file)

    def generate(
        self,
        plan_file,
        output_file,
        file_list,
        context_file=None,
        prompt_file=None,
    ):
        log_file = os.path.join(self.work_dir, "generate.log")
        input_file = os.path.join(self.work_dir, "generate.txt")

        with open(plan_file, "r") as plan_f:
            plan_content = plan_f.read()
        with open(input_file, "w") as input_f:
            question = ["@generate /noformat"]
            if context_file:
                question.append("/nocontext")

            input_f.write(
                f"""{" ".join(question)}
                             
{plan_content}
"""
            )
            for modify_file_name in file_list:
                # If the file doesn't exist
                if not os.path.exists(modify_file_name):
                    print(f"File {modify_file_name} does not exist. Skipping.")
                    continue

                with open(modify_file_name, "r") as modify_f:
                    modify_content = modify_f.read()
                input_f.write(
                    f"""
<file>
<path>{modify_file_name}</path>
<content>
{modify_content}
</content>
</file>
"""
                )

        command = self._build_command(
            input_path=input_file,
            output_path=output_file,
            context_path=context_file,
            prompt_path=prompt_file,
            log_file=log_file,
        )
        self._execute(command, log_file)

    def test(
        self,
        issue_file,
        output_file,
        file_list=[],
        context_file=None,
        prompt_file=None,
    ):
        log_file = os.path.join(self.work_dir, "test.log")
        input_file = os.path.join(self.work_dir, "test.txt")

        with open(issue_file, "r") as issue_f:
            issue_content = issue_f.read()

        with open(input_file, "w") as input_f:
            question = ["@test /noformat"]
            if context_file:
                question.append("/nocontext")

            input_f.write(
                f"""{" ".join(question)}
                             
{issue_content}
"""
            )
            for modify_file_name in file_list:
                # If the file doesn't exist
                if not os.path.exists(modify_file_name):
                    print(f"File {modify_file_name} does not exist. Skipping.")
                    continue

                with open(modify_file_name, "r") as modify_f:
                    modify_content = modify_f.read()
                input_f.write(
                    f"""
<file>
<path>{modify_file_name}</path>
<content>
{modify_content}
</content>
</file>
"""
                )

        command = self._build_command(
            input_path=input_file,
            output_path=output_file,
            context_path=context_file,
            prompt_path=prompt_file,
            log_file=log_file,
        )
        self._execute(command, log_file)

    def apply(self, solution_file, apply_file, all=True, file_name=None):
        log_file = os.path.join(self.work_dir, "apply.log")
        input_file = os.path.join(self.work_dir, "apply.txt")

        with open(solution_file, "r") as sol_f:
            solution_content = sol_f.read()

        if not all and not file_name:
            raise ValueError("file_name must be provided when all is False")

        with open(input_file, "w") as apply_f:
            apply_option = "/all" if all else file_name
            apply_f.write(
                f"""@apply {apply_option}

{solution_content}
"""
            )

        command = self._build_command(
            input_path=input_file,
            output_path=apply_file,
            log_file=log_file,
        )
        self._execute(command, log_file)

    def _prepare_env(self):
        env = {
            "APPMAP_NAVIE_TEMPERATURE": str(self.temperature),
        }
        if self.token_limit:
            env["APPMAP_NAVIE_TOKEN_LIMIT"] = str(self.token_limit)
        return env

    def _build_command(
        self,
        output_path,
        log_file,
        context_path=None,
        input_path=None,
        prompt_path=None,
        additional_args=None,
    ):
        env = self._prepare_env()
        env_str = " ".join([f"{k}={v}" for k, v in env.items()])

        cmd = f"{env_str} {self.appmap_command} navie --log-navie"
        if input_path:
            cmd += f" -i {input_path}"
        if context_path:
            cmd += f" -c {context_path}"
        if prompt_path:
            cmd += f" -p {prompt_path}"
        cmd += f" -o {output_path}"
        if additional_args:
            cmd += f" {additional_args}"
        cmd += f" > {log_file} 2>&1"

        return cmd

    def _execute(self, command, log_file):
        self.log(command)

        result = os.system(command)

        if result != 0:
            raise RuntimeError(
                f"Failed to execute command {command}. See {log_file} for details."
            )

        return result
