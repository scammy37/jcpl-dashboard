# ⚡ JCP&L Electricity Dashboard

Personal electricity usage tracker — charts, filters, and billing history for JCP&L accounts.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Main dashboard — charts, table, filters |
| `extract.html` | Instructions for adding a new bill (PIN protected) |
| `data.json` | All billing records — the data source |
| `add_bill.py` | Script to add a new bill entry and push automatically |

---

## Adding a new bill

The **Add Bill** page (`extract.html`) is PIN protected. Click the link in the dashboard header to open it — it explains all three options below.

### Option A — Claude chat (recommended)
1. Go to [claude.ai](https://claude.ai), attach your JCP&L PDF bill
2. Use the prompt on the Add Bill page to extract the data as JSON
3. Open `data.json`, add the entry at the end of the array (comma after the previous entry), save
4. `git add data.json && git commit -m "Add [Month] bill" && git push`

### Option B — GitHub web editor
1. Go to your repo on github.com and open `data.json`
2. Click the ✏️ pencil icon to edit
3. Add the new entry at the end of the array
4. Click **Commit changes** — GitHub Pages redeploys automatically

### Option C — Script (fastest)
Get the JSON from Claude (Option A), then run:
```
python add_bill.py
```
Paste the JSON when prompted, press Enter twice, then Y to commit and push. Done.

---

## data.json entry format

```json
{"label":"Jun 26","period":"Jun 04–Jul 03, 2026","days":30,"kwh":1717,"cost":312.30,"temp":66,"rate":"Time-of-Day","onPeak":331,"offPeak":1386,"onPct":19.3,"offPct":80.7}
```

For Standard rate months set `onPeak`, `offPeak`, `onPct`, `offPct` all to `null`.

## Field reference

| Field | Type | Notes |
|-------|------|-------|
| `label` | string | End month, 2-digit year: `"Jun 26"` |
| `period` | string | Full billing period: `"Jun 04–Jul 03, 2026"` |
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
python -m http.server 8080
# Open http://localhost:8080
```

Or use the [Live Server](https://marketplace.visualstudio.com/items?itemName=ritwickdey.LiveServer) VS Code extension.
