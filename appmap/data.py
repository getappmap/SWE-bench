from datasets import Dataset, load_dataset, load_from_disk
from pathlib import Path

datasets_dir = Path(__file__).parent / "datasets"


def load_data(dataset_name) -> Dataset:
    if Path(dataset_name).exists():
        return load_from_disk(dataset_name)

    dataset_dir = datasets_dir / dataset_name.replace("/", "__")
    dataset = None
    if Path(dataset_dir).exists():
        dataset = load_from_disk(str(dataset_dir))
    else:
        dataset = load_dataset(dataset_name)
        Path.mkdir(dataset_dir, parents=True)
        dataset.save_to_disk(str(dataset_dir))

    return dataset
