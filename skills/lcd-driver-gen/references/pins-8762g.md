# RTL8762G Display Pins (RGB / eDPI + QSPI + 8080 / DBIB)

RTL8762G display pins: **RGB is a single physical parallel port** (with 4 color mappings: RGB888 + RGB565 Config1/2/3),
**QSPI has 3 groups (Group1 / Group2 / Group3)**, **8080 also has 3 groups (Group1 / Group2 / Group3)**.

After selecting the interface/group, the `lcdc_init.LCDC_GroupSel` assignment rules (verified against existing drivers pin by pin):

| Interface | `LCDC_GroupSel` | Basis |
|------|-----------------|------|
| RGB / eDPI | **1** (consistent across all RGB reference drivers) | EK9716 / NV3047 / ST7282 / st7701s×3 all `=1` |
| QSPI | **= selected group number** (Group1→1, Group2→2, Group3→3) | NV3030B/st7789_spi(G1)=1, ST77903(G2)=2, co5300(G3)=3 |
| 8080 / DBIB | Existing drivers **do not set it** (default **0**), and all use I8080 Group2 pins | st7789_8080 / st7796 both do not set `LCDC_GroupSel` |

> ⚠️ **Don't trust `//QFN88 2 - QFN68 1` comments**: some QSPI drivers have this template comment, but it contradicts actual pins
> (co5300 uses Group3 pins, `rtk_lcd_hal_init` has `GroupSel=3`, which is neither 2 nor 1).
> **Set `GroupSel` based on the actual group number the pins belong to**, and cross-reference the reference driver for the **same package**, don't copy the number from the comment.

> **Reference drivers (verified pin by pin, matching this QFN88 table)**:
> - RGB: `EK9716_800480_rgb.c`, `NV3047_480272_rgb.c`, `ST7282_480272_rgb.c`, `st7701s_480480_rgb.c` (`GroupSel=1`).
> - QSPI: `NV3030B_76x284_spi.c` / `st7789_170_320_lcdc_spi.c` (Group1), `ST77903_400400_RLSPI.c` (Group2), `co5300_390x390_qspi.c` (Group3, Octal).
> - 8080: `st7789_320_240_8080.c`, `st7796_320320_dbib.c` (both I8080 Group2, `GroupSel` not set=0), `nt35510_480800_dbib.c`.
>
> ⚠️ **Package note**: This table only covers **QFN88**. QFN68 / MCM have fewer pins, some groups may be unavailable; verify separately for other packages.

---

## 1. RGB / eDPI (Single Parallel Port + 4 Color Mappings)

RGB is a single physical parallel port (LCDC = D0–D23); color depth/order is determined by 4 color mappings:
All RGB reference drivers have `LCDC_GroupSel = 1`.

**Control signals (common to all 4 mappings, QFN88)**:

| Signal (Full Name) | Pin | Signal | Pin |
|--------------|------|------|------|
| DE (Data Enable, macro `LCDC_CSN_DE`) | P0_0 | HSYNC (Horizontal Sync) | P1_5 |
| VSYNC (Vertical Sync) | P0_1 | SD (Shutdown) | P1_6 |
| PCLK (Pixel Clock, macro `LCDC_RGB_WRCLK`) | P0_2 | CM (Color Mode) | P3_6 |

**RGB888 (Column R, 24-bit, uses all D0–D23)**:

| Channel | Bit0 | Bit1 | Bit2 | Bit3 | Bit4 | Bit5 | Bit6 | Bit7 |
|------|-----|-----|-----|-----|-----|-----|-----|-----|
| B (Blue) | P0_4 | P0_5 | P0_6 | P0_7 | P4_0 | P4_1 | P4_2 | P4_3 |
| G (Green) | P1_2 | P4_4 | P4_5 | P4_6 | P4_7 | P9_2 | P3_2 | P3_3 |
| R (Red) | P3_4 | P3_5 | P5_5 | P5_4 | P5_3 | P5_2 | P5_1 | P5_0 |

**RGB565 (16-bit) three configurations** — all R5G6B5, but use different pads; the user must confirm which Config:

| Channel | Config1 (Column S) | Config2 (Column T) | Config3 (Column U) |
|------|-----------------|-----------------|-----------------|
| B0..B4 | P0_4,P0_5,P0_6,P0_7,P4_0 | P0_4,P0_5,P0_6,P0_7,P4_0 | P0_5,P0_6,P0_7,P4_0,P4_1 |
| G0..G5 | P4_1,P4_2,P4_3,P1_2,P4_4,P4_5 | P1_2,P4_4,P4_5,P4_6,P4_7,P9_2 | P1_2,P4_4,P4_5,P4_6,P4_7,P9_2 |
| R0..R4 | P4_6,P4_7,P9_2,P3_2,P3_3 | P3_4,P3_5,P5_5,P5_4,P5_3 | P3_5,P5_5,P5_4,P5_3,P5_2 |

