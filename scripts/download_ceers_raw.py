#!/usr/bin/env python3
"""
CEERS / JWST NIRCam UNCAL Downloader (robust / resumable version)
===================================================================

HOW TO RUN THIS RELIABLY ON THE IUCAA HPC (survives SSH disconnects)
---------------------------------------------------------------------
Pick ONE of these. tmux/screen is recommended since you can also
re-attach and watch it live if you want.

  Option A - tmux (recommended):
      tmux new -s ceers
      python3 download_ceers_raw.py
      # detach with:  Ctrl+b then d
      # reconnect later:  tmux attach -t ceers

  Option B - nohup:
      nohup python3 download_ceers_raw.py > ceers_stdout.log 2>&1 &
      disown

  Option C - SLURM batch job (if your login node requires it):
      sbatch --job-name=ceers --time=48:00:00 --cpus-per-task=4 \
             --wrap="python3 download_ceers_raw.py"

HOW TO CHECK PROGRESS AT ANY TIME (from a NEW terminal, doesn't touch
the running job):
  1) Live log:
       tail -f /home/iit-t/pegasus_mount/Brenjit/Level_zero/download_ceers_raw.log
  2) Machine-readable snapshot (updated after every file):
       cat /home/iit-t/pegasus_mount/Brenjit/Level_zero/ceers_progress.json
  3) Quick file count vs manifest:
       wc -l /home/iit-t/pegasus_mount/Brenjit/Level_zero/ceers_uncal_manifest.txt
       ls /home/iit-t/pegasus_mount/Brenjit/Level_zero/raw_uncal | wc -l

RESUMABILITY
------------
Just re-run the exact same command again (in a fresh tmux/nohup session)
if the HPC disconnects, the process gets killed, or the node reboots.
Already-downloaded and size-verified files are skipped automatically.
No manual cleanup needed.
"""

import os
import sys
import time
import json
import shutil
import logging
import concurrent.futures
from astropy.table import Table, vstack

try:
    from astroquery.mast import Observations
except ImportError:
    print("astroquery not installed. Install using: pip install astroquery")
    sys.exit(1)

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
BASE_DIR = "/Users/gayathrykj/Downloads/CEERS"
DOWNLOAD_DIR = "/Users/gayathrykj/Downloads/CEERS/raw_uncal"

LOG_FILE = os.path.join(BASE_DIR, "download_ceers_raw.log")
MANIFEST_FILE = os.path.join(BASE_DIR, "ceers_uncal_manifest.txt")
FAILED_FILE = os.path.join(BASE_DIR, "ceers_failed_downloads.txt")
PROGRESS_FILE = os.path.join(BASE_DIR, "ceers_progress.json")

MAX_WORKERS = int(os.environ.get("CEERS_MAX_WORKERS", 3))
MAX_RETRIES = 3            # per-file retry attempts
RETRY_BACKOFF_SEC = 15      # base backoff, doubles each retry
OBS_CHUNK_SIZE = 5          # observations per get_product_list call (MAST guidance)
SIZE_TOLERANCE = 0.99       # accept file if >= 99% of reported remote size
MIN_FREE_GB_BUFFER = 50     # warn if less than this much free space remains after estimate


def setup_logger():
    logger = logging.getLogger("CEERS_DOWNLOAD")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


logger = setup_logger()

# progress.json is written from multiple threads -> guard with a lock
progress_lock = __import__("threading").Lock()


def one_row_table(row):
    return Table(rows=[row], names=row.colnames)


def write_progress(total, downloaded, existing, failed, completed, start_time,
                    failed_files, phase="downloading"):
    elapsed = time.time() - start_time
    rate = completed / elapsed if elapsed > 0 else 0
    remaining = total - completed
    eta_sec = remaining / rate if rate > 0 else None

    payload = {
        "phase": phase,
        "total_files": total,
        "completed": completed,
        "downloaded": downloaded,
        "already_existing": existing,
        "failed": failed,
        "percent_complete": round(100 * completed / total, 2) if total else 0,
        "elapsed_minutes": round(elapsed / 60, 2),
        "eta_minutes": round(eta_sec / 60, 2) if eta_sec is not None else None,
        "failed_files_sample": failed_files[-20:],  # last 20 only, keep file small
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    with progress_lock:
        tmp_path = PROGRESS_FILE + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, PROGRESS_FILE)  # atomic, so readers never see a half-written file


