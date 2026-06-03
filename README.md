# sig-translator

A minimal, always-on overlay for **Star Citizen** that reads the mining/salvage
**signature number** off your screen in real time and tells you *what material it
is* and *how many nodes are in the cluster*.

Example: a scanned signature of `3185` → **Stileron ×1**, `6370` → **Stileron ×2**,
`19125` → **Laranite ×5**.

> Status: **design / handoff stage.** No application code yet — this document
> captures the decisions made so far so development can continue on another
> machine (see [Handoff](#handoff--continuing-on-another-machine)).

---

## What it should do

- Continuously capture a small, fixed region of the screen where the in-game
  signature number always appears (top-center HUD position).
- OCR the digits in that region.
- Translate the number into **material name + node count** using the known
  radar-signature (RS) base values.
- Draw a tiny, unobtrusive label **right above or below** the in-game number so
  it's easy to read and doesn't get in the way.
- Show **nothing** when there's no signature on screen.
- Provide a **toggle** (global hotkey and/or a small control button) to turn the
  overlay on/off.
- Let the user configure the **scan FPS** (how often it samples the screen).

## How the translation works

Each mineable/salvageable material has a **base RS value** (its 1-node
signature). The reading scales linearly with node count:

```
node_count = round(scanned_signature / base_RS_value)
```

So given a scanned number, we find the material whose base value divides it most
cleanly, and `count = scanned / base`. The material's **rarity tier** caps the
max node count:

| Tier        | Max nodes |
|-------------|-----------|
| Legendary   | 2 |
| Epic        | 3 |
| Rare        | 4 |
| Uncommon    | 5 |
| Common      | 6 |
| ROC Mineables | 7 (base 4,000) |
| FPS Mineables | 10 (base 3,000) |
| Salvage     | 15 (base 2,000) |

A "confidence" score (how cleanly the number divides) helps disambiguate when
two materials have similar base values.

---

## Decisions made so far

| Topic | Decision | Notes |
|-------|----------|-------|
| **Language / stack** | **Python** | Fast to build screen-capture + OCR + a transparent always-on-top overlay; ships as a `.exe` via PyInstaller. |
| **EasyAntiCheat safety** | **Do NOT inject into or read the game process.** | Capture the **desktop** image (read-only, BitBlt / `mss`, the same technique screenshot/OBS tools use) and draw the overlay as a **separate top-most, click-through window**. The risky thing is *injecting* an overlay that hooks the game's DirectX — we explicitly avoid that. |
| **OCR engine** | **RapidOCR (ONNX)** | Pip-installable, bundles its own model → no separate install for the user. Good on small HUD digits. We'll restrict recognition to digits. |
| **Data source** | **OPEN — to be explored from `Data.p4k` on the Mac.** | See below. |

### The open question: where do the RS values come from?

The user wants the app to read RS values from the game's `Data.p4k` so it never
needs manual updates per patch.

**Research finding (to be verified):** every existing community tool — the
scmdb chart, the `RainbowRamen/sc-mining-hud` calculator, etc. — uses
**community-measured** RS values (the MrKraken per-patch chart), *not* values
extracted from `Data.p4k`. The in-game signature appears to be derived at runtime
from each rock's physical/radar cross-section, so it may not be stored as a clean
field in the p4k.

**However**, the values show a suspiciously systematic pattern (within each
rarity tier, the base steps by ~15 per material; tiers have distinct bases),
which *hints* the numbers may be derivable from entity data even though no tool
has bothered to extract them. **This is worth confirming directly against the
actual `Data.p4k`** before settling the data source — which is the main reason
development is moving to a machine that has the game files.

**Candidate data-source strategies (decide after exploring the p4k):**
1. **Extract from `Data.p4k`** (ideal if the values are actually in there) — zero
   manual updates, always patch-accurate. Use [`scdatatools`](https://pypi.org/project/scdatatools/)
   (Python) and/or [`unp4k`](https://github.com/dolkensp/unp4k) / `unforge` to
   convert the DataForge `game.dcb` and inspect mineable/ore entity records and
   any radar/signature parameters. Grep extracted records for ore names
   (`Quantainium`, `Stileron`, `Laranite`, …) and look for fields that match the
   known base values.
2. **Bundled JSON + auto-update URL** (reliable fallback) — ship the current
   chart as JSON so it works offline instantly; on launch fetch an updated JSON
   from a remote/maintained file. Patch updates = edit one JSON, no app rebuild.
3. **Bundled JSON only** — simplest; update the repo's JSON each patch.

**Recommended architecture regardless of outcome:** a pluggable `DataProvider`
interface so the p4k extractor and the JSON provider are interchangeable, with
the bundled JSON always present as a fallback/cache.

---

## Community documentation & data-extraction findings

Research into how the community sources these values turned up two camps and,
importantly, a concrete extraction path:

**1. User-facing tools mostly use community-measured values.**
The scmdb chart, `RainbowRamen/sc-mining-hud`, and the widely-shared **MrKraken**
per-patch chart all use values measured in-game and updated by hand each patch.
No public document gives a *formula* that derives RS from rock mass / cross
section — RS is treated as a **predefined per-resource property**, and the total
cluster reading is simply `base_RS × node_count` (confirmed across multiple
guides).

**2. But there are open-source game-data dumps where per-resource data lives.**
Several projects parse the actual game files into browsable JSON — meaning the
value may be **greppable without unpacking `Data.p4k` from scratch**:

| Project | What it is | Use |
|---|---|---|
| [`StarCitizenWiki/scunpacked-data`](https://github.com/StarCitizenWiki/scunpacked-data) | The **already-dumped** game data as JSON | Clone & grep directly — fastest way to check if RS is in the data, no p4k needed |
| [`octfx/ScDataDumper`](https://github.com/octfx/ScDataDumper) | Current/maintained .NET loader that dumps game files → JSON | Run against the local install to produce a fresh dump for the live patch |
| [`richardthombs/scunpacked`](https://github.com/richardthombs/scunpacked) | Original .NET data browser/API; parses extracted XML → JSON (`items/` folder per class) | Reference for entity/field structure |
| [`scdatatools`](https://pypi.org/project/scdatatools/) | Python-native p4k + DataForge tools | Python alternative; fits our stack |
| [`dolkensp/unp4k`](https://github.com/dolkensp/unp4k) + `unforge` | Raw extractor + CryXML/DataForge deserializer | Low-level fallback |

**Confirmed mechanic:** ship-mineable rocks / gem deposits carry a **Radar
Signature (RS)** value per resource type; the scanner shows `base_RS × nodes`.
What I could **not** confirm from the open web (GitHub code search and the SC
wiki are auth/bot-gated) is the **exact DataForge field name** and whether the
dumped value equals the chart value byte-for-byte or needs scaling. That's the
one thing to verify first on the Mac.

### Fastest way to settle the data-source question (do this first)
1. **Check the pre-dumped JSON, no p4k required:**
   `git clone https://github.com/StarCitizenWiki/scunpacked-data` and grep for ore
   names (`Quantainium`, `Stileron`, `Bexalite`, `Laranite`) and for likely field
   names (`radar`, `signature`, `RS`, `signal`). See if a value like Bexalite
   `3600` or Quantainium `3170` appears against a mineable entity.
2. **If found** → note the exact field/path; implement `data/p4k.py` to read the
   same field (either from the live `Data.p4k` via `scdatatools`, or by running
   `ScDataDumper` and reading its JSON). Validate every value against the table
   below.
3. **If the dumped value differs / isn't present** → the chart values really are
   measured, not stored; ship the bundled JSON (+ optional auto-update URL) and
   move on. Either way the `DataProvider` interface keeps both options open.

> Note: even the "extract from p4k" path is really "run a dumper, then read its
> output" — the same pipeline the community dumps use — so it's automatable per
> patch regardless.

---

## Reference: known RS base values (from the scmdb / MrKraken chart)

Seed data for a bundled JSON fallback and for validating any p4k extraction.
Base value = 1-node signature.

### Legendary (max ×2)
| Material | Base RS |
|---|---|
| Quantainium | 3,170 |
| Stileron | 3,185 |
| Savrilium | 3,200 |

### Epic (max ×3)
| Material | Base RS |
|---|---|
| Ouratite | 3,370 |
| Riccite | 3,385 |
| Lindinium | 3,400 |

### Rare (max ×4)
| Material | Base RS |
|---|---|
| Beryl | 3,540 |
| Taranite | 3,555 |
| Borase | 3,570 |
| Gold | 3,585 |
| Bexalite | 3,600 |

### Uncommon (max ×5)
| Material | Base RS |
|---|---|
| Laranite | 3,825 |
| Aslarite | 3,840 |
| Titanium | 3,855 |
| Tungsten | 3,870 |
| Agricium | 3,885 |
| Torite | 3,900 |

### Common (max ×6)
| Material | Base RS |
|---|---|
| Hephaestanite | 4,180 |
| Tin | 4,195 |
| Quartz | 4,210 |
| Corundum | 4,225 |
| Copper | 4,240 |
| Silicon | 4,255 |
| Iron | 4,270 |
| Aluminium | 4,285 |
| Ice | 4,300 |

### Special tiers
| Type | Base RS | Max nodes |
|---|---|---|
| ROC Mineables | 4,000 | 7 |
| FPS Mineables | 3,000 | 10 |
| Salvage | 2,000 | 15 |

> Values reflect the chart provided by the user (Star Citizen 4.x era). Treat as
> a starting point; verify against the live game / `Data.p4k`.

---

## Proposed architecture

```
sig-translator/
├── sigtranslator/
│   ├── capture.py      # grab the configured screen region (mss / BitBlt, read-only)
│   ├── ocr.py          # RapidOCR digit recognition
│   ├── translate.py    # signature -> (material, count, confidence)
│   ├── data/
│   │   ├── provider.py # DataProvider interface
│   │   ├── p4k.py      # extract RS values from Data.p4k (scdatatools)
│   │   ├── json_provider.py
│   │   └── signatures.json  # bundled seed/fallback (from the table above)
│   ├── overlay.py      # transparent, top-most, click-through label window
│   ├── config.py       # region, scan FPS, hotkey, on/off
│   └── app.py          # main loop: capture -> ocr -> translate -> overlay
├── pyproject.toml
└── README.md
```

Main loop runs at the configured FPS: capture region → OCR → if a number is
found, translate and position the overlay label at the fixed HUD spot; otherwise
hide the overlay.

---

## Handoff — continuing on another machine

This repo is being handed off to a local **macOS** Claude Code session where the
game's `Data.p4k` is available.

**Note on platform:** the *final app* targets **Windows** (Star Citizen is
Windows-only) — overlay, hotkeys, and screen capture should be implemented/tested
on Windows. The Mac is being used for **`Data.p4k` exploration** and general
development; do the overlay/capture integration testing on the Windows machine.

### Next steps
1. **Resolve the data-source question first.** Point Claude Code at the local
   `Data.p4k`. Use `scdatatools` (or `unp4k` + `unforge`) to dump DataForge
   records and search for the mineable ore entities. Check whether RS base values
   (or something they're computed from) are present and match the table above.
    - If **yes** → implement `data/p4k.py` as the primary `DataProvider`.
    - If **no** → fall back to the bundled JSON (+ optional auto-update URL).
2. Scaffold the Python project (`pyproject.toml`, package layout above).
3. Implement, in order: `data` layer → `translate.py` (pure logic, easy to unit
   test) → `capture.py` → `ocr.py` → `overlay.py` → `app.py`.
4. Add a settings UI/config for: overlay on/off, global hotkey, scan FPS, and the
   capture region (with a one-time "calibrate region" helper).
5. Package with PyInstaller for distribution.

### Branch
Work continues on `claude/focused-meitner-FCUK6` until told otherwise.
