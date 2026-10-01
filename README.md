# Garden Ledger

A local planting journal for a home garden. It keeps a log of what you planted, checks upcoming nights against each crop’s cold limit, and can talk to Claude through MCP.

Weather comes from [Open-Meteo](https://open-meteo.com/) (no API key). The catalog is a small set of kitchen crops, herbs, and companions. Everything about *your* plot stays on your machine.

## Your data stays private

These files are yours. They are gitignored and should not be published:

| File | What it is |
| --- | --- |
| `config.toml` | Coordinates, timezone, garden name, frost dates |
| `data/garden.db` | Planting log (SQLite) |
| `data/layout.json` | Optional bulk layout backup |

First-run setup writes `config.toml` for you. If you fork this project, leave those files out of GitHub.

## Requirements

- Python 3.11+
- Optional: [Node.js](https://nodejs.org/) only if you use MCP Inspector

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## First run (web app)

```powershell
garden-planner-web
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/). The app asks:

1. **Where is the garden?** City, town, or ZIP. Pick the right match so forecast and frost use that point.
2. **What is the plot like?** Name, aspect, sun, typical last spring frost and first fall frost (US dates are fine). Frost dates are prefilled from latitude if you do not know them.
3. **What is growing?** Optional rows for plant, variety, bed, date, quantity, and notes.

You can skip plantings and use **Log a planting** later. **Edit** (top right) opens fields; **Save** writes them and returns to the journal view.

## First run with Claude

If you use Claude Desktop or another MCP client, attach this server and start from the **`set_up_my_garden`** prompt. The same interview lives in [`prompts/garden-setup.md`](prompts/garden-setup.md) if you want to paste it.

Claude should:

1. Ask for location (or coordinates)
2. Call `search_places` and confirm the match
3. Ask about the plot and each bed / planting
4. Call `save_garden_setup` so `config.toml` and the SQLite log are written locally

## MCP Inspector

From the project directory, with the venv active:

```powershell
npx.cmd @modelcontextprotocol/inspector python -m garden_planner
```

On Windows, if PowerShell blocks `npx`, use `npx.cmd`. Point Inspector at the venv Python if `python` is not that interpreter.

## Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS). Use **your** clone path:

```json
{
  "mcpServers": {
    "garden-planner": {
      "command": "C:\\path\\to\\garden-planner\\.venv\\Scripts\\python.exe",
      "args": ["-m", "garden_planner"],
      "cwd": "C:\\path\\to\\garden-planner"
    }
  }
}
```

Restart Claude Desktop after saving.

**Tools:** `search_places`, `save_garden_setup`, `log_planting`, `list_plantings`, `update_planting`, `get_forecast`, `frost_check`, `planting_window`

Temperatures in tools and the web UI are Fahrenheit. Dates accept forms like `2026-05-01`, `05-01-2026`, and `5/1/26`.

## Tests

```powershell
pytest
pytest -m network
```

The network mark hits Open-Meteo’s archive (used to replay a known freeze).

## License

MIT. See [LICENSE](LICENSE).
