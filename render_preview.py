#!/usr/bin/env python3
"""
render_preview.py
=================

Renders ``layout_preview.svg`` - a static visual mock-up of every tab in the
MuseEditor device.  It imports the authoritative layout (TABS, the palette and
the geometry constants) from ``generate_device.py`` and reproduces the exact
positions/sizes that ``make_control`` uses, so the preview always matches the
generated device.

Each tab is drawn as one stacked panel; controls are drawn the way Live draws
them: dials as arc knobs, faders as vertical/horizontal sliders, on/off
parameters as labelled accent buttons, multi-option parameters as menus.

Run:  python3 render_preview.py   (standard library only)
"""

import generate_device as G

K, B, T, M, S, H, PB = G.K, G.B, G.T, G.M, G.S, G.H, G.PB
COL_W, SEC_PAD_X, SEC_GAP = G.COL_W, G.SEC_PAD_X, G.SEC_GAP
SEC_TITLE_H, SLIDER_W, DIAL = G.SEC_TITLE_H, G.SLIDER_W, G.DIAL
LABEL_H, LABEL_GAP, MARGIN = G.LABEL_H, G.LABEL_GAP, G.MARGIN
SEC_H = G.SEC_H
W = G.DEVICE_WIDTH


def rgba(c):
    r, g, b, a = c
    return "rgba(%d,%d,%d,%g)" % (round(r * 255), round(g * 255),
                                  round(b * 255), a)


PANEL = rgba(G.COL_PANEL)
BORDER = rgba(G.COL_BORDER)
ACCENT = rgba(G.COL_ACCENT)
TITLE = rgba(G.COL_TITLE)
LABEL = rgba(G.COL_LABEL)
BTN_OFF = rgba(G.COL_BTN_OFF)
BTN_TXT = rgba(G.COL_BTN_TXT)
WHITE = rgba(G.COL_WHITE)
BG = "rgb(43,44,47)"          # Live device background (approximate)
DIAL_TRK = "rgba(255,255,255,0.14)"

TAB_H = 16
TAB_GAP = 24                  # vertical gap between stacked tab mock-ups
DEVH = 5 + TAB_H + SEC_H + 8  # one tab's drawn height


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, s, fill, size=8, anchor="middle", weight="normal"):
    return ('<text x="%.1f" y="%.1f" fill="%s" font-size="%d" '
            'font-family="Helvetica,Arial,sans-serif" font-weight="%s" '
            'text-anchor="%s">%s</text>'
            % (x, y, fill, size, weight, anchor, esc(s)))


def dial(cx, cy, r):
    """A knob: track ring + accent arc (~210 deg) + indicator."""
    import math
    out = ['<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" stroke="%s" '
           'stroke-width="2.2"/>' % (cx, cy, r, DIAL_TRK)]
    a0, a1 = 130, 130 + 210 * 0.7
    p0 = (cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0)))
    p1 = (cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1)))
    out.append('<path d="M %.1f %.1f A %.1f %.1f 0 0 1 %.1f %.1f" fill="none" '
               'stroke="%s" stroke-width="2.2"/>'
               % (p0[0], p0[1], r, r, p1[0], p1[1], ACCENT))
    ix, iy = cx + r * 0.55 * math.cos(math.radians(a1)), \
        cy + r * 0.55 * math.sin(math.radians(a1))
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
               'stroke-width="1.6"/>' % (cx, cy, ix, iy, WHITE))
    return "".join(out)


