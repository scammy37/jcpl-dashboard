# ⚡ JCP&L Electricity Dashboard

Personal electricity usage tracker — charts, filters, and billing history for JCP&L accounts.

Live site: **https://scammy37.github.io/jcpl-dashboard**

---

## Files

| File | Purpose |
|------|---------|
| `index.html` | Main dashboard — charts, table, filters |
| `extract.html` | Add-bill page (PIN protected) |
| `data.json` | All billing records — the data source |
| `add_bill.py` | Script to manually add a bill entry and push |
| `sw.js` | Service worker — enables PWA install and offline access |
| `manifest.json` | PWA manifest — name, icon, display settings |
| `icon.svg` | App icon used by the PWA manifest |
| `scripts/fetch_and_update.py` | Auto-fetch script run by GitHub Actions |
| `.github/workflows/fetch-bill.yml` | Workflow: downloads and parses the latest bill automatically |

---

## Auto-fetch (GitHub Actions)

A workflow runs daily from the 7th–12th of each month and:
1. Logs in to firstenergycorp.com using a saved cookie session
2. Downloads the latest bill PDF
3. Parses it and appends a new entry to `data.json`
4. Commits and pushes if new data was found
5. Sends an email to `michael.zagame@gmail.com` with the result

**Secrets required** (set in repo Settings → Secrets → Actions):

| Secret | What it is |
|--------|-----------|
| `JCPL_COOKIES` | Cookie header string copied from Chrome DevTools after logging in |
| `GMAIL_APP_PASSWORD` | Gmail app password for the notification email |

Refresh `JCPL_COOKIES` only when needed: the workflow emails you a failure message ("Session cookies have expired") when they stop working. When that happens, log in to firstenergycorp.com in Chrome, open DevTools → Network, find any request, right-click → Copy as cURL, extract the `Cookie:` header value, and update the secret. Cookies typically last several months.

You can also trigger the workflow manually from the **Actions** tab → **Fetch JCP&L Bill** → **Run workflow**.

---

## Adding a bill manually

The **Add Bill** page (`extract.html`) is PIN protected. Click the link in the dashboard header to open it.

### Option A — Claude chat (recommended)
1. Go to [claude.ai](https://claude.ai) and attach your JCP&L PDF bill
2. Use the prompt on the Add Bill page to extract the data as JSON
3. Open `data.json`, add the entry at the end of the array, save
4. `git add data.json && git commit -m "Add [Month] bill" && git push`

### Option B — GitHub web editor
1. Open `data.json` in your repo on github.com
2. Click the ✏️ pencil icon to edit
3. Add the new entry at the end of the array
4. Click **Commit changes** — GitHub Pages redeploys automatically

### Option C — Script (fastest)
Get the JSON from Claude (Option A), then run:
```
python add_bill.py
```
Paste the JSON when prompted, press Enter twice, then Y to commit and push.

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