> **Config2 = RGB888 with the lower bits of each channel removed** (taking the high bits of B/G/R), same pad segment as RGB888 — most common.
> **Config1** packs 16 lines into lower P0_/P4_/P3_ pads (no P5_); **Config3** is similar to Config2 but shifted up by one bit.
> The specific color order is determined by `eDPI_ColorMap` / `LCDC_PixelOutputFormat`, **the configured B/G/R line set must exactly match the selected Config**.

**Config number ↔ `eDPI_ColorMap` register value (verified against `rtl_lcdc_edpi.h`)**:
Config number = register value = macro suffix, one-to-one correspondence, just use directly:

| Selected Config | `eDPI_ColorMap` value (Macro / Value) | Pin set source |
|-------------|--------------------------------|--------------|
| RGB888      | `EDPI_PIXELFORMAT_RGB888`   (0x0) | RGB888 table above (uses all D0–D23) |
| Config1 (S) | `EDPI_PIXELFORMAT_RGB565_1` (0x1) | Config1 table above (16 lines = D0–D15) |
| Config2 (T) | `EDPI_PIXELFORMAT_RGB565_2` (0x2) | Config2 table above |
| Config3 (U) | `EDPI_PIXELFORMAT_RGB565_3` (0x3) | Config3 table above |

> **Only enable pads used by the selected Config**: e.g., Config1 only needs D0–D15 (16 lines), don't also `Pad_Dedicated_Config(ENABLE)` for D16–D23 —
> extra configured pins become LCDC-dedicated, which may conflict if the board uses P5_x for other purposes. In the reference drivers, `st7701s_480640` (Config1, only enables D0–D15) is the correct example;
> `st7701s_320800` (Config1 but enables all D0–D23) is a counterexample, don't copy it.

- **CM** (Color Mode) and **SD** (Shutdown) are optional eDPI signals. Most drivers disable them, using the freed pins as GPIO.
- **RESET / BL are regular GPIO** (`Pad_Config(..., PAD_PINMUX_MODE, ...)` + `Pinmux_Config(pin, DWGPIO)`, driven as output),
  **their assignment varies by board/color depth**. Verified: `st7701s_480480_rgb` defaults `LCDC_RESET` to **P3_6 (CM pin)**, with backup **P9_0**;
  panel initialization commands use a **dedicated 3-wire SPI0** (e.g., P9_0/P1_3/P1_6/P9_1 or P3_6), separate from the RGB pixel bus.
  → When generating, fill in RESET/BL/SPI0 pins according to the customer's board, do not blindly copy a reference driver.

### Pin Configuration Skeleton (8762G style: no `Pad_HighSpeed*`)

```c
/* Each high-speed data/control line: PAD_PINMUX_MODE + Pad_Dedicated_Config(ENABLE), no HighSpeed calls */
Pad_Config(LCDC_DATA0, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
/* ... configure B/G/R lines per selected Config + VSYNC/HSYNC/PCLK/DE ... */
Pad_Dedicated_Config(LCDC_DATA0, ENABLE);
/* ... each remaining data/control line similarly followed by Pad_Dedicated_Config(pin, ENABLE) ... */

/* RESET as GPIO */
Pad_Config(LCDC_RESET, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_ENABLE, PAD_OUT_HIGH);
Pinmux_Config(LCDC_RESET, DWGPIO);
```

---

## 2. QSPI (3 Groups; Group3 supports Octal)

