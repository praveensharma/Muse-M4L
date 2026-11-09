#!/usr/bin/env python3
"""
Build the local MuseEditor Tonight Max for Live MIDI-effect candidate.

102 CC controls retain the upstream layout and automation names. Output and
input-through gates start closed; session-only OUTPUT and THRU header buttons
open them deliberately. Hardware feedback updates UI via set without echo when
THRU is off. PANIC bypasses both gates and releases pedal/latch/notes. Preset
selectors write cold storage; SEND snapshots the UI and emits the transaction.

Run python3 build_tonight.py for tests, artifacts, preview and ZIP packaging.
Running this generator alone writes build/tonight/MuseEditor Tonight.{amxd,maxpat}.
The root upstream device and patch are left untouched. See TONIGHT_GUIDE.md.
"""

import json
import re
import struct

DEVICE_NAME = "MuseEditor"
AMXD_PATH = DEVICE_NAME + ".amxd"
MAXPAT_PATH = DEVICE_NAME + ".maxpat"

# control kinds.  K/B/S/H are all continuous 0-127 (routed identically); they
# differ only in how they're drawn so the device echoes the Muse's front panel:
#   K knob        -> live.dial      (rotary, like the Muse's knobs)
#   B bipolar      -> live.dial      (centre-detent knob, e.g. detune/pan)
#   S vert slider  -> live.slider    (mixer levels + envelope ADSR, like the panel)
#   H horiz slider -> live.slider    (oscillator wave-mix faders)
#   T toggle       -> live.toggle    (sends 0 / 127)
#   M multistate   -> live.menu      (sends the centre value of the CC band)
K, B, T, M, S, H = "knob", "bip", "toggle", "multi", "vslider", "hslider"
PB = "pitchbend"   # special 14-bit pitch-bend dial (not a CC; wired to xbendin)

OCT = ["16'", "8'", "4'", "2'"]
KBT = ["Off", "Half", "Full"]

# CC value -> menu index: upper bound of every band except the last, so the
# index is exactly sum(value > bound).  Keyed by number of bands.
BOUNDS = {3: [42, 84], 4: [31, 63, 95], 5: [24, 49, 74, 99]}

from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent / "Muse_MIDI_CCs.csv"


def load_descriptions():
    """cc -> manufacturer description text, read from the Muse CSV."""
    import csv
    info = {}
    try:
        with open(CSV_PATH, newline="") as f:
            for row in csv.DictReader(f):
                cc = (row.get("cc_msb") or "").strip()
                if cc.isdigit():
                    desc = (row.get("parameter_description") or "").strip()
                    note = (row.get("usage") or "").strip()
                    info[int(cc)] = (desc, note)
    except FileNotFoundError:
        pass
    return info


CC_INFO = load_descriptions()

# Supplementary descriptions for parameters the CSV leaves blank, written from
# the Moog Muse manual / Moog's published material.  The CSV's own text (which
# is Moog's) takes priority; these fill the gaps.
DESC_EXTRA = {
    8: "High-pass 'low cut' on the timbre output; raise to thin out lows.",
    11: "Expression (CC 11) - overall performance level for the active timbre.",
    13: "Overall output depth of LFO 1 to its mod-map destinations.",
    16: "Overall output depth of LFO 2 to its mod-map destinations.",
    46: "Blends Oscillator 1 between triangle (down) and sawtooth (up).",
    47: "Pulse width / duty cycle of Oscillator 1's pulse wave.",
    48: "Crossfades Oscillator 1 between its tri/saw mix and its pulse wave.",
    51: "Blends Oscillator 2 between triangle (down) and sawtooth (up).",
    52: "Pulse width / duty cycle of Oscillator 2's pulse wave.",
    53: "Crossfades Oscillator 2 between its tri/saw mix and its pulse wave.",
    54: "Hard-syncs OSC 1 to OSC 2 (resets OSC 1's phase) for sync timbres.",
    55: "Linear FM of OSC 1 by OSC 2 (depth set by FM Amount).",
    56: "Linear FM of OSC 2 by OSC 1 (depth set by FM Amount).",
    57: "Depth of oscillator-to-oscillator linear FM (2>1 / 1>2 switches).",
    58: "Level of Oscillator 1 into the mixer.",
    59: "Level of Oscillator 2 into the mixer.",
    60: "Level of the ring modulator (OSC 1 x OSC 2) into the mixer.",
    61: "Level of the Modulation Oscillator into the mixer (audible at audio rate).",
    62: "Level of the noise generator into the mixer.",
    65: "OVERLOAD - overdrives the mixer sum for overtones, CP3-mixer style.",
    66: "Switches Filter 1 to high-pass (on/off; off 0-63, on 64-127).",
    67: "Cutoff of Filter 1, a discrete Moog transistor-ladder filter (904a-style).",
    68: "Resonance/emphasis at Filter 1's cutoff; self-oscillates when high.",
    69: "Amount of the Filter envelope applied to Filter 1 cutoff.",
    70: "How much Filter 1 cutoff tracks keyboard pitch (Off / Half / Full).",
    71: "Latches/holds currently held notes so they keep sounding.",
    72: "Cutoff of Filter 2, a dedicated low-pass Moog ladder filter.",
    73: "Resonance/emphasis at Filter 2's cutoff; self-oscillates when high.",
    75: "Amount of the Filter envelope applied to Filter 2 cutoff.",
    76: "How much Filter 2 cutoff tracks keyboard pitch (Off / Half / Full).",
    77: "Links Filter 1 & 2 so one cutoff control sweeps both.",
    78: "Filter routing: Serial (1>2), Stereo (1 left / 2 right), or Parallel.",
    79: "Attack time of the Filter envelope.",
    80: "Decay time of the Filter envelope (fall to the sustain level).",
    81: "Sustain level held by the Filter envelope while a key is down.",
    82: "Release time of the Filter envelope after key release.",
    83: "Loops the Filter envelope for cycling, LFO-like modulation.",
    85: "Makes the Filter envelope depth respond to key velocity.",
    86: "Attack time of the Amplifier (VCA) envelope.",
    87: "Decay time of the Amplifier (VCA) envelope (fall to the sustain level).",
    88: "Sustain level held by the Amplifier (VCA) envelope while a key is down.",
    89: "Release time of the Amplifier envelope after key release.",
    90: "Loops the Amplifier envelope for cycling, tremolo-like modulation.",
    91: "Makes loudness respond to key velocity via the Amplifier envelope.",
    92: "Progressively detunes the analog voices for a fatter, wider sound.",
    93: "Delay time of the left channel of the stereo Diffusion Delay.",
    94: "Delay time of the right channel of the stereo Diffusion Delay.",
    95: "Links left & right delay times so one control sets both.",
    102: "Syncs delay times to the clock/tempo instead of free milliseconds.",
    103: "Delay feedback - how many times the repeats echo.",
    104: "Tone/diffusion character of the delay repeats, clean to smeared.",
    105: "Dry/wet balance of the Diffusion Delay.",
    106: "Routes Timbre A through the delay.",
    107: "Routes Timbre B through the delay.",
    108: "Unison - stacks all voices on each note for a massive sound.",
    109: "Monophonic mode - one voice at a time.",
    110: "Clock division for the sequencer (speed vs the master clock).",
    111: "Clock division for the arpeggiator (speed vs the master clock).",
    112: "Turns the arpeggiator on or off.",
    113: "Arpeggiator forward / backward direction.",
    114: "Arpeggiator note order: Order (as played), Pattern, or Random.",
    115: "Number of octaves the arpeggio spans (1-4).",
    116: "Master clock tempo (BPM) for arp, sequencer, and synced delay.",
}


