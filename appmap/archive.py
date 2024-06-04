import glob
import os


class Archive:
    def __init__(self, path: str) -> None:
        self.path = path

    def extract(self, workdir: str) -> None:
        os.system(f"tar -xf {self.path} -C {workdir}")

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


class ArchiveFinder:
    def __init__(self, base_path: str) -> None:
        self.base_path = base_path

    def find_archive(self, repo_version: str) -> Archive:
        """Finds the archive for the given repo-version (eg. flask-2.3)."""
        pattern = f"{repo_version}*.tar.xz"
        entries = glob.glob(os.path.join(self.base_path, pattern))
        return Archive(entries[0]) if entries else None
