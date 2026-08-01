#!/usr/bin/env python3
"""Download the small CiP-DMD subset required by the P3 MVP.

The full sensor archive is intentionally excluded. Public share credentials are
published through Zenodo record 10118474 and must be supplied through
environment variables.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.parse
import urllib.request


BASE_URL = "https://cloud.ptw-darmstadt.de/public.php/webdav/"
FILES = [
    "README.md",
    "dataset_structure.png",
    "cylinder/meta_data.json",
    "cylinder/assembly/quality_data/quality_data.csv",
    "cylinder_bottom/meta_data.json",
    "cylinder_bottom/saw/quality_data/quality_data.csv",
    "cylinder_bottom/cnc_milling_machine/quality_data/quality_data.csv",
    "piston_rod/meta_data.json",
    "piston_rod/reworked_piston_rods_meta_data.json",
    "piston_rod/cnc_lathe/quality_data/quality_data.csv",
    "production_logs/production_log_milling.xlsx",
    "production_logs/production_log_sawing.xlsx",
    "production_logs/production_log_turning.xlsx",
]


def sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_with_resume(
    url: str,
    target: Path,
    base_headers: dict[str, str],
    max_attempts: int = 6,
) -> None:
    temporary_target = target.with_suffix(target.suffix + ".part")

    for attempt in range(1, max_attempts + 1):
        current_size = (
            temporary_target.stat().st_size if temporary_target.exists() else 0
        )
        request_headers = dict(base_headers)
        if current_size:
            request_headers["Range"] = f"bytes={current_size}-"

        try:
            request = urllib.request.Request(url, headers=request_headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                status = getattr(response, "status", 200)
                content_length = response.headers.get("Content-Length")

                if current_size and status != 206:
                    current_size = 0
                    write_mode = "wb"
                else:
                    write_mode = "ab" if current_size else "wb"

                expected_size = None
                if content_length is not None:
                    response_bytes = int(content_length)
                    expected_size = (
                        current_size + response_bytes
                        if status == 206
                        else response_bytes
                    )

                with temporary_target.open(write_mode) as destination:
                    while chunk := response.read(1024 * 1024):
                        destination.write(chunk)

            actual_size = temporary_target.stat().st_size
            if expected_size is not None and actual_size != expected_size:
                raise IOError(
                    f"incomplete download: expected {expected_size}, got {actual_size}"
                )

            temporary_target.replace(target)
            return
        except Exception as error:
            if attempt == max_attempts:
                raise RuntimeError(f"failed to download {url}: {error}") from error
            print(
                f"retry {attempt}/{max_attempts}: {target.name} ({error})",
                flush=True,
            )
            time.sleep(min(attempt, 4))


def main() -> None:
    share_token = os.environ.get("CIP_SHARE_TOKEN")
    share_password = os.environ.get("CIP_SHARE_PASSWORD")
    if not share_token or not share_password:
        raise SystemExit(
            "Set CIP_SHARE_TOKEN and CIP_SHARE_PASSWORD from Zenodo record 10118474."
        )

    project_root = Path(__file__).resolve().parents[1]
    output_root = project_root / "data" / "raw" / "cip_dmd"
    output_root.mkdir(parents=True, exist_ok=True)

    encoded_credentials = base64.b64encode(
        f"{share_token}:{share_password}".encode("utf-8")
    ).decode("ascii")
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "User-Agent": "p3-cip-dmd-mvp/1.0",
    }

    manifest_files = []
    for relative_name in FILES:
        target = (output_root / relative_name).resolve()
        if output_root.resolve() not in target.parents:
            raise ValueError(f"Unsafe target path: {relative_name}")
        target.parent.mkdir(parents=True, exist_ok=True)

        encoded_path = urllib.parse.quote(relative_name, safe="/")
        download_with_resume(BASE_URL + encoded_path, target, headers)

        manifest_files.append(
            {
                "path": relative_name,
                "bytes": target.stat().st_size,
                "sha256": sha256_file(target),
                "source": BASE_URL + encoded_path,
            }
        )
        print(
            f"downloaded {relative_name} ({target.stat().st_size:,} bytes)",
            flush=True,
        )

    manifest = {
        "dataset": "CiP-DMD",
        "source_record": "https://zenodo.org/records/10118474",
        "subset_policy": "metadata, quality tables, production logs; no HDF5 signals",
        "files": manifest_files,
        "total_bytes": sum(item["bytes"] for item in manifest_files),
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    main()