def annotation_for(cc, longname):
    """Build the Info-View / hint text for a control."""
    desc, note = CC_INFO.get(cc, ("", ""))
    if not desc:
        desc = DESC_EXTRA.get(cc, "")
    text = "%s  ·  CC %d" % (longname, cc)
    if desc:
        text += "  —  " + desc
    if note:
        text += "  (" + note + ")"
    return text


# Non-zero defaults so a freshly-loaded device shows a basic playable INIT
# patch instead of silence: one oscillator at full level,
# filter open, amp envelope sustaining.  Values are CC values; menus use the
# option index.  Everything not listed defaults to 0 / first option.
INIT = {
    7: 127,    # Timbre Volume
    10: 64,    # Pan -> centre (0 = left, 64 = centre, 127 = right)
    44: 1,     # OSC 1 Octave -> 8'
    58: 127,   # OSC 1 Level
    46: 64,    # OSC 1 Tri/Saw Mix -> midway
    67: 127,   # Filter 1 Cutoff -> open
    81: 127,   # Filter Env Sustain
    88: 127,   # VCA Env Sustain
    86: 0,     # VCA Env Attack -> instant
    89: 20,    # VCA Env Release -> short
}

# --------------------------------------------------------------------------
# Authoritative parameter map, grouped like the Muse's front panel.
#
#   TABS    = [(tab-name, [section, ...]), ...]
#   section = (title, [row, ...])           # a bordered, titled box
#   row     = [control, ...]                # controls sit in a small grid
#   control = (cc, long-name, kind, enum, short-label)
#
# Sections are drawn as titled boxes (like the panel's LFO 1 / LFO 2 / Pitch
# LFO etc.) and laid out left to right within a tab; rows stack inside a box.
# The long-name is the unique Live automation/MIDI-map name; the short-label is
# what's printed under the control (the section title supplies the context).
# Tab order follows the panel scanned left to right.
# --------------------------------------------------------------------------
LFO_WAVES = ["Triangle", "Saw", "Square", "Random", "User"]
MOD_WAVES = ["Sine", "Saw", "Ramp", "Square", "Noise"]

