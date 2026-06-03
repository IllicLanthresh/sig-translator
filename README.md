# sig-translator

A lightweight, always-on overlay for **Star Citizen** mining & salvage. It reads the
scanner **signature number** off your screen and instantly tells you **what material**
it is and **how many nodes** are in the cluster.

> Example: your scanner shows `6,770` → the overlay shows **Riccite ×2**.

No install, no dependencies, nothing to keep updated — download one `.exe` and run it.

---

## Download

1. Go to the **[latest release](../../releases/latest)** and download
   `sig-translator-vX.Y.Z.exe`.
2. Run it. The first time, Windows SmartScreen may say *"Windows protected your PC /
   unknown publisher."* That's only because the app isn't code-signed (it costs money
   to sign a hobby tool). Click **More info → Run anyway**. See
   [Is this safe?](#is-this-safe-eac--bans) below.

## Setup (once)

1. Run the exe — a small **control panel** opens.
2. Click **Calibrate box…**. A selection box appears over your screen:
   - **Drag inside** it to move, **drag the handles** to resize, **arrow keys** to nudge.
   - Put it over the spot where the **signature number** shows on your mining/salvage HUD.
   - **Save** (button, double-click, or Enter).
3. That's it. Calibration is saved — you only redo it if your HUD/resolution changes.

> Multi-monitor is supported — calibrate on whichever screen the game is on.

## Using it

- Scan a rock or wreck. A label appears just below the number showing the **material**
  (colored by rarity) and a `sig 6,770` line echoing the number it read, so you can
  double-check at a glance.
- Turn the overlay **on/off** with the big button in the panel or the global hotkey
  (**Ctrl+Alt+S** by default).
- When there's no signature on screen, the overlay shows nothing.

## Settings (in the control panel)

| Setting | What it does |
|---|---|
| **Capture on/off** | Big button + global hotkey (editable). |
| **Scan FPS** | How often it reads the screen. |
| **Accent color** | Color picker for the readout tint — match your ship manufacturer's HUD color. |
| **Label size** | Overlay text size. |
| **Accurate OCR (slower)** | Turn on only if a number gets misread. |
| **Show all matches for shared signatures** | ROC / FPS / Salvage deposits share some signature values (e.g. `6,000` could be **FPS ×2** *or* **Salvage ×3**). With this on, all valid readings are shown so you can decide. |

All settings are saved to `config.json` next to the exe.

## Is this safe? (EAC / bans)

**Yes.** The app never touches, reads, or injects into the game. It only takes a
read-only screenshot of a small region of your **desktop** — the same thing OBS and
screenshot tools do — and draws a separate transparent window on top. It does not read
or modify game memory, so it doesn't interact with EasyAntiCheat.

## Troubleshooting

- **Wrong number, or no label appears:** re-calibrate so the box hugs *just* the number,
  and try turning on **Accurate OCR**. The `sig …` echo line tells you what it read.
- **Label in the wrong place:** it sits just below your calibrated box — move the box.
- **Two/three materials shown:** that signature is genuinely shared between deposit types
  (ROC/FPS/Salvage). Toggle **Show all matches** off to see only the most likely one.

## How it works (short version)

Every deposit type has a fixed radar signature, and the scanner shows
`signature × node count`. The app divides the number you scanned by the known base
values to recover the material and the node count. Those values are baked into the app,
so it works offline and never needs updating.
