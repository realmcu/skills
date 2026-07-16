#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seq_convert.py — Convert LCD initialization sequences from vendor datasheets
to driver init sequence code.

Pipeline: datasheet paragraph text --> normalized intermediate representation
[(cmd, [params...], delay_ms)] --> target style rendering.

Supported input forms (auto-detected, can be mixed):
  A. Function-call style (common in repo .txt files):
       write_command(0x11);
       platform_delay_ms(120);
       write_command(0xFF); write_data(0x77); write_data(0x01);
      Compatible aliases: WriteComm/WriteData/wr_cmd/wr_dat/LCD_WR_REG/LCD_WR_DATA/DBI_WriteCmd...
      Delay aliases: platform_delay_ms/delay_ms/DelayMs/Delay/mdelay/msleep/Delayms
  B. Table/hex style (each line: command params ..., may include delay=NN or
     trailing comments):
       0xFF 0x77 0x01 0x00 0x00 0x10
       0x11 delay=120
       0xF0,0x28

Output styles:
  --style qspi-table   Generate QSPI CMD_DESC[] table (instruction always the
                       write opcode, command goes in index)
  --style inline       Generate inline write_command()/write_data()/
                       platform_delay_ms() calls (RGB/SPI/8080)

Usage:
  python seq_convert.py --in seq.txt --style qspi-table --prefix ST77916
  cat seq.txt | python seq_convert.py --style inline --cmd-fn st7789_cmd --data-fn st7789_data