TABS = [
    ("LFO", [
        ("LFO 1", [
            [(12, "LFO 1 Rate", K, None, "Rate"),
             (13, "LFO 1 Amount", K, None, "Amount"),
             (14, "LFO 1 Waveform", M, LFO_WAVES, "Waveform")],
        ]),
        ("LFO 2", [
            [(15, "LFO 2 Rate", K, None, "Rate"),
             (16, "LFO 2 Amount", K, None, "Amount"),
             (17, "LFO 2 Waveform", M, LFO_WAVES, "Waveform")],
        ]),
        ("Pitch LFO", [
            [(18, "Pitch LFO Rate", K, None, "Rate"),
             (19, "Pitch LFO Shape", B, None, "Shape"),
             (20, "Pitch LFO Amount", B, None, "Amount")],
            [(21, "Pitch LFO>OSC 1", T, None, "OSC 1"),
             (22, "Pitch LFO>OSC 2", T, None, "OSC 2"),
             (23, "Pitch LFO>Mod Osc", T, None, "Mod Osc"),
             (24, "Pitch LFO>Detune", T, None, "Detune")],
        ]),
    ]),
    ("MOD", [
        ("Mod Oscillator", [
            [(25, "Mod Osc Frequency", K, None, "Freq"),
             (28, "Mod Osc Waveform", M, MOD_WAVES, "Waveform"),
             (26, "Mod Osc Audio Rate", T, None, "Audio")],
            [(27, "Mod Osc KB Track", T, None, "KB Track"),
             (29, "Mod Osc KB Reset", T, None, "KB Reset"),
             (30, "Mod Osc Unipolar", T, None, "Unipolar")],
        ]),
        ("Pitch", [
            [(31, "Mod Osc Pitch Amount", K, None, "Amount")],
            [(33, "Mod Osc Pitch>OSC 1", T, None, "OSC 1"),
             (34, "Mod Osc Pitch>OSC 2", T, None, "OSC 2")],
        ]),
        ("PWM", [
            [(35, "Mod Osc PWM Amount", K, None, "Amount")],
            [(36, "Mod Osc PWM>OSC 1", T, None, "OSC 1"),
             (37, "Mod Osc PWM>OSC 2", T, None, "OSC 2")],
        ]),
        ("Filter", [
            [(39, "Mod Osc Filter Amount", K, None, "Amount")],
            [(40, "Mod Osc Filter>F1", T, None, "Filter 1"),
             (41, "Mod Osc Filter>F2", T, None, "Filter 2")],
        ]),
        ("VCA", [
            [(42, "Mod Osc VCA Amount", K, None, "Amount")],
            [(43, "Mod Osc VCA Pan", T, None, "Pan")],
        ]),
    ]),
    ("OSC", [
        ("Oscillator 1", [
            [(44, "OSC 1 Octave", M, OCT, "Octave"),
             (45, "OSC 1 Frequency", B, None, "Freq"),
             (47, "OSC 1 PW", K, None, "Pulse W")],
            [(46, "OSC 1 Tri/Saw Mix", K, None, "Tri/Saw"),
             (48, "OSC 1 Wave Mix", H, None, "Wave Mix")],
        ]),
        ("Oscillator 2", [
            [(49, "OSC 2 Octave", M, OCT, "Octave"),
             (50, "OSC 2 Frequency", B, None, "Freq"),
             (52, "OSC 2 PW", K, None, "Pulse W")],
            [(51, "OSC 2 Tri/Saw Mix", K, None, "Tri/Saw"),
             (53, "OSC 2 Wave Mix", H, None, "Wave Mix")],
        ]),
        ("Sync / FM", [
            [(54, "OSC 2>1 Sync", T, None, "Sync"),
             (57, "FM Amount", K, None, "FM Amt")],
            [(55, "OSC 2>1 FM", T, None, "2>1 FM"),
             (56, "OSC 1>2 FM", T, None, "1>2 FM")],
        ]),
    ]),
    ("MIX", [
        # The mixer faders, in panel order, then the Overload/clipping drive.
        ("Mixer", [
            [(58, "OSC 1 Level", S, None, "OSC 1"),
             (60, "Ring Mod Level", S, None, "Ring Mod"),
             (59, "OSC 2 Level", S, None, "OSC 2"),
             (61, "Mod Osc Level", S, None, "Mod Osc"),
             (62, "Noise Level", S, None, "Noise"),
             (65, "Clipping Level", S, None, "Overload")],
        ]),
    ]),
    ("FILTER", [
        ("Filter 1", [
            [(67, "Filter 1 Cutoff", K, None, "Cutoff"),
             (66, "Filter 1 High Pass", T, None, "High Pass"),
             (68, "Filter 1 Resonance", K, None, "Resonance")],
            [(69, "Filter 1 Env Amount", K, None, "Env Amt"),
             (70, "Filter 1 KB Track", M, KBT, "KB Track"),
             (77, "Link Filters", T, None, "Link")],
        ]),
        ("Filter 2", [
            [(72, "Filter 2 Frequency", K, None, "Cutoff"),
             (73, "Filter 2 Resonance", K, None, "Resonance"),
             (78, "Filter Order", M, ["Serial", "Stereo", "Parallel"], "Order")],
            [(75, "Filter 2 Env Amount", K, None, "Env Amt"),
             (76, "Filter 2 KB Track", M, KBT, "KB Track")],
        ]),
    ]),
    ("ENV", [
        # Filter Envelope and VCA Envelope as two separate boxes, like the panel.
        ("Filter Envelope", [
            [(79, "Filter Env Attack", S, None, "Attack"),
             (80, "Filter Env Decay", S, None, "Decay"),
             (81, "Filter Env Sustain", S, None, "Sustain"),
             (82, "Filter Env Release", S, None, "Release"),
             (83, "Filter Env Loop", T, None, "Loop"),
             (85, "Filter Env Velocity", T, None, "Vel")],
        ]),
        ("VCA Envelope", [
            [(86, "VCA Env Attack", S, None, "Attack"),
             (87, "VCA Env Decay", S, None, "Decay"),
             (88, "VCA Env Sustain", S, None, "Sustain"),
             (89, "VCA Env Release", S, None, "Release"),
             (90, "VCA Env Loop", T, None, "Loop"),
             (91, "VCA Env Velocity", T, None, "Vel")],
        ]),
    ]),
    ("VCA", [
        ("VCA / Output", [
            [(7, "Timbre Volume", K, None, "Volume"),
             (10, "Pan", B, None, "Pan"),
             (9, "Pan Spread", K, None, "Spread")],
            [(8, "Low Cut", K, None, "Low Cut"),
             (3, "Mute", T, None, "Mute")],
        ]),
    ]),
    ("DELAY", [
        ("Diffusion Delay", [
            [(93, "Delay Time Left", K, None, "Time L"),
             (94, "Delay Time Right", K, None, "Time R"),
             (95, "Link Delays", T, None, "Link"),
             (102, "Delay Clock Sync", T, None, "Sync")],
            [(103, "Delay Feedback", K, None, "Feedback"),
             (104, "Delay Character", K, None, "Character"),
             (105, "Delay Mix", K, None, "Mix")],
        ]),
        ("Sends", [
            [(106, "Delay>Timbre A", T, None, "Timbre A")],
            [(107, "Delay>Timbre B", T, None, "Timbre B")],
        ]),
    ]),
    ("ARP", [
        ("Arpeggiator", [
            [(112, "Arp On/Off", T, None, "On"),
             (113, "Arp FW/BK", T, None, "Fw/Bk"),
             (114, "Arp Direction", M, ["Order", "Pattern", "Random"], "Mode"),
             (115, "Arp Octave Range", M, ["1", "2", "3", "4"], "Octaves")],
            [(111, "Arp Clock Div", K, None, "Arp Div"),
             (110, "Seq Clock Div", K, None, "Seq Div"),
             (116, "Clock Tempo", K, None, "Tempo")],
        ]),
    ]),
    ("VOICE", [
        ("Voice Control", [
            [(92, "Voice Detune", K, None, "Detune"),
             (108, "Voice Unison", T, None, "Unison"),
             (109, "Voice Mono", T, None, "Mono"),
             (5, "Glide Time", K, None, "Glide")],
            [(1, "Mod Wheel", K, None, "Mod Wheel"),
             (11, "Expression", K, None, "Express"),
             (71, "Hold", T, None, "Hold"),
             (64, "Sustain Pedal", T, None, "Sustain")],
        ]),
        ("Pitch Bend", [
            [(None, "Pitch Bend", PB, None, "Bend")],
        ]),
    ]),
]


def iter_sections():
    """Yield (tab-name, title, rows) for every section."""
    for tabname, sections in TABS:
        for title, rows in sections:
            yield tabname, title, rows


def iter_controls():
    """Yield every (cc, longname, kind, enum, short) control across all tabs."""
    for _tab, _title, rows in iter_sections():
        for row in rows:
            for ctrl in row:
                yield ctrl

# Caption = on-screen label (the tab already provides the context).
CAPTION_MAP = [
    ("OSC 1 ", "1 "), ("OSC 2 ", "2 "), ("OSC ", ""),
    ("Filter 1 ", "F1 "), ("Filter 2 ", "F2 "),
    ("Filter Env ", "F.Env "), ("Filter ", ""),
    ("VCA Env ", "VCA "), ("Mod Osc ", ""),
    ("Pitch LFO>", "P.LFO>"), ("Pitch LFO ", "P.LFO "),
    ("LFO 1 ", "L1 "), ("LFO 2 ", "L2 "),
    ("Delay>", "→"), ("Delay ", ""),
    ("Arp ", ""), ("Voice ", ""),
]


# Whole-word abbreviations applied to on-screen captions for legibility.
WORD_ABBR = {
    "Resonance": "Reso", "Frequency": "Freq", "Amount": "Amt",
    "Attack": "Atk", "Release": "Rel", "Sustain": "Sus", "Decay": "Dec",
    "Velocity": "Vel", "Waveform": "Wave", "Octave": "Oct", "Level": "Lvl",
    "Character": "Char", "Feedback": "Fbk", "Expression": "Expr",
    "Direction": "Dir", "Pedal": "Ped", "Range": "Rng", "Spread": "Spr",
    "Wheel": "Whl", "Reset": "Rst", "Unison": "Uni", "Unipolar": "Uni",
    "Clipping": "Clip",
}


# Explicit short labels where the tab already supplies the context and the
# auto-abbreviation would be unclear (mixer faders, the two ADSR envelopes).
CAPTION_OVERRIDE = {
    "OSC 1 Level": "OSC 1", "OSC 2 Level": "OSC 2",
    "Ring Mod Level": "Ring", "Mod Osc Level": "Mod Osc",
    "Noise Level": "Noise", "Clipping Level": "Drive",
    "Timbre Volume": "Volume", "Seq Clock Div": "Seq Div",
    "Pitch LFO>Mod Osc": "P.LFO>Mod",
    "OSC 1 Tri/Saw Mix": "Tri/Saw 1", "OSC 2 Tri/Saw Mix": "Tri/Saw 2",
    "Filter Env Attack": "F Atk", "Filter Env Decay": "F Dec",
    "Filter Env Sustain": "F Sus", "Filter Env Release": "F Rel",
    "Filter Env Loop": "F Loop", "Filter Env Velocity": "F Vel",
    "VCA Env Attack": "A Atk", "VCA Env Decay": "A Dec",
    "VCA Env Sustain": "A Sus", "VCA Env Release": "A Rel",
    "VCA Env Loop": "A Loop", "VCA Env Velocity": "A Vel",
}


