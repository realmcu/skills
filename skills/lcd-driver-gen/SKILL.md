---
name: lcd-driver-gen
description: >
  Generate a low-level driver for a new LCD panel in the Realtek display repository.
  Strategy: "clone an existing driver + replace only the real variables":
  From device/general/lcd/<chip>/, pick a verified driver with the same interface as a template,
  replace model/resolution/pins/color-depth/init sequence,
  translate the vendor datasheet's init paragraphs into the target driver's representation style,
  and finally register in Kconfig / CMakeLists.txt / SConscript.
  Current scope: single-chip new drivers (choose one of 8773E / 8773G / 8762G).
  Trigger: user says "generate/add a panel driver", "add an LCD panel", "port a panel",
  "add st77916 driver for 8773G", "generate init sequence from datasheet", etc.
---

# lcd-driver-gen — Generate LCD Panel Low-Level Driver

Targets `D:\Repositories\display\display`, generates a single-panel driver implementing `rtk_lcd_hal_*`.

**Core principle: never write register ops from scratch.** Clone the verified driver of the same interface; replace model, resolution, pins, color depth, init sequence.

## Parameter Collection Protocol (strictly follow this)

### Mandatory Rules

1. **Ask only 1 spec-dependent question per turn.** Simple short facts (model/resolution/interface/chip) can be asked together.
2. **Never offer "use a default placeholder" options.** Timing, pins, color depth, Group, colormap, and clock have no defaults.
3. **User does not respond within 60s → re-ask; do not proceed with placeholder values.** Better to block than generate wrong output.
4. **Record each parameter to project memory** before asking the next question.

The following 4 short facts can be asked in one AskUserQuestion:
- Panel model (e.g. `st77916`)
- Resolution (e.g. `360x360`)
- Interface type (QSPI / RGB / 8080 / SPI / RLSPI)
- Target chip (8773G / 8773E / 8762G)

### Round 1: Basic Info

Ask the 4 facts above together. Record answers, then proceed to Round 2.

### Round 2: Interface-Specific Parameters (one at a time, do NOT batch)

Branch by interface from Round 1. Each question uses a separate AskUserQuestion.

#### QSPI Branch

1. INPUT (framebuffer) bytes per pixel? → `INPUT_PIXEL_BYTES = 2/3/4`
2. OUTPUT (on-wire) bytes per pixel? → `OUTPUT_PIXEL_BYTES = 2/3`
3. Which QSPI Group? → Group1 / Group2 / Group3
4. TE needed? → pin number or `TE_VALID=0`
5. RS/D-C pin needed? (9-bit QSPI) → pin number
6. RST pin number?
7. BL or PWR_EN pin needed? → pin number
8. Max SCLK from AC Timing table? (required); typical (optional)
9. Init sequence? → paste datasheet if yes
10. Select reference driver → skill recommends closest-resolution, **wait for confirmation**

#### RGB Branch

1. INPUT format? → `LCDC_INPUT_RGB565` or `LCDC_INPUT_RGB888`
2. OUTPUT format? → `RGB565` or `RGB888`
   - If 565 → also ask which colormap: `EDPI_PIXELFORMAT_RGB565_1` / `_2` / `_3`
   - If 888 → colormap `EDPI_PIXELFORMAT_RGB888`
3. Group0 or Group1?
4. RST pin number?
5. BL pin needed? → pin number
6. Max PCLK from AC Timing? (required); typical (optional)
7. **6 timing values**: HSA / HBP / HFP + VSA / VBP / VFP (from RGB/DPI Timing table)
8. Init sequence? (need separate SPI?) → paste if yes; SPI pins/init are your responsibility
9. Select reference driver → skill recommends closest-resolution, **wait for confirmation**

#### 8080(DBIB) / SPI / RLSPI Branch

Same structure as QSPI; interface-specific details in `references/interface-map.md`.

## Main Flow (6 Steps)

