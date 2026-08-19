# Organise_PC

Automatically organizes, cleans, and maintains your **Downloads**, **Pictures**, and **Videos** folders — and only those three. Runs quietly in the background and reacts instantly when files are added.

## What it does

| Feature | Where | Behavior |
|---|---|---|
| Sort by file type | Downloads | Moves files into `PDFs/`, `Images/`, `Installers/`, `Zips/`, `Documents/`, `Videos/`, `Audio/` |
| Sort Documents further by extension | Downloads | `Documents/` is split into `Documents/docx/`, `Documents/xlsx/`, `Documents/pdf/`, etc. — configurable |
| Auto-rename | Downloads | Renames sorted files to `Name_ext_DDMMYYYY` (e.g. `invoice_pdf_15082026.pdf`) |
| Duplicate detection | Downloads, Pictures, Videos | Matches by file content (SHA-256), moves duplicates to a `Duplicates/` folder — only compares files within the **same destination folder**, not across the whole tree |
| Screenshot organizer | Pictures, Videos | Detects filenames containing "screenshot", sorts into `Screenshots/<image\|video>/YYYY-MM/`, renames to `Screenshot_image_DDMMYYYY` |
| Format conversion | Pictures, Videos | `HEIC → JPG`, `MOV → MP4` (originals kept by default) |
| System maintenance | Whole system (read-only outside scope) | Disk space check, OS temp file cleanup, large-file report — runs every few hours |
| Excluded folders | Downloads | Folders you list (e.g. `Projects`) are never scanned, sorted, or renamed — not even read |
| Paginated startup report | Console | Every launch shows what changed, 20 items at a time — press Enter for the next page, or `q` to stop |
| Crash-resilient file ops | All of the above | A single locked/permission-denied file is logged and skipped — it no longer halts the entire run |
| Single-instance lock | Whole suite | Only one copy can ever run at a time — a second launch exits immediately instead of running alongside the first |
| AI-suggested renaming | Downloads | Reads file content and suggests a descriptive name, with your approval (dialog or Telegram) — falls back to `Name_ext_date` if rejected/unavailable |
| Telegram approval bot | Whole suite | Approve/reject rename suggestions from your phone; stays silent until you send it `/start`; supports instant message cleanup and `/clearall` |

**Scope guarantee:** every action is confined to `Downloads`, `Pictures`, and `Videos`. Temp cleanup only touches the OS temp directory. Nothing else on your PC is read, moved, renamed, or deleted. Folders listed in `DOWNLOADS_EXCLUDED_FOLDERS` are skipped entirely — the walk never even enters them.

## Setup (local, without Docker)

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

## AI-assisted renaming

Instead of (or alongside) the standard `Name_ext_date` convention, supported files can have their actual content read and a short, descriptive name suggested by AI — you approve or reject it before anything changes.

### 1. Get a Gemini API key
The AI renamer uses Google's Gemini API. Google currently offers a free tier for Gemini 2.5 Flash-Lite, subject to rate limits — see Gemini API pricing at ai.google.dev/gemini-api/docs/pricing.
1. Create a key in Google AI Studio (aistudio.google.com).
2. Set it as the `GEMINI_API_KEY` environment variable (or in `.env` — see `.env.example`):
```powershell
$env:GEMINI_API_KEY="YOUR_API_KEY"
```

### 2. Enable it
In `config/settings.py`:
```python
AI_RENAME_ENABLED = True
AI_RENAME_MODEL = "gemini-3.5-flash-lite"
```
Only extensions listed in `AI_RENAME_EXTENSIONS` get content read — everything else always uses the standard convention untouched. `AI_RENAME_AUTO_APPROVE = True` skips the approval step entirely (renames instantly, no prompt) — leave it `False` if you want to review suggestions first.

**The AI step is always approval-based unless auto-approve is on**: Gemini only *suggests* a name — nothing is renamed until you approve it, and it always falls back to the standard `Name_ext_date` naming if the API is unavailable, rate-limited, times out, or you reject the suggestion.

### 3. Choose how you approve: Windows dialog or Telegram

**Windows dialog (default)** — a Yes/No popup appears on your screen for each suggestion, auto-dismissing to "No" after `AI_RENAME_APPROVAL_TIMEOUT_SECONDS`.

**Telegram (optional, recommended if the suite runs silently in the background)** — suggestions are sent to your phone instead, so you don't need to be looking at the PC:

