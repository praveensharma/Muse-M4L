# MuseEditor Tonight r2 - 2026-10-24

Load **MuseEditor Tonight r2.amxd** onto a MIDI track. This is the modified test candidate; the upstream MuseEditor.amxd in the repository root is unchanged.

## Start here

1. Set the track's **MIDI To** to your Muse port and intended channel. Enable **Receive CC** on the Muse.
2. The device opens with **OUTPUT OFF** and **THRU OFF**. Click **OUTPUT OFF** to enable output, then move a cutoff control. Enabling output does not send the displayed patch or flush previously blocked changes.
3. For MIDI clips or an external keyboard/controller routed through this track, enable **THRU ON** as well. Both switches must be on for input MIDI to reach the Muse. THRU preserves incoming MIDI, including performance controls and program changes; use a specific input port/channel.
4. For **Muse hardware-knob feedback**, leave **THRU OFF**, enable Muse **Send CC**, select the Muse input port and intended input channel on the track, and set Monitor to In. Received CCs update the display without being returned to the synth. OUTPUT can remain on for on-screen editing.
5. **PANIC** is always available in the header, even with OUTPUT OFF. It releases Sustain and Hold, then sends All Notes Off and All Sound Off. Turning OUTPUT or THRU off also sends Panic to release notes previously passed through.

OUTPUT and THRU are session switches, not saved/automatable parameters. Re-enable them deliberately after loading or reopening a Set. The 102 synth CC controls remain automatable. Parameter automation that runs while OUTPUT is off is discarded; after arming, subsequent automation values are transmitted.

## Preset recall

Enable **Receive Program Change** on the Muse. Select Bank 1-16 and Patch 1-16 on BANK, then press **SEND** with OUTPUT on. Changing the selectors, including their automation or restoration, does not send preset messages. SEND reads their current displayed values and sends Bank MSB, Bank LSB, then Program Change in order.

This candidate sends CC0=0, CC32=Bank (1-16), and Program Change=Patch-1 (0-15). Bank numbering follows the literal Bank Select range in the Muse 1.4 manual; Program Change uses conventional zero-based wire numbering. Confirm Bank 1/Patch 1, Bank 2/Patch 1, and Bank 16/Patch 16 against the Muse display. This mapping has not been verified on hardware.

Preset recall does not synchronize the entire UI. The displayed controls are only a partial state, updated as individual hardware CCs arrive. There is no full patch pull or SEND ALL in this build.

## Two timbres

Start with one instance. For two, enable Muse Multi Mode, assign distinct receive channels to A and B, and use one Live track per channel. Set both MIDI To **and MIDI From** explicitly per track; selecting only an output channel does not separate incoming feedback. The Muse has configurable keyboard and left-hand-controller output channels, so confirm which channel panel changes actually use. Do not feed all hardware channels into both editors.

THRU is for performance input. Leaving it on while monitoring the Muse returns its messages, including locally played notes, to the Muse. For tonight, test hardware feedback and external-controller/clip performance as separate routing arrangements. No local keyboard setting is changed by this device.

## r2 button fix

Replaces the unresponsive OUTPUT and THRU live.text controls with standard Max textbutton toggles, with explicit click enablement and toggle mode. Other MIDI routing is unchanged.

## Changes in this candidate

- Output and input-through gates start closed, including during initialization.
- Independent, always-visible OUTPUT, THRU, and PANIC controls.
- Preset selection is SEND-only, with fresh selector readback before transmission.
- Corrected midiformat and fixed-CC ctlin port metadata; removed the invalid channel-initialization wire.
- Bank Select uses 1-16 rather than bank-minus-one.
- Panic also releases Hold/Sustain and silently resets their displayed controls.
- Original control coverage and 728-pixel-wide layout retained; header tabs narrowed to accommodate the new controls.
- Original upstream AMXD, Max patch, and SVG remain unchanged for comparison.

## Validation and first test

Twelve automated graph-level regression tests pass. They cover output gating, simulated restore events, preset order, selector readback, input-through, feedback updates without echo, Panic, all 102 CC destinations and menu bands, valid patch connections, presentation bounds, session-switch metadata, and AMXD JSON round-trip. The packaged AMXD is checked against the generated Max patch. The preview is a static mock-up, not a Live screenshot.

These tests execute a small synchronous model of the generated graph. They do not establish Max runtime behavior, Live parameter persistence, actual MIDI bytes, or audible Muse operation. **r2 was loaded in the already-open Ableton Live 12 Beta on 2026-10-24. OUTPUT was clicked OFF -> ON -> OFF -> ON, and THRU OFF -> ON -> OFF, with visible label/color changes confirmed. The broken instance on MUSE EDITOR was replaced with r2; the Set was not saved. Actual MIDI data, bank recall, hardware response, audible results, and save/reopen behavior remain unverified.**

Use a disposable Set and a patch you can reload. Confirm silence on insertion, then enable output and check cutoff, a toggle, an octave menu, and preset boundary cases. Add hardware feedback with THRU off; test clips/controller performance with THRU on. Finally check notes release, Panic, automation, and save/reopen behavior. Do not save changes over a valued Muse patch during the first test.

## Rebuild

From the repository directory, run:

```sh
python3 build_tonight.py
```

The build uses the Python standard library and writes the device, editable patch, guide, mock-up preview, test log, and checksums under `build/tonight-r2/`, plus `build/MuseEditor-Tonight-r2-2026-10-24.zip`.

Reference: [Muse 1.4 manual](https://cdn.inmusicbrands.com/Moog/Muse/Muse_Manual-1.4.0.pdf), MIDI settings pp. 110-111; [Max midiformat](https://docs.cycling74.com/reference/midiformat/); [Max gate](https://docs.cycling74.com/reference/gate/).