def caption(longname):
    if longname in CAPTION_OVERRIDE:
        return CAPTION_OVERRIDE[longname]
    out = longname
    for pre, repl in CAPTION_MAP:
        if out.startswith(pre):
            out = repl + out[len(pre):]
            break
    return " ".join(WORD_ABBR.get(w, w) for w in out.split(" "))


def slug(longname):
    return re.sub(r"[^0-9A-Za-z]+", "_", longname).strip("_")


# --------------------------------------------------------------------------
# Max patcher construction
# --------------------------------------------------------------------------
class Patch:
    def __init__(self):
        self.boxes = []
        self.lines = []
        self._n = 0

    def _id(self):
        self._n += 1
        return "obj-%d" % self._n

    def box(self, maxclass, rect, present=False, **attrs):
        oid = self._id()
        b = {
            "id": oid,
            "maxclass": maxclass,
            "numinlets": attrs.pop("numinlets", 1),
            "numoutlets": attrs.pop("numoutlets", 0),
            "patching_rect": [float(v) for v in rect],
        }
        ot = attrs.pop("outlettype", None)
        if ot is not None:
            b["outlettype"] = ot
        if present:
            b["presentation"] = 1
            b["presentation_rect"] = [float(v) for v in rect]
        b.update(attrs)
        self.boxes.append({"box": b})
        return oid

    def obj(self, text, rect, **kw):
        kw.setdefault("numoutlets", 1)
        kw.setdefault("outlettype", [""])
        return self.box("newobj", rect, text=text, **kw)

    def msg(self, text, rect, **kw):
        kw.setdefault("numinlets", 2)
        kw.setdefault("numoutlets", 1)
        kw.setdefault("outlettype", [""])
        return self.box("message", rect, text=text, **kw)

    def comment(self, text, rect, present=True, varname=None,
                fontsize=8.0, fontface=0, justify=1, textcolor=None):
        attrs = dict(text=text, numinlets=1, numoutlets=0,
                     fontsize=fontsize, fontface=fontface,
                     textjustification=justify)
        if textcolor is not None:
            attrs["textcolor"] = textcolor
        if varname:
            attrs["varname"] = varname
        return self.box("comment", rect, present=present, **attrs)

    def section_frame(self, x, y, w, h, varname):
        """Draw a section as a subtly-lighter rounded panel with a hairline
        border and a thin blue accent rule under its title.

        The panels are placed in the patcher's *background layer*
        (``background 1``).  Max draws the background layer behind the entire
        foreground layer regardless of object order, so the filled panel sits
        behind the controls (which are foreground) instead of covering them -
        this is the documented way to do backgrounds and what z-order alone
        can't achieve.  ``ignoreclick`` also keeps it from stealing the mouse.
        The title text stays in the foreground so it reads on top of the panel.
        Returns the panel scripting names so they show/hide with the tab.
        """
        names = []
        # filled, rounded, bordered background panel
        self.box("panel", [x, y, w, h], present=True, varname=varname + "_bg",
                 background=1, mode=0, rounded=6, bgfillcolor_type="color",
                 bgcolor=COL_PANEL, bordercolor=COL_BORDER, border=1,
                 ignoreclick=1)
        names.append(varname + "_bg")
        # thin accent rule just under the title strip (also background)
        self.box("panel", [x + 6, y + SEC_TITLE_H - 1, w - 12, 1], present=True,
                 varname=varname + "_uln", background=1, mode=0, rounded=0,
                 bgfillcolor_type="color", bgcolor=COL_ACCENT, ignoreclick=1)
        names.append(varname + "_uln")
        return names

    def text_button(self, rect, varname, label):
        """A momentary (mode 0) live.text button with its caption inside it,
        styled to match the on/off buttons.  Emits on click; wire its outlet
        like a Max ``button``."""
        return self.box("live.text", rect, present=True, varname=varname,
                        numinlets=1, numoutlets=2, outlettype=["bang", ""],
                        parameter_enable=0, mode=0, text=label, texton=label, fontsize=9.0,
                        bgcolor=COL_BTN_OFF, bgoncolor=COL_ACCENT,
                        activebgcolor=COL_ACCENT, activebgoncolor=COL_ACCENT,
                        textcolor=COL_BTN_TXT, textoncolor=COL_WHITE,
                        bordercolor=COL_BORDER)

    def tab_panel(self, varname):
        """Full-width background panel for the Bank / Misc tabs, matching the
        section panels on the other tabs.  In the background layer so it sits
        behind the controls.  Returns its scripting name."""
        self.box("panel", [MARGIN, SEC_TOP, DEVICE_WIDTH - 2 * MARGIN, SEC_H],
                 present=True, varname=varname, background=1, mode=0, rounded=6,
                 bgfillcolor_type="color", bgcolor=COL_PANEL,
                 bordercolor=COL_BORDER, border=1, ignoreclick=1)
        return varname

    def connect(self, src, sout, dst, din):
        self.lines.append({"patchline": {"source": [src, sout],
                                          "destination": [dst, din]}})

    def live(self, maxclass, rect, longname, ptype, mmin, mmax,
             enum=None, varname=None, annotation=None, initial=None,
             shortname=None, showname=None, orientation=None,
             extra_attrs=None):
        v = {
            "parameter_longname": longname,
            "parameter_shortname": (shortname or caption(longname))[:14],
            "parameter_type": ptype,
            "parameter_mmin": mmin,
            "parameter_mmax": mmax,
            "parameter_initial_enable": 1 if initial is not None else 0,
            "parameter_initial": [initial if initial is not None else 0],
            "parameter_invisible": 0,
        }
        if enum is not None:
            v["parameter_enum"] = enum     # live.menu / live.toggle
            v["parameter_range"] = enum    # live.tab
        extra = {}
        if annotation:
            # shows in Ableton's Info View (bottom-left) and as a hover hint
            extra["annotation"] = annotation
            extra["hint"] = annotation
        if showname is not None:
            # hide the object's own name text so it doesn't duplicate the
            # printed label beneath the control (live.dial / live.slider)
            extra["showname"] = showname
        if orientation is not None:
            # live.slider defaults to vertical; 1 = horizontal (wave-mix faders)
            extra["orientation"] = orientation
        if extra_attrs:
            # styling pass-through (colours, live.text button mode/labels, ...)
            extra.update(extra_attrs)
        return self.box(
            maxclass, rect, present=True,
            numinlets=1, numoutlets=2, outlettype=["", ""],
            parameter_enable=1,
            varname=varname or slug(longname),
            saved_attribute_attributes={"valueof": v},
            **extra,
        )

    def to_maxpat(self):
        return {"patcher": {
            "fileversion": 1,
            "appversion": {"major": 8, "minor": 6, "revision": 0,
                           "architecture": "x64", "modernui": 1},
            "classnamespace": "box",
            "rect": [60.0, 80.0, 1100.0, 720.0],
            "bglocked": 0,
            "openinpresentation": 1,
            "default_fontsize": 12.0,
            "default_fontface": 0,
            "default_fontname": "Arial",
            "gridonopen": 1,
            "gridsize": [15.0, 15.0],
            "gridsnaponopen": 1,
            "objectsnaponopen": 1,
            "statusbarvisible": 2,
            "toolbarvisible": 1,
            "lefttoolbarpinned": 0,
            "toptoolbarpinned": 0,
            "righttoolbarpinned": 0,
            "bottomtoolbarpinned": 0,
            "toolbars_unpinned_last_save": 0,
            "tallnewobj": 0,
            "boxanimatetime": 200,
            "enablehscroll": 1,
            "enablevscroll": 1,
            "devicewidth": float(DEVICE_WIDTH),
            "description": "Moog Muse editor",
            "digest": "",
            "tags": "",
            "style": "",
            "subpatcher_template": "",
            "assistshowspatchername": 0,
            "boxes": self.boxes,
            "lines": self.lines,
            "dependency_cache": [],
            "autosave": 0,
        }}


