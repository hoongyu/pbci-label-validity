"""Download COG-BCI from Zenodo into data/raw.

`data/raw` is read-only for the rest of the project (`dataset.md` §1). This
script is the only thing that may write there.

Record: Zenodo DOI 10.5281/zenodo.6874128, CC-BY 4.0.
34 files: 29 per-subject zips plus notebook.mat, triggerlist.txt, RSME.txt,
KSS.txt and COG-BCI_info.pdf.

Usage:
    python -m src.io.download --check          # preflight only, downloads nothing
    python -m src.io.download --metadata-only  # the 5 small top-level files
    python -m src.io.download                  # full record (~29.5 GB)
    python -m src.io.download --extract        # unzip subject archives in place
    python -m src.io.download --verify         # re-check md5 of local files
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import yaml

RECORD_ID = "6874128"
DOI = "10.5281/zenodo.6874128"
API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"

# gates.md G0.2 requires "~50 GB free verified before download". The record is
# ~29.5 GB compressed; dataset.md §1 estimates ~50 GB extracted. Both exist on
# disk at once unless the archives are deleted after extraction, so the peak
# requirement is the sum. EXTRACT_FACTOR is an estimate, not a measurement --
# it is checked against reality by --extract and reported in the G0.2 log.
EXTRACT_FACTOR = 1.7
MIN_FREE_BYTES = 50 * 1024**3  # hard floor from G0.2, applied regardless
HEADROOM = 1.05

METADATA_FILES = {
    "notebook.mat",
    "triggerlist.txt",
    "RSME.txt",
    "KSS.txt",
    "COG-BCI_info.pdf",
}

REPO_ROOT = Path(__file__).resolve().parents[2]


class PreflightError(RuntimeError):
    """Raised when the download must not proceed."""


def load_config() -> dict:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def raw_dir(config: dict) -> Path:
    path = Path(config["paths"]["raw"])
    return path if path.is_absolute() else REPO_ROOT / path


def fetch_record() -> dict:
    with urllib.request.urlopen(API_URL, timeout=60) as response:
        return json.load(response)


def gb(n: int | float) -> str:
    return f"{n / 1024**3:.2f} GB"


def preflight(config: dict, *, metadata_only: bool) -> dict:
    """Verify the record and the disk before anything is written.

    Raises PreflightError rather than returning a status, so that a caller
    cannot proceed past a failed check by ignoring a return value.
    """
    record = fetch_record()
    files = record["files"]

    licence = record["metadata"].get("license", {}).get("id")
    if licence != "cc-by-4.0":
        raise PreflightError(
            f"licence is {licence!r}, expected 'cc-by-4.0'. Attribution terms "
            "may have changed; check before redistributing derived data (G4.2)."
        )

    selected = [f for f in files if f["key"] in METADATA_FILES] if metadata_only else files
    download_bytes = sum(f["size"] for f in selected)

    if metadata_only:
        need = int(download_bytes * HEADROOM)
    else:
        extracted = int(download_bytes * EXTRACT_FACTOR)
        need = max(int((download_bytes + extracted) * HEADROOM), MIN_FREE_BYTES)

    target = raw_dir(config)
    target.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(target).free

    print(f"record      : {record['metadata']['title'][:70]}")
    print(f"licence     : {licence}")
    print(f"files       : {len(selected)} selected of {len(files)} in record")
    print(f"download    : {gb(download_bytes)}")
    if not metadata_only:
        print(f"extracted   : ~{gb(download_bytes * EXTRACT_FACTOR)} (estimated)")
    print(f"target      : {target}")
    print(f"free space  : {gb(free)}")
    print(f"required    : {gb(need)}")

    if free < need:
        raise PreflightError(
            f"insufficient disk space: {gb(free)} free, {gb(need)} required at "
            f"{target}. Point config.yaml:paths.raw at a larger drive before "
            "downloading -- moving ~30 GB afterwards is painful."
        )

    print("preflight   : OK")
    return {"record": record, "files": selected, "download_bytes": download_bytes}


def download(config: dict, *, metadata_only: bool, retries: int) -> int:
    info = preflight(config, metadata_only=metadata_only)
    target = raw_dir(config)

    # Do NOT pass --md5 here. Despite the help text documenting that behaviour
    # only for --wget, zenodo_get treats --md5 as write-checksums-and-exit: it
    # creates md5sums.txt and downloads nothing. Checksums are verified instead
    # by --verify, which checks against the Zenodo API rather than a local file.
    cmd = [
        sys.executable, "-m", "zenodo_get",
        "--doi", DOI,
        "--output-dir", str(target),
        "--retry", str(retries),
        "--continue-on-error",  # one bad file must not abort 29 GB of progress
    ]
    if metadata_only:
        for key in sorted(METADATA_FILES):
            cmd += ["--glob", key]

    print(f"\n$ {' '.join(cmd)}\n", flush=True)
    return subprocess.call(cmd)


def md5_of(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.md5()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def verify(config: dict) -> int:
    """Re-check every local file against the checksums Zenodo publishes."""
    record = fetch_record()
    expected = {f["key"]: f["checksum"].split(":", 1)[1] for f in record["files"]}
    target = raw_dir(config)

    missing, bad, ok = [], [], []
    for key, want in sorted(expected.items()):
        path = target / key
        if not path.exists():
            missing.append(key)
            continue
        got = md5_of(path)
        (ok if got == want else bad).append(key)
        print(f"  {'OK  ' if got == want else 'BAD '} {key}")

    print(f"\nverified {len(ok)}/{len(expected)} | bad {len(bad)} | missing {len(missing)}")
    if missing:
        print("missing :", ", ".join(missing))
    if bad:
        print("bad     :", ", ".join(bad))
        print("Delete the bad files and re-run the download; do not patch them.")
    return 1 if bad else 0


def extract(config: dict) -> int:
    """Unzip subject archives into data/raw, skipping already-extracted ones."""
    target = raw_dir(config)
    archives = sorted(target.glob("sub-*.zip"))
    if not archives:
        print(f"no sub-*.zip archives in {target}; nothing to extract")
        return 1

    before = shutil.disk_usage(target).free
    for archive in archives:
        subject = archive.stem
        if (target / subject / "ses-S1").is_dir():
            print(f"  skip    {subject} (already extracted)")
            continue
        free = shutil.disk_usage(target).free
        with zipfile.ZipFile(archive) as zf:
            need = sum(i.file_size for i in zf.infolist())
            if free < need * HEADROOM:
                print(
                    f"  STOP    {subject}: needs {gb(need)}, only {gb(free)} free",
                    file=sys.stderr,
                )
                return 1
            print(f"  extract {subject} -> {gb(need)}", flush=True)
            _extract_normalised(zf, target / subject)

    used = before - shutil.disk_usage(target).free
    print(f"\nextracted, consuming {gb(used)}")
    print("Archives kept. Delete sub-*.zip once the inventory (G0.2) passes.")
    return 0


def _member_relpath(name: str) -> str | None:
    """Path of a zip member relative to its subject directory.

    The archives are not packaged consistently: sub-01 and sub-02 contain
    `sub-XX/ses-SY/...`, while sub-03 through sub-29 contain
    `sub-XX/sub-XX/ses-SY/...` -- one redundant level. Extracting verbatim
    yields two different on-disk layouts, and a loader globbing
    `sub-*/ses-S*/eeg/*.set` then silently finds 2 subjects instead of 29.

    Anchoring on the `ses-S*` component instead of on nesting depth normalises
    both layouts, and any further variation. Returns None for members that sit
    above the session level (the redundant directory entries themselves).
    """
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]
    for i, part in enumerate(parts):
        if part.startswith("ses-S"):
            return "/".join(parts[i:])
    return None


def _extract_normalised(zf: zipfile.ZipFile, subject_dir: Path) -> None:
    """Extract `zf` under `subject_dir`, stripping redundant nesting."""
    for member in zf.infolist():
        rel = _member_relpath(member.filename)
        if rel is None:
            continue
        dest = subject_dir / rel
        if member.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)


def normalise(config: dict) -> int:
    """Repair subject directories that were extracted with redundant nesting.

    Idempotent. Moves `sub-XX/sub-XX/ses-SY` up to `sub-XX/ses-SY`.
    """
    target = raw_dir(config)
    fixed = 0
    for subject_dir in sorted(target.glob("sub-*")):
        if not subject_dir.is_dir():
            continue
        if (subject_dir / "ses-S1").is_dir():
            continue
        nested = subject_dir / subject_dir.name
        if not (nested / "ses-S1").is_dir():
            print(f"  ?????   {subject_dir.name}: no ses-S1 at either depth")
            continue
        for child in list(nested.iterdir()):
            shutil.move(str(child), str(subject_dir / child.name))
        nested.rmdir()
        print(f"  fixed   {subject_dir.name}")
        fixed += 1
    print(f"\nnormalised {fixed} subject directories")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="preflight only; download nothing")
    mode.add_argument("--verify", action="store_true",
                      help="re-check md5 of local files against Zenodo")
    mode.add_argument("--extract", action="store_true",
                      help="unzip subject archives in place")
    mode.add_argument("--normalise", "--normalize", action="store_true",
                      dest="normalise",
                      help="repair redundantly nested sub-XX/sub-XX layouts")
    parser.add_argument("--metadata-only", action="store_true",
                        help="fetch only the 5 small top-level files")
    parser.add_argument("--retry", type=int, default=3,
                        help="application-level retries per file (default: 3)")
    args = parser.parse_args(argv)

    config = load_config()
    try:
        if args.check:
            preflight(config, metadata_only=args.metadata_only)
            return 0
        if args.verify:
            return verify(config)
        if args.extract:
            return extract(config)
        if args.normalise:
            return normalise(config)
        return download(config, metadata_only=args.metadata_only, retries=args.retry)
    except PreflightError as exc:
        print(f"\nPREFLIGHT FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
