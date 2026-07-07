#!/usr/bin/env python3
"""
process_bill.py — Parse a downloaded JCP&L bill PDF and add it to data.json

Usage:
    python scripts/process_bill.py path/to/bill.pdf

With no argument, looks for a single PDF in incoming/ and processes that one.
On success, deletes the source PDF if it came from incoming/.
"""

import re
import json
import sys
from pathlib import Path
import pdfplumber

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / "data.json"
INCOMING_DIR = ROOT / "incoming"


def parse_pdf(pdf_path: Path) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    m = re.search(
        r"Billing Period:\s*(\w+ \d{2}) to (\w+ \d{2}, \d{4}) for (\d+) days", text
    )
    if not m:
        print(f"--- PDF text (first 1500 chars) ---\n{text[:1500]}\n---")
        raise ValueError("Could not find billing period in PDF — check the PDF format above.")

    start_str = m.group(1)
    end_str   = m.group(2)
    days      = int(m.group(3))

    end_m   = re.match(r"(\w+) \d+, (\d{4})", end_str)
    start_m = re.match(r"(\w+)", start_str)
    end_year = int(end_m.group(2))
    start_month = start_m.group(1)
    # Dec→Jan bills: start year is one less than end year
    start_year = end_year - 1 if start_month == "Dec" and end_m.group(1) == "Jan" else end_year
    label  = f"{start_month} {str(start_year)[2:]}"
    period = f"{start_str}–{end_str}"

    m   = re.search(r"KWH used\s+([\d,]+)", text)
    kwh = int(m.group(1).replace(",", "")) if m else None

    m    = re.search(r"Current Consumption Bill Charges\s+([\d.]+)", text)
    cost = float(m.group(1)) if m else None

    rate = "Time-of-Day" if re.search(r"Time Of Day|Time-of-Day", text) else "Standard"

    on_peak = off_peak = on_pct = off_pct = None
    if rate == "Time-of-Day":
        m = re.search(r"OnPeak KWH Used \(([\d.]+)%\)\s+(\d+)", text)
        if m:
            on_pct, on_peak = float(m.group(1)), int(m.group(2))
        m = re.search(r"OffPeak KWH Used \(([\d.]+)%\)\s+([\d,]+)", text)
        if m:
            off_pct, off_peak = float(m.group(1)), int(m.group(2).replace(",", ""))

    temp = None
    m = re.search(r"Average Daily Temperature\s+\d+\s+(\d+)", text)
    if m:
        temp = int(m.group(1))

    return {
        "label":   label,
        "period":  period,
        "days":    days,
        "kwh":     kwh,
        "cost":    cost,
        "temp":    temp,
        "rate":    rate,
        "onPeak":  on_peak,
        "offPeak": off_peak,
        "onPct":   on_pct,
        "offPct":  off_pct,
    }


def update_data_json(entry: dict) -> bool:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        bills = json.load(f)

    if any(b["label"] == entry["label"] for b in bills):
        print(f"Entry for {entry['label']} already exists — skipping.")
        return False

    # Append the new entry without rewriting existing lines (preserves their formatting)
    new_line = "  " + json.dumps(entry, separators=(",", ":"), ensure_ascii=False)
    raw = DATA_PATH.read_text(encoding="utf-8").rstrip()
    assert raw.endswith("]"), "Unexpected data.json format"
    updated = raw[:-1].rstrip() + ",\n" + new_line + "\n]\n"
    DATA_PATH.write_text(updated, encoding="utf-8")

    print(f"Added {entry['label']} to data.json")
    return True


def find_incoming_pdf() -> Path:
    pdfs = sorted(INCOMING_DIR.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(
            f"No PDF found in {INCOMING_DIR}/ — drop the bill PDF there, or pass a path directly."
        )
    if len(pdfs) > 1:
        raise ValueError(
            f"Multiple PDFs found in {INCOMING_DIR}/ — pass the one to process as an argument: "
            f"{[p.name for p in pdfs]}"
        )
    return pdfs[0]


def main():
    pdf_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else find_incoming_pdf()

    entry = parse_pdf(pdf_path)
    print(f"\nParsed entry:\n{json.dumps(entry, indent=2)}")
    added = update_data_json(entry)

    if added and pdf_path.resolve().is_relative_to(INCOMING_DIR.resolve()):
        pdf_path.unlink()
        print(f"Removed processed PDF: {pdf_path}")

    if added:
        print(f"\n✓ NEW bill added: {entry['label']} | {entry['kwh']} KWH | ${entry['cost']:.2f}")
    else:
        print(f"\nNo update: {entry['label']} already in dashboard")


if __name__ == "__main__":
    main()
