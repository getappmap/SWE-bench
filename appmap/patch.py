from inference.run_api import call_chat
from inference.make_datasets.utils import extract_diff
from swebench.harness.utils import extract_minimal_patch
from subprocess import run
from tempfile import NamedTemporaryFile

def is_valid_patch(patch, directory):
    if patch:
      try:
          with NamedTemporaryFile(mode="w") as f:
            f.write(patch)
            f.flush()
            run(["git", "apply", "--no-apply", f.name], cwd=directory, check=True)
          return True
      except:
          pass
    return False

def extract_patch(completion, directory):
    """
    Parses the given response for a patch. If it can be applied to the given directory, returns the patch. Otherwise, returns None.
    """
    patch = extract_diff(completion)
    print(patch)
    if is_valid_patch(patch, directory):
        return patch
    patch = extract_minimal_patch(patch)
    print(patch)
    if is_valid_patch(patch, directory):
        return patch
    return None
   

def gen_patch(text, directory, retries=5, model_name="gpt-4o-2024-05-13", temperature=0.1, use_azure=False, top_p=1.0):
    """
    Generates a patch file using the given text and model. Retries up to retries times if the patch is malformed.
    Patch files will be tested against the given directory to ensure they apply.
    """
    total_cost = 0
    for i in range(retries):
        print(f"Generating patch (attempt {i+1}/{retries})")
        response, cost = call_chat(model_name, text, use_azure, temperature, top_p)
        total_cost += cost
        completion = response.choices[0].message.content
        patch = extract_patch(completion, directory)
        if patch:
            print("Successfully generated patch")
            return patch, completion, total_cost
    print("Failed to get generate valid patch")
    return None, None, total_cost