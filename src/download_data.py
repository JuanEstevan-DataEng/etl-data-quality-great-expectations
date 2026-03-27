"""
download_data.py - Download the raw dataset from Google Drive.

Google Drive adds a confirmation token for files above a certain size,
which breaks a plain requests.get() call. gdown handles that token
automatically, making it the standard tool for Drive downloads.

This script is called automatically by main.py when the raw data file
is not found. It can also be run standalone at any time:

    python src/download_data.py

The file is only downloaded if it does not already exist locally.
"""

import gdown
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent.parent
RAW_DIR  = ROOT / "data" / "raw"
RAW_PATH = RAW_DIR / "retail_etl_dataset.csv"

# Google Drive file ID — extracted from the sharing link:
# https://drive.google.com/file/d/<FILE_ID>/view?usp=sharing
FILE_ID = "19VQLj7XTTbM7ViSxxmUojkLiK2F28d4e"


def download(dest_path=None) -> Path:
    """
    Download the raw dataset from Google Drive if it does not exist.

    Parameters
    ----------
    dest_path : Path or None
        Where to save the file. Defaults to data/raw/retail_etl_dataset.csv.

    Returns
    -------
    Path
        The path where the file was saved (whether newly downloaded or already present).
    """
    target = Path(dest_path) if dest_path else RAW_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        print(f"Raw data already present → {target}  (skipping download)")
        return target

    print(f"Downloading raw dataset from Google Drive...")
    print(f"  File ID : {FILE_ID}")
    print(f"  Saving to: {target}")

    # gdown.download() accepts the file ID directly via the `id` parameter.
    # fuzzy=True makes it tolerant of different URL formats.
    # quiet=False shows a progress bar during the download.
    result = gdown.download(id=FILE_ID, output=str(target), quiet=False, fuzzy=True)

    if result is None or not target.exists():
        raise RuntimeError(
            "Download failed. Possible causes:\n"
            "  - The file is not shared publicly on Google Drive.\n"
            "  - Your internet connection is unavailable.\n"
            "  - The file ID has changed.\n"
            f"  File ID used: {FILE_ID}"
        )

    size_mb = target.stat().st_size / (1024 * 1024)
    print(f"Download complete — {size_mb:.1f} MB saved to {target}")
    return target


if __name__ == "__main__":
    download()