# --------------------------------------------------------------------------
# Layout - everything must fit inside Live's fixed 169px device height.
#
# Each tab is a left-to-right run of titled section boxes (like the panel's
# bordered LFO 1 / LFO 2 / Pitch LFO groups).  Inside a box the controls sit in
# a small grid; each control has a short label printed directly above it (the
# box title carries the context, so labels stay short and never overlap).
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# Colour palette.  Kept deliberately restrained: sections are a subtly lighter
# rounded panel on the (darker) Live device background, hairline borders, and a
# single blue accent used for the title rules, the dial/slider fill, and the
# "lit" state of the on/off buttons - so the device reads cleanly like a piece
# of hardware rather than a wall of identical knobs.
# --------------------------------------------------------------------------
COL_PANEL   = [0.255, 0.265, 0.285, 1.0]   # section fill (lighter than the bg)
COL_BORDER  = [0.355, 0.375, 0.405, 1.0]   # hairline section border
COL_ACCENT  = [0.42, 0.56, 0.78, 1.0]      # blue accent (rules, dial fill, lit)
COL_TITLE   = [0.80, 0.84, 0.90, 1.0]      # section title text
COL_LABEL   = [0.62, 0.65, 0.70, 1.0]      # control caption text
COL_BTN_OFF = [0.205, 0.215, 0.235, 1.0]   # on/off button, unlit fill
COL_BTN_TXT = [0.66, 0.69, 0.74, 1.0]      # on/off button, unlit text
COL_WHITE   = [0.96, 0.97, 0.99, 1.0]      # lit button text

MARGIN = 10
COL_W = 56                     # width of one control cell inside a section
DIAL = 34
LABEL_H = 11
LABEL_GAP = 2                  # gap between a label and its control
SEC_TOP = 23                   # top of every section box (below the tab strip)
SEC_H = 141                    # section box height (23 + 141 = 164 <= 169)
SEC_TITLE_H = 14               # title strip at the top of a section box
SEC_PAD_X = 7                  # left/right padding inside a section box
SEC_GAP = 8                    # gap between section boxes
SLIDER_W = 18                  # vertical fader width


def _cols_in_section(rows):
    return max(len(row) for row in rows)


def section_width(rows):
    return _cols_in_section(rows) * COL_W + 2 * SEC_PAD_X


def tab_width(sections):
    inner = sum(section_width(rows) for _t, rows in sections)
    inner += SEC_GAP * (len(sections) - 1)
    return inner


DEVICE_WIDTH = 2 * MARGIN + max(tab_width(secs) for _n, secs in TABS)


