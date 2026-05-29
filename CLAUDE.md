# Project Notes

## ⚠️ PYTHON 3.9 COMPATIBILITY — MANDATORY ⚠️

**KiCad bundles Python 3.9.** All code in `src/kicad_jlcimport/` MUST be compatible with Python 3.9. This is non-negotiable — violations silently break the plugin inside KiCad with no error shown to the user.

**DO NOT USE:**
- `str | None`, `int | str` (PEP 604 union syntax — requires 3.10) → use `Optional[str]`, `Union[int, str]`
- `match`/`case` (structural pattern matching — requires 3.10)
- `type X = ...` (type aliases — requires 3.12)
- `ExceptionGroup`, `except*` (requires 3.11)
- `tomllib` (requires 3.11) → use `tomli` backport
- `asyncio.TaskGroup` (requires 3.11)

**ALWAYS USE:** `from typing import Optional, Union, List, Dict` instead of built-in generics (`list[str]`, `dict[str, int]` — requires 3.9+ but `Optional`/`Union` require `typing`).

**CI enforces this.** The test matrix runs the full suite on Python 3.9. Any 3.10+ syntax in `src/` will fail the CI build. Do NOT try to work around this with local compatibility shims or skip markers — just write 3.9-compatible code.

Tests and tools (`tests/`, `tools/`) may use newer syntax since they run in the dev venv, not inside KiCad.

## DEVELOPMENT ENVIRONMENT

All work must be done inside the project's virtual environment. Activate it before running any commands:

```bash
source install.sh
```

This creates the venv and installs dependencies on first run, or just activates the existing venv.

## BEFORE COMMITTING - MANDATORY BUILD CHECKS

**NEVER COMMIT WITHOUT RUNNING ALL THREE CHECKS:**

```bash
# Run from project root directory (venv must be active)
ruff check .
ruff format --check .
pytest tests/ -q --cov=kicad_jlcimport --cov-fail-under=80
```

ALL THREE must pass with zero errors before any commit or push.

## NO TODO COMMENTS

Never add `TODO`, `FIXME`, or `XXX` comments to source files. If something needs fixing, fix it now or surface it in the PR description / conversation. Don't leave rot in the codebase.

## GIT WORKFLOW

**NEVER push directly to main.** Always create a feature branch and open a PR. Do not push to or modify main without explicit user permission. Do not revert commits on main without explicit user permission.

## PROJECT STRUCTURE

This project uses the standard **src layout**. The package source lives in `src/kicad_jlcimport/`.

```
src/kicad_jlcimport/         # main package
├── easyeda/                  # EasyEDA data fetching, types, and parsing
├── kicad/                    # KiCad file generation and library management
├── gui/                      # wxPython GUI
├── tui/                      # Textual TUI
├── importer.py               # import orchestration
└── ...
tests/                        # test suite
tools/                        # developer utilities (not part of the package)
```

## TWO UIs

This project has two separate UIs: a wxPython dialog (`src/kicad_jlcimport/dialog.py`) and a Textual TUI (`src/kicad_jlcimport/tui/app.py`). When the user shows a screenshot or describes a UI issue, verify which UI it applies to before implementing changes. Native-looking widgets = wxPython dialog; terminal-rendered widgets = TUI.

## GIT STASH

NEVER run `git stash` without asking the user first. Stashing someone's in-progress work without permission is not acceptable — ask how they want to handle uncommitted changes.

## FIXING TEST FAILURES

**Understand the root cause before changing anything.** Don't jump to the first edit that makes tests pass.

- **Never modify production code just to make a test pass.** If a test fails, first determine whether the test or the production code is wrong. Read the production code's docstrings, comments, and recent commit history before deciding.
- **Treat merged/reviewed production code as intentional.** If code is deliberately designed a certain way (especially error handling, security boundaries, or API contracts), fix the tests to match the design — not the other way around.
- **Mock external dependencies.** When tests fail because they make real network, filesystem, or OS calls, mock the external dependency. Don't weaken production error handling to tolerate environment differences.

## RELEASING — `/release`

When the user says `/release` or asks to cut a release, follow these steps exactly.

### 1. Determine the new version

Ask the user for the version bump type (patch, minor, or major) if not specified. Parse the current version from `pyproject.toml` and compute the new version.

### 2. Run all checks

```bash
source install.sh
ruff check .
ruff format --check .
pytest tests/ -q --cov=kicad_jlcimport --cov-fail-under=80
```

