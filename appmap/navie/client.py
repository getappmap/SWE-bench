import os

from appmap.navie.log_print import log_print

# EXCLUDE_PYTHON_TESTS_PATTERN = """(\\btesting\\b|\\btest\\b|\\btests\\b|\\btest_|_test\\.py$|\\.txt$|\\.html$|\\.rst$|\\.md$)"""


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

    def apply(self, file_path, replace, search=None):
        log_file = os.path.join(self.work_dir, "apply.log")

        env = self._prepare_env()
        env_str = " ".join([f"{k}={v}" for k, v in env.items()])

        cmd = f"{env_str} {self.appmap_command} apply"
        if search:
            cmd += f" -s {search}"
        cmd += f" -r {replace} {file_path}"
        cmd += f" > {log_file} 2>&1"
        self._execute(cmd, log_file)

    def compute_update(self, file_path, new_content_file, prompt_file=None):
        file_slug = "".join([c if c.isalnum() else "_" for c in file_path]).strip("_")
        log_file = os.path.join(self.work_dir, file_slug, "compute_update.log")
        output_file = os.path.join(self.work_dir, file_slug, "compute_update.txt")

        command = self._build_command(
            input_path=file_path,
            context_path=new_content_file,
            output_path=output_file,
            log_file=log_file,
            prompt_path=prompt_file,
        )
        self._execute(command, log_file)

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
        self,
        query_file,
        output_file,
        exclude_pattern=None,
        include_pattern=None,
        vectorize_query=True,
    ):
        log_file = os.path.join(self.work_dir, "search_terms.log")

        with open(query_file, "r") as f:
            query_content = f.read()

        question = ["@context /nofence /format=yaml"]
        if not vectorize_query:
            question.append("/noterms")
        if exclude_pattern:
            question.append(f"/exclude={exclude_pattern}")
        if include_pattern:
            question.append(f"/include={include_pattern}")

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

    def search(
        self,
        query_file,
        output_file,
        context_file=None,
        prompt_file=None,
        format_file=None,
    ):
        log_file = os.path.join(self.work_dir, "search.log")
        input_file = os.path.join(self.work_dir, "search.txt")

        with open(query_file, "r") as query_f:
            query_content = query_f.read()

        with open(input_file, "w") as search_f:
            question = ["@search"]
            if context_file:
                question.append("/nocontext")
            if format_file:
                question.append(f"/noformat")
            search_f.write(
                f"""{" ".join(question)}
                
{query_content}
"""
            )

        if format_file:
            if not prompt_file:
                prompt_file = format_file
            else:
                # Append format instructions to the prompt
                with open(format_file) as format_f:
                    format = format_f.read()

                with open(prompt_file, "a") as prompt_f:
                    prompt_f.write(
                        f"""

{format}
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

        command = self._build_command(
            input_path=input_file,
            output_path=output_file,
            context_path=context_file,
            prompt_path=prompt_file,
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
