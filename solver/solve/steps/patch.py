# Filter any changes to the tests directory from the provided patch.
#
# retain: If True, retain only the changes to the tests directory. If False, filter out the changes to the tests directory.
def filter_patches_to_tests(model_patch, retain):
    # Apache License
    # https://github.com/paul-gauthier/aider-swe-bench/blob/6e98cd6c3b2cbcba12976d6ae1b07f847480cb74/tests.py#L45
    lines = model_patch.splitlines(keepends=True)
    filtered_lines = []
    is_tests = False
    for line in lines:
        if line.startswith("diff --git a/"):
            pieces = line.split()
            to = pieces[-1]
            if to.startswith("b/") and (
                "/test/" in to
                or "/tests/" in to
                or "/testing/" in to
                or "/test_" in to
                or "/tox.ini" in to
            ):
                is_tests = True
            else:
                is_tests = False

        if retain:
            if is_tests:
                filtered_lines.append(line)
        else:
            if not is_tests:
                filtered_lines.append(line)

    return "".join(filtered_lines)
