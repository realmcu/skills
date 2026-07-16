#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clock_calc.py — RTL display clock: Calculate register divider values from
panel spec's max interface clock frequency.

Supports three chips (--chip, default 8773g) and three interfaces (--iface).
**Divider formula is identical for all three chips**, differences are only in
1) clock source frequency, 2) source selection method (see comments under each
chip):

    qspi : QSPI_clock = src / (2 * DBIC_SPEED_SEL)
    rgb  : PCLK       = src / eDPI_ClockDiv           (input IS the divider, no +/-1, min 2)
    dbib : DBIB_clock = src / (2 * DBIB_Clock_Divider) (DBIB_Clock_Divider 2..64)

Each chip clock source and selection method:
    8773g : Sources 200M/280M(+40M); QSPI uses LCDC_Clock_Sel, RGB/DBIB use
            RCC_DisplayClockConfig
    8773e : Sources PLL1=200M/PLL2=160M/XTAL=40M (no PLL3); all three
            interfaces use RCC_DisplayClockConfig
    8762g : Sources PLL1=125M/PLL2=160M/XTAL=40M; no API, write bitfield
            PERIBLKCTRL_PERI_CLK->u_324.BITS_324

Divider values (from hardware headers, same for all three chips):
    qspi DBIC_SPEED_SEL     : integer (default 1), this script enumerates 1..16
    rgb  eDPI_ClockDiv      : write divider directly (input IS the divider, no
                              +/-1); this script enumerates 2..64
    dbib DBIB_Clock_Divider : 2..64

Selection rule: actual frequency must **not exceed** --max; if --typical is
given, pick the one closest to typical, otherwise pick the highest <=max.

Usage:
    python clock_calc.py --chip 8773g --iface qspi --max 80 --typical 60
    python clock_calc.py --chip 8773e --iface rgb  --max 30
    python clock_calc.py --chip 8762g --iface qspi --max 40
    python clock_calc.py --chip 8762g --iface rgb  --max 12 --src 125