def control_svg(kind, short, x, row_top, band):
    """Reproduce make_control's geometry for one cell at (x, row_top)."""
    top = row_top + LABEL_H + LABEL_GAP
    avail = band - LABEL_H - LABEL_GAP - 2
    out = []

    def cx(w):
        return x + (COL_W - w) / 2.0

    def label():
        out.append(text(x + COL_W / 2.0, row_top + 8, short, LABEL, 8))

    if kind == T:
        bw, bh = COL_W - 6, 17
        by = row_top + max(0.0, (band - bh) / 2.0)
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2.5" '
                   'fill="%s" stroke="%s" stroke-width="1"/>'
                   % (cx(bw), by, bw, bh, BTN_OFF, BORDER))
        out.append(text(x + COL_W / 2.0, by + bh / 2.0 + 3, short, BTN_TXT, 8))
        return "".join(out)
    if kind == M:
        label()
        w = COL_W - 8
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="18" rx="2.5" '
                   'fill="%s" stroke="%s" stroke-width="1"/>'
                   % (cx(w), top, w, BTN_OFF, BORDER))
        out.append(text(cx(w) + 6, top + 12, short, BTN_TXT, 8, anchor="start"))
        out.append('<path d="M %.1f %.1f l 4 0 l -2 4 z" fill="%s"/>'
                   % (cx(w) + w - 10, top + 6, BTN_TXT))
        return "".join(out)
    if kind == S:
        label()
        h = max(24.0, avail)
        sx = cx(SLIDER_W)
        out.append('<rect x="%.1f" y="%.1f" width="%d" height="%.1f" rx="2" '
                   'fill="%s" stroke="%s" stroke-width="1"/>'
                   % (sx, top, SLIDER_W, h, BTN_OFF, BORDER))
        fill_h = h * 0.55
        out.append('<rect x="%.1f" y="%.1f" width="%d" height="%.1f" rx="2" '
                   'fill="%s"/>'
                   % (sx, top + h - fill_h, SLIDER_W, fill_h, ACCENT))
        out.append('<rect x="%.1f" y="%.1f" width="%d" height="3" fill="%s"/>'
                   % (sx, top + h - fill_h - 1, SLIDER_W, WHITE))
        return "".join(out)
    if kind == H:
        label()
        hh = 15
        w = COL_W - 10
        hy = top + max(0.0, (avail - hh) / 2.0)
        sx = cx(w)
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="2" '
                   'fill="%s" stroke="%s" stroke-width="1"/>'
                   % (sx, hy, w, hh, BTN_OFF, BORDER))
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="2" '
                   'fill="%s"/>' % (sx, hy, w * 0.5, hh, ACCENT))
        out.append('<rect x="%.1f" y="%.1f" width="3" height="%d" fill="%s"/>'
                   % (sx + w * 0.5 - 1, hy, hh, WHITE))
        return "".join(out)
    # K / B / PB -> dial
    label()
    out.append(dial(x + COL_W / 2.0, top + DIAL / 2.0, DIAL / 2.0))
    return "".join(out)


def render():
    tab_labels = [t[0] for t in G.TABS] + ["BANK", "MISC"]
    rows_out = []
    y = 0
    parts = []
    total_h = (DEVH + TAB_GAP) * len(G.TABS) + 80

    parts.append('<rect x="0" y="0" width="%d" height="%d" fill="rgb(30,30,32)"/>'
                 % (W + 2 * MARGIN, total_h))

    for ti, (name, sections) in enumerate(G.TABS):
        oy = y
        # device background slab for this tab
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s"/>'
                     % (MARGIN, oy, W, DEVH, BG))
        # tab strip
        tw = (W - 2 * MARGIN - 220) / float(len(tab_labels))
        for li, lab in enumerate(tab_labels):
            on = (li == ti)
            tx = MARGIN + li * tw
            parts.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" '
                         'fill="%s" stroke="%s" stroke-width="0.5"/>'
                         % (tx, oy + 5, tw, TAB_H,
                            ACCENT if on else "rgb(55,56,60)", BORDER))
            parts.append(text(tx + tw / 2.0, oy + 5 + 11, lab,
                              WHITE if on else LABEL, 7,
                              weight="bold" if on else "normal"))
        hx = W - MARGIN - 212
        for offset, width, label in [(0, 72, "OUTPUT OFF"), (76, 72, "THRU OFF"), (152, 60, "PANIC")]:
            parts.append('<rect x="%.1f" y="%d" width="%d" height="16" rx="2" fill="%s" stroke="%s"/>'
                         % (hx + offset, oy + 5, width, BTN_OFF, BORDER))
            parts.append(text(hx + offset + width/2, oy + 16, label, BTN_TXT, 8))
        # sections
        sx = MARGIN
        for title, rows in sections:
            sec_w = G.section_width(rows)
            sy = oy + G.SEC_TOP
            parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%d" '
                         'rx="6" fill="%s" stroke="%s" stroke-width="1"/>'
                         % (sx, sy, sec_w, SEC_H, PANEL, BORDER))
            parts.append(text(sx + 6, sy + 11, title, TITLE, 8,
                              anchor="start", weight="bold"))
            parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="1" '
                         'fill="%s"/>'
                         % (sx + 6, sy + SEC_TITLE_H - 1, sec_w - 12, ACCENT))
            body_top = sy + SEC_TITLE_H + 3
            band = (SEC_H - SEC_TITLE_H - 6) / len(rows)
            for ri, row in enumerate(rows):
                row_top = body_top + ri * band
                for ci, (cc, longname, kind, enum, short) in enumerate(row):
                    cellx = sx + SEC_PAD_X + ci * COL_W
                    parts.append(control_svg(kind, short, cellx, row_top, band))
            sx += sec_w + SEC_GAP
        y += DEVH + TAB_GAP

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d">%s</svg>'
           % (W + 2 * MARGIN, total_h, W + 2 * MARGIN, total_h, "".join(parts)))
    from pathlib import Path
    output = Path("build/tonight-r2/layout_preview.svg")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg)
    print("Wrote %s (%d tabs, device %dpx wide)" % (output, len(G.TABS), W))


if __name__ == "__main__":
    render()
