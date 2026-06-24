#!/usr/bin/env python3
"""
fetch_and_update.py
Downloads the latest JCP&L bill PDF using a saved browser session (no login needed),
parses it, and updates data.json.

GitHub Actions secrets required:
  JCPL_COOKIES  — raw cookie string copied from Chrome DevTools (Network tab, Cookie header)

Refresh JCPL_COOKIES monthly by repeating the "Copy as cURL" step from Chrome.
"""

import asyncio
import os
import re
import json
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import pdfplumber

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / "data.json"
SCREENSHOT_DIR = ROOT / "screenshots"
DOWNLOAD_DIR = ROOT / "downloads"


async def fetch_pdf() -> Path:
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    cookies_raw = os.environ["JCPL_COOKIES"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            accept_downloads=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/149.0.0.0 Safari/537.36"
            ),
        )

        # Inject session cookies — skips login entirely
        cookies = []
        for pair in cookies_raw.split("; "):
            if "=" in pair:
                name, _, value = pair.partition("=")
                cookies.append({
                    "name": name.strip(),
                    "value": value.strip(),
                    "url": "https://www.firstenergycorp.com",
                })
        await context.add_cookies(cookies)
        print(f"   Loaded {len(cookies)} cookies")

        page = await context.new_page()

        # Navigate to account overview to verify session is valid
        print("-> Checking session...")
        await page.goto(
            "https://www.firstenergycorp.com/my_account.html",
            wait_until="networkidle",
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "01_account.png"))
        print(f"   URL: {page.url}")

        if "log_in" in page.url:
            await browser.close()
            raise RuntimeError(
                "Session cookies have expired. "
                "Log in to firstenergycorp.com in Chrome, do 'Copy as cURL' from the Network tab, "
                "and update the JCPL_COOKIES secret."
            )

        # Navigate to bill & payment history where PDF lives
        print("-> Navigating to bill history...")
        await page.goto(
            "https://www.firstenergycorp.com/my_account/bill_payment_history.html",
            wait_until="networkidle",
        )
        await asyncio.sleep(2)
        await page.screenshot(path=str(SCREENSHOT_DIR / "02_bill_history.png"))
        print(f"   URL: {page.url}")

        # Find and download the bill PDF
        print("-> Looking for bill PDF download link...")
        await page.screenshot(path=str(SCREENSHOT_DIR / "03_bill_section.png"))

        pdf_path = DOWNLOAD_DIR / "latest_bill.pdf"
        download_selectors = [
            "a[href*='.pdf']",
            "a:has-text('View Bill')",
            "a:has-text('Download Bill')",
            "a:has-text('Current Bill')",
            "a:has-text('PDF')",
            "button:has-text('View Bill')",
            "button:has-text('Download')",
            "a:has-text('View')",
        ]

        for selector in download_selectors:
            try:
                async with page.expect_download(timeout=15000) as dl:
                    await page.click(selector, timeout=5000)
                download = await dl.value
                await download.save_as(str(pdf_path))
                print(f"   Downloaded via '{selector}' -> {pdf_path}")
                await browser.close()
                return pdf_path
            except PlaywrightTimeoutError:
                print(f"   Selector '{selector}' timed out, trying next...")
                continue
            except Exception as e:
                print(f"   Selector '{selector}' failed: {e}")
                continue

        await page.screenshot(path=str(SCREENSHOT_DIR / "04_download_failed.png"))
        html = await page.content()
        (ROOT / "debug_page.html").write_text(html, encoding="utf-8")
        await page.screenshot(path=str(ROOT / "debug_page.png"))
        await browser.close()
        raise RuntimeError(
            "Could not find or click a bill download link. "
            "Check the uploaded debug screenshots and debug-page artifacts."
        )


def parse_pdf(pdf_path: Path) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    m = re.search(
        r"Billing Period:\s+(\w+ \d{2}) to (\w+ \d{2}, \d{4}) for (\d+) days", text
    )
    if not m:
        raise ValueError("Could not find billing period in PDF — check the PDF format.")

    start_str = m.group(1)
    end_str   = m.group(2)
    days      = int(m.group(3))

    end_m = re.match(r"(\w+) \d+, (\d{4})", end_str)
    label  = f"{end_m.group(1)} {end_m.group(2)[2:]}"
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
        m = re.search(r"OffPeak KWH Used \(([\d.]+)%\)\s+(\d+)", text)
        if m:
            off_pct, off_peak = float(m.group(1)), int(m.group(2))

    temp = None
    m = re.search(r"Average Daily Temperature[\s\S]{0,300}?This Year\s+\d+\s+(\d+)", text)
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

    bills.append(entry)
    lines = ["["]
    for i, bill in enumerate(bills):
        comma = "," if i < len(bills) - 1 else ""
        lines.append("  " + json.dumps(bill, separators=(",", ":"), ensure_ascii=False) + comma)
    lines.append("]")

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Added {entry['label']} to data.json")
    return True


async def main():
    pdf_path = await fetch_pdf()
    entry = parse_pdf(pdf_path)
    print(f"\nParsed entry:\n{json.dumps(entry, indent=2)}")
    update_data_json(entry)


if __name__ == "__main__":
    asyncio.run(main())