def check_disk_space(final_list):
    try:
        total_bytes = sum(int(row["size"]) for row in final_list if row["size"])
    except Exception:
        total_bytes = 0

    total_gb = total_bytes / (1024 ** 3)
    usage = shutil.disk_usage(DOWNLOAD_DIR)
    free_gb = usage.free / (1024 ** 3)

    logger.info(f"Estimated total download size : {total_gb:.1f} GB")
    logger.info(f"Free space at DOWNLOAD_DIR     : {free_gb:.1f} GB")

    if free_gb - total_gb < MIN_FREE_GB_BUFFER:
        logger.warning(
            f"LOW DISK SPACE WARNING: after downloading ~{total_gb:.1f} GB, "
            f"only ~{free_gb - total_gb:.1f} GB would remain free "
            f"(buffer target: {MIN_FREE_GB_BUFFER} GB). "
            f"Consider freeing space or downloading in batches."
        )


def file_is_valid(out_path, expected_size):
    if not os.path.exists(out_path):
        return False
    if not expected_size:
        # no size info from MAST to compare against; existence is all we can check
        return True
    actual = os.path.getsize(out_path)
    return actual >= expected_size * SIZE_TOLERANCE


def download_product(product, index, total):
    filename = str(product["productFilename"])
    out_path = os.path.join(DOWNLOAD_DIR, filename)

    expected_size = None
    try:
        if product["size"]:
            expected_size = int(product["size"])
    except Exception:
        expected_size = None

    if file_is_valid(out_path, expected_size):
        size_mb = os.path.getsize(out_path) / 1024 / 1024
        logger.info(f"[{index}/{total}] SKIP existing (verified): {filename} ({size_mb:.2f} MB)")
        return "existing", filename

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"[{index}/{total}] START download (attempt {attempt}/{MAX_RETRIES}): {filename}")

            Observations.download_products(
                one_row_table(product),
                download_dir=DOWNLOAD_DIR,
                flat=True
            )

            if file_is_valid(out_path, expected_size):
                size_mb = os.path.getsize(out_path) / 1024 / 1024
                logger.info(f"[{index}/{total}] DONE: {filename} ({size_mb:.2f} MB)")
                return "downloaded", filename
            else:
                last_error = "file missing or size mismatch after download"
                logger.warning(f"[{index}/{total}] INCOMPLETE (attempt {attempt}): {filename} | {last_error}")
                if os.path.exists(out_path):
                    os.remove(out_path)  # drop partial file so retry / next run doesn't mistake it for good

        except Exception as e:
            last_error = str(e)
            logger.warning(f"[{index}/{total}] ERROR (attempt {attempt}): {filename} | {last_error}")

        if attempt < MAX_RETRIES:
            backoff = RETRY_BACKOFF_SEC * (2 ** (attempt - 1))
            logger.info(f"[{index}/{total}] Retrying {filename} in {backoff}s...")
            time.sleep(backoff)

    logger.error(f"[{index}/{total}] FAILED after {MAX_RETRIES} attempts: {filename} | Last error: {last_error}")
    return "failed", filename


def get_products_in_chunks(obs):
    """MAST recommends querying products in small chunks of observations
    rather than one giant call, to avoid timeouts / hangs on large proposals."""
    chunks = [obs[i:i + OBS_CHUNK_SIZE] for i in range(0, len(obs), OBS_CHUNK_SIZE)]
    tables = []
    for i, chunk in enumerate(chunks, 1):
        logger.info(f"Fetching product list chunk {i}/{len(chunks)} ({len(chunk)} observations)...")
        try:
            tables.append(Observations.get_product_list(chunk))
        except Exception as e:
            logger.error(f"Chunk {i} failed to fetch product list: {e}. Retrying once...")
            time.sleep(10)
            try:
                tables.append(Observations.get_product_list(chunk))
            except Exception as e2:
                logger.error(f"Chunk {i} failed again, skipping this chunk: {e2}")
    return vstack(tables) if tables else Table()


