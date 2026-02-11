# Repository Guidelines

## Project Structure & Module Organization
`app.py` hosts the Flask entry point and queues while `newznab.py` and `sabnzbd.py` provide XML helpers and queue persistence. Plugins are loaded from `CONFIG/plugins/search` and `CONFIG/plugins/download`, so treat the `config/` directory as both runtime configuration and workspace for plugin code. Docker assets (`docker-compose.yaml`, `dockerfile`, `entrypoint.sh`) live at the root alongside `requirements.txt`. Static screenshots used in the UI are kept in `images/`.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate`: create a local environment prior to installing dependencies.
- `pip install -r requirements.txt`: installs Flask, requests, and other runtime libraries.
- `CONFIG=$PWD/config FLASK_RUN_HOST=0.0.0.0 FLASK_RUN_PORT=10000 python app.py`: runs the service directly for iterative work; ensure the `CONFIG` path points to a writable directory with `config.json` and plugin folders.
- `docker build -t newznabarr:dev .` then `docker run -p 10000:10000 -v $PWD/config:/config -v $PWD/downloads:/data/downloads/downloadarr newznabarr:dev`: builds and exercises the container image.
- `docker-compose up --build newznabarr`: preferred for parity with production defaults.

## Coding Style & Naming Conventions
Follow standard PEP 8: four‑space indentation, snake_case for module-level functions, and CapWords for classes. Plugins should subclass `PluginSearchBase` or `PluginDownloadBase`; name them after their capability (`ReadarrSearch`, `LidarrDownload`) and expose concise `getprefix()` identifiers that match queue prefixes. Keep configuration keys lowercase with underscores (e.g., `sab_api`). Favor explicit logging over print statements when touching request handlers to simplify container diagnostics.

## Testing Guidelines
There is no dedicated test suite yet; new work should include targeted checks. Portable smoke testing can be done with `pytest` modules under `tests/` (create this folder if absent) and by invoking Flask endpoints via `curl "http://localhost:10000/api?t=caps"`. Aim to cover plugin-specific parsing and queue transitions; mark network-heavy tests with `pytest.mark.integration` to skip them in quick runs. Before opening a PR, exercise both direct `python app.py` runs and containerized runs to ensure plugin discovery succeeds with `CONFIG` mounted read/write.

## Commit & Pull Request Guidelines
Craft commits in the imperative mood (“Add Lidarr download plugin”) and keep them focused (code, tests, docs). When proposing changes, open a PR that includes: context on the feature or bug, reproduction or validation steps (commands above), screenshots of any UI changes (`/queue` page), and notes on plugin compatibility. Reference related issues (`Fixes #12`) to auto-close them and mention any configuration migrations so operators can adjust volumes or environment variables during deployment.
