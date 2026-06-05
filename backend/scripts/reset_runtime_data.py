from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def reset_runtime_data(project_root: str | Path) -> dict:
    root = Path(project_root)
    datasets_dir = root / "datasets"
    removed: list[str] = []

    if datasets_dir.exists():
        for child in sorted(datasets_dir.iterdir()):
            if child.name == "_train_tune":
                shutil.rmtree(child)
                removed.append("datasets/_train_tune")
                child.mkdir(parents=True, exist_ok=True)
                continue
            if child.is_dir():
                shutil.rmtree(child)
                removed.append(f"datasets/{child.name}")
            elif child.is_file():
                child.unlink()
                removed.append(f"datasets/{child.name}")

    datasets_dir.mkdir(parents=True, exist_ok=True)
    (datasets_dir / "_train_tune").mkdir(parents=True, exist_ok=True)
    return {"removed": removed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset LabelLens runtime datasets and Train Tune artifacts.")
    parser.add_argument("--project-root", default=Path(__file__).resolve().parents[2])
    parser.add_argument("--yes", action="store_true", help="Required confirmation flag.")
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("Refusing to reset runtime data without --yes")
    result = reset_runtime_data(Path(args.project_root))
    print(result)


if __name__ == "__main__":
    main()
