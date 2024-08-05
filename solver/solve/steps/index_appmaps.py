from navie.config import Config
from solve.run_command import run_command
from solve.steps.count_appmaps import count_appmaps


def index_appmaps(instance_id, log_dir):
    appmap_count = count_appmaps()
    if appmap_count > 0:
        print(f"[index_appmaps] ({instance_id}) Counted {appmap_count} AppMap files")
        print(f"[index_appmaps] ({instance_id}) Indexing AppMap data")
        try:
            run_command(
                log_dir,
                command=f"{Config.get_appmap_command()} index",
                fail_on_error=True,
            )
        except RuntimeError as e:
            print(
                f"[index_appmaps] ({instance_id}) AppMap data indexing failed: {e} {e.output}"
            )
        else:
            print(f"[index_appmaps] ({instance_id}) Index complete")
