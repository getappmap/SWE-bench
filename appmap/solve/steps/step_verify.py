from appmap.solve.steps.run_test import run_test


def step_verify(tcm, test_file):
    print(f"[verify] Verifying the solution using generated test file {test_file}")

    (succeeded,) = run_test(tcm, test_file)

    if succeeded:
        print("[verify] Test passed")
    else:
        print("[verify] Test failed")

    return succeeded
