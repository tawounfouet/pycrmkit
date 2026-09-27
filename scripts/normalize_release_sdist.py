"""Normalize a Python sdist tar.gz for deterministic release hashing."""

from __future__ import annotations

import argparse
import gzip
import os
import tarfile
import tempfile
from pathlib import Path


def normalize_sdist(source: Path, *, epoch: int) -> None:
    with tempfile.TemporaryDirectory(prefix="pycrmkit-sdist-normalize-") as tmp:
        tmp_path = Path(tmp)
        root = tmp_path / "root"
        root.mkdir()

        with tarfile.open(source, "r:gz") as archive:
            archive.extractall(root)

        raw_tar = tmp_path / "normalized.tar"
        with tarfile.open(raw_tar, "w", format=tarfile.PAX_FORMAT) as archive:
            for path in sorted(root.rglob("*")):
                arcname = path.relative_to(root).as_posix()
                info = archive.gettarinfo(str(path), arcname=arcname)
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = epoch
                info.pax_headers = {}
                if path.is_file():
                    with path.open("rb") as stream:
                        archive.addfile(info, stream)
                else:
                    archive.addfile(info)

        with raw_tar.open("rb") as raw, source.open("wb") as target:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=target,
                compresslevel=9,
                mtime=epoch,
            ) as compressed:
                compressed.write(raw.read())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sdist", type=Path)
    args = parser.parse_args()

    epoch_text = os.environ.get("SOURCE_DATE_EPOCH")
    if not epoch_text:
        raise SystemExit("SOURCE_DATE_EPOCH is required")
    epoch = int(epoch_text)

    if not args.sdist.is_file():
        raise SystemExit(f"sdist does not exist: {args.sdist}")

    normalize_sdist(args.sdist, epoch=epoch)
    print(f"normalized {args.sdist} at SOURCE_DATE_EPOCH={epoch}")


if __name__ == "__main__":
    main()
