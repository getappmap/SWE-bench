import json
import os
import re
import shutil
import sys
import time
from appmap.navie.fences import extract_fenced_content
from appmap.navie.client import Client


class Editor:
    def __init__(
        self, work_dir, temperature=0.0, token_limit=None, log=None, clean=False
    ):
        self.work_dir = work_dir
        os.makedirs(self.work_dir, exist_ok=True)

        self.temperature = temperature
        self.token_limit = token_limit
        if log:
            self.log = log
        else:
            log_file = os.path.join(self.work_dir, "navie.log")
            log_file_handle = open(log_file, "w")
            self.log = lambda msg: log_file_handle.write(msg + "\n")
        self.clean = clean

        self._terms = None
        self._plan = None
        self._files = None
        self._context = None
        self._generated_code = None

    def _log_action(self, action, content):
        clean_content = re.sub(r"[\r\n\t\x0b\x0c]", " ", content)
        clean_content = re.sub(r" +", " ", clean_content)
        if len(clean_content) > 100:
            clean_content = clean_content[:100] + "..."
        self.log(f"{action}: {clean_content}")

    def ask(self, question, prompt=None, context=None, cache=True):
        self._log_action("Asking", question)

        work_dir = self._work_dir("ask")
        question_file = os.path.join(work_dir, "ask.input.txt")
        output_file = os.path.join(work_dir, "ask.md")

        def read_output(save_cache):
            with open(output_file, "r") as f:
                explanation = f.read()

            if save_cache:
                self._save_cache(
                    work_dir, question, "question", prompt, "prompt", context, "context"
                )

            print(f"  Output is available at {output_file}")

            return explanation

        if cache and self._all_cache_valid(
            work_dir, question, "question", prompt, "prompt", context, "context"
        ):
            print("  Using cached answer")
            return read_output(False)

        with open(question_file, "w") as f:
            f.write(question)

        if prompt:
            prompt_file = os.path.join(work_dir, "ask.prompt.md")
            with open(prompt_file, "w") as f:
                f.write(prompt)
        else:
            prompt_file = None

        if context:
            context_file = os.path.join(work_dir, "ask.context.md")
            with open(context_file, "w") as f:
                f.write(context)
        else:
            context_file = None

        Client(work_dir, self.temperature, self.token_limit, self.log).ask(
            question_file,
            output_file,
            prompt_file=prompt_file,
            context_file=context_file,
        )

        return read_output(True)

    def suggest_terms(self, question):
        work_dir = self._work_dir("suggest_terms")
        issue_file = os.path.join(work_dir, "terms.input.txt")
        terms_file = os.path.join(work_dir, "terms.json")

        self._log_action("Suggesting terms for", question)

        with open(issue_file, "w") as f:
            f.write(question)

        Client(work_dir, self.temperature, self.token_limit, self.log).terms(
            issue_file, terms_file
        )

        with open(terms_file, "r") as f:
            raw_terms = f.read()
            terms = self.extract_fenced_content(raw_terms)

        self._terms = terms

        return terms

    def context(
        self,
        query,
        vectorize_query=True,
        exclude_pattern=None,
    ):
        work_dir = self._work_dir("context")
        query_file = os.path.join(work_dir, "context.input.txt")

        self._log_action("Searching for context", query)

        with open(query_file, "w") as f:
            f.write(query)
        output_file = os.path.join(work_dir, "context.yaml")

        Client(work_dir, self.temperature, self.token_limit, self.log).context(
            query_file, output_file, exclude_pattern, vectorize_query
        )

        with open(output_file, "r") as f:
            raw_context = f.read()
            context = self.extract_fenced_content(raw_context)

        self._context = context

        return context

    def plan(
        self,
        issue,
        context=None,
        context_file_extension=None,
        prompt=None,
        list_files=True,
        cache=True,
    ):
        work_dir = self._work_dir("plan")
        issue_file = os.path.join(work_dir, "plan.input.txt")
        output_file = os.path.join(work_dir, "plan.md")

        self._log_action("Planning", issue)

        def read_output_and_list_files(save_cache):
            with open(output_file, "r") as f:
                self._plan = f.read()

            if save_cache:
                self._save_cache(
                    work_dir,
                    issue,
                    "issue",
                    context,
                    "context",
                    prompt,
                    "prompt",
                )

            if list_files:
                self.list_files()

            print(f"  Output is available at {output_file}")

            return self._plan

        if cache and self._all_cache_valid(
            work_dir, issue, "issue", context, "context", prompt, "prompt"
        ):
            print("  Using cached plan")
            return read_output_and_list_files(False)

        with open(issue_file, "w") as f:
            f.write(issue)

        if context:
            extension = context_file_extension or "txt"
            context_file = os.path.join(work_dir, f"plan.context.{extension}")
            with open(context_file, "w") as f:
                f.write(context)
        else:
            context_file = None

        if prompt:
            prompt_file = os.path.join(work_dir, "plan.prompt.md")
            with open(prompt_file, "w") as f:
                f.write(prompt)
        else:
            prompt_file = None

        Client(work_dir, self.temperature, self.token_limit, self.log).plan(
            issue_file, output_file, context_file, prompt_file=prompt_file
        )

        return read_output_and_list_files(True)

    def files(self, load=False):
        if not self._files:
            if load:
                self.list_files()
            else:
                raise ValueError("The file list is not available, and load is disabled")

        return self._files

    def list_files(self, plan=None, cache=True):
        work_dir = self._work_dir("list_files")
        input_file = os.path.join(work_dir, "list_files.input.txt")
        output_file = os.path.join(work_dir, "list_files.json")

        if not plan:
            if not self._plan:
                raise ValueError("No plan provided or generated")
            plan = self._plan

        def read_output(save_cache):
            with open(output_file, "r") as f:
                self._files = []
                raw_files = f.read()
                content_items = extract_fenced_content(raw_files)
                for list in content_items:
                    self._files.extend(json.loads(list))

            if save_cache:
                self._save_cache(work_dir, self._plan, "plan")

            return self._files

        if cache and self._all_cache_valid(work_dir, self._plan, "plan"):
            return read_output(False)

        with open(input_file, "w") as f:
            f.write(plan)

        Client(work_dir, self.temperature, self.token_limit, self.log).list_files(
            input_file, output_file
        )

        return read_output(True)

    def generate(
        self,
        plan=None,
        files=None,
        context=None,
        auto_context=True,
        prompt=None,
        cache=True,
    ):
        work_dir = self._work_dir("generate")
        plan_file = os.path.join(work_dir, "generate.input.txt")
        output_file = os.path.join(work_dir, "generate.md")

        if not plan:
            if not self._plan:
                raise ValueError("No plan provided or generated")
            plan = self._plan

        if not files:
            if self._files is None:
                raise ValueError("No file list is available")
            if len(self._files) == 0:
                raise ValueError("File list is empty")
            files = self._files

        if not context:
            context = self._context

        self._log_action("Generating", plan)

        def read_output(save_cache):
            with open(output_file, "r") as f:
                self._generated_code = f.read()

            if save_cache:
                self._save_cache(
                    work_dir,
                    self._plan,
                    "plan",
                    self._files,
                    "files",
                    self._context,
                    "context",
                    prompt,
                    "prompt",
                )

            print(f"  Output is available at {output_file}")

            return self._generated_code

        if cache and self._all_cache_valid(
            work_dir, plan, "plan", files, "files", context, "context", prompt, "prompt"
        ):
            print("  Using cached generated code")
            return read_output(False)

        if context:
            context_file = os.path.join(work_dir, "generate.context.yaml")
            with open(context_file, "w") as f:
                f.write(context)
        else:
            if not auto_context:
                raise ValueError(
                    "No context provided is available, and auto_context is disabled"
                )
            context_file = None

        with open(plan_file, "w") as f:
            f.write(plan)

        if prompt:
            prompt_file = os.path.join(work_dir, "generate.prompt.md")
            with open(prompt_file, "w") as f:
                f.write(prompt)
        else:
            prompt_file = None

        Client(work_dir, self.temperature, self.token_limit, self.log).generate(
            plan_file,
            output_file,
            files,
            context_file=context_file,
            prompt_file=prompt_file,
        )

        return read_output(True)

    def apply(self, generated_code=None, all=True, file_name=None):
        work_dir = self._work_dir("apply_all")
        solution_file = os.path.join(work_dir, "apply_all.input.txt")
        apply_file = os.path.join(work_dir, "apply_all.md")

        if not generated_code:
            if not self._generated_code:
                raise ValueError("No generated code provided or generated")
            generated_code = self._generated_code

        with open(solution_file, "w") as f:
            f.write(generated_code)

        Client(work_dir, self.temperature, self.token_limit, self.log).apply(
            solution_file,
            apply_file,
            all=all,
            file_name=file_name,
        )

        with open(apply_file, "r") as f:
            applied_code = f.read()
        return applied_code

    def _save_cache(self, work_dir, *contents):
        # Enumerate the contents in pairs. The first item is the content, and the second item is the content name.
        for i in range(0, len(contents), 2):
            content = contents[i]
            if isinstance(content, list):
                content = json.dumps(content)
            if content is None:
                content = ""
            content_name = contents[i + 1]
            cache_file = os.path.join(work_dir, f"{content_name}.cache")
            with open(cache_file, "w") as f:
                f.write(content)

    def _all_cache_valid(self, work_dir, *contents):
        # Enumerate the contents in pairs. The first item is the content, and the second item is the content name.
        # Return true if all content caches are valid, otherwise return false.
        for i in range(0, len(contents), 2):
            content = contents[i]
            if isinstance(content, list):
                content = json.dumps(content)
            if content is None:
                content = ""

            content_name = contents[i + 1]
            if not self._is_cache_valid(work_dir, content, content_name):
                self.log(
                    f"Cache for {content_name} is invalid. The action will be performed."
                )
                return False

        return True

    def _is_cache_valid(self, work_dir, content, content_name):
        cache_file = os.path.join(work_dir, f"{content_name}.cache")
        if not os.path.exists(cache_file):
            return False

        with open(cache_file, "r") as f:
            cached_content = f.read()
            return cached_content == content

    def _work_dir(self, name):
        rename_existing = self.clean

        work_dir = os.path.join(self.work_dir, name)
        if rename_existing and os.path.exists(work_dir):
            # Rename the existing work dir according to the timestamp of the oldest file in the directory
            files = [
                os.path.join(work_dir, f)
                for f in os.listdir(work_dir)
                if os.path.isfile(os.path.join(work_dir, f))
            ]

            if len(files > 0):
                # Get the oldest file's timestamp
                oldest_file = min(files, key=os.path.getctime)
                oldest_timestamp = time.strftime(
                    "%Y%m%d%H%M%S", time.gmtime(os.path.getctime(oldest_file))
                )
                new_name = f"{work_dir}_{oldest_timestamp}"
                print(f"Renaming existing work dir to {new_name}")
                shutil.move(work_dir, new_name)
            else:
                print(f"Removing empty work dir {work_dir}")
                shutil.rmtree(work_dir)

        os.makedirs(work_dir, exist_ok=True)
        return work_dir