Note: This script handles "translation", does not guarantee correctness.
Always verify delays (0x11/0x29), parameter counts, and color depth command
(0x3A) after generation. This is an initial scaffold; parsing rules will be
refined with real datasheet cases.
"""

import argparse
import re
import sys

# Force UTF-8 output to prevent Windows console codepage from garbling output
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# ---- Regex: scan all tokens in order ------------------------------------------

_CMD_ALIASES = r"write_command|writecomm|wr_cmd|wr_reg|lcd_wr_reg|dbi_writecmd|spi_writecmd|write_cmd"
_DAT_ALIASES = r"write_data|writedata|wr_dat|wr_data|lcd_wr_data|dbi_writedata|spi_writedata"
_DLY_ALIASES = r"platform_delay_ms|platform_delay|delay_ms|delayms|mdelay|msleep|delay"

_NUM = r"(0x[0-9a-fA-F]+|\d+)"

_TOKEN_RE = re.compile(
    r"(?P<cmd>(?:%s)\s*\(\s*%s\s*\))"
    r"|(?P<dat>(?:%s)\s*\(\s*%s\s*\))"
    r"|(?P<dly>(?:%s)\s*\(\s*(\d+)\s*\))" % (_CMD_ALIASES, _NUM, _DAT_ALIASES, _NUM, _DLY_ALIASES),
    re.IGNORECASE,
)
_INNER_NUM_RE = re.compile(_NUM)


def _to_int(tok):
    tok = tok.strip()
    return int(tok, 16) if tok.lower().startswith("0x") else int(tok)


def parse_function_style(text):
    """Parse write_command/write_data/delay form. Returns [(cmd, [params], delay)] or None (not recognized)."""
    matches = list(_TOKEN_RE.finditer(text))
    if not matches:
        return None
    seq = []
    cur = None  # [cmd, params, delay]
    for m in matches:
        if m.group("cmd") is not None:
            val = _to_int(_INNER_NUM_RE.search(m.group("cmd")).group(0))
            cur = [val, [], 0]
            seq.append(cur)
        elif m.group("dat") is not None:
            val = _to_int(_INNER_NUM_RE.search(m.group("dat")).group(0))
            if cur is None:
                # data before any command -- abnormal, skip and warn
                sys.stderr.write("warn: write_data before any command, skipped: 0x%02X\n" % val)
                continue
            cur[1].append(val)
        else:  # delay
            val = int(re.search(r"\d+", m.group("dly")).group(0))
            if cur is None:
                sys.stderr.write("warn: delay before any command (%d ms), skipped\n" % val)
                continue
            cur[2] = val
    return seq


def parse_table_style(text):
    """Parse table/hex format: each line 'command params...'."""
    seq = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        line = re.split(r"//|/\*", line, 1)[0].strip()  # strip trailing comments
        if not line:
            continue
        delay = 0
        m = re.search(r"delay\s*[=:]?\s*(\d+)", line, re.IGNORECASE)
        if m:
            delay = int(m.group(1))
            line = (line[:m.start()] + line[m.end():]).strip()
        nums = _INNER_NUM_RE.findall(line)
        if not nums:
            continue
        vals = [_to_int(n) for n in nums]
        seq.append([vals[0], vals[1:], delay])
    return seq or None


def parse(text):
    seq = parse_function_style(text)
    if seq:
        return seq
    seq = parse_table_style(text)
    if seq:
        return seq
    sys.stderr.write("error: could not identify any init commands from input\n")
    sys.exit(2)


# ---- Rendering ----------------------------------------------------------------

def render_qspi_table(seq, prefix, write_op=0x02, indent="    "):
    P = prefix.upper()
    lines = []
    lines.append("/* Generated by seq_convert.py -- verify delays & param counts; replace %s prefix. */" % P)
    lines.append("static const %s_CMD_DESC %s_POWERON_SEQ_CMD[] =" % (P, P))
    lines.append("{")
    for cmd, params, delay in seq:
        wc = len(params)
        payload = ", ".join("0x%02X" % p for p in params) if params else "0x00"
        lines.append("%s{0x%02X, 0x%02X, %d, %d, {%s}}," % (indent, write_op, cmd, delay, wc, payload))
    lines.append("%s{0x00, 0, 0, 0, {0}}, /* SEQ_FINISH_CODE */" % indent)
    lines.append("};")
    max_para = max((len(p) for _, p, _ in seq), default=0)
    lines.insert(0, "/* Suggest: #define %s_MAX_PARA_COUNT %d (max param count, leave margin) */" % (P, max(max_para, 1)))
    return "\n".join(lines)


def render_inline(seq, cmd_fn, data_fn, delay_fn, indent=""):
    lines = ["/* Generated by seq_convert.py -- verify delays & param counts. */"]
    for cmd, params, delay in seq:
        lines.append("%s%s(0x%02X);" % (indent, cmd_fn, cmd))
        for p in params:
            lines.append("%s%s(0x%02X);" % (indent, data_fn, p))
        if delay:
            lines.append("%s%s(%d);" % (indent, delay_fn, delay))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="datasheet init sequence -> driver init sequence code")
    ap.add_argument("--in", dest="infile", help="Input file; if omitted, read from stdin")
    ap.add_argument("--style", required=True, choices=["qspi-table", "inline"])
    ap.add_argument("--prefix", default="PANEL", help="qspi-table: macro/type prefix, e.g. ST77916")
    ap.add_argument("--write-op", default="0x02", help="qspi-table: QSPI write opcode, default 0x02")
    ap.add_argument("--cmd-fn", default="write_command", help="inline: command function name")
    ap.add_argument("--data-fn", default="write_data", help="inline: data function name")
    ap.add_argument("--delay-fn", default="platform_delay_ms", help="inline: delay function name")
    args = ap.parse_args()

    text = open(args.infile, "r", encoding="utf-8", errors="replace").read() if args.infile else sys.stdin.read()
    seq = parse(text)

    if args.style == "qspi-table":
        out = render_qspi_table(seq, args.prefix, write_op=_to_int(args.write_op))
    else:
        out = render_inline(seq, args.cmd_fn, args.data_fn, args.delay_fn)

    sys.stdout.write(out + "\n")
    sys.stderr.write("ok: parsed %d commands\n" % len(seq))


if __name__ == "__main__":
    main()
