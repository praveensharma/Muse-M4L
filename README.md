# Moog Muse Editor for Max for Live

This checkout includes **Tonight r2**, a local MIDI editor build for the Moog
Muse. It provides controls for 102 synth parameters and explicit preset recall
from an Ableton MIDI track.

1. Use Live 11 or 12 with Max for Live and connect the Muse over USB MIDI or a
   MIDI interface.
2. Run `python3 build_tonight.py` to generate
   `build/tonight-r2/MuseEditor Tonight r2.amxd`. Copy the AMXD to
   `User Library/Max4Live/Muse-M4L/` and load it on a MIDI track.
3. Select the Muse port and channel in **MIDI To**. Enable **Receive CC** on the
   Muse and turn **OUTPUT** on in the device. Move a filter control to test.
   Enable **THRU** when sending clips or external performance MIDI through the
   same track. For synth-knob feedback, leave **THRU** off.

The device starts with **OUTPUT** and **THRU** off. Preset recall happens
when you press **SEND**. Follow the [Tonight r2 guide](TONIGHT_GUIDE.md)
for routing, preset recall, two timbres, and hardware test status.

---

## Upstream device reference

A Max for Live **MIDI-effect** device that turns Ableton into a full editor for
the Moog Muse. All 102 CC-addressable parameters are exposed as
Ableton-automatable controls, plus Program Change for recalling the synth's own
stored presets. The tabs and controls follow the Muse's own **front-panel
layout** — tabs run in signal-flow order, sections are grouped the way they sit
on the hardware (OSC 1 over OSC 2, Filter 1 over Filter 2, ...), and the mixer
and envelopes are drawn as **faders** like the panel rather than knobs — so it
reads like the instrument. Both of the Muse's timbres can be controlled by
running an instance per Ableton track (see
[Controlling both timbres](#controlling-both-timbres-multi-mode)).

> **⚠️ Disclaimer:** This is an **unofficial** plugin and is **not supported or endorsed** by Ableton or Moog. Use at your own risk. For official support, contact Moog or Ableton directly.

| File | What it is |
|------|------------|
| **`MuseEditor.amxd`** | The device. Load this into Live. |
| `generate_device.py` | Generator that builds the device from the parameter map. Re-run to regenerate. |
| `MuseEditor.maxpat` | The same patcher as plain JSON, for inspecting/editing in Max. |
| `Muse_MIDI_CCs.csv` | Reference: the Muse's MIDI CC map. |
| `render_preview.py` / `layout_preview.svg` | Generates / holds a static mock-up of every tab's layout. |

## Requirements

- Ableton **Live 11 or 12** with **Max for Live** (Live Suite, or the Max for
  Live add-on) and Max 8.6+.
- A MIDI connection from your computer to the Muse (USB or a MIDI interface).
- **Moog Muse Firmware 1.4** (this plugin has only been tested with this version).

## Critical Muse setup

The Muse ignores incoming CC and Program Change **by default** — turn them on:

- **MENU → MIDI → RECEIVE CC: ON** (required for every control in this device)
- **MENU → MIDI → RECEIVE PGM CHNG: ON** (required for the Program Change
  feature)
- **MENU → MIDI → SEND CC: ON** (only needed for hardware → UI sync, below)

For **bi-timbral** control (both timbres at once), also set up Multi Mode — see
[Controlling both timbres](#controlling-both-timbres-multi-mode) below.

## Installing

1. Copy `MuseEditor.amxd` into your Live **User Library** under
   `Presets/MIDI Effects/Max MIDI Effect/`, or just drag the `.amxd` from
   Finder/Explorer onto a MIDI track.
2. Make a **MIDI track** and set its **MIDI To** output to the port (and
   channel) your Muse is on.
3. Drop **MuseEditor** onto that track's device chain.
4. Move a control — the Muse responds.

The device sends CCs on MIDI channel 1; Live's track **MIDI To** routing
determines the actual destination channel, so set the channel there to match
the Muse.

### Hardware → UI sync (bidirectional)

The device also listens for CCs coming *back* from the Muse: turn a knob on the
synth and the matching on-screen control follows (without re-transmitting, so
there's no feedback loop). For this to work the Muse's MIDI output has to reach
the device:

1. On the Muse, set **SEND CC: ON**.
2. On the same Live track, set **MIDI From** to the Muse's input port, and set
   the track's **Monitor to `In`** (this is the important one — with `Auto`,
   incoming MIDI only reaches the device when the track is armed).

If the controls don't follow the hardware, it's almost always the monitor
setting: switch it to **In** and confirm the track's MIDI From shows MIDI
activity (the small indicator by the track meter flickers when you turn a Muse
knob). Each control listens on its own CC number on any channel, so the channel
doesn't need to match.

If you don't need hardware → UI sync, you can ignore this — sending to the Muse
works without it.

## Using it

**Tabs** — click the strip at the top to switch between sections:

The tabs run in the Muse's panel order (left to right). Within each tab the
controls sit in **titled, bordered boxes** that mirror the panel's own sections
(e.g. the LFO tab has separate LFO 1, LFO 2 and Pitch LFO boxes; the OSC tab has
Oscillator 1 / Oscillator 2 / Sync-FM boxes), so the layout reads like the
hardware:

| Tab | Contents |
|-----|----------|
| OSC | OSC 1 (top) / OSC 2 (bottom): octave, freq, tri-saw & wave-mix faders, PW, sync, FM |
| MIX | Mixer faders — OSC 1, Ring Mod, OSC 2, Mod Osc, Noise — plus the Overload drive |
| FILTER | Filter 1 (top, with high-pass) / Filter 2 (bottom): cutoff/res/env, link, routing |
| ENV | Filter envelope + VCA (amp) envelope, as ADSR faders with loop/velocity |
| VCA | Timbre volume, pan, pan spread, low cut, mute |
| MOD | The modulation oscillator and all its pitch / PWM / filter / VCA routings |
| LFO | LFO 1 & 2 (top), the Pitch LFO and its destinations (bottom) |
| DELAY | Diffusion Delay: times, sync, feedback, character, mix, and timbre sends |
| ARP | Arpeggiator settings + arp/sequencer clock divisions and tempo |
| VOICE | Detune, unison/mono, glide, mod wheel, expression, hold, sustain, pitch bend |
| BANK | Program Change (recall the Muse's stored patches) |
| MISC | Panic and notes |

**Control types** — each control is drawn to echo the matching panel control:
rotary parameters are dials; the **mixer levels and the ADSR envelopes are
vertical faders**, and the oscillator **tri-saw / wave-mix blends are horizontal
faders**, just like the hardware (all of these are continuous 0–127). Dials and
faders have a short label printed directly above them (the box title supplies
the context); the objects' own built-in name text is turned off so nothing is
duplicated. **On/off parameters are labelled buttons** — the name sits inside
the button and it lights up in the accent colour when engaged (sends 0 / 127),
the way the panel's switches read — so there's no floating label above a bare
checkbox. Multi-option parameters (octave, waveform, KB tracking, filter order,
arp direction/range) are menus that send a value centred in the matching CC
band, so the Muse always lands on the chosen option. Sections are drawn as
subtly-lighter rounded panels with a hairline border and a thin accent rule
under each title, so the device reads like a piece of hardware rather than a
grid of identical knobs.

**Info View help** — hover any control and Ableton's **Info View** (bottom-left
of the window) shows what that control does on the Muse, taken from Moog's MIDI
docs, along with its CC number. The same text appears as a hover tooltip.

**Program Change (Bank tab)** — set **Bank** (1–16) and **Patch** (1–16), then
click **SEND** to recall that slot on the Muse (sends Bank Select MSB 0 + LSB +
Program Change). 16 banks × 16 patches = 256 slots.

**Misc tab** — **Panic** sends All Notes Off / All Sound Off to clear stuck
notes. (Pitch Bend is on the **Voice** tab — bidirectional, sending pitch-bend
to the synth and following the Muse's pitch wheel — along with Mod Wheel, Hold,
Expression and Sustain.)

## Controlling both timbres (Multi Mode)

The Muse is bi-timbral: in **Multi Mode** it routes incoming CC to Timbre A or
Timbre B purely by **MIDI channel** (the CC numbers are identical for both). You
don't need anything special in the device for this — Ableton's per-track **MIDI
To** channel does the work. Use **one device instance per timbre, on its own
track**:

1. On the Muse, set **MENU → MIDI → MULTI MODE: ON** (on by default), then set
   **MIDI IN CHANNEL** (Timbre A, e.g. Ch 1) and **MULTI IN B CHANNEL** (Timbre
   B, e.g. Ch 2) to **different** channels.
2. **Track A:** put a MuseEditor on it and set the track's **MIDI To** to your
   Muse port on **Ch 1** → this instance now controls **Timbre A**.
3. **Track B:** put a second MuseEditor on another track and set its **MIDI To**
   to the same Muse port on **Ch 2** → this instance controls **Timbre B**.

Live forces all of a track's MIDI onto the channel chosen in **MIDI To**, so the
device's internal channel doesn't matter — each track lands on its own timbre.
This is cleaner than an in-device A/B switch: each instance is a full,
independently-automatable on-screen patch, and bidirectional sync works per track
(set each track's **MIDI From** to the Muse and **Monitor** to `In`). Note that
Delay and Clock are global on the Muse, so they affect the whole instrument from
either track.

## Regenerating

The device is generated from the parameter map in `generate_device.py`. Edit
the map (or layout) and run:

```bash
python3 generate_device.py
```

No third-party packages required (standard library only). The `.amxd` binary
container (ampf / meta / ptch with the mx@c + dlst trailer) is written to the
format Ableton's maxdevtools produces.

## How it routes (under the hood)

```
OUT (UI → Muse):
live.dial / live.slider ───▶ prepend <cc> ─┐
live.toggle ─▶ [* 127] ─────▶ prepend <cc> ─┼─▶ midiformat ─▶ midiout ─▶ Muse
live.menu   ─▶ [expr …] ────▶ prepend <cc> ─┘      ▲   ▲
Program Change: Bank MSB/LSB ──────────────────────┘   │ (program-change inlet)
                Patch ─▶ [- 1] ────────────────────────┘

IN  (Muse → UI):  one [ctlin <cc>] per control
ctlin <cc> ─▶ [>=64 / expr] ─▶ prepend set ─▶ live.*
midiin ─▶ xbendin ─▶ [/ 128] ─▶ prepend set ─▶ live.dial (Pitch Bend, 0–127)
midiin ────────────────────────────────────────────▶ midiout   (note thru)
```

Each `ctlin <cc>` catches just its own controller number; `prepend set` updates
the control without making it re-output, so incoming CCs move the UI but never
echo back out. The device sends on MIDI channel 1; Live's per-track **MIDI To**
remaps that to whatever channel (and timbre) the track targets.

Tab switching uses `live.tab → thispatcher "script show/hide"`; each control
and label has a unique scripting name and the per-tab name lists are generated
alongside the objects so they can't drift out of sync.

## Known limitations

- **Compact, fixed-height UI.** Live devices are locked to 169 px tall with no
  vertical scrolling, so each section box packs its controls into one or two
  dense rows and the device is wide rather than tall (you may need to scroll the
  device chain horizontally to see all of a tab).
- **Bidirectional sync covers CC parameters only.** Hardware → UI tracking works
  for the 102 CCs; it can't reflect changes the Muse makes that aren't sent as
  CC (e.g. Mod Map edits, preset loads from the synth's own menus).
- **CC parameters only — no full patch dump.** The Muse has no SysEx patch
  transfer, so snapshots (Live presets) capture the 102 CC parameters but
  **not** Mod Map routings, sequencer step data, arp patterns, or global
  settings. Full patch backup is via the Muse's USB Disk Mode.
- **Mod Map not accessible.** The modulation routing matrix is menu-driven on
  the hardware with no CC representation, so it can't be controlled here.
- **One timbre per instance.** A single device controls one timbre (one MIDI
  channel). For both timbres, run an instance per track on different channels —
  see [Controlling both timbres](#controlling-both-timbres-multi-mode).

## Data sources

The MIDI CC parameter map and descriptions were compiled from:

- [pencilresearch/midi: Moog/Muse.csv](https://github.com/pencilresearch/midi/blob/main/Moog/Muse.csv)
- Moog Muse 1.4 official documentation (Appendix A) — used to correct the
  Filter/VCA envelope stage labels (CC 80/81 and 87/88 are Decay/Sustain, not
  Sustain/Delay).
- Hardware-verified control types where the manual/CC list disagreed with the
  front panel: the Mod Osc per-destination enables (CC 33, 34, 36, 37, 40, 41,
  43) and Filter 1 High Pass (CC 66) are **on/off** switches (off 0–63, on
  64–127), not continuous knobs; the oscillator Tri/Saw Mix (CC 46, 51) are
  knobs while the Wave Mix (CC 48, 53) are faders. These eight on/off
  corrections are now recorded back in `Muse_MIDI_CCs.csv` (the `usage` column
  carries the `0-63: Off; 64-127: On` band that Moog's own CC list left blank),
  so the CSV reflects the hardware rather than the documentation.

## TODO

- Re-implement a safe "push patch" / SEND ALL (send every control to the Muse
  at once). The previous SEND ALL blasted all 102 CCs simultaneously, which made
  the Muse misbehave; a future version should throttle/stagger the sends (and
  possibly skip channel/global CCs) so the synth can keep up.

## Status / testing note

This device was generated and validated structurally (binary container, JSON,
parameter-name uniqueness, and the full routing/tab/Program-Change graph), but
it has **not yet been loaded in Ableton from this build** — that requires Max/
Live, which the build environment doesn't have. The data-driven parts (controls,
CC routing, Program Change) are straightforward; if anything needs a touch-up on
first load it's most likely the `thispatcher` tab show/hide. Everything is
regenerable from `generate_device.py`, so fixes are quick.
