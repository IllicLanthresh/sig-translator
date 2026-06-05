# sig-translator

A small always-on overlay for **Star Citizen** mining and salvage. It reads the scanner
**signature number** off your screen and tells you **what material** it is and **how many
nodes** are in the cluster.

> Example: your scanner shows `6,770`, the overlay shows **Riccite ×2**.

No install and no dependencies. Download one `.exe` and run it.

![18,000 reads as FPS Mineable ×6 or Salvage ×9 (a shared signature), each colored by rarity](screenshots/image.png)

---

## Download

1. Go to the **[latest release](../../releases/latest)** and download
   `sig-translator-vX.Y.Z.exe`.
2. Run it. The first time, Windows SmartScreen may say *"Windows protected your PC /
   unknown publisher."* That just means the app isn't code-signed (signing a hobby tool
   costs money). Click **More info**, then **Run anyway**. See
   [What it does](#what-it-does-and-what-it-doesnt-do) below.

## Setup (once)

1. Run the exe. A small **control panel** opens.
2. Click **Calibrate box…**. A selection box appears over your screen:
   - **Drag inside** it to move, **drag the handles** to resize, **arrow keys** to nudge.
   - Put it over the spot where the **signature number** shows on your mining/salvage HUD.
   - **Save** (button, double-click, or Enter).
3. Calibration is saved. You only redo it if your HUD or resolution changes.

> Calibration is required on first launch. The app won't scan until the box is set.

> Multi-monitor works. Calibrate on whichever screen the game is on.

![The calibration box: drag inside to move, drag the handles to resize, then Save](screenshots/image5.png)

## Using it

- Scan a rock or wreck. A label appears just below the number. The recognized signature
  shows in brackets (e.g. `[ 6,770 ]`) on top, so you can check it matches the game, with
  the **material** (colored by rarity) underneath.
- Turn the overlay **on/off** with the big button in the panel, or the global hotkey
  (**Ctrl+Alt+S** by default).
- When there's no signature on screen, the overlay shows nothing.

The material name is colored by its rarity tier. It works the same in space or on a
planet surface:

<p>
  <img src="screenshots/image4.png" width="280" alt="Riccite ×1 (Epic)">
  <img src="screenshots/image2.png" width="280" alt="Torite ×4 (Uncommon)">
  <img src="screenshots/image7.png" width="280" alt="Iron ×5 (Common), on a planet surface">
</p>

## Settings (in the control panel)

| Setting | What it does |
|---|---|
| **Capture on/off** | Big button plus a global hotkey (editable). |
| **Scan FPS** | How often it reads the screen. |
| **Accent color** | Color picker for the readout tint, to match your ship manufacturer's HUD color. |
| **Label size** | Overlay text size. |
| **Show rarity** | Show or hide the rarity tier after the name, e.g. `Riccite ×2 (Epic)`. |
| **Customize sigs** | Slide-out panel to show or hide individual materials (grouped by tier, with show all / none). Hidden materials show only the bracketed signature when scanned, so you can focus on what you want to mine. |

Settings are saved to `%APPDATA%\sig-translator\config.json` (Windows).

On startup the app makes one optional check to GitHub for a newer release and shows a
clickable notice in the panel if there is one. It never downloads or installs anything,
and it fails silently when you're offline. Set `"check_updates": false` in `config.json`
to turn it off.

ROC, FPS and Salvage deposits share some signature values (for example `18,000` could be
**FPS ×6** or **Salvage ×9**). When a number is genuinely shared, the overlay shows every
valid reading so you can decide.

## What it does (and what it doesn't do)

sig-translator is a read-only reference overlay. It reads the signature number that's
already on your screen and looks up the matching material from a built-in table, the same
lookup you could do by hand from a community chart. It is built to stay entirely outside
the game:

- It does **not** modify, inject into, hook, or read the game or its memory, and it does
  **not** touch any game files.
- It does **not** automate or perform any gameplay action. You scan, fly and mine exactly
  as you would without it.
- It captures a small region of your **desktop** image (the way OBS or a screenshot tool
  does) and draws its label in a separate window. Nothing connects to or communicates
  with Star Citizen.
- It offers no mechanical advantage. It only saves a manual chart lookup of information
  that's already visible on your screen.

It's an unofficial, community-made tool, and **Cloud Imperium's rules are the final
word.** If CIG's position is that a tool like this isn't welcome, we'll follow their
guidance.

## Troubleshooting

- **Wrong number, or no label appears.** Re-calibrate so the box hugs just the number.
  The bracketed `[ … ]` readback tells you what it read.
- **Label in the wrong place.** It sits just below your calibrated box, so move the box.
- **Two or three materials shown.** That signature is genuinely shared between deposit
  types (ROC/FPS/Salvage), so the app shows every valid reading. Pick the one that matches
  what you're scanning.

## How it works (short version)

Every deposit type has a fixed radar signature, and the scanner shows
`signature × node count`. The app divides the number you scanned by the known base values
to recover the material and the node count. Those values are baked into the app, so it
works offline and never needs updating.