def build():
    p = Patch()

    # ---- shared MIDI plumbing (off-canvas, not in presentation) ----------
    wx = DEVICE_WIDTH + 80
    midiin = p.obj("midiin", [wx, 20, 60, 22])
    midiformat = p.obj("midiformat 1", [wx + 150, 60, 90, 22], numinlets=7,
                       numoutlets=2, outlettype=["int", ""])
    midiout = p.box("newobj", [wx + 150, 120, 60, 22], numinlets=1,
                    numoutlets=0, text="midiout")
    # Gates start CLOSED in the object itself, before any parameter restoration.
    output_gate = p.obj("gate 1 0", [wx + 150, 95, 70, 22], numinlets=2)
    thru_gate = p.obj("gate 1 0", [wx, 60, 70, 22], numinlets=2)
    p.connect(midiin, 0, thru_gate, 1)
    p.connect(thru_gate, 0, output_gate, 1)
    p.connect(midiformat, 0, output_gate, 1)
    p.connect(output_gate, 0, midiout, 0)
    output_button, thru_button, panic = build_header(p, midiout, wx)
    p.connect(output_button, 0, output_gate, 0)
    p.connect(thru_button, 0, thru_gate, 0)
    # Disabling either path releases held notes. This is a user action only;
    # load-time button resets use 'set' and cannot trigger Panic.
    for button in (output_button, thru_button):
        off = p.obj("sel 0", [wx + 60, 180, 50, 22], numinlets=2,
                    numoutlets=2, outlettype=["bang", ""])
        p.connect(button, 0, off, 0)
        p.connect(off, 0, panic, 0)

    # ---- header: tab strip (16px tall so live.tab stays a single row) ----
    tab_labels = [t[0] for t in TABS] + ["BANK", "MISC"]
    tab = p.live("live.tab", [MARGIN, 5, DEVICE_WIDTH - 2 * MARGIN - 220, 16],
                 "Tab", 2, 0, len(tab_labels) - 1, enum=tab_labels,
                 varname="TabSel")

    # ---- per-tab sections + controls (only the active tab is shown) ------
    tab_members = []
    for _name, sections in TABS:
        members = []
        x = MARGIN
        for si, (title, rows) in enumerate(sections):
            sec_w = section_width(rows)
            box_vn = "sec_%d_%d" % (len(tab_members), si)
            members += p.section_frame(x, SEC_TOP, sec_w, SEC_H, box_vn)
            p.comment(title, [x + 6, SEC_TOP + 3, sec_w - 12, 11],
                      varname=box_vn + "_ti", fontsize=8.0, fontface=1,
                      justify=0, textcolor=COL_TITLE)
            members.append(box_vn + "_ti")

            body_top = SEC_TOP + SEC_TITLE_H + 3
            band = (SEC_H - SEC_TITLE_H - 6) / len(rows)
            for ri, row in enumerate(rows):
                row_top = body_top + ri * band
                for ci, (cc, longname, kind, enum, short) in enumerate(row):
                    cx = x + SEC_PAD_X + ci * COL_W
                    sn = slug(longname)
                    members.append(sn)
                    # on/off buttons carry their caption inside the button, so
                    # they don't get a separate floating label above them.
                    if kind != T:
                        members.append(sn + "_L")
                    if kind == PB:                  # bidirectional pitch bend
                        ann = ("Pitch Bend wheel (0-127, 64 = centre). Sends "
                               "to and follows the Muse's pitch wheel.")
                        ctrl = make_control(p, kind, longname, enum, short, cx,
                                            row_top, band, ann, 64)
                        place_label(p, short, cx, row_top, sn)
                        wire_pitchbend(p, ctrl, midiin, midiformat, wx)
                        continue
                    ctrl = make_control(p, kind, longname, enum, short, cx,
                                        row_top, band,
                                        annotation_for(cc, longname),
                                        INIT.get(cc))
                    if kind != T:
                        place_label(p, short, cx, row_top, sn)
                    route_out(p, kind, enum, cc, ctrl, midiformat, wx)  # ->Muse
                    route_in(p, kind, enum, cc, ctrl, wx)               # Muse->
            x += sec_w + SEC_GAP
        tab_members.append(members)

    # Panic also reflects pedal/latch release in the UI without re-sending.
    reset_latches = p.msg("set 0", [wx + 650, 420, 60, 22])
    p.connect(panic, 0, reset_latches, 0)
    for name in ("Hold", "Sustain_Pedal"):
        control = next(b["box"]["id"] for b in p.boxes if b["box"].get("varname") == name)
        p.connect(reset_latches, 0, control, 0)

    # ---- Bank tab (Program Change) and Misc tab (panic / bend) -----------
    tab_members.append(build_bank_tab(p, midiformat, wx))
    tab_members.append(build_misc_tab(p, panic))

    # ---- tab switching machinery (thispatcher script show/hide) ----------
    thisp = p.obj("thispatcher", [wx, 380, 90, 22], numinlets=1, numoutlets=2,
                  outlettype=["", ""])
    all_names = [n for m in tab_members for n in m]
    hide_all = p.msg(", ".join("script hide " + n for n in all_names),
                     [wx, 420, 200, 22])
    p.connect(hide_all, 0, thisp, 0)
    tii = p.obj("t i i", [wx + 260, 300, 60, 22], numinlets=1, numoutlets=2,
                outlettype=["int", "int"])
    p.connect(tii, 1, hide_all, 0)                       # right fires first
    sel = p.obj("sel " + " ".join(str(i) for i in range(len(tab_members))),
                [wx + 260, 340, 220, 22], numinlets=1,
                numoutlets=len(tab_members) + 1,
                outlettype=["bang"] * len(tab_members) + [""])
    p.connect(tii, 0, sel, 0)
    for ti, members in enumerate(tab_members):
        show = p.msg(", ".join("script show " + n for n in members),
                     [wx + 500, 300 + ti * 26, 220, 22])
        p.connect(sel, ti, show, 0)
        p.connect(show, 0, thisp, 0)
    p.connect(tab, 0, tii, 0)

    # ---- load-time init: close output/thru, select tab 0 -------------------------
    lb = p.box("loadbang", [wx, 90, 60, 22], numinlets=1, numoutlets=1,
               outlettype=["bang"])
    reset_ui = p.msg("set 0", [wx, 120, 50, 22])
    p.connect(lb, 0, reset_ui, 0)
    p.connect(reset_ui, 0, output_button, 0)
    p.connect(reset_ui, 0, thru_button, 0)
    close_gates = p.msg("0", [wx, 150, 40, 22])
    p.connect(lb, 0, close_gates, 0)
    p.connect(close_gates, 0, output_gate, 0)
    p.connect(close_gates, 0, thru_gate, 0)
    dly = p.obj("delay 300", [wx + 80, 120, 70, 22], numinlets=2)
    zero = p.msg("0", [wx + 80, 150, 40, 22])
    p.connect(lb, 0, dly, 0)
    p.connect(dly, 0, zero, 0)
    p.connect(zero, 0, tab, 0)
    p.connect(zero, 0, tii, 0)
    return p


def build_header(p, midiout, wx):
    """Always-visible, nonstored session switches plus unconditional Panic."""
    x = DEVICE_WIDTH - MARGIN - 212
    buttons = []
    for i, (name, off, on, hint) in enumerate([
        ("OutputEnable", "OUTPUT OFF", "OUTPUT ON", "Enable MIDI output after loading. Does not push current UI values."),
        ("MidiThru", "THRU OFF", "THRU ON", "Pass incoming notes and controls. Keep OFF when receiving Muse feedback."),
    ]):
        buttons.append(p.box("textbutton", [x + i * 76, 5, 72, 16],
            present=True, varname=name, numinlets=1, numoutlets=3,
            outlettype=["", "", "int"], parameter_enable=0, mode=1,
            active=1, ignoreclick=0, outputmode=1, usebgoncolor=1, usegradient=0,
            text=off, texton=on, annotation=hint, hint=hint, fontsize=8.0,
            bgcolor=COL_BTN_OFF, bgoncolor=COL_ACCENT,
            textcolor=COL_BTN_TXT, textoncolor=COL_WHITE))
    panic_button = p.text_button([x + 152, 5, 60, 16], "HeaderPanic", "PANIC")
    # Separate formatter bypasses the closed output gate, so Panic always works.
    panic_format = p.obj("midiformat 1", [wx + 600, 100, 90, 22],
                         numinlets=7, numoutlets=2, outlettype=["int", ""])
    p.connect(panic_format, 0, midiout, 0)
    panic = p.obj("t b b b b", [wx + 600, 140, 90, 22], numinlets=1,
                  numoutlets=4, outlettype=["bang"] * 4)
    p.connect(panic_button, 0, panic, 0)
    for outlet, cc in zip((3, 2, 1, 0), (64, 71, 123, 120)):
        message = p.msg("%d 0" % cc, [wx + 600, 180 + outlet * 26, 60, 22])
        p.connect(panic, outlet, message, 0)
        p.connect(message, 0, panic_format, 2)
    return buttons[0], buttons[1], panic


