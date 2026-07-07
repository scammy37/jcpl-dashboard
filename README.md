# ⚡ JCP&L Electricity Dashboard

Personal electricity usage tracker — charts, filters, and billing history for JCP&L accounts.

Live site: **https://scammy37.github.io/jcpl-dashboard**

---

## Files

| File | Purpose |
|------|---------|
| `index.html` | Main dashboard — charts, table, filters |
| `extract.html` | Add-bill page — instructions and setup guide |
| `data.json` | All billing records — the data source |
| `add_bill.py` | Script to manually add a bill entry and push |
| `sw.js` | Service worker — enables PWA install and offline access |
| `manifest.json` | PWA manifest — name, icon, display settings |
| `icon.svg` | App icon used by the PWA manifest |
| `scripts/process_bill.py` | Parses a bill PDF and appends the entry to `data.json` |
| `incoming/` | Drop a bill PDF here for Claude (or `process_bill.py`) to pick up |

---

## Adding a new bill

There's no automated login or scraping — JCP&L's site blocks scripted logins
(bot detection on the Azure B2C login flow), so bill PDFs are added manually.
The **Add Bill** page (`extract.html`) has full instructions; click the link
in the dashboard header. Three options:

### Option A — Drop the PDF + ask Claude (easiest, any device)
1. Download the latest bill PDF from firstenergycorp.com
2. Upload it to [github.com/scammy37/jcpl-dashboard → `incoming/`](https://github.com/scammy37/jcpl-dashboard/upload/main/incoming) (works from the GitHub mobile app or any browser)
3. Message Claude: "process the new bill" — it runs `scripts/process_bill.py`, commits the result, and deletes the processed PDF

### Option B — Claude + GitHub web editor (any device)
1. Go to [claude.ai](https://claude.ai), attach your JCP&L PDF, use the prompt on the Add Bill page
2. Copy the JSON Claude returns
3. Open `data.json` on [github.com/scammy37/jcpl-dashboard](https://github.com/scammy37/jcpl-dashboard), click ✏️, paste the entry, commit

### Option C — Script (home PC, fastest)
Either run the parser directly on the PDF:
```
python scripts/process_bill.py path/to/bill.pdf
```
or get JSON from Claude (Option B) and run:
```
python add_bill.py
```
Paste the JSON when prompted, press Enter twice, then Y to commit and push.

> **New machine?** See the "First time on a new computer?" section on the Add Bill page for Git, Python, and clone setup instructions.

> **Cleanup note:** this project previously had a GitHub Actions workflow that
> logged in with saved cookies and emailed results. It's been removed — if you
> still have `JCPL_COOKIES` or `GMAIL_APP_PASSWORD` secrets set on the repo
> (Settings → Secrets → Actions), they're no longer used and can be deleted.

---

## data.json entry format

```json
{"label":"Jun 25","period":"Jun 04–Jul 03, 2025","days":30,"kwh":1414,"cost":245.10,"temp":78,"rate":"Time-of-Day","onPeak":280,"offPeak":1134,"onPct":19.8,"offPct":80.2}
```

For Standard rate months set `onPeak`, `offPeak`, `onPct`, `offPct` all to `null`.

## Field reference

| Field | Type | Notes |
|-------|------|-------|
| `label` | string | Start month + 2-digit year: `"Jun 25"` |
| `period` | string | Full billing period: `"Jun 04–Jul 03, 2025"` |
| `days` | integer | Days in billing cycle |
| `kwh` | integer | Total KWH consumed |
| `cost` | number | Electricity charges only, 2 decimal places |
| `temp` | number or null | Average temp °F for the period |
| `rate` | string | `"Standard"` or `"Time-of-Day"` |
| `onPeak` | integer or null | On-peak KWH (Time-of-Day only) |
| `offPeak` | integer or null | Off-peak KWH (Time-of-Day only) |
| `onPct` | number or null | On-peak % of total |
| `offPct` | number or null | Off-peak % of total |

---

## Running locally

The dashboard uses `fetch('data.json')` which requires a local server (browsers block file:// fetches).

```bash
cd jcpl-dashboard
python serve.py
# Open http://localhost:8080
```

`serve.py` reads the `PORT` environment variable so it also works with the Claude Code preview pane automatically.

Or use the [Live Server](https://marketplace.visualstudio.com/items?itemName=ritwickdey.LiveServer) VS Code extension.

---

## PWA install

The dashboard is installable as a Progressive Web App. In Chrome/Edge, click the install icon in the address bar (or the three-dot menu → "Install JCP&L Electricity Dashboard"). Once installed it works offline using the last-fetched data.