def main():
    start_time = time.time()

    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    logger.info("=" * 80)
    logger.info("CEERS / JWST NIRCam UNCAL Downloader (robust/resumable)")
    logger.info("=" * 80)
    logger.info(f"BASE_DIR     = {BASE_DIR}")
    logger.info(f"DOWNLOAD_DIR = {DOWNLOAD_DIR}")
    logger.info(f"LOG_FILE     = {LOG_FILE}")
    logger.info(f"PROGRESS_FILE= {PROGRESS_FILE}")
    logger.info(f"MAX_WORKERS  = {MAX_WORKERS}")
    logger.info("Querying MAST for CEERS Proposal 1345 NIRCam imaging observations...")

    obs = Observations.query_criteria(
        proposal_id="1345",
        instrument_name="NIRCAM/IMAGE"
    )
    obs = obs[:1]

    logger.info(f"Number of CEERS NIRCam observations found: {len(obs)}")

    if len(obs) == 0:
        logger.warning("No observations found. Exiting.")
        return

    logger.info("Querying product list from MAST in chunks...")
    products = get_products_in_chunks(obs)

    logger.info(f"Total products returned by MAST: {len(products)}")

    mask = [
        str(subgroup).upper() == "UNCAL" and str(filename).endswith("_uncal.fits")
        for subgroup, filename in zip(
            products["productSubGroupDescription"],
            products["productFilename"]
        )
    ]

    uncal_products = products[mask]
    logger.info(f"Total UNCAL *_uncal.fits products found: {len(uncal_products)}")

    unique = {}
    for row in uncal_products:
        unique[str(row["productFilename"])] = row

    final_list = list(unique.values())
    total = len(final_list)

    logger.info(f"Unique UNCAL files to process: {total}")

    if total == 0:
        logger.warning("No UNCAL files matched. Exiting.")
        return

    with open(MANIFEST_FILE, "w") as f:
        for row in final_list:
            f.write(str(row["productFilename"]) + "\n")

    logger.info(f"Manifest written to: {MANIFEST_FILE}")

    check_disk_space(final_list)

    existing_count = 0
    downloaded_count = 0
    failed_count = 0
    failed_files = []

    logger.info("Starting parallel downloads...")
    logger.info("-" * 80)

    write_progress(total, 0, 0, 0, 0, start_time, [], phase="downloading")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_product, product, i + 1, total): str(product["productFilename"])
            for i, product in enumerate(final_list)
        }

        completed = 0

        for future in concurrent.futures.as_completed(futures):
            completed += 1
            filename = futures[future]

            try:
                status, fname = future.result()

                if status == "existing":
                    existing_count += 1
                elif status == "downloaded":
                    downloaded_count += 1
                else:
                    failed_count += 1
                    failed_files.append(fname)

            except Exception as e:
                failed_count += 1
                failed_files.append(filename)
                logger.error(f"Unhandled exception for {filename}: {e}")

            logger.info(
                f"PROGRESS: {completed}/{total} finished | "
                f"downloaded={downloaded_count}, existing={existing_count}, failed={failed_count}"
            )

            # write a fresh progress snapshot after every file so it can be
            # checked at any moment from another terminal
            write_progress(total, downloaded_count, existing_count, failed_count,
                            completed, start_time, failed_files, phase="downloading")

    with open(FAILED_FILE, "w") as f:
        for fname in failed_files:
            f.write(fname + "\n")

    elapsed = time.time() - start_time
    elapsed_min = elapsed / 60

    write_progress(total, downloaded_count, existing_count, failed_count,
                    total, start_time, failed_files, phase="done")

    logger.info("-" * 80)
    logger.info("DOWNLOAD SUMMARY")
    logger.info("-" * 80)
    logger.info(f"Total unique UNCAL files : {total}")
    logger.info(f"Already existing files   : {existing_count}")
    logger.info(f"Newly downloaded files   : {downloaded_count}")
    logger.info(f"Failed files             : {failed_count}")
    logger.info(f"Manifest file            : {MANIFEST_FILE}")
    logger.info(f"Failed list              : {FAILED_FILE}")
    logger.info(f"Elapsed time             : {elapsed_min:.2f} minutes")
    if failed_count > 0:
        logger.info(f"To retry failed files, just re-run this script — it will "
                     f"skip everything already downloaded and retry the rest.")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()