def build_bank_tab(p, midiformat, wx):
    """Program Change (Bank/Patch) controls, shown only on the Bank tab."""
    members = [p.tab_panel("bank_bg")]
    bx = MARGIN + 8

    def lbl(text, rect, vn, bold=False, color=None):
        members.append(vn)
        p.comment(text, rect, varname=vn, justify=0, fontsize=8.0,
                  fontface=1 if bold else 0,
                  textcolor=color or (COL_TITLE if bold else COL_LABEL))

    lbl("PROGRAM CHANGE", [bx, SEC_TOP + 3, 160, 12], "pc_t0", bold=True)
    lbl("Bank", [bx, 58, 30, 14], "pc_l1")
    bank = p.live("live.numbox", [bx + 34, 56, 40, 18], "PC Bank", 1, 1, 16,
                  varname="PCBank", initial=1, annotation="Muse bank to recall (1-16)",
                  extra_attrs={"bordercolor": COL_BORDER})
    members.append("PCBank")
    lbl("Patch", [bx + 86, 58, 34, 14], "pc_l2")
    patch = p.live("live.numbox", [bx + 122, 56, 40, 18], "PC Patch", 1, 1,
                   16, varname="PCPatch", initial=1,
                   annotation="Patch within the bank to recall (1-16)",
                   extra_attrs={"bordercolor": COL_BORDER})
    members.append("PCPatch")
    send = p.text_button([bx + 176, 56, 56, 18], "PCSend", "SEND")
    members.append("PCSend")
    lbl("Recalls one of the Muse's stored patches (16 banks x 16 patches).",
        [bx, 92, 520, 14], "pc_h1")
    lbl("Requires MENU > MIDI > RECEIVE PGM CHNG: ON on the Muse.",
        [bx, 110, 520, 14], "pc_h2")

    # SEND is the sole trigger. Selector changes/automation/restore only write
    # cold storage. Bank Select is a literal 1..16 (Muse 1.4 manual p.111);
    # Program Change uses the conventional zero-based wire value 0..15.
    pc_t = p.obj("t b b b", [wx + 300, 460, 80, 22], numinlets=1,
                 numoutlets=3, outlettype=["bang", "bang", "bang"])
    # Read the displayed selectors first, including any silent host restore.
    capture = p.obj("t b b b", [wx + 200, 430, 80, 22], numinlets=1,
                    numoutlets=3, outlettype=["bang"] * 3)
    p.connect(send, 0, capture, 0)
    p.connect(capture, 2, bank, 0)
    p.connect(capture, 1, patch, 0)
    p.connect(capture, 0, pc_t, 0)
    msb = p.msg("0 0", [wx + 300, 500, 50, 22])
    p.connect(pc_t, 2, msb, 0)                           # fires first
    p.connect(msb, 0, midiformat, 2)
    bank_store = p.obj("i 1", [wx + 300, 540, 50, 22], numinlets=2)
    p.connect(bank, 0, bank_store, 1)
    p.connect(pc_t, 1, bank_store, 0)
    blsb = p.obj("prepend 32", [wx + 300, 570, 80, 22], numinlets=2)
    p.connect(bank_store, 0, blsb, 0)
    p.connect(blsb, 0, midiformat, 2)
    patch_store = p.obj("i 1", [wx + 420, 510, 50, 22], numinlets=2)
    p.connect(patch, 0, patch_store, 1)
    p.connect(pc_t, 0, patch_store, 0)                   # fires last
    psub = p.obj("- 1", [wx + 420, 540, 50, 22], numinlets=2)
    p.connect(patch_store, 0, psub, 0)
    p.connect(psub, 0, midiformat, 3)
    return members


def wire_pitchbend(p, pb, midiin, midiformat, wx):
    """Bidirectional 14-bit pitch bend for the dial ``pb`` (0-127, 64 = centre).

    Out: dial -> midiformat pitch-bend inlet.
    In:  midiin -> xbendin (0..16383) -> / 128 -> prepend set -> dial
    (``set`` updates the dial without re-transmitting, so there's no feedback).
    """
    p.connect(pb, 0, midiformat, 5)                      # pitch-bend inlet (out)
    xb = p.obj("xbendin", [wx + 980, 440, 70, 22], numinlets=1, numoutlets=2,
               outlettype=["", ""])
    p.connect(midiin, 0, xb, 0)                          # raw bytes from midiin
    pbsc = p.obj("expr $i1 / 128", [wx + 980, 470, 170, 22],
                 numinlets=1, numoutlets=1, outlettype=[""])
    p.connect(xb, 0, pbsc, 0)                            # 0..16383 -> 0-127
    pbset = p.obj("prepend set", [wx + 980, 500, 80, 22], numinlets=2)
    p.connect(pbsc, 0, pbset, 0)
    p.connect(pbset, 0, pb, 0)


def build_misc_tab(p, panic):
    """Panic and notes - only on the Misc tab."""
    members = [p.tab_panel("misc_bg")]
    bx = MARGIN + 8

    def lbl(text, rect, vn, bold=False):
        members.append(vn)
        p.comment(text, rect, varname=vn, justify=0, fontsize=8.0,
                  fontface=1 if bold else 0,
                  textcolor=COL_TITLE if bold else COL_LABEL)

    lbl("PANIC", [bx, SEC_TOP + 3, 160, 12], "ms_t0", bold=True)
    pn = p.text_button([bx, 56, 150, 18], "MiscPanic", "ALL NOTES OFF")
    members.append("MiscPanic")
    p.connect(pn, 0, panic, 0)

    lbl("PANIC releases Sustain / Hold and sends All Notes Off / All Sound Off.",
        [bx, 92, 600, 14], "ms_h0")
    lbl("OUTPUT enables sending. THRU passes incoming MIDI: leave OFF for hardware feedback.",
        [bx, 110, 650, 14], "ms_h1")
    lbl("UI values are partial: loading a Muse preset does not synchronize every control.",
        [bx, 128, 600, 14], "ms_h2")
    return members




def make_control(p, kind, longname, enum, short, x, row_top, band, annotation,
                 initial=None):
    """Draw one control just below its label, in the cell at (x, row_top).

    The label is printed by ``place_label``; ``showname=0`` keeps live.dial /
    live.slider from drawing their own (duplicate) name text.  On/off (``T``)
    parameters are drawn as a labelled ``live.text`` button - the caption sits
    inside the button and it lights up in the accent colour when on - so they
    read like the hardware's switches instead of a bare checkbox + floating
    label.
    """
    top = row_top + LABEL_H + LABEL_GAP         # control top (right under label)
    avail = band - LABEL_H - LABEL_GAP - 2      # vertical room for the control

    def cx(w):                                  # horizontally centre width w
        return x + (COL_W - w) / 2.0

    if kind == T:                               # on/off -> labelled button
        bw, bh = COL_W - 6, 17
        by = row_top + max(0.0, (band - bh) / 2.0)   # centre in the whole cell
        return p.live("live.text", [cx(bw), by, bw, bh],
                      longname, 2, 0, 1, enum=["off", "on"],
                      shortname=short, annotation=annotation, initial=initial,
                      extra_attrs={
                          "mode": 1,                 # 1 = toggle (latching)
                          "text": short, "texton": short,
                          "fontsize": 8.0,
                          "bgcolor": COL_BTN_OFF,
                          "bgoncolor": COL_ACCENT,
                          "activebgcolor": COL_BTN_OFF,
                          "activebgoncolor": COL_ACCENT,
                          "textcolor": COL_BTN_TXT,
                          "textoncolor": COL_WHITE,
                          "bordercolor": COL_BORDER,
                      })
    if kind == M:
        return p.live("live.menu", [cx(COL_W - 8), top, COL_W - 8, 18],
                      longname, 2, 0, len(enum) - 1, enum=enum,
                      shortname=short, showname=0,
                      annotation=annotation, initial=initial,
                      extra_attrs={"bordercolor": COL_BORDER})
    if kind == S:                               # vertical fader (mixer / ADSR)
        h = max(24.0, avail)
        return p.live("live.slider", [cx(SLIDER_W), top, SLIDER_W, h],
                      longname, 1, 0, 127, shortname=short, showname=0,
                      annotation=annotation, initial=initial,
                      extra_attrs={"slidercolor": COL_ACCENT})
    if kind == H:                               # horizontal wave-mix fader
        hh = 15
        hy = top + max(0.0, (avail - hh) / 2.0)  # centre it in the cell
        return p.live("live.slider", [cx(COL_W - 10), hy, COL_W - 10, hh],
                      longname, 1, 0, 127, shortname=short, showname=0,
                      orientation=1, annotation=annotation, initial=initial,
                      extra_attrs={"slidercolor": COL_ACCENT})
    # K / B: rotary dial.
    return p.live("live.dial", [cx(DIAL), top, DIAL, DIAL],
                  longname, 1, 0, 127, shortname=short, showname=0,
                  annotation=annotation, initial=initial,
                  extra_attrs={"slidercolor": COL_ACCENT})