| Signal (Full Name) | Driver Macro (Convention) | Group1 (`GroupSel=1`) | Group2 (`GroupSel=2`) | Group3 (`GroupSel=3`) |
|--------------|--------------|-----------------------|-----------------------|-----------------------|
| QSPI_CLK (Clock, PHY)   | `LCD_QSPI_CLK` / `LCD_SPI_CLK` | P4_0 | P4_0 | P5_4 |
| QSPI_CS (Chip Select)         | `LCD_QSPI_CS` / `LCD_SPI_CS`   | P4_3 | P4_3 | P5_2 |
| QSPI_SIO0              | `LCD_QSPI_D0`  | P4_2 | P4_2 | P5_5 |
| QSPI_SIO1              | `LCD_QSPI_D1`  | P4_1 | P4_1 | P1_5 |
| QSPI_SIO2              | `LCD_QSPI_D2`  | P3_2 | P0_6 | P1_6 |
| QSPI_SIO3              | `LCD_QSPI_D3`  | P3_3 | P0_7 | P3_6 |
| QSPI_SIO4              | —              | —    | —    | P3_5 |
| QSPI_SIO5              | —              | —    | —    | P3_4 |
| QSPI_SIO6              | —              | —    | —    | P3_3 |
| QSPI_SIO7              | —              | —    | —    | P3_2 |
| QSPI_DCX (D/C Data/Command Select) | `LCD_QSPI_RS` | P3_4 | P1_5 | P5_1 |
| LCD_TE (Tearing Effect = VSYNC) | `LCD_QSPI_TE` | P0_5 | P0_1 | P5_3 |
| LCD_RESX (Reset, active low) | `LCD_QSPI_RST` | P3_6 | P3_6 | (P3_6 is used as SIO3, see below) |

- **Group1 / Group2 are quad only** (SIO0–3); **Group3 supports Octal (SIO0–7)**.
- **RESX = P3_6** is valid for Group1/Group2 (P3_6 is `LCD_RESX` for these groups), all quad QSPI reference drivers have `RST=P3_6`.
  **In Group3, P3_6 is used as SIO3**, so co5300 (Group3) has `LCD_QSPI_RST=P3_6` **commented out**, and reset must use a different free pin.
- **RESET / BL are board-variant GPIOs**: reference drivers use **P1_4** (NV3030B / st7789_spi / icna3311) or **P1_2** (co5300 / ST77903) for BL.
- ⚠️ **icna3311_280x456_qspi is a special case**: the `.h` file has **duplicate `#define`** for QSPI data macros (first Group1's P3_2/P3_3, then Group2's P0_6/P0_7, the latter takes effect),
  but `GroupSel=1`. The pins (Group2) and GroupSel(1) are inconsistent — suspected driver typo. **Don't use it as a template**; NV3030B(G1)/ST77903(G2)/co5300(G3) are cleaner.

Pad skeleton is the same as RGB: each line uses `Pad_Config(pin, PAD_PINMUX_MODE, ...)` + `Pad_Dedicated_Config(pin, ENABLE)`, **no `Pad_HighSpeed*`**.

---

## 3. 8080 / DBIB (Intel 8080 Parallel, 3 Groups, 8-bit Data D0–D7)

