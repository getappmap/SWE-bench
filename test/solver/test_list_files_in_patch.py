import unittest

from solver.solve.steps.patch import list_files_in_patch


class TestListFilesInPatch(unittest.TestCase):
    def test_list_files_in_patch(self):
        """
        Test the list_files_in_patch function to ensure it correctly extracts file names from a patch.
        """
        patch = """diff --git a/file1.txt b/file1.txt
index 83db48f..f735c2d 100644
--- a/file1.txt
+++ b/file1.txt
@@ -1 +1 @@
-Hello World
+Hello Python
diff --git a/dir/file2.txt b/dir/file2.txt
index 83db48f..f735c2d 100644
--- a/dir/file2.txt
+++ b/dir/file2.txt
@@ -1 +1 @@
-Hello World
+Hello Python
"""
        expected_files = ["file1.txt", "dir/file2.txt"]
        result = list_files_in_patch(patch)
        self.assertEqual(result, expected_files)


if __name__ == "__main__":
    unittest.main()