Note: --max / --typical are panel spec timing values and should be confirmed by
the customer after reading the spec (safety-critical, do not auto-trust
parsing).
"""

import argparse
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


# Interface definitions: divider formula, divider range, formula text (shared across chips)
IFACES = {
    "qspi": {
        "freq": lambda src, d: src / (2.0 * d),
        "divs": range(1, 17),
        "formula": "src / (2 * DBIC_SPEED_SEL)",
    },
    "rgb": {
        "freq": lambda src, d: src / float(d),
        "divs": range(2, 65),                # eDPI divider (integer, input IS the divider, no +/-1)
        "formula": "src / eDPI_ClockDiv",
    },
    "dbib": {
        "freq": lambda src, d: src / (2.0 * d),
        "divs": range(2, 65),                # DBIB_Clock_Divider 2..64
        "formula": "src / (2 * DBIB_Clock_Divider)",
    },
}

# Default candidate sources per chip per interface (MHz); --src can override
CHIP_IFACE_SRC = {
    "8773g": {"qspi": [200, 280], "rgb": [200],      "dbib": [40, 200, 280]},
    "8773e": {"qspi": [200, 160], "rgb": [200, 160], "dbib": [40, 200, 160]},
    "8762g": {"qspi": [125, 160], "rgb": [125, 160], "dbib": [40, 125, 160]},
}

# All valid sources per chip (for --src validation)
CHIP_VALID_SRC = {
    "8773g": {40, 200, 280},
    "8773e": {40, 160, 200},
    "8762g": {40, 125, 160},
}

# RCC_DisplayClockConfig source enum (used by 8773g rgb/dbib, all 8773e interfaces)
RCC_ENUM = {
    ("8773g", 200): "DISPLAY_CLOCK_SOURCE_PLL1",
    ("8773g", 40):  "DISPLAY_CLOCK_SOURCE_40MHZ",
    ("8773e", 200): "DISPLAY_CLOCK_SOURCE_PLL1",
    ("8773e", 160): "DISPLAY_CLOCK_SOURCE_PLL2",
    ("8773e", 40):  "DISPLAY_CLOCK_SOURCE_40MHZ",
}


def default_src(chip, iface):
    return CHIP_IFACE_SRC[chip][iface]


def valid_src(chip, iface):
    """Return the set of allowed sources for the given chip and interface."""
    if chip == "8773g" and iface == "qspi":
        return {200, 280}          # LCDC_Clock_Sel only supports 200/280
    return CHIP_VALID_SRC[chip]


def emit_src(chip, iface, src):
    """Emit source selection code lines (list of str), varies by chip/interface."""
    src = int(src)
    if chip == "8773g" and iface == "qspi":
        return ["LCDC_Clock_Sel(LCDC_BUS_CLK_%dM);" % src]
    if chip == "8762g":
        lines = [
            "PERIBLKCTRL_PERI_CLK->u_324.BITS_324.disp_ck_en          = 1;",
            "PERIBLKCTRL_PERI_CLK->u_324.BITS_324.disp_func_en        = 1;",
            "PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_mux_clk_cg_en = 1;",
        ]
        if src == 40:
            lines.append("/* Source = XTAL 40MHz: leave the PLL select bitfield below unwritten (defaults to 40M) */")
        else:
            sel0 = 0 if src == 125 else 1   # 125->PLL1, 160->PLL2
            lines += [
                "PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_div_en       = 1;",
                "PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_clk_src_sel0 = %d;  /* 0=PLL1(125M), 1=PLL2(160M) */" % sel0,
                "PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_clk_src_sel1 = 1;  /* 1=PLL, 0=XTAL(40M) */",
                "PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_div_sel      = 1;  /* Delegate division to interface */",
            ]
        return lines
    # Everything else uses RCC_DisplayClockConfig (8773g rgb/dbib, all 8773e)
    enum = RCC_ENUM.get((chip, src))
    if enum:
        return ["RCC_DisplayClockConfig(%s, DISPLAY_CLOCK_DIV_1);" % enum]
    return ["/* Source %dMHz: use RCC_DisplayClockConfig to select this source (no matching enum, please confirm manually) */" % src]


def candidates(iface, sources):
    cfg = IFACES[iface]
    out = []
    for src in sources:
        for d in cfg["divs"]:
            out.append({"src": src, "div": d, "freq": cfg["freq"](src, d)})
    return out


def choose(cands, max_mhz, typical_mhz):
    valid = [c for c in cands if c["freq"] <= max_mhz + 1e-9]
    if not valid:
        return None
    if typical_mhz is not None:
        valid.sort(key=lambda c: (abs(c["freq"] - typical_mhz), -c["freq"], c["div"]))
    else:
        valid.sort(key=lambda c: (-c["freq"], c["div"]))
    return valid[0]


def emit(chip, iface, best):
    """Print ready-to-paste configuration code: select source first, then write divider."""
    src, d, f = best["src"], best["div"], best["freq"]
    if iface == "qspi":
        print("/* QSPI clock = %d / (2 * %d) = %.2f MHz */" % (src, d, f))
        for line in emit_src(chip, iface, src):
            print(line)
        print("dbic_init.DBIC_SPEED_SEL = %d;" % d)
    elif iface == "rgb":
        print("/* eDPI PCLK = %d / %d = %.2f MHz */" % (src, d, f))
        for line in emit_src(chip, iface, src):
            print(line)
        macro_hint = (", also available as EDPI_CLOCKDIV%d" % d) if 2 <= d <= 8 else "(>8 no matching macro, write raw int)"
        print("eDPICfg.eDPI_ClockDiv = %d;   /* = %d/%d = %.2f MHz; write divider directly (min 2)%s */"
              % (d, src, d, f, macro_hint))
    elif iface == "dbib":
        print("/* DBIB clock = %d / (2 * %d) = %.2f MHz */" % (src, d, f))
        for line in emit_src(chip, iface, src):
            print(line)
        print("dbib_init.DBIB_Clock_Divider = %d;" % d)


def main():
    ap = argparse.ArgumentParser(description="RTL display interface clock divider calculation (chip: 8773g/8773e/8762g; iface: qspi/rgb/dbib)")
    ap.add_argument("--chip", choices=list(CHIP_IFACE_SRC), default="8773g", help="Target chip (default 8773g)")
    ap.add_argument("--iface", choices=list(IFACES), default="qspi", help="Interface type")
    ap.add_argument("--max", dest="max_mhz", type=float, required=True, help="Panel max interface clock (MHz)")
    ap.add_argument("--typical", dest="typical_mhz", type=float, default=None, help="Panel typical clock (MHz, optional)")
    ap.add_argument("--src", default=None, help="Override candidate source list, comma-separated MHz, e.g. 125 or 200,160")
    ap.add_argument("--top", type=int, default=6, help="Number of candidates to display")
    args = ap.parse_args()

    chip, iface = args.chip, args.iface

    if args.src:
        req = [int(float(x)) for x in args.src.split(",") if x.strip()]
        allowed = valid_src(chip, iface)
        bad = [s for s in req if s not in allowed]
        if bad:
            sys.stderr.write("warn: [%s/%s] sources can only be %s, ignoring %s\n"
                             % (chip, iface, sorted(allowed), bad))
        sources = [s for s in req if s in allowed] or default_src(chip, iface)
    else:
        sources = default_src(chip, iface)

    if args.typical_mhz is not None and args.typical_mhz > args.max_mhz:
        sys.stderr.write("warn: typical(%.3g) > max(%.3g), using max as hard upper limit\n" % (args.typical_mhz, args.max_mhz))

    cands = candidates(iface, sources)
    best = choose(cands, args.max_mhz, args.typical_mhz)
    if best is None:
        sys.stderr.write("error: [%s/%s] no combination <= %.3g MHz found in sources %s\n"
                         % (chip, iface, sources, args.max_mhz))
        sys.exit(2)

    shortlist = sorted([c for c in cands if c["freq"] <= args.max_mhz + 1e-9],
                       key=lambda c: (-c["freq"], c["div"]))[:args.top]
    sys.stderr.write("[%s/%s] %s, candidates (freq <= %.3g MHz):\n"
                     % (chip, iface, IFACES[iface]["formula"], args.max_mhz))
    for c in shortlist:
        mark = "  <== Recommended" if c is best else ""
        sys.stderr.write("  src=%-4dMHz div=%-3d -> %7.2f MHz%s\n"
                         % (c["src"], c["div"], c["freq"], mark))

    emit(chip, iface, best)


if __name__ == "__main__":
    main()
