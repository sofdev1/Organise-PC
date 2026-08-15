# Organise_PC

Automatically organizes, cleans, and maintains your **Downloads**, **Pictures**, and **Videos** folders — and only those three. Runs quietly in the background and reacts instantly when files are added.

## What it does

| Feature | Where | Behavior |
|---|---|---|
| Sort by file type | Downloads | Moves files into `PDFs/`, `Images/`, `Installers/`, `Zips/`, `Documents/`, `Videos/`, `Audio/` |
| Sort Documents further by extension | Downloads | `Documents/` is split into `Documents/docx/`, `Documents/xlsx/`, `Documents/pdf/`, etc. — configurable |
| Auto-rename | Downloads | Renames sorted files to `Name_ext_DDMMYYYY` (e.g. `invoice_pdf_15082026.pdf`) |
| Duplicate detection | Downloads, Pictures, Videos | Matches by file content (SHA-256), moves duplicates to a `Duplicates/` folder |
| Screenshot organizer | Pictures, Videos | Detects filenames containing "screenshot", sorts into `Screenshots/<image\|video>/YYYY-MM/`, renames to `Screenshot_image_DDMMYYYY` |
| Format conversion | Pictures, Videos | `HEIC → JPG`, `MOV → MP4` (originals kept by default) |
| System maintenance | Whole system (read-only outside scope) | Disk space check, OS temp file cleanup, large-file report — runs every few hours |
| Excluded folders | Downloads | Folders you list (e.g. `Projects`) are never scanned, sorted, or renamed — not even read |
| Paginated startup report | Console | Every launch shows what changed, 20 items at a time — press Enter for the next page, or `q` to stop |
| Crash-resilient file ops | All of the above | A single locked/permission-denied file is logged and skipped — it no longer halts the entire run |

**Scope guarantee:** every action is confined to `Downloads`, `Pictures`, and `Videos`. Temp cleanup only touches the OS temp directory. Nothing else on your PC is read, moved, renamed, or deleted. Folders listed in `DOWNLOADS_EXCLUDED_FOLDERS` are skipped entirely — the walk never even enters them.

## Setup

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

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
├── main.py                    # Entry point — starts the live watcher
├── cleanup_rename.py          # Standalone: undo the _ext_date rename suffix
├── config/
│   └── settings.py            # All paths & feature toggles live here
├── core/
│   ├── watcher.py             # Watchdog observers + paginated startup report
│   ├── pipeline.py            # Chains sort -> convert -> screenshot -> dedupe -> rename
│   └── maintenance.py         # Scheduled disk/temp/large-file checks
├── utils/
│   ├── sorter.py              # Downloads sort, extension subsort, folder exclusion
│   ├── renamer.py             # Name_ext_date renaming, collision-safe
│   ├── duplicates.py          # SHA-256 content-hash duplicate detection
│   ├── screenshots.py
│   ├── converter.py
│   ├── paginate.py            # 20-at-a-time console pagination
│   └── logger.py
├── scripts/
│   ├── install_startup.bat    # Adds auto-start shortcut
│   ├── uninstall_startup.bat  # Removes it
│   └── run_silent.vbs         # Launches main.py with no console window
└── logs/
    ├── activity.log           # Every action taken (or would-take, in dry run) — complete, unpaginated
    └── maintenance_report.txt # Latest large-file report
```

## Notes
- Duplicate detection compares file **content**, not filename — a renamed copy of the same file is still caught. Files already sitting inside a `Duplicates/` folder are never re-compared against each other, so a nested `Duplicates/Duplicates/` folder can't form.
- Format conversion keeps originals by default. Set `DELETE_ORIGINAL_AFTER_CONVERT = True` in settings once you trust it.
- Unrecognized file types in Downloads are left exactly where they are — nothing is dumped into a catch-all folder.
- Folders inside Downloads listed in `DOWNLOADS_EXCLUDED_FOLDERS` are pruned from the scan entirely (not just skipped file-by-file) — the suite never descends into them, so it's safe to keep the project itself inside Downloads.
- If a file can't be renamed/moved/hashed (locked by another program, permission denied, etc.), it's logged as a failure in `logs/activity.log` and skipped — it no longer stops the rest of the run.