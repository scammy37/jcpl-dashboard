#!/usr/bin/env python3
"""
add_bill.py  —  Add a new JCP&L bill entry to the dashboard

Usage:
    python add_bill.py '{"label":"Jun 26","period":"Jun 04–Jul 03, 2026",...}'

Or run with no arguments to be prompted to paste the JSON interactively.

Get the JSON by sharing your bill PDF with Claude at claude.ai using the
prompt on the Add Bill page, then copy the JSON it returns here.
"""

import sys
import os
import json
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(SCRIPT_DIR, "data.json")

REQUIRED_KEYS = {"label", "period", "days", "kwh", "cost", "temp", "rate",
                 "onPeak", "offPeak", "onPct", "offPct"}


def write_data_json(bills):
    lines = ["["]
    for i, bill in enumerate(bills):
        comma = "," if i < len(bills) - 1 else ""
        lines.append("  " + json.dumps(bill, separators=(",", ":"), ensure_ascii=False) + comma)
    lines.append("]")
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def validate(entry):
    missing = REQUIRED_KEYS - entry.keys()
    if missing:
        raise ValueError(f"Missing fields: {', '.join(missing)}")
    if not isinstance(entry["days"], int):
        raise ValueError("'days' must be an integer")
    if not isinstance(entry["kwh"], int):
        raise ValueError("'kwh' must be an integer")
    if entry["rate"] not in ("Standard", "Time-of-Day"):
        raise ValueError("'rate' must be 'Standard' or 'Time-of-Day'")


def main():
    # Get JSON string from argument or interactive prompt
    if len(sys.argv) >= 2:
        raw = " ".join(sys.argv[1:])
    else:
        print("Paste the JSON entry from Claude, then press Enter twice:")
        lines = []
        while True:
            line = input()
            if line == "" and lines:
                break
            lines.append(line)
        raw = "\n".join(lines)

    raw = raw.strip().replace("```json", "").replace("```", "").strip()

    try:
        entry = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON — {e}")
        sys.exit(1)

    try:
        validate(entry)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Preview
    print("\nEntry to add:")
    for k, v in entry.items():
        print(f"  {k:10} {v}")

    # Load existing data
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        bills = json.load(f)

    # Duplicate check
    if any(b["label"] == entry["label"] for b in bills):
        print(f"\nWarning: an entry for {entry['label']} already exists.")
        answer = input("Overwrite it? (y/N): ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)
        bills = [b for b in bills if b["label"] != entry["label"]]

    bills.append(entry)
    write_data_json(bills)
    print(f"\n✓ Added {entry['label']} to data.json")

    # Commit & push
    answer = input("Commit and push to GitHub now? (Y/n): ").strip().lower()
    if answer == "n":
        print("Skipped — run 'git add data.json && git commit && git push' when ready.")
        return

    try:
        subprocess.run(["git", "add", "data.json"], cwd=SCRIPT_DIR, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Add {entry['label']} bill"],
            cwd=SCRIPT_DIR, check=True
        )
        subprocess.run(["git", "push"], cwd=SCRIPT_DIR, check=True)
        print("✓ Pushed to GitHub — refresh the dashboard.")
    except subprocess.CalledProcessError as e:
        print(f"\nGit error: {e}")
        print("data.json was updated locally. Run 'git add data.json && git commit && git push' manually.")


if __name__ == "__main__":
    main()