def place_label(p, cap, x, row_top, sn):
    p.comment(cap, [x, row_top, COL_W, LABEL_H],
              varname=sn + "_L", fontsize=8.0, justify=1, textcolor=COL_LABEL)


def route_out(p, kind, enum, cc, ctrl, midiformat, wx):
    """control -> [scale] -> prepend <cc> -> midiformat control inlet."""
    wy = 200 + cc * 8
    src, sout = ctrl, 0
    if kind == T:
        sc = p.obj("* 127", [wx + 600, wy, 50, 22], numinlets=2)
        p.connect(src, sout, sc, 0)
        src, sout = sc, 0
    elif kind == M:
        n = len(enum)
        step, base = round(128 / n), round(128 / n) // 2
        ex = p.obj("expr $i1 * %d + %d" % (step, base),
                   [wx + 600, wy, 110, 22], numinlets=1)
        p.connect(src, sout, ex, 0)
        src, sout = ex, 0
    pre = p.obj("prepend %d" % cc, [wx + 740, wy, 80, 22], numinlets=2)
    p.connect(src, sout, pre, 0)
    p.connect(pre, 0, midiformat, 2)


def route_in(p, kind, enum, cc, ctrl, wx):
    """[ctlin <cc>] -> [convert] -> prepend set -> control (no re-output).

    One ctlin per CC filters incoming control-change by number on any channel,
    so turning that knob on the Muse moves the matching on-screen control.  The
    `set` prefix updates the control's value/display without making it output,
    so nothing is echoed back to the synth (no feedback loop).
    """
    wy = 240 + cc * 8
    ci = p.obj("ctlin %d" % cc, [wx + 980, wy, 70, 22], numinlets=1,
               numoutlets=2, outlettype=["int", "int"])
    src, sout = ci, 0                                    # outlet 0 = value
    if kind == T:
        ge = p.obj(">= 64", [wx + 1060, wy, 50, 22], numinlets=2)
        p.connect(src, sout, ge, 0)
        src, sout = ge, 0
    elif kind == M:
        expr = " + ".join("($i1 > %d)" % b for b in BOUNDS[len(enum)])
        ex = p.obj("expr " + expr, [wx + 1060, wy, 150, 22], numinlets=1)
        p.connect(src, sout, ex, 0)
        src, sout = ex, 0
    ps = p.obj("prepend set", [wx + 1220, wy, 80, 22], numinlets=2)
    p.connect(src, sout, ps, 0)
    p.connect(ps, 0, ctrl, 0)


# --------------------------------------------------------------------------
# .amxd binary writer  (port of js2max/src/amxd/writer.ts)
# --------------------------------------------------------------------------
def be32(v):
    return struct.pack(">I", v)


def le32(v):
    return struct.pack("<I", v)


def tlv(tag, data):
    return tag.encode("ascii") + be32(8 + len(data)) + data


def tlv_u32(tag, val):
    return tlv(tag, be32(val))


def tlv_str(tag, s):
    enc = s.encode("ascii")
    pad = (4 - (len(enc) % 4)) % 4
    return tlv(tag, enc + b"\x00" * pad)


def make_dlst(filename, json_size):
    dire = tlv("dire", b"".join([
        tlv_str("type", "JSON"),
        tlv_str("fnam", filename),
        tlv_u32("sz32", json_size + 2),
        tlv_u32("of32", 16),
        tlv_u32("vers", 0),
        tlv_u32("flag", 0x11),
        tlv_u32("mdat", 0),
    ]))
    return tlv("dlst", dire)


def build_amxd(maxpat, device_code, filename):
    json_bytes = json.dumps(maxpat, indent="\t").encode("utf-8")
    json_size = len(json_bytes)
    separator = b"\x0a\x00"
    mx_val = json_size + len(separator) + 16
    mx_header = b"mx@c" + be32(16) + be32(0) + be32(mx_val)
    ptch = mx_header + json_bytes + separator + make_dlst(filename, json_size)
    return b"".join([
        b"ampf" + le32(4) + device_code.encode("ascii"),
        b"meta" + le32(4) + le32(7),
        b"ptch" + le32(len(ptch)) + ptch,
    ])


def main():
    longs = [c[1] for c in iter_controls()]
    assert len(longs) == len(set(longs)), "duplicate parameter long-name"
    slugs = [slug(n) for n in longs]
    assert len(slugs) == len(set(slugs)), "duplicate scripting name"

    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Build the MuseEditor tonight candidate")
    parser.add_argument("--output-dir", default="build/tonight-r2")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    maxpat_path = output / "MuseEditor Tonight r2.maxpat"
    amxd_path = output / "MuseEditor Tonight r2.amxd"
    patch = build()
    maxpat = patch.to_maxpat()
    with maxpat_path.open("w") as f:
        json.dump(maxpat, f, indent="\t")
    amxd = build_amxd(maxpat, "mmmm", amxd_path.name)
    with amxd_path.open("wb") as f:
        f.write(amxd)

    # report max presentation Y so we know it fits the 169px device height
    maxy = max((b["box"]["presentation_rect"][1] +
                b["box"]["presentation_rect"][3])
               for b in maxpat["patcher"]["boxes"]
               if b["box"].get("presentation"))
    print("Parameters: %d across %d tabs" % (len(longs), len(TABS)))
    print("Max presentation Y: %.0f px (must be <= 169)" % maxy)
    print("Wrote %s (%d bytes) and %s" %
          (amxd_path, len(amxd), maxpat_path))


if __name__ == "__main__":
    main()
