# JLCImport-Imp

Fork of [`jvanderberg/kicad_jlcimport`](https://github.com/jvanderberg/kicad_jlcimport) that auto-integrates with the [`impossible-inc/imp-kicad-lib`](https://github.com/impossible-inc/imp-kicad-lib) shared component library.

All upstream `kicad_jlcimport` features (project/global library import, KiCad 8/9/10, CLI/GUI/TUI, footprint reuse, KiCad footprint browser, 3D models) are preserved. This fork adds a deep integration with the shared `imp-kicad-lib` so a team can build up a clean, deduped, normalized component library without manual curation.

## What this fork adds

### Shared-library integration
- **Auto-detect submodule.** When the active KiCad project has `imp-kicad-lib` checked out as a git submodule (or you set `imp_lib_path` in the config), every import is mirrored into the shared lib in addition to the project library.
- **Background auto-pull on dialog open.** A background thread runs `git fetch` + `git pull --ff-only` on the shared lib the moment the import dialog appears, so dedupe checks always see the latest state. Failure modes (no upstream, not a git repo, network down) are silent. Toggle with `imp_lib_auto_pull`.
- **Auto-categorize.** Parts are routed into the right `<Cat>__C.kicad_symdir` based on description and EasyEDA category: `Capacitor_SMD__C`, `Basic_Capacitors_Resistors__C`, `Extended_Capacitors_Resistors__C`, `Inductor__C`, `LED__C`, `Transistor_FET__C`, `Connector_USB__C`, `Switch__C`, plus `to-be-organized__C` as fallback.
- **Imp-lib-primary mode.** When the part is successfully contributed to the shared library, the parallel project `JLCImport` library files are cleaned up so you don't end up with two copies referenced from two lib-table entries.
- **Auto-commit + push.** New parts are staged, committed, and pushed to the `imp-kicad-lib` remote in one shot. Push failures keep the local commit so nothing is lost. Toggle with `imp_lib_auto_push`.
- **Remove from library button.** Pick a part in the dialog and click *Remove from imp-kicad-lib* to delete the symbol, footprint, and 3D model files; the removal is committed and pushed.

### Smart dedupe and similarity surfacing
- **Strict exact-match detection.** Before download, the plugin checks for an existing part by symbol name, by LCSC C-number (also looking inside the `(property "LCSC" …)` field of each `.kicad_sym` — important for connectors whose canonical name is the MPN, not the C-number), and by parsed spec.
- **"Part already in library!" dialog.** When an exact match is found, a dedicated info dialog pops up with two clear choices: `Cancel import` (default) or `Import Anyways (overwrite)`. The overwrite path bypasses dedupe and rewrites the existing files in-place.
- **Side-by-side similar-parts popup.** When no exact match exists but near matches do (same value within 1 %, configurable up to 3 candidates), a structured comparison popup shows each candidate next to the new part with `✓` / `✗` markers on every spec row.
- **Generalized spec parser.** Caps, resistors, inductors, LEDs, transistors, and connectors each get a kind-specific table — caps show Value/Voltage/Dielectric/Tolerance/Size; resistors show Value/Size/Tolerance/Power; LEDs show Color/Size; etc.
- **MPN-aware cap spec parsing.** When JLCPCB's description lacks specs, the plugin decodes the manufacturer part number (IEC 60062 three-digit value codes like `101` → 100 pF, voltage codes like `500` → 50 V, `6R3` → 6.3 V, tolerance letters `F`=±1 % / `J`=±5 % / etc., dielectric codes `X7R`/`C0G`/`X5R`) so dedupe still works on generic descriptions.
- **JLC Basic-tier highlighting in lib.** When importing an Extended part, any same-spec Basic-tier alternative already in `imp-kicad-lib` is ranked to the top of the popup with a `⚠ Basic alternative` badge.
- **Live JLCPCB Basic-tier query.** For Extended imports, the plugin also queries the JLCPCB search API filtered to `componentLibraryType=base`, parses each result's spec, and shows any same-spec Basic part (with LCSC code, name, price, stock) in a dedicated dialog with `Cancel — use Basic instead` / `Import Extended anyway` so you can switch before paying assembly fees.

### Library normalization on write
- **Reference designators.** `R`/`C`/`L`/`D`/`Q`/`SW`/`J` set automatically from detected kind.
- **Hidden Value on passives** with a correctly-placed `(hide yes)` flag that survives KiCad 10's nested `(at …)` / `(effects …)` blocks (an early version of this fix mangled freshly-imported symbols — fixed in v1.8.1).
- **Purple `_1_1` annotation.** A short value tag (`100nF/50V/X7R`, `6.8k`, `3.9uH`, `Green LED 0603`) is injected at color `163 59 255 1`, size 1.27, above the symbol body so the schematic stays readable when Value is hidden.
- **Footprint property prefix.** Set to `<Category>__C:<footprint name>` so KiCad resolves it through the `__C` lib-table entries instead of the project library.
- **3D model paths rewritten.** `(model …)` paths point at `../../packages3d/<Cat>__C.3dshapes/<part>.step` so the model resolves from the shared-lib root regardless of which project the footprint is used in.

![Search and details](images/search_results.png)

![Search and details](images/search_results.png)

## Install

1. Open KiCad and go to **Tools > Plugin and Content Manager**
2. Open repository settings and add:

   ```
   https://github.com/RedHawk989/kicad_jlcimport_imp/releases/latest/download/repository.json
   ```

3. Refresh repositories
4. Install **JLCImport-Imp**

Fallback: install from ZIP via [Releases](https://github.com/RedHawk989/kicad_jlcimport_imp/releases) (`JLCImport-Imp-vX.X.X.zip`, not "Source code" ZIP).

For local development, link `src/kicad_jlcimport` into your KiCad plugin directory and restart KiCad.

## Use In KiCad

Open `PCB Editor > Tools > External Plugins > JLCImport-Imp`.

1. Search for a part.
2. Pick Project or Global destination.
3. Set library name if needed.
4. Click Import.

If `imp-kicad-lib` is detected as a submodule of the project, the part is also reformatted and written into the shared library, with a commit + push attempt. The log panel reports the category chosen, any duplicate match, and the push result.

If `sym-lib-table` or `fp-lib-table` is created for the first time, reopen the project once.

## imp-kicad-lib configuration

Settings live in `jlcimport.json` in your KiCad config directory (`~/.config/kicad/` on Linux, `~/Library/Preferences/kicad/` on macOS).

| Key | Default | Purpose |
|---|---|---|
| `imp_lib_enabled` | `true` | Master switch for the imp-kicad-lib integration. Set to `false` to skip the contribution step entirely. |
| `imp_lib_path` | `""` | Absolute fallback path used when no `.gitmodules` entry pointing at `imp-kicad-lib` can be found by walking up from the project. |
| `imp_lib_dedupe` | `true` | Run the same-spec / same-LCSC / same-name check before contributing. When matched, the dialog now offers an *Import Anyways (overwrite)* option instead of silently skipping. |
| `imp_lib_auto_push` | `true` | After the local commit, attempt `git push`. Push failures are logged but never break the import — the local commit is kept. |
| `imp_lib_auto_pull` | `true` | Background `git fetch` + `git pull --ff-only` on the shared lib when the dialog opens, so the dedupe check sees the latest state. |

The lib is discovered by:

1. Walking up from the active KiCad project looking for a `.gitmodules` entry whose URL contains `imp-kicad-lib`.
2. If not found, falling back to `imp_lib_path` if set.
3. Otherwise, the integration does nothing — you still get the normal local project (or global) library import.

The import dialog has a **Share to imp-kicad-lib** checkbox (bound to `imp_lib_enabled`). Its inline hint shows the effective destination at a glance — whether a shared library was detected, or parts will be imported to the local library only. Uncheck it to force a purely local import without touching `jlcimport.json`.

## Companion: live JLCPCB lookups

For live Basic-vs-Extended verification, MPN→C-number resolution, and parametric search, see the [`dubnubdubnub/claude-jlc-tools`](https://github.com/dubnubdubnub/claude-jlc-tools) Claude Code plugin (`jlcpcb-catalog` skill). This plugin doesn't make the JLCPCB API call itself; if you care whether a part you're about to import is Basic or Extended, query that skill first.

## CLI, GUI, and TUI

The standalone tools work the same as upstream, and the imp-kicad-lib hook runs for all of them:

```bash
jlcimport-cli search "100nF 0402" -t basic
jlcimport-cli import C427602 -p /path/to/project   # also contributes to imp-kicad-lib if detected
jlcimport-gui -p /path/to/project
jlcimport-tui --kicad-version 9
```

Create or activate the local environment with:

```bash
source install.sh      # macOS/Linux
. .\install.ps1        # Windows PowerShell
```

## Naming convention reference

| Part type | `_1_1` annotation format | Examples |
|---|---|---|
| Ceramic cap | `<value>/<voltage>/<dielectric>` | `100nF/50V/X7R`, `10uF/25V/X5R` |
| Polymer / tantalum cap | `<value>/<voltage> Polymer` | `22uF/35V Polymer` |
| Resistor | `<value>` | `6.8k`, `10Ω`, `100mΩ 1/4W` |
| Inductor | `<value>` | `3.9uH` |
| Ferrite bead | `<impedance>@<freq>` | `120Ω@100MHz` |
| LED | `<Color> LED <size>` | `Green LED 0603` |
| FET | `<Family> <type> <Vds>` | `AO3401A P-FET 30V` |
| Switch | descriptor | `Tact 2.5x3.25mm` |

Text is rendered in purple (`color 163 59 255 1`) at size 1.27, placed above the symbol body. The library's CLAUDE.md has the full post-import cleanup checklist (pin types, descriptions, ref designators).

## Recent updates

- `v1.11.1`: prominent "reopen project" popup after the first import into a project — KiCad only loads a project's library tables at open, so a freshly created `JLCImport` library stays invisible in Place Symbol until the project is reopened. The plugin now says so explicitly instead of burying it in the log.
- `v1.11.0`: **Share to imp-kicad-lib** checkbox in the import dialog — toggle shared-library contribution on/off without editing `jlcimport.json`, with an inline hint showing whether a shared lib was detected or parts will import locally only.
- `v1.10.0`: live JLCPCB Basic-tier check before each Extended import — queries JLCPCB for same-spec Basic parts and surfaces them in a popup with `Cancel — use Basic instead` / `Import Extended anyway`.
- `v1.9.3`: match by LCSC C-number even when it only appears inside the `(property "LCSC" …)` field of the `.kicad_sym` (common for connectors whose canonical name is the manufacturer MPN).
- `v1.9.2`: dedicated *Part already in library!* dialog for exact matches, with `Cancel` (default) / `Import Anyways (overwrite)` choice.
- `v1.9.1`: fix duplicate / double `__C` entries in the similar-parts popup.
- `v1.9.0`: generalized side-by-side spec comparison popup (cap / resistor / inductor / LED / FET / connector kinds).
- `v1.8.7`: MPN-aware capacitor spec parsing — pulls value/voltage/dielectric/tolerance from IEC 60062 codes in the part name when the JLCPCB description lacks them.
- `v1.8.6`: auto-pull `imp-kicad-lib` in background when the dialog opens.
- `v1.8.5`–`v1.8.3`: tighter similar-parts popup, JLC Basic-vs-Extended alternative highlighting.
- `v1.8.2`: similar-parts pre-flight popup before import.
- `v1.8.1`: fix malformed `(hide yes)` placement when KiCad 10 `Value` properties contain nested parens.
- `v1.8.0`: imp-lib-primary mode (skip parallel project library), explicit dedupe logging, *Remove from library* button.
- `v1.7.x`: rename plugin to `JLCImport-Imp`, smarter dedupe, proper `<Cat>__C.kicad_symdir` layout.
- `v1.7.0`: imp-kicad-lib integration baseline — auto-detect submodule, categorize, dedupe, reformat, commit + push.
- `v1.6.7` (upstream): normalize tiny EasyEDA geometry residuals to common metric/imperial grids.
- `v1.4.0` (upstream): KiCad footprint browser with live preview, footprint/3D model renaming, library footprint reuse.

## Compatibility

KiCad 8, 9, and 10. No extra Python packages required inside KiCad.

For standalone tools:

- GUI needs `wxPython` (`pip install -e '.[gui]'`)
- TUI needs Python 3.10+ and `textual` dependencies (`pip install -e '.[tui]'`)

## Troubleshooting

- **`imp-kicad-lib: not_found`** — the plugin couldn't locate the shared library. Either set up `imp-kicad-lib` as a git submodule of your project (`git submodule add https://github.com/impossible-inc/imp-kicad-lib.git`) or set `imp_lib_path` in the config to an absolute path of a local checkout.
- **"Part already in library!" dialog** — strict dedupe matched an existing part. Either use the existing part (`Cancel import`), or pick `Import Anyways (overwrite)` to rewrite the lib copy with the new download. To disable the check entirely, set `imp_lib_dedupe: false` in the config.
- **`imp-kicad-lib: git push failed`** — the local commit was made but couldn't push. Confirm your credentials have write access to the lib's remote, then push manually from the submodule. Set `imp_lib_auto_push: false` to stop attempting.
- **Windows wxPython preview crash on KiCad 9** — `wx.svg._nanosvg` missing; see [fixes/README.md](fixes/README.md).

## Detailed documentation

- [Full usage guide](docs/usage.md)
- [3D model notes](docs/3d-models.md)
- [Architecture overview](docs/architecture.md)

## License

[MIT](LICENSE)
