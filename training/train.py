import argparse
import json
from pathlib import Path

from training.dataset import download_dataset, load_dataset
from training.pipeline import export_artifact, train_and_evaluate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the UCI house-price Ridge model")
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/datasets/uci-real-estate"))
    parser.add_argument("--output", type=Path, default=Path("models/uci-real-estate-ridge-v1.json"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive_path = download_dataset(args.cache_dir)
    dataset = load_dataset(archive_path)
    artifact = train_and_evaluate(dataset)
    export_artifact(artifact, args.output)
    print(json.dumps(artifact["training"]["metrics"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
