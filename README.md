# JLCImport-Imp

Fork of [`jvanderberg/kicad_jlcimport`](https://github.com/jvanderberg/kicad_jlcimport) that auto-integrates with the [`impossible-inc/imp-kicad-lib`](https://github.com/impossible-inc/imp-kicad-lib) shared component library.

When this plugin imports a part and detects `imp-kicad-lib` as a git submodule of the active KiCad project (or via a configured fallback path), it:

1. **Auto-pulls** the latest `imp-kicad-lib` in the background when the import dialog opens, so dedupe checks run against current state.
2. **Categorizes** the part (`Capacitor_SMD__C`, `Basic_Capacitors_Resistors__C`, `Inductor__C`, `LED__C`, `Transistor_FET__C`, `Connector_USB__C`, `Switch__C`, or `to-be-organized`).
3. **Pre-flight similarity check** before download — opens a side-by-side comparison popup of any near matches (same value within 1 %, plus voltage/dielectric/tolerance/size differences flagged). JLC Basic alternatives to Extended parts are highlighted.
4. **Exact-match dialog** — when the part is identical (same name, same LCSC code via the `(property "LCSC" …)` field, or same parsed spec), shows a dedicated *"Part already in library!"* dialog with `Cancel` (default) or `Import Anyways (overwrite)`.
5. **Reformats** the symbol to match the library's conventions: correct Reference (`R`/`C`/`L`/`D`/`Q`/`SW`/`J`), hides Value on passives, injects a purple `_1_1` text annotation (`100nF/50V/X7R`, `6.8k`, `3.9uH`, `Green LED 0603`), prefixes the Footprint property with `<Category>__C:`.
6. **Writes** the files into the lib's per-symbol layout (`symbols/<Cat>__C.kicad_symdir/<part>.kicad_sym`, etc.) and rewrites the `.kicad_mod` `(model …)` paths to `../../packages3d/<Cat>__C.3dshapes/<part>.step`.
7. **Optionally `git add` + `commit` + `push`** to the imp-kicad-lib remote.

A **Remove from library** button in the dialog deletes a selected part's symbol/footprint/3D files from the shared lib and commits+pushes the removal.

All upstream JLCImport-Imp features (project/global library import, KiCad 8/9/10, CLI, GUI, TUI) are preserved.

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
3. Otherwise, the integration silently does nothing — you still get the normal project-library import.

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