All three must pass. Do not proceed if any fail.

### 3. Merge to main if on a feature branch

If currently on a feature branch:
1. Ensure all changes are committed and pushed.
2. Check if an open PR exists for this branch (`gh pr list --head <branch>`). If not, create one.
3. Merge the PR: `gh pr merge --squash --delete-branch`
4. Switch to main and pull: `git checkout main && git pull`

If already on main, just ensure it's up to date: `git pull`

### 4. Update version in these files

| File | Field |
|---|---|
| `pyproject.toml` | `version = "X.Y.Z"` |
| `metadata.json` | `"version": "X.Y.Z"` in the `versions[0]` object |

### 5. Add a changelog entry to README.md

Add a line to the **Recent Updates** section at the top of the list:

```
- `vX.Y.Z`: <short summary of changes since last release>
```

Build the summary from `git log` since the last tag.

### 6. Commit, push, and tag

```bash
git add pyproject.toml metadata.json README.md
git commit -m "Release vX.Y.Z"
git push
git tag vX.Y.Z
git push origin vX.Y.Z
```

### 6a. ⚠️ THIS REPO IS A FORK — GitHub Actions DOES NOT RUN. Publish the release manually.

`RedHawk989/kicad_jlcimport_imp` is a fork of `jvanderberg/kicad_jlcimport`. GitHub disables
Actions on forks until someone clicks "enable" once in the web Actions tab. The REST API still
reports `"enabled": true`, so **do not trust that** — confirm with the runs count:
`GET /repos/RedHawk989/kicad_jlcimport_imp/actions/runs` returns `total_count: 0` (no run has
ever executed here). The `v*` tag push therefore triggers **nothing**: it does NOT build binaries
and does NOT create the release. Every existing release (v1.9.x, v1.10.0, …) was published by hand
with the steps below, and you must do the same.

Also: **`gh` CLI is not installed** on this machine. Use the GitHub REST API with the token from
the stored git credential — it is a classic PAT with `repo` + `workflow` scope:

```bash
TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill 2>/dev/null | sed -n 's/^password=//p')
REPO="RedHawk989/kicad_jlcimport_imp"
```

This same token/API approach replaces the `gh pr ...` commands in step 3 (create PR via
`POST /repos/$REPO/pulls`, merge via `PUT /repos/$REPO/pulls/<n>/merge` with `{"merge_method":"squash"}`,
delete branch via `DELETE /repos/$REPO/git/refs/heads/<branch>`).

**Build the PCM artifacts locally** (pure Python, platform-independent — this is all KiCad needs;
the PyInstaller standalone binaries from the matrix can't be built on one OS and are not required
for the plugin update):

```bash
python tools/build_pcm.py --tag vX.Y.Z --github-repo "$REPO" --output-dir .
# produces: JLCImport-Imp-vX.Y.Z.zip, packages.json, repository.json, resources.zip
```

**Create the release and upload all four assets** (KiCad's PCM repo URL resolves
`releases/latest/download/repository.json`, so the latest release MUST carry these four files —
match exactly what prior releases attach):

```bash
# create release (draft:false, prerelease:false so it becomes "latest")
curl -s -X POST -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/$REPO/releases" \
  -d "$(jq -n --arg tag vX.Y.Z --arg body "$NOTES" '{tag_name:$tag,name:$tag,body:$body,draft:false,prerelease:false}')"
# upload each asset (.zip -> application/zip, .json -> application/json) to release id <REL_ID>:
curl -s -X POST -H "Authorization: token $TOKEN" -H "Content-Type: application/zip" \
  --data-binary @JLCImport-Imp-vX.Y.Z.zip \
  "https://uploads.github.com/repos/$REPO/releases/<REL_ID>/assets?name=JLCImport-Imp-vX.Y.Z.zip"
```

Then `rm` the four build artifacts from the working tree (they are not gitignored).

### 7. Verify

The tag push triggers no workflow, so verify the **release** directly, not a run:

```bash
curl -s "https://api.github.com/repos/$REPO/releases/latest" | jq '{tag_name, assets:[.assets[].name]}'
# must show vX.Y.Z with all 4 assets
curl -sL "https://github.com/$REPO/releases/latest/download/packages.json" | jq -r '.packages[0].versions[0].version'
# must print X.Y.Z — this is what KiCad's PCM reads
```
