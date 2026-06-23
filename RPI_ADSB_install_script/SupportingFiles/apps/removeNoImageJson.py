#!/usr/bin/env python3
import json
from pathlib import Path


# Configuration — no command-line arguments required.
JSON_DIR = Path("/var/www/html/hex")


def main():
    if not JSON_DIR.is_dir():
        print(f"Directory not found: {JSON_DIR}")
        return

    deleted = 0
    skipped = 0
    errors = 0

    for json_path in sorted(JSON_DIR.glob("*.json")):
        try:
            record = json.loads(json_path.read_text(errors="ignore"))
            if record.get("image_status") != "NO_IMAGE":
                skipped += 1
                continue

            json_path.unlink()
            deleted += 1
            print(f"Deleted: {json_path.name}")

        except Exception as exc:
            errors += 1
            print(f"Error reading {json_path.name}: {exc}")

    print(
        f"Finished: {deleted} NO_IMAGE JSON files deleted, "
        f"{skipped} kept, {errors} errors."
    )


if __name__ == "__main__":
    main()
