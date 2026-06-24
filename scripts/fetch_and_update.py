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
import urllib.request
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

        async def dismiss_privacy_modal():
            for sel in [
                "button:has-text('ACCEPT ALL')",
                "button:has-text('Accept All')",
                "button:has-text('REJECT')",
            ]:
                try:
                    await page.click(sel, timeout=3000)
                    await asyncio.sleep(0.5)
                    print("   Dismissed privacy modal")
                    return
                except PlaywrightTimeoutError:
                    continue

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

        await dismiss_privacy_modal()
        await page.screenshot(path=str(SCREENSHOT_DIR / "02_account_clean.png"))

        pdf_path = DOWNLOAD_DIR / "latest_bill.pdf"

        # "View Bill" opens the PDF in a new tab — catch the popup, grab the URL, download directly
        print("-> Clicking 'View Bill' (expecting new tab)...")
        try:
            async with context.expect_page(timeout=20000) as new_page_info:
                await page.click("button:has-text('View Bill')", timeout=8000)
            popup = await new_page_info.value
            await popup.wait_for_load_state("domcontentloaded")
            pdf_url = popup.url
            print(f"   Popup URL: {pdf_url}")
            await popup.screenshot(path=str(SCREENSHOT_DIR / "03_pdf_popup.png"))
            await popup.close()

            # Download PDF with session cookies via urllib (no extra dependencies)
            cookie_dict = {}
            for pair in cookies_raw.split("; "):
                if "=" in pair:
                    name, _, value = pair.partition("=")
                    cookie_dict[name.strip()] = value.strip()
            cookie_header = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())

            req = urllib.request.Request(
                pdf_url,
                headers={
                    "Cookie": cookie_header,
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/149.0.0.0 Safari/537.36"
                    ),
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                pdf_path.write_bytes(resp.read())
            print(f"   Saved PDF -> {pdf_path}")
            await browser.close()
            return pdf_path

        except PlaywrightTimeoutError:
            print("   No popup appeared — button may behave differently")
            await page.wait_for_load_state("networkidle")
            await page.screenshot(path=str(SCREENSHOT_DIR / "03_after_view_bill.png"))
            print(f"   URL after click: {page.url}")
        except Exception as e:
            print(f"   Popup approach failed: {e}")
            await page.screenshot(path=str(SCREENSHOT_DIR / "03_after_view_bill.png"))

        # Look for a PDF link on wherever we landed
        await dismiss_privacy_modal()
        for sel in ["a[href*='.pdf']", "a:has-text('Download')", "a:has-text('PDF')", "button:has-text('Download')"]:
            try:
                async with page.expect_download(timeout=15000) as dl:
                    await page.click(sel, timeout=5000)
                download = await dl.value
                await download.save_as(str(pdf_path))
                print(f"   Downloaded via '{sel}' -> {pdf_path}")
                await browser.close()
                return pdf_path
            except PlaywrightTimeoutError:
                continue
            except Exception as e:
                print(f"   '{sel}' failed: {e}")

        # Fall back to bill history page
        print("-> Navigating to bill history page...")
        await page.goto(
            "https://www.firstenergycorp.com/my_account/bill_payment_history.html",
            wait_until="networkidle",
        )
        await asyncio.sleep(3)
        await dismiss_privacy_modal()
        await asyncio.sleep(3)
        await page.screenshot(path=str(SCREENSHOT_DIR / "04_bill_history.png"))
        print(f"   URL: {page.url}")

        for sel in [
            "a[href*='.pdf']",
            "a:has-text('View Bill')",
            "a:has-text('Download Bill')",
            "a:has-text('PDF')",
            "button:has-text('View Bill')",
            "button:has-text('Download')",
        ]:
            try:
                async with page.expect_download(timeout=15000) as dl:
                    await page.click(sel, timeout=5000)
                download = await dl.value
                await download.save_as(str(pdf_path))
                print(f"   Downloaded via '{sel}' -> {pdf_path}")
                await browser.close()
                return pdf_path
            except PlaywrightTimeoutError:
                print(f"   '{sel}' timed out")
                continue
            except Exception as e:
                print(f"   '{sel}' failed: {e}")

        await page.screenshot(path=str(SCREENSHOT_DIR / "05_download_failed.png"))
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

    # Write full text for debugging
    debug_path = ROOT / "debug_pdf_text.txt"
    debug_path.write_text(text, encoding="utf-8")
    print(f"--- PDF text (first 800 chars) ---\n{text[:800]}\n---")

    m = re.search(
        r"Billing Period:\s*(\w+ \d{2}) to (\w+ \d{2}, \d{4}) for (\d+) days", text
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
