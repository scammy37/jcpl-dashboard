#!/usr/bin/env python3
"""
fetch_and_update.py
Logs into JCP&L, downloads the latest bill PDF, parses it, and updates data.json.
Designed to run in GitHub Actions with JCPL_USERNAME and JCPL_PASSWORD env vars set.
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

    username = os.environ["JCPL_USERNAME"]
    password = os.environ["JCPL_PASSWORD"]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

        # Step 1: Login
        print("-> Loading login page...")
        await page.goto("https://www.firstenergycorp.com/log_in.html", wait_until="networkidle")
        await asyncio.sleep(2)  # allow JS-rendered form to finish mounting
        await page.screenshot(path=str(SCREENSHOT_DIR / "01_login.png"))

        try:
            # The login page has no form — it has a button that triggers an OAuth2/B2C redirect.
            # Click it and wait for navigation to the Microsoft B2C login page.
            print("-> Clicking Log In button (OAuth2 redirect)...")
            await page.click("a.b2cLoginButton, [data-login-page]", timeout=10000)
            await page.wait_for_load_state("networkidle")
            await page.screenshot(path=str(SCREENSHOT_DIR / "02_b2c_page.png"))
            print(f"   Redirected to: {page.url}")

            # Azure AD B2C standard field IDs
            print("-> Filling username on B2C page...")
            await page.fill("#signInName", username, timeout=15000)
            await page.fill("#password", password, timeout=10000)
            await page.screenshot(path=str(SCREENSHOT_DIR / "03_b2c_filled.png"))

            print("-> Submitting B2C login...")
            await page.click("#next, button[type='submit']", timeout=10000)
            await page.wait_for_load_state("networkidle")
            await page.screenshot(path=str(SCREENSHOT_DIR / "04_after_login.png"))
            print(f"   URL after login: {page.url}")

        except Exception:
            html = await page.content()
            (ROOT / "debug_page.html").write_text(html, encoding="utf-8")
            await page.screenshot(path=str(ROOT / "debug_page.png"))
            await browser.close()
            raise

        # Step 2: Navigate to billing
        print("-> Navigating to billing & payments...")
        await page.goto(
            "https://www.firstenergycorp.com/my_account/billing_payments.html",
            wait_until="networkidle",
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "05_billing.png"))
        print(f"   URL: {page.url}")

        # Step 3: Find and download the bill PDF
        print("-> Looking for bill PDF download link...")
        await page.screenshot(path=str(SCREENSHOT_DIR / "06_bill_section.png"))

        pdf_path = DOWNLOAD_DIR / "latest_bill.pdf"
        download_selectors = [
            "a[href*='.pdf']",
            "a:has-text('View Bill')",
            "a:has-text('Download Bill')",
            "a:has-text('PDF')",
            "button:has-text('View Bill')",
            "button:has-text('Download')",
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

        await page.screenshot(path=str(SCREENSHOT_DIR / "06_download_failed.png"))
        await browser.close()
        raise RuntimeError(
            "Could not find or click a bill download link. "
            "Check the uploaded debug screenshots in the Actions run artifacts."
        )


def parse_pdf(pdf_path: Path) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    # Billing period: "Billing Period: May 05 to Jun 03, 2026 for 30 days"
    m = re.search(
        r"Billing Period:\s+(\w+ \d{2}) to (\w+ \d{2}, \d{4}) for (\d+) days", text
    )
    if not m:
        raise ValueError("Could not find billing period in PDF — check the PDF format.")

    start_str = m.group(1)   # "May 05"
    end_str   = m.group(2)   # "Jun 03, 2026"
    days      = int(m.group(3))

    # Label: end month + 2-digit year  e.g. "Jun 26"
    end_m = re.match(r"(\w+) \d+, (\d{4})", end_str)
    label  = f"{end_m.group(1)} {end_m.group(2)[2:]}"
    period = f"{start_str}–{end_str}"   # en-dash

    # KWH
    m   = re.search(r"KWH used\s+([\d,]+)", text)
    kwh = int(m.group(1).replace(",", "")) if m else None

    # Consumption cost only (not total amount due)
    m    = re.search(r"Current Consumption Bill Charges\s+([\d.]+)", text)
    cost = float(m.group(1)) if m else None

    # Rate
    rate = "Time-of-Day" if re.search(r"Time Of Day|Time-of-Day", text) else "Standard"

    # On/off peak (Time-of-Day only)
    on_peak = off_peak = on_pct = off_pct = None
    if rate == "Time-of-Day":
        m = re.search(r"OnPeak KWH Used \(([\d.]+)%\)\s+(\d+)", text)
        if m:
            on_pct, on_peak = float(m.group(1)), int(m.group(2))
        m = re.search(r"OffPeak KWH Used \(([\d.]+)%\)\s+(\d+)", text)
        if m:
            off_pct, off_peak = float(m.group(1)), int(m.group(2))

    # Average daily temperature — in comparison table after "This Year"
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
