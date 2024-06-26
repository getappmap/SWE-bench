from filelock import FileLock
from functools import cache
import glob
import os
import shutil
from typing import Optional, Protocol

from github import Github, UnknownObjectException
from github.Artifact import Artifact
from github.Requester import Requester

if "GITHUB_TOKEN" not in os.environ:
    print("GITHUB_TOKEN environment variable not set, using unauthenticated GitHub")
github_client = Github(os.environ.get("GITHUB_TOKEN", None))
github_requester: Requester = github_client._Github__requester

RUNS = {
    "getappmap/download-gdrive-appmap-archives": [9357711421],
    "getappmap/SWE-bench": [
        9387841075,
        9387836277,
        9387750538,
        9387818738,
        9387246481,
        9387560383,
        9387556159,
        9387552571,
        9387550441,
        9387545110,
        9391200795,
        9391182409,
        9391037925,
        9404783807,
        9404779233,
        9404773898,
        9404853224,
        9404795820,
        9403533528,
        9422673252,
        9422663223,
        9403096497,
        9390993060,
    ],
}


def download_artifact(self: Artifact) -> str:
    """Get a redirect URL to download the artifact."""
    status, headers, _ = self._requester.requestJson("GET", self.archive_download_url)
    assert status == 302
    return headers["location"]


Artifact.download = download_artifact


class Archive(Protocol):
    def extract(self, workdir: str) -> None: ...

    @property
    def name(self) -> str: ...


class FileArchive:
    def __init__(self, path: str) -> None:
        self.path = path

    def extract(self, workdir: str) -> None:
        os.system(f"tar -xf {self.path} -C {workdir}")

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    def __str__(self) -> str:
        return f"FileArchive({self.path})"


ARCHIVE_DIR = "/tmp/appmap-archives"
os.makedirs(ARCHIVE_DIR, exist_ok=True)


class GithubArchive:
    def __init__(self, artifact: Artifact) -> None:
        self.artifact = artifact
        self.name = artifact.name

        self.dirname = self.name.removesuffix(".tar.xz")
        self.dirpath = os.path.join(ARCHIVE_DIR, self.dirname)
        self.appmap_yml_path = os.path.join(self.dirpath, "appmap.yml")

    @property
    def is_unpacked(self):
        return os.path.exists(self.appmap_yml_path)

    def extract(self, workdir: str) -> None:
        if not self.is_unpacked:
            with FileLock(self.dirpath + ".lock"):
                self._download_archive()
        # Copy appmap.yml to workdir
        dest_appmap_yml = os.path.join(workdir, "appmap.yml")
        shutil.copy(self.appmap_yml_path, dest_appmap_yml)

        # Ensure workdir/tmp exists
        tmp_dir = os.path.join(workdir, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)

        # Symlink self.dirpath/tmp/appmap in workdir/tmp
        src_symlink = os.path.join(self.dirpath, "tmp/appmap")
        dest_symlink = os.path.join(tmp_dir, "appmap")
        if os.path.exists(dest_symlink):
            os.remove(dest_symlink)  # Remove existing symlink/file
        os.symlink(src_symlink, dest_symlink)

    def _download_archive(self) -> None:
        if self.is_unpacked:
            return
        zip_path = self.dirpath + ".zip"
        url = self.artifact.download()
        assert os.system(f"wget -q '{url}' -O {zip_path}") == 0
        assert os.system(f"unzip -u {zip_path} -d {ARCHIVE_DIR}") == 0

        tarpath = os.path.join(ARCHIVE_DIR, self.name)
        assert os.path.exists(tarpath)
        os.remove(zip_path)

        os.makedirs(self.dirpath, exist_ok=True)
        os.system(f"tar -xf {tarpath} -C {self.dirpath}")
        os.remove(tarpath)
        appmaps = glob.glob(
            os.path.join(self.dirpath, "tmp/appmap/**/*.appmap.json"), recursive=True
        )
        print(f"Extracted {len(appmaps)} appmaps from {self}", flush=True)
        assert self.is_unpacked

    def __str__(self) -> str:
        return f"GithubArchive({self.artifact.name})"


@cache
def get_artifacts(repo_id: str, run_id: str) -> list[Artifact]:
    try:
        repo = get_repo(repo_id)
    except UnknownObjectException:
        print(f"Repository {repo_id} is unavailable", flush=True)
        return []
    run = repo.get_workflow_run(run_id)
    return run.get_artifacts()


@cache
def get_repo(repo_id):
    return github_client.get_repo(repo_id)


class ArchiveFinder:

    def __init__(self, base_path: Optional[str] = None) -> None:
        self.base_path = base_path

    def find_archive(self, repo_version: str) -> Archive:
        """Finds the archive for the given repo-version (eg. flask-2.3)."""
        archive = self._find_local(repo_version)
        if archive:
            return archive
        return self._find_github(repo_version)

    def _find_local(self, repo_version: str) -> Optional[Archive]:
        if not self.base_path:
            return None
        pattern = f"{repo_version}*.tar.xz"
        entries = glob.glob(os.path.join(self.base_path, pattern))
        return FileArchive(entries[0]) if entries else None

    def _find_github(self, repo_version: str) -> Archive:
        for repo_id, runs in RUNS.items():
            for run_id in runs:
                for artifact in get_artifacts(repo_id, run_id):
                    if artifact.name.startswith(repo_version):
                        return GithubArchive(artifact)
