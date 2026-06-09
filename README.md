# ⚡ JCP&L Electricity Dashboard

Personal electricity usage dashboard for account 100 082 853 803 — 6 Faesch Ct, Rockaway NJ 07866.

## Files

| File | Purpose |
|------|---------|
| `index.html` | Main dashboard — charts, table, filters |
| `extract.html` | Upload a PDF bill → Claude extracts the data |
| `data.json` | All billing records — edit this to add/change data |

---

## Setup: GitHub Pages (one-time)

1. **Create a new GitHub repo** (e.g. `jcpl-dashboard`) — set it to **Public**
2. **Upload all three files** (`index.html`, `extract.html`, `data.json`) to the repo root
3. Go to **Settings → Pages**
4. Under *Source*, select **Deploy from a branch → main → / (root)**
5. Click **Save**

GitHub will give you a URL like:
```
https://yourusername.github.io/jcpl-dashboard/
```

That URL works on **any PC or phone** — just bookmark it.

---

## Adding a new bill

### Option A — PDF Upload (recommended)
1. Go to your dashboard URL and click **"Add Bill (PDF)"** in the header
2. Enter your [Anthropic API key](https://console.anthropic.com/keys) (only needed once per session — never stored)
3. Upload your JCP&L PDF bill
4. Claude extracts the data — review it, then click **Copy JSON Entry**
5. Open `data.json` in GitHub, paste the new entry at the end of the array (add a comma after the previous entry), and commit

### Option B — Manual edit
Open `data.json` and add a new entry following this format:

```json
{
  "label": "Jun 26",
  "period": "Jun 04–Jul 05, 2026",
  "days": 31,
  "kwh": 1550,
  "cost": 295.40,
  "temp": 76,
  "rate": "Time-of-Day",
  "onPeak": 290,
  "offPeak": 1260,
  "onPct": 18.7,
  "offPct": 81.3
}
```

For Standard rate months, set `onPeak`, `offPeak`, `onPct`, `offPct` all to `null`.

---

## Field reference

| Field | Type | Notes |
|-------|------|-------|
| `label` | string | Short label: `"Jun 26"` |
| `period` | string | Full billing period text |
| `days` | integer | Days in billing cycle |
| `kwh` | integer | Total KWH consumed |
| `cost` | number | Total charges (2 decimal places) |
| `temp` | number or null | Average temp °F for the period |
| `rate` | string | `"Standard"` or `"Time-of-Day"` |
| `onPeak` | integer or null | On-peak KWH (Time-of-Day only) |
| `offPeak` | integer or null | Off-peak KWH (Time-of-Day only) |
| `onPct` | number or null | On-peak % of total |
| `offPct` | number or null | Off-peak % of total |

---

## Running locally (optional)

The dashboard uses `fetch('data.json')` which requires a local server (browsers block file:// fetches).

```bash
# Python (simplest)
cd jcpl-dashboard
python3 -m http.server 8080
# Open http://localhost:8080
```

Or use the [Live Server](https://marketplace.visualstudio.com/items?itemName=ritwickdey.LiveServer) VS Code extension.