| Signal (Full Name) | Driver Macro (Convention) | Group1 (Column W) | Group2 (Column Y) | Group3 (Column AA) |
|--------------|--------------|---------------|---------------|----------------|
| 8080_D0 | `LCD_8080_D0` | P3_5 | P0_4 | P5_5 |
| 8080_D1 | `LCD_8080_D1` | P0_1 | P0_5 | P1_5 |
| 8080_D2 | `LCD_8080_D2` | P0_2 | P0_6 | P1_6 |
| 8080_D3 | `LCD_8080_D3` | P0_4 | P0_7 | P3_6 |
| 8080_D4 | `LCD_8080_D4` | P4_0 | P4_0 | P3_5 |
| 8080_D5 | `LCD_8080_D5` | P4_1 | P4_1 | P3_4 |
| 8080_D6 | `LCD_8080_D6` | P4_2 | P4_2 | P3_3 |
| 8080_D7 | `LCD_8080_D7` | P4_3 | P4_3 | P3_2 |
| 8080_WR# (Write strobe, active low) | `LCD_8080_WR`  | P3_2 | P0_2 | P5_4 |
| 8080_CS# (Chip Select, active low)    | `LCD_8080_CS`  | P3_3 | P0_0 | P5_2 |
| 8080_DCX (Data/Command Select D/C#, i.e. RS)   | `LCD_8080_DCX` | P3_4 | P1_5 | P5_1 |
| 8080_RD# (Read strobe, active low)  | `LCD_8080_RD`  | P2_0 | P1_6 | P5_0 |
| 8080_LCD_TE (Tearing Effect) | `LCD_TE`       | P0_5 | P0_1 | P5_3 |
| LCD_RESX (Reset, active low)                | `LCD_8080_RST` | P3_6 | P3_6 | — |

- **Both existing 8080 reference drivers (st7789_8080 / st7796) use Group2, and do not set `LCDC_GroupSel` (default 0)** —
  DBIB routing differs from QSPI; pin selection is done via pad configuration (`Pad_Dedicated_Config`) rather than GroupSel.
  When porting to another group, start with Group2 to get it working first; verify GroupSel semantics if Group1/Group3 is needed.
- **RESET / BL are board-level GPIOs**: st7789_8080 `RST=P1_4`, st7796 `RST=P2_0`, both have `BL=P1_2`.
- Pad skeleton is the same as above: `Pad_Config(pin, PAD_PINMUX_MODE, ...)` + `Pad_Dedicated_Config(pin, ENABLE)`, no `Pad_HighSpeed*`.

---

## 4. Pin Muxing Quick Reference (Same Pad Across Different Interfaces, QFN88)

| pad | RGB/eDPI (LCDC) | QSPI | 8080 |
|-----|-----------------|------|------|
| P0_0 | DE | — | 8080_CS#(G2) |
| P0_1 | VSYNC | LCD_TE(G2) | 8080_TE(G2) / 8080_D1(G1) |
| P0_2 | PCLK | — | 8080_WR#(G2) / 8080_D2(G1) |
| P0_4–P0_7 | D0–D3 | SIO2/SIO3(G2 uses P0_6/P0_7) | 8080_D0–D3(G2) |
| P1_5 | HSYNC | SIO1(G3)/DCX(G2) | 8080_DCX(G2)/D1(G3) |
| P1_6 | SD | SIO2(G3) | 8080_RD#(G2)/D2(G3) |
| P3_2/P3_3 | D14/D15 | SIO2/SIO3(G1), SIO7/SIO6(G3) | 8080_WR#/CS#(G1), D7/D6(G3) |
| P3_4 | D16 | DCX(G1)/SIO5(G3) | 8080_DCX(G1)/D5(G3) |
| **P3_6** | **CM** | **RESX(G1/G2)** / SIO3(G3) | **RESX(G1/G2)** / D3(G3) |
| P4_0–P4_3 | D4–D7 | CLK/SIO0/SIO1/CS(G1/G2) | 8080_D4–D7 |
| P5_0–P5_5 | D23–D18 | Group3 segment (CLK/CS/SIO0/DCX/TE) | I8080 Group3 segment |

> **P3_6 is a critical mux pin**: RGB uses it as CM, QSPI/8080 Group1/Group2 use it as **RESX (Reset)**, Group3 uses it as data (SIO3/D3).
> When selecting Group3, it becomes a data line, so reset must use a different pin — that's why co5300 comments out `RST=P3_6`.

---

## 5. Generation Steps & Self-Check

1. **RGB**: Confirm color depth (RGB888 / RGB565); if 565, confirm **Config1/2/3**. Fill in B/G/R lines per selected mapping + VSYNC/HSYNC/PCLK/DE,
   `LCDC_GroupSel = 1`. CM/SD are usually disabled. RESET/BL/SPI0 are separate GPIOs per board.
2. **QSPI**: Confirm which group (quad → Group1/Group2; Octal → Group3 only). Fill in pin macros per group,
   **`LCDC_GroupSel = group number`** (G1→1/G2→2/G3→3), don't trust `//QFN88 2 - QFN68 1` comments. RESX: G1/G2=P3_6, G3 must use another pin.
3. **8080**: 8-bit D0–D7 + WR/CS/DCX/RD/TE, prefer existing Group2 reference drivers (`LCDC_GroupSel` default 0). RESET/BL per board.
4. All high-speed data/control pads use `Pad_Config(pin, PAD_PINMUX_MODE, ...)` + `Pad_Dedicated_Config(pin, ENABLE)` —
   **8762G has no `Pad_HighSpeedFuncSel/MuxSel`** (this is the key difference from 8773E/8773G).

**Self-Check**:
- [ ] Pin macros match this table for **QFN88** one by one; if targeting non-QFN88, verify separately.
- [ ] QSPI `LCDC_GroupSel` matches the **group number the pins belong to** (G1→1/G2→2/G3→3), **did not copy `//QFN88 2 - QFN68 1` comments**.
- [ ] RGB `LCDC_GroupSel=1`; 8080 follows reference drivers (default 0).
- [ ] RGB565 `eDPI_ColorMap` matches the selected Config number (Config1→`RGB565_1`/Config2→`RGB565_2`/Config3→`RGB565_3`),
      B/G/R line set corresponds exactly and **only** enables pads for that Config (e.g., Config1 only D0–D15); RGB888 uses all D0–D23.
- [ ] Pads use `Pad_Dedicated_Config`, **not** `Pad_HighSpeed*` (not present on 8762G).
- [ ] When selecting QSPI/8080 Group3, reset does not use P3_6 (that pin is used as data SIO3/D3).
- [ ] Did not use icna3311 as a template (its pins/GroupSel are inconsistent).
