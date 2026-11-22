# Demo video and automated local captures on Windows

Consulted: 2026-11-22. Branch chore/phase-c-plan.

## Question
Which free, reliable Windows tool records the demo video with microphone (Snipping Tool video, Xbox Game Bar, OBS Studio)? How do I automate screenshots of local things (FastAPI Swagger UI, which is off in this repo; `python main.py eval` results; curl output) with Playwright (Python) or another tool, with minimal install and disk/RAM cost? Can a terminal GIF be generated automatically on Windows (asciinema, VHS, ttyrec)?

## Answer
- **Video**: Snipping Tool records video (Windows 10 and 11): `Win + Shift + R`, choose area, record, save as-is or edit in Clipchamp. The page does not mention microphone input or the file format: ⚠ not confirmed (check the recorder toolbar for a microphone toggle). Xbox Game Bar (`Win + G`) and OBS Studio are not covered by the 3 cited sources: ⚠ not confirmed here (from general knowledge, OBS is free and records mic and screen, but it was not verified; its install is heavier).
- **Screenshots of local things with Playwright (Python)**: `pip install playwright`, then `playwright install` downloads Chromium, Firefox and WebKit (about 650 MB combined, per Microsoft docs; per-browser size not stated: ⚠ not confirmed). Cheaper: `playwright install --only-shell` (Chromium headless shell only, intended to reduce download size) or skip downloads and use the installed Edge with `channel="msedge"` (no browser download). Cache folder: `%USERPROFILE%\AppData\Local\ms-playwright`; move it with `PLAYWRIGHT_BROWSERS_PATH` (useful because C: is tight and D: is slow; ⚠ speed impact not measured). RAM use of headless Chromium: ⚠ not confirmed.
- **Minimal script idea** (not run here, ⚠ not tested): launch with `channel="msedge"`, `page.goto("http://127.0.0.1:8000/health")` or an API endpoint, `page.screenshot(path="docs/screenshots/x.png")`. `/docs` is off in this repo, so Swagger UI is not capturable; options: capture raw JSON responses, or write a small local HTML page that renders the JSON/eval output and screenshot that file with `file://`. Custom headers (API key) via `browser.new_context(extra_http_headers={...})` (⚠ API usage from general knowledge, not in the cited page).
- **Terminal GIF**: VHS (Charm) generates GIF, MP4, WebM and PNG frames from a text "tape" file (`Output demo.gif`, `Type "..."`, `Enter`, `Sleep 5s`). Windows install: `winget install charmbracelet.vhs` or `scoop install vhs`, but it also needs `ttyd` and `ffmpeg` on PATH, so setup is heavier (extra disk) and Windows reliability is ⚠ not confirmed (the page only suggests Windows support via source files). asciinema and ttyrec: ⚠ not researched (limit of 3 sources); asciinema's recorder is generally POSIX-oriented, ⚠ not verified for native Windows.
- Simplest no-install-risk path: run commands in a terminal and use Snipping Tool video, or screenshots of the terminal with `Win + Shift + S`.

## Recommended decision
Use Snipping Tool (`Win + Shift + R`) for the demo video, with a 30-second test recording to confirm the microphone works; fall back to OBS only if it does not. For still images, use Playwright with `channel="msedge"` (no browser download) to screenshot JSON/API responses and an HTML rendering of the `python main.py eval` output, saved to `docs/screenshots/`. Skip terminal GIFs unless time allows; if wanted, try VHS in a throwaway install and delete it afterward (needs ttyd and ffmpeg).

## Sources
- Playwright Python: Browsers. https://playwright.dev/python/docs/browsers (consulted 2026-11-22)
- Use Snipping Tool to capture screenshots (video recording section), Microsoft Support. https://support.microsoft.com/en-us/windows/use-snipping-tool-to-capture-screenshots-00246869-1843-655f-f220-97299b865f6b (consulted 2026-11-22)
- charmbracelet/vhs (README). https://github.com/charmbracelet/vhs (consulted 2026-11-22)