1. `pip install python-telegram-bot>=21.0` (already in `requirements.txt`)
2. Message **@BotFather** on Telegram → `/newbot` → copy the token it gives you
3. Message **@userinfobot** (or similar) to get your own numeric chat ID
4. Set in `.env` (or environment variables):
```dotenv
TELEGRAM_ENABLED=True
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```
5. **Open a chat with your bot and send `/start`.** This step is required — the bot stays completely silent, even if it's running and fully configured, until the configured chat sends `/start` at least once. This avoids it suddenly messaging you the moment the suite launches, before you've opened the chat yourself.

Once started, each suggestion arrives as a message with **Approve** / **Skip** buttons. This is fire-and-forget — the watcher sends the suggestion and immediately moves on to the next file, it never blocks waiting for your reply. The file keeps its original name until you tap something.

**Bot commands** (shown in Telegram's `/` menu):

| Command | What it does |
|---|---|
| `/start` | Activates the bot for this chat — required before any suggestions are sent |
| `/help` | Lists all commands |
| `/status` | Shows current settings, whether `/start` has been sent, pending suggestion count |
| `/pending` | Lists files currently awaiting your approval |
| `/skipall` | Skips every pending suggestion at once — those files keep their original names |
| `/clearall` | Erases every message the bot has sent in this chat, all at once (see below) |

**Message cleanup:** after you tap Approve/Skip, the confirmation message is controlled by `TELEGRAM_AUTO_DELETE_SECONDS` in `config/settings.py`:
- `0` (default) — deletes **instantly**, right when you tap, so the chat never accumulates a scrollback of old renames
- a positive number — deletes after that many seconds instead
- `None` — disables auto-delete, keeps every message permanently

This only ever removes the *Telegram message* — `logs/activity.log` always keeps the full permanent record regardless of what happens in the chat.

**`/clearall`** wipes every message the bot has sent in that chat this session (suggestions, confirmations, other command replies) in one go — useful for tidying up after a busy sorting session, or as a global reset for the message history without touching any actual files or the log. Note: Telegram's Bot API only allows a bot to delete messages *it* sent — it can't delete messages you typed yourself.

### 2. Install ffmpeg (for MOV → MP4 conversion)
- Windows: [download ffmpeg](https://ffmpeg.org/download.html) and add it to your PATH
- Or via winget: `winget install ffmpeg`

If ffmpeg isn't installed, MOV conversion is skipped automatically (everything else still works).

### 3. Configure
Open `config/settings.py` and check:
- `DOWNLOADS_FOLDER`, `PICTURES_FOLDER`, `VIDEOS_FOLDER` — defaults to your OS user folders, change if yours differ
- `DRY_RUN = True` — **keep this on for your first run**
- `RENAME_DATE_FORMAT = "%d%m%Y"` — produces `DDMMYYYY` (e.g. `15082026` for 15 Aug 2026). Change to `"%Y%m%d"` for `YYYYMMDD` instead, if you ever prefer that.
- `DOWNLOADS_EXCLUDED_FOLDERS = ["Projects"]` — add any other folder names inside Downloads you want left completely alone (e.g. the folder this project itself lives in)
- `SUBSORT_BY_EXTENSION_CATEGORIES = ["Documents"]` — categories that get further split by extension (`Documents/docx/`, `Documents/xlsx/`, etc.). Add more category names here, or set to `[]` to disable.

### 4. Do a dry run first
```bash
python main.py
```
With `DRY_RUN = True`, it logs everything it *would* do (in the console and `logs/activity.log`) without touching any files. On every launch, the startup scan shows results in pages of 20 — press **Enter** to see the next page, or **q** to stop paging (the full list is always in `logs/activity.log` either way). After the initial scan, it switches to live mode and prints new events as they happen.

### 5. Go live
Once you're happy with the dry-run log, open `config/settings.py` and set:
```python
DRY_RUN = False
```
Run `python main.py` again — it will now actually sort, rename, convert, and flag duplicates.

## Running with Docker

The app is fully containerized. This is the easiest way to run it without managing a local Python environment, and it's what the CI/CD pipeline builds and publishes automatically on every push.

### 1. Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and **running** (check the whale icon in your system tray shows "Engine running")

### 2. Configure your folder paths
Docker needs your real Windows folder paths mounted into the container. Copy the example env file:
```powershell
copy .env.example .env
```
Edit `.env` and replace `YourUsername` with your actual Windows username (find it with `echo $env:USERNAME` in PowerShell):
```dotenv
DOWNLOADS_PATH=C:/Users/YourUsername/Downloads
PICTURES_PATH=C:/Users/YourUsername/Pictures
VIDEOS_PATH=C:/Users/YourUsername/Videos
```
> Why not `${HOME}`? On native Windows PowerShell/cmd, `$HOME` doesn't reliably resolve the way it does on Linux/Mac — explicit paths in `.env` avoid that entirely. `.env` is git-ignored, so your real paths never get committed.

### 3. Build and run
```powershell
docker compose up --build
```
This builds the image from the `Dockerfile`, mounts your Downloads/Pictures/Videos folders (read-write) plus `./config` and `./logs`, and starts `main.py` inside the container. Logs land in `./logs/activity.log` on your host machine exactly as they would running locally.

Stop it with `Ctrl+C`, or run it detached:
```powershell
docker compose up --build -d
docker compose logs -f          # tail the logs
docker compose down             # stop and remove the container
```

### 4. How the container maps paths
Inside the container, the app's `HOME` is explicitly set to `/home/user` (not the container's default `/root`), and your host folders are mounted to `/home/user/Downloads`, `/home/user/Pictures`, `/home/user/Videos` — matching what `config/settings.py`'s `Path.home()` resolves to. If you ever edit the Dockerfile's `ENV HOME=...` line, update the matching mount targets in `docker-compose.yml` too, or the app will silently look in the wrong place.

### 5. Pre-built images
Every push to `main` publishes a fresh image to both:
- Docker Hub: `sofdev1/organise-pc:main`
- GitHub Container Registry: `ghcr.io/sofdev1/organise-pc:main`

To run the published image directly without building locally:
```powershell
docker pull sofdev1/organise-pc:main
docker run -d --name organise-pc `
  -v "C:\Users\YourUsername\Downloads:/home/user/Downloads" `
  -v "C:\Users\YourUsername\Pictures:/home/user/Pictures" `
  -v "C:\Users\YourUsername\Videos:/home/user/Videos" `
  sofdev1/organise-pc:main
```

## GitHub Actions / CI-CD Workflows

Three workflows live in `.github/workflows/` and run automatically on GitHub:

### `python-lint.yml` — code quality checks
**Triggers:** every push and pull request to `main`.
**What it does:** runs `black --check .` (formatting), `isort --check-only .` (import order), and `flake8` (syntax/style) against the source. It fails the build if any file isn't already formatted/sorted correctly — it does **not** auto-fix anything, just reports.

To fix locally before pushing:
```powershell
pip install black isort
black .
isort .
git add .
git commit -m "Apply formatting"
```

Note: `isort` is configured via `pyproject.toml` (`profile = "black"`) so its import ordering matches Black's formatting style instead of conflicting with it. If you ever recreate `pyproject.toml` on Windows, see the BOM troubleshooting note below — writing it with `Out-File -Encoding utf8` breaks isort's ability to read it.

### `docker-build.yml` — build and publish the Docker image
**Triggers:** every push to `main`, every version tag (`v*`), and pull requests to `main` (build-only, no push, on PRs).
**What it does:**
1. Checks out the repo
2. Logs into Docker Hub and GitHub Container Registry (skipped on PRs)
3. Lowercases the repository name (Docker registries reject uppercase — `Organise-PC` becomes `organise-pc`)
4. Builds tags/labels from the commit metadata
5. Builds and pushes the image to both registries, with layer caching to speed up future builds

**Required secrets** (repo → Settings → Secrets and variables → Actions):
| Secret name | Value |
|---|---|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | A Docker Hub access token with **Read & Write** permission (Account Settings → Security → Personal access tokens on Docker Hub — never use your account password) |

`GITHUB_TOKEN` (for GHCR) is provided automatically by GitHub Actions — no setup needed.

### `release.yml` — tagged releases
**Triggers:** pushing a git tag matching `v*` (e.g. `v1.0.0`).
**What it does:** creates a GitHub Release for the tag, builds a Python distribution (`python -m build`), and uploads it as a release artifact.

To cut a release:
```powershell
git tag v1.0.0
git push origin v1.0.0
```

## Auto-start on login (Windows)

1. Run `scripts/install_startup.bat` (double-click it, or run from a terminal)
2. It adds a shortcut to your Startup folder that launches the suite silently (no console window) using `pythonw.exe`
3. Restart your PC (or log out/in) to confirm it's running — check `logs/activity.log` for a new "Suite starting" entry

To stop it from auto-starting, run `scripts/uninstall_startup.bat`.

> Note: the paginated console prompts only work in an interactive terminal. When auto-started silently via `pythonw.exe` (no console window), pagination has nowhere to prompt, so the startup scan just runs straight through without stopping — the full record is still in `logs/activity.log`.

> macOS/Linux: use `cron` (`@reboot python3 /path/to/main.py`) or a `launchd`/`systemd` service instead — the Python code itself is cross-platform, only the auto-start scripts here are Windows-specific.

## Stopping the suite

- If running in a visible terminal: `Ctrl+C`
- If running silently via Startup: open Task Manager, end the `pythonw.exe` process
- If running via Docker: `docker compose down`

## Undoing a rename — `cleanup_rename.py`

A separate, standalone script for reversing the `_ext_date` suffix the renamer adds — e.g. `LBP6300dn_R150_V110_W64_uk_EN_1_exe_15082026.exe` → `LBP6300dn_R150_V110_W64_uk_EN_1.exe`.

```bash
python cleanup_rename.py
```

- `DRY_RUN = True` by default — review the paginated preview first
- **Scoped by default** to legacy Windows driver-cache files only: extensions ending in `_` (`.dl_`, `.ex_`, `.ch_`, `.bi_`, `.da_`, `.ic_`, `.pr_`, `.in_`, `.up_`, `.xp_`, `.AV_`, etc. — trailing underscore is stripped too, e.g. `.dl_` → `.dl`) plus `.dll`, `.inf`, `.cat`, `.ini` (kept as-is, just the suffix removed)
- Normal files (`.docx`, `.pptx`, `.csv`, images, etc.) are **not** touched by default — edit `TARGET_EXTENSIONS` / `EXTRA_EXTENSIONS` near the top of the script to widen or narrow scope
- Self-contained — only depends on `config/settings.py`, so it can be dropped into the project root on its own without needing the rest of `utils/`
- Respects `DOWNLOADS_EXCLUDED_FOLDERS` the same way `main.py` does
- Also fixes the "double-rename" edge case where a file that collided with an existing name (`..._1`) would otherwise keep growing a new suffix every run

This script is separate from `main.py` on purpose — it never runs automatically, only when you launch it yourself.

## Project structure
```
pc-automation-suite/
├── main.py                    # Entry point — starts the live watcher, holds the single-instance lock (port 54891)
├── cleanup_rename.py          # Standalone: undo the _ext_date rename suffix
├── config/
│   └── settings.py            # All paths & feature toggles live here
├── core/
│   ├── watcher.py             # Watchdog observers + paginated startup report
│   ├── pipeline.py            # Chains sort -> convert -> screenshot -> dedupe -> rename; per-folder duplicate scoping
│   └── maintenance.py         # Scheduled disk/temp/large-file checks
├── utils/
│   ├── sorter.py              # Downloads sort, extension subsort, folder exclusion
│   ├── renamer.py             # Name_ext_date renaming, collision-safe
│   ├── duplicates.py          # SHA-256 content-hash duplicate detection
│   ├── screenshots.py
│   ├── converter.py
│   ├── content_extractor.py   # Pulls text content from files for AI naming
│   ├── ai_namer.py            # Calls Gemini to suggest a filename from content
│   ├── ai_rename_registry.py  # Tracks in-flight AI rename suggestions
│   ├── approval_ui.py         # Windows Yes/No dialog for approving suggestions
│   ├── telegram_bot.py        # Telegram-based approval (alternative to the dialog)
│   ├── paginate.py            # 20-at-a-time console pagination
│   └── logger.py
├── scripts/
│   ├── install_startup.bat    # Adds auto-start shortcut
│   ├── uninstall_startup.bat  # Removes it
│   └── run_silent.vbs         # Launches main.py with no console window
├── tests/
│   └── test_ai_rename_auto_approve.py
├── .github/
│   └── workflows/
│       ├── python-lint.yml    # black + isort + flake8 checks
│       ├── docker-build.yml   # Builds & publishes to Docker Hub + GHCR
│       └── release.yml        # Tagged GitHub Releases
├── Dockerfile                  # Container image definition
├── docker-compose.yml          # Local Docker run configuration
├── .env.example                # Template for your real folder paths (copy to .env)
├── pyproject.toml              # isort config (`profile = "black"`) — must be saved as UTF-8 without BOM
└── logs/
    ├── activity.log           # Every action taken (or would-take, in dry run) — complete, unpaginated
    └── maintenance_report.txt # Latest large-file report
```

## Troubleshooting

### Local / general

**Check if it's actually running, at all, first.** This answers most "why isn't it working" questions immediately:
```powershell
Get-NetTCPConnection -LocalPort 54891 -ErrorAction SilentlyContinue | Select-Object OwningProcess
```
The suite binds local port `54891` purely as a single-instance lock — nothing is sent over it. If this returns nothing, the suite is **not running**, full stop. Start it (`python main.py` or `wscript.exe .\scripts\run_silent.vbs`) before troubleshooting anything else.

**A file I just created/downloaded didn't move.** Check, in order:
1. Is it running at all? (see above)
2. Is `DRY_RUN` actually `False`? `Select-String -Path .\config\settings.py -Pattern "DRY_RUN ="` — if `True`, it only *logs* what it would do, nothing actually moves.
3. Did you check too soon after launch? On startup, the suite runs a full sweep of your existing files *before* it starts live-watching for new ones — on a large Downloads folder this can take a while. Live watching has only begun once `logs\activity.log` shows a line like `Suite is running. Press Ctrl+C to stop`. A file created during the sweep itself may be missed by that particular run, but will be picked up by the *next* sweep (i.e. next launch) or the next matching live event.
4. Check the tail of the log for the file's name directly: `Select-String -Path .\logs\activity.log -Pattern "your_file_name"`

**Task Manager shows multiple `pythonw.exe` processes.** This is expected and not a bug — Windows can show 2-3 process entries for one logical launch (a launcher stub plus the real interpreter). Only one of them is ever actually doing work, guaranteed by the single-instance lock above. To find which PID is the real one:
```powershell
Get-NetTCPConnection -LocalPort 54891 | Select-Object OwningProcess
```

**A file landed in `Duplicates/` and I don't think it should have.** Duplicate detection compares file *content* (SHA-256), not filename, and only within the same destination folder. If you see something like:
```
Moved duplicate: Worksheet_X_docx_17082026.docx (same content as Worksheet_X.docx)
```
that means two byte-identical copies of the same file genuinely existed in that folder (often from cloud sync — OneDrive/Google Drive re-depositing a file that was already organized in an earlier run). Nothing is deleted — the "duplicate" copy is just relocated into `Duplicates/` inside that same folder. Safe to manually delete once you've confirmed it's redundant.

**The suite auto-started on login but I checked too fast and it looked like it hadn't.** Windows can genuinely take 30-60+ seconds to get to Startup-folder items after login, especially with other startup programs competing. Wait a bit longer before checking, rather than assuming it failed.

**Running silently (via Startup) but nothing seems to be happening, and there's no error visible.** `pythonw.exe` has no console window, so if `main.py` fails to start (e.g. a second instance blocked by the lock, or a genuine crash), you'll never see it. Run it directly to surface any error immediately:
```powershell
python main.py
```
If it prints `Organise_PC is already running (another instance holds the lock)`, that confirms a real instance is already active elsewhere — check the port command above to find it.

**One specific file keeps failing to rename/move (`FAILED to rename... continuing` in the log).** That file is locked by another program (antivirus scanning, the file being open elsewhere, driver install in progress, etc.). The suite logs it and skips it rather than crashing — it'll be retried on the next sweep/event once the lock clears.

**`ModuleNotFoundError` or dependency errors after `pip install -r requirements.txt`**
Make sure you're in a fresh virtual environment (`python -m venv venv`, then activate it) before installing — installing into a stale or wrong Python environment is the most common cause.

### Telegram

**Bot doesn't send any suggestions, even though it's configured and running**
Did you send `/start` to the bot's chat? It's required — the bot stays completely silent until the configured chat has sent `/start` at least once, even if `TELEGRAM_ENABLED`/token/chat ID are all correctly set. Check `/status` to confirm.

**Suggestions still not arriving after `/start`**
Check the log for a startup line confirming the bot actually launched: `Select-String -Path .\logs\activity.log -Pattern "Telegram"`. If you instead see a line about `python-telegram-bot` not being installed, or `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` not being set, the suite has already silently fallen back to the Windows dialog for every file — fix the missing piece and restart.

**`/clearall` didn't delete something I expected**
It can only delete messages the bot itself sent — not messages you typed, and not anything older than Telegram's ~48-hour deletion window. Anything it does delete is removed from its internal tracking too, so a second `/clearall` right after should report 0.

**A suggestion's Approve/Skip buttons don't do anything when tapped**
Most likely the suite was restarted (or crashed) after the suggestion was sent — pending suggestions only live in memory for that run, so a restart clears them. The buttons will just report "already expired" if you tap them afterward; the file simply keeps its original name.

### Docker

**App doesn't seem to find any files to organize**
Check `.env` has your real Windows username, not the `YourUsername` placeholder — `docker compose up --build` silently mounts an empty/nonexistent path otherwise.

### GitHub Actions / CI

**`docker/login-action` fails with "Username and password required"**
The `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` secrets aren't set (or are misspelled) in the repo's Settings → Secrets and variables → Actions. Secret names are case-sensitive and must match exactly what the workflow file references.

**`repository name ... must be lowercase`**
Docker registries reject uppercase repo names. `docker-build.yml` already handles this by lowercasing `github.repository` into `env.REPO_LC` before using it in any image/cache reference — if you add new steps that reference the registry path, use `${{ env.REPO_LC }}`, not `${{ github.repository }}` directly.

**Push blocked: "Push cannot contain secrets"**
GitHub's push protection caught a literal token/credential in a committed file. Never hardcode tokens in workflow YAML — always reference them via `${{ secrets.SECRET_NAME }}`. If this happens, revoke the exposed credential immediately (even if the push was blocked) and fix the file before retrying.

**`black --check .` / `isort --check-only .` fail in CI**
These only check, they don't fix. Run `black .` and `isort .` locally, review the diff, then commit.

**`isort` warns `Failed to pull configuration information from ...pyproject.toml`, or errors with `Invalid statement (at line 1, column 1)`**
This means `pyproject.toml` has a UTF-8 **BOM** (byte-order mark) at the start of the file — a common side effect of creating it with PowerShell's `Out-File -Encoding utf8`, which adds a BOM by default. TOML parsers can't read past the BOM, so isort silently fails to pick up `profile = "black"` and falls back to its default import style, which then disagrees with Black's formatting (e.g. isort's multi-import-per-line vs Black's one-per-line-with-trailing-comma).

Rewrite the file without a BOM:
```powershell
# PowerShell 7+ (pwsh)
@"
[tool.isort]
profile = "black"
"@ | Out-File -Encoding utf8NoBOM pyproject.toml

# Windows PowerShell 5.1 (no utf8NoBOM option) — fine since content is plain ASCII
@"
[tool.isort]
profile = "black"
"@ | Out-File -Encoding ascii pyproject.toml
```
Verify with `Format-Hex pyproject.toml` (older PowerShell versions don't support the `-Count` parameter, so just run it without arguments on this small file) — the file should start with `5B 74 6F 6F ...` (`[too...`), not `EF BB BF`. Then redo the formatting so isort actually applies the `black` profile:
```powershell
git checkout core/pipeline.py
python -m isort core/pipeline.py
black core/pipeline.py
git diff core/pipeline.py
```

## Notes
- Duplicate detection compares file **content**, not filename — a renamed copy of the same file is still caught, but only within the same destination folder (see Troubleshooting above). Files already sitting inside a `Duplicates/` folder are never re-compared against each other, so a nested `Duplicates/Duplicates/` folder can't form.
- Format conversion keeps originals by default. Set `DELETE_ORIGINAL_AFTER_CONVERT = True` in settings once you trust it.
- Unrecognized file types in Downloads are left exactly where they are — nothing is dumped into a catch-all folder.
- Folders inside Downloads listed in `DOWNLOADS_EXCLUDED_FOLDERS` are pruned from the scan entirely (not just skipped file-by-file) — the suite never descends into them, so it's safe to keep the project itself inside Downloads.
- If a file can't be renamed/moved/hashed (locked by another program, permission denied, etc.), it's logged as a failure in `logs/activity.log` and skipped — it no longer stops the rest of the run.
- Only one instance of the suite can run at a time (enforced via a local port lock, `54891` by default). A second launch — whether manual or from a duplicate Startup entry — exits immediately rather than running alongside the first.
- AI rename suggestions never bypass approval unless `AI_RENAME_AUTO_APPROVE = True` — rejecting, ignoring, or any failure along the way (extraction, API, timeout) always falls back to the standard `Name_ext_date` convention, never leaves a file unrenamed or in a broken state.
- The Telegram bot only ever acts on the single configured `TELEGRAM_CHAT_ID` — messages from any other chat are ignored outright, even if someone finds the bot by its username.