1. **Collect Parameters**: Follow the protocol above. Record each answer to project memory (`C:\Users\astor_zhang\.claude\projects\D--Repositories-display-display\memory\`). Do NOT proceed until all parameters are collected.
2. **Select Template Source**: Read `references/interface-map.md`, check target chip dir for existing `.c/.h` of same interface.
   - **Reference exists** → pick closest-resolution driver; note its init style (table-driven or inline).
   - **No reference** → read `references/code-skeletons.md`, take the interface+chip block, replace template variables.
3. **Convert Init Sequence**: Run `scripts/seq_convert.py`:
   ```
   python .claude/skills/lcd-driver-gen/scripts/seq_convert.py \
       --in <file or paste> --style <qspi-table|inline> --prefix <PANEL_MACRO>
   ```
   Review delays (~120ms after 0x11, ~20ms after 0x29), param count, 0x3A.
4. **Rewrite the Driver**: Based on template/skeleton, replace:
   - Filename, header guard, includes, macros per `references/hal-contract.md` §1
   - Pin macros → `references/pins-<chip>.md`
   - `set_window` 0x2A/0x2B/0x2C (check x/y offset)
   - RGB timing → `references/rgb-timing.md`
   - Clock → `clock_calc.py --chip <chip> --iface <iface> --max <mhz> [--typical <mhz>]`; source per `references/clock-<chip>.md`
   - Reset → `references/reset-sequence.md`
   - Init sequence from step 3
   - HAL functions per `references/hal-contract.md` (§5 for RGB data path)
   - Register 3 places per `references/registration.md`
5. **Register in 3 Places**: Modify Kconfig, CMakeLists.txt, SConscript per `references/registration.md`. **Cross-check CONFIG_ symbol is byte-identical in all three** — historically bug-prone.
6. **Output the Checklist Below**: Present each item for manual confirmation.

## Self-Check Checklist (output after every generation)

- [ ] CONFIG symbol matches across Kconfig/CMakeLists/SConscript byte-identically
- [ ] HAL surface + `T_LCDC_TE_TYPE` enum = `references/hal-contract.md` spec (verbatim)
- [ ] `power_on/off` return `bool` — **do NOT copy template** (legacy mixes `bool`/`uint32_t`)
- [ ] `init` retains INPUT/OUTPUT `#if` blocks; `clear_screen` packs per INPUT, `0x3A` per OUTPUT
- [ ] Header macros: `<MODEL>_<W>_<H>_LCD_WIDTH/_LCD_HEIGHT` (infix mandatory); `_DRV_PIXEL_BITS` infix per interface; `INPUT/OUTPUT_PIXEL_BYTES`/`TE_VALID` only for GRAM, **not in RGB headers**
- [ ] `INPUT=3` → `LCD_WIDTH` 4-pixel-aligned or DMA misaligns. Don't copy deprecated `#error`
- [ ] QSPI: commands in `CMD_DESC.index`, `instruction=0x02`; SPI/8080/RGB send bytes directly
- [ ] Color depth changes only `OUTPUT_PIXEL_BYTES`; DMA `DataSize=Word` fixed; `Msize+DmaThreshold=128`
- [ ] Pins per target chip doc: 8773E (`pins-8773e.md`), 8773G QSPI (`pins-8773g-qspi.md`), 8773G RGB (`pins-8773g-rgb.md`), 8773G DBIB (`pins-8773g-dbib.md`), 8762G (`pins-8762g.md`)
- [ ] 8773G RGB: `INPUT`/`OUTPUT`/`eDPI_ColorMap` are independent; mixed formats valid (e.g. EK9716 INPUT=565/OUTPUT=888/colormap=888)
- [ ] RLSPI: no-GRAM confirmed; `RamlessEn=ENABLE`; struct/spec per `references/ramless-qspi.md`
- [ ] Clock ≤ panel spec max; source/selection per `references/clock-<chip>.md`
- [ ] eDPI: `eDPI_ClockDiv` = raw divisor (no ±1), min 2, bare integer
- [ ] RGB data path: `set_window/clear_screen/start_transfer/transfer_done` all empty `return;`; data = `<panel>_dma_init()` (LLI: block=1 row, sar_offset=2 rows) + `update_framebuffer` (first→init, later→`Infinite_Buf_Update`)
- [ ] RGB extra SPI: user-configured, skill leaves call sites only, **no hardcoded periph/pin**
- [ ] Reset: HIGH→LOW→HIGH, t3 ≥120ms before commands, power stable first
- [ ] `set_window` x/y offset needed? (some panels GRAM not at 0,0)
- [ ] Init seq ends with terminator (QSPI: `SEQ_FINISH_CODE`)
- [ ] Delays preserved after 0x11 (~120ms) and 0x29 (~20ms)

## Reference Docs

- `references/hal-contract.md` — `rtk_lcd_hal_*` unified contract: functions, enum, macros, pixel format; §5 = RGB data path differences
- `references/code-skeletons.md` — Full code skeletons (3 interfaces × 3 platforms) for no-reference case
- `references/interface-map.md` — Interface → header → style → recommended drivers
- `references/registration.md` — Kconfig/CMakeLists/SConscript templates
- `references/pins-8773e.md` — 8773E pins: RGB/QSPI 2 groups each, 8080 Group0, CM=ADC3
- `references/pins-8773g-qspi.md` — 8773G QSPI 2 groups + GroupSel mapping
- `references/pins-8773g-rgb.md` — 8773G RGB 2 groups + colormap → D-line mapping
- `references/pins-8773g-dbib.md` — 8773G DBIB: Group0, 8-bit, RD# conflict
- `references/pins-8762g.md` — 8762G: RGB single port, QSPI 3 groups, 8080 3 groups, no HighSpeed*
- `references/clock-8773g.md` — 8773G clock: src 200M/280M, formulas
- `references/clock-8773e.md` — 8773E clock: src PLL1/PLL2/40M, unified RCC API
- `references/clock-8762g.md` — 8762G clock: src PLL1/PLL2/40M, BITS_324 bitfield
- `references/rgb-timing.md` — Timing params: names, acquisition, register formulas, bit-width limits
- `references/ramless-qspi.md` — RLSPI: no-GRAM, register mapping, init table (0xDE)
- `references/reset-sequence.md` — Reset waveform, safe defaults, edge cases
- `scripts/seq_convert.py` — Datasheet → normalized sequence → target style
- `scripts/clock_calc.py` — `--chip 8773g|8773e|8762g --iface qspi|rgb|dbib`: clock → register divider
