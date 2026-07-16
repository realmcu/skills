# RTL8773E Display Pins (RGB / eDPI + QSPI + 8080 / DBIB)

RTL8773E display pins: **RGB and QSPI each have 2 groups (Group0 / Group1), 8080 only has Group0**.
After selecting a group, `lcdc_init.LCDC_GroupSel` must point to the same group (Group0→0 / Group1→1, pin group and GroupSel must match).

> "**Display Controller Timing Constrain**" is a large cross-column section whose sub-headers (row 2) split it into 5 columns:
>
> | Column | Sub-header | Meaning |
> |----|--------|------|
> | c14 | `RGB888 (30Mhz)`                    | **RGB Group0** |
> | c15 | `I8080 Group0 (40Mhz)`              | **8080 Group0** |
> | c16 | `QSPI Group0 (60Mhz)`               | **QSPI Group0** |
> | c17 | `RGB888 (30Mhz) Group1`            | **RGB Group1** |
> | c18 | `QSPI Group1 (60Mhz)`               | **QSPI Group1** |
>
> ⚠️ There is also a section "Obsolete Display interface" (c19/c20) marked **"Not supported"** — that is the old mapping, **never use it for 8773E**.
>
> **Reference drivers (verified pin by pin, fully matching this QFN88 table)**:
> - RGB: `st7701s_480480_rgb.c` (RGB565, Group0), `lcd_st7265_800480_rgb.c` (RGB888, Group0).
> - QSPI: `lcd_st77916_360_360_qspi.c` (Group0, `GroupSel=0`), `nv3041A_480_272_qspi.c` (Group0, octal SIO0–7),
>   `SH8601Z_454454_qspi.c` (**Group1**, `GroupSel=1`).
> - 8080: **8773E has no existing 8080 reference driver** — port the pad form from 8773G `st77916_360_360_dbib_8080.c`.

---

## 1. RGB / eDPI (2 Groups)

Control signals (VSYNC/HSYNC/PCLK/DE/CM) and D0–D17 **are identical between the two groups**, only **SD and D18–D23** differ:

| Signal | Group0 (`GroupSel=0`) | Group1 (`GroupSel=1`) |
|------|-----------------------|-----------------------|
| SD   | P9_0 | P6_0 |
| D18  | P9_1 | P6_1 |
| D19  | P9_2 | P6_2 |
| D20  | P9_3 | P6_3 |
| D21  | P9_4 | P6_4 |
| D22  | P9_5 | P6_5 |
| D23  | P9_6 | P6_6 |

Group1 moves SD + D18–D23 entirely to **P6_0–P6_6** (contiguous), freeing P9_0–P9_6.

Pins shared by both groups (QFN88):

| Signal (Full Name) | Pin | Signal | Pin | Signal | Pin |
|--------------|------|------|------|------|------|
| VSYNC (Vertical Sync) | P2_2 | D0 | P2_6 | D10 | P8_0 |
| DE (Data Enable, macro `LCDC_CSN_DE`) | P2_3 | D1 | P2_7 | D11 | P8_1 |
| HSYNC (Horizontal Sync) | P2_4 | D2 | P4_0 | D12 | P8_2 |
| PCLK (Pixel Clock, macro `LCDC_RGB_WRCLK`) | P2_5 | D3 | P4_1 | D13 | P8_3 |
| CM (Color Mode) | **ADC3 (DWA_3)** | D4 | P4_2 | D14 | P8_4 |
|  |  | D5 | P4_3 | D15 | P8_5 |
|  |  | D6 | P4_4 | D16 | P8_6 |
|  |  | D7 | P4_5 | D17 | P8_7 |
|  |  | D8 | P4_6 | **SD / D18–D23** | See "Differences" table above |
|  |  | D9 | P4_7 |  |  |

- **CM** (`eDPI_ColorModeEn`) and **SD** (Shutdown, `eDPI_ShutdnEn`) are optional eDPI signals. Most drivers disable them (`=0`), using the freed pins as GPIO.
- **RESET / BL / PWREN are regular GPIO** (`Pad_Config(..., PAD_SW_MODE, ..., PAD_OUT_ENABLE, ...)`), not part of the high-speed data bus,
  **their assignment varies by board/color depth** — they typically land on pins freed by the selected interface or color map. Three verified RGB reference drivers differ:

  | Reference Driver | color map | D lines used | RESET | BL | Other |
  |------|-----------|-----------|-------|-----|------|
  | `st7701s_480480_rgb` | RGB565_2 | D0–4,D8–13,D16–20 | **P9_0** (SD pin) | **P0_3** | — |
  | `lcd_st7265_800480_rgb` | RGB888 | D0–D23 (all) | P9_0 | — | — |
  | `hx8369_480480_rgb` | RGB565_1 | D0–D15 | **P9_1** (D18 pin freed) | **P9_0** (SD pin freed) | PWREN=ADC_1 |

  → When generating, fill in RESET/BL pins according to the customer's board, do not blindly copy a single reference driver. **CM on 8773E is ADC3(DWA_3)** (not P0_3; P0_3 is just an unused GPIO used as BL by st7701s).

### ⚠️ Which D lines are used depends on OUTPUT format + color map

The RGB bus has up to 24 lines (D0–D23), the actual number used depends on color depth:

- **OUTPUT = RGB888**: Use all **D0–D23**, `eDPI_ColorMap = EDPI_PIXELFORMAT_RGB888` (reference driver `lcd_st7265_800480_rgb.c` is this case).
- **OUTPUT = RGB565**: Only use **16 lines**, which 16 depends on `eDPI_ColorMap`, **the user must confirm the color map**:

  | `eDPI_ColorMap` macro | Value | D lines actually used |
  |--------------------|----|-----------------|
  | `EDPI_PIXELFORMAT_RGB565_1` | 0x1 | **D0–D15** |
  | `EDPI_PIXELFORMAT_RGB565_2` | 0x2 | **D0–4, D8–13, D16–20** |
  | `EDPI_PIXELFORMAT_RGB565_3` | 0x3 | **D1–5, D8–13, D17–21** |

  **Reference driver `st7701s_480480_rgb.c` uses `RGB565_2`**: unconditionally configures `D0–4, D8–13, D16–20`, and places the remaining D lines inside `#if ..._DRV_PIXEL_BITS == 24` (only configured for 888).
  **The configured D line set must exactly match the color map.**

> Note: The two groups only differ at **SD and D18 and above**. Therefore:
> - `RGB565_1` (uses only D0–D15) → data lines are identical between groups, group selection only affects the SD pin;
> - `RGB565_2/565_3` / `RGB888` → use D18+, so the group must be confirmed.

### Pin Configuration Skeleton (Group0, RGB565_2, following 8773E reference driver)

```c
/* Data lines: first configure D0-4/D8-13/D16-20 used by 565(RGB565_2); each pad is followed by a pair of high-speed selects */
Pad_Config(LCDC_DATA0, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
Pad_HighSpeedFuncSel(LCDC_DATA0, HS_Func0);
Pad_HighSpeedMuxSel(LCDC_DATA0, FROM_CORE_DOMAIN);   /* FROM_CORE_DOMAIN == FROM_HS_MUX == 1 */
/* ... D1-4, D8-13, D16-20 same as above ... */
#if <PANEL>_DRV_PIXEL_BITS == 24        /* RGB888: fill in remaining D lines D5-7,14,15,21-23 */
/* ... */
#endif
/* Control lines (each also followed by a pair of high-speed selects) */
Pad_Config(LCDC_RGB_WRCLK, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH); /* PCLK  = P2_5 */
Pad_Config(LCDC_HSYNC,     PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH); /* HSYNC = P2_4 */
Pad_Config(LCDC_VSYNC,     PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH); /* VSYNC = P2_2 */
Pad_Config(LCDC_CSN_DE,    PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH); /* DE    = P2_3 */
/* RESET / BL as GPIO */
Pad_Config(LCDC_RESET,     PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_NONE, PAD_OUT_ENABLE, PAD_OUT_HIGH);    /* P9_0 (Group0 SD pin) */
Pad_Config(LCD_ST7701_BL,  PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_NONE, PAD_OUT_ENABLE, PAD_OUT_HIGH);    /* P0_3 */
```

---

## 2. QSPI (2 Groups)

| Signal (Full Name) | Driver Macro (Convention) | Group0 (`GroupSel=0`) | Group1 (`GroupSel=1`) |
|--------------|--------------|-----------------------|-----------------------|
| QSPI_CS (Chip Select)            | `LCD_QSPI_CS`  | P2_3 | P9_2 |
| QSPI_CLK (Clock, PHY)      | `LCD_QSPI_CLK` | P2_5 | P9_4 |
| QSPI_SIO0                 | `LCD_QSPI_D0`  | P2_6 | P9_3 |
| QSPI_SIO1                 | `LCD_QSPI_D1`  | P2_7 | P9_1 |
| QSPI_SIO2                 | `LCD_QSPI_D2`  | P4_0 | P9_0 |
| QSPI_SIO3                 | `LCD_QSPI_D3`  | P4_1 | P9_5 |
| QSPI_SIO4                 | —              | P4_2 | — (Group1 only has quad SIO0–3) |
| QSPI_SIO5                 | —              | P4_3 | — |
| QSPI_SIO6                 | —              | P4_4 | — |
| QSPI_SIO7                 | —              | P4_5 | — |
| QSPI_DCX (D/C Select)       | `LCD_QSPI_RS`  | P2_4 | P4_5 |
| LCD_TE (Tearing Effect, VSYNC) | `LCD_QSPI_TE` | P2_2 | P2_2 |
| LCD_RESX (Reset)          | `LCD_QSPI_RST` | P9_0 | P4_4 |

- **Group0** on P2_/P4_ pins provides **SIO0–SIO7 (up to Octal)** — regular quad QSPI displays only use SIO0–3 (P2_6/P2_7/P4_0/P4_1).
  Reference driver `nv3041A` uses all eight lines; `st77916` uses only quad.
- **Group1** on P9_ pins is quad only (SIO0–3). Reference driver `SH8601Z_454454_qspi.c` uses Group1 (`GroupSel=1`).
- Note `P9_0`: Group0 uses it as **RESX**, Group1 uses it as **SIO2** — the same pin carries different signals in different groups, only the selected group is activated.
- QSPI group pins are **identical to RTL8773G QSPI groups** (see `pins-8773g-qspi.md`), cross-reference is fine.
- **RESET / BL are also board-variant GPIOs** (QSPI doesn't use DCX so the DCX pin can be freed for other uses). Verified Group0 QSPI reference drivers:
  - `nv3041A_480_272_qspi` (Octal): RESX=P9_0 (table value), BL=**ADC3** (CM/RD# pin, idle under QSPI), uses all SIO0–7.
  - `lcd_st77916_360_360_qspi` (Quad): RST=**P2_4** (DCX pin freed for reset), BL=P6_0, uses only SIO0–3.
  - Group1 reference driver `SH8601Z_454454_qspi` / `lcd_sh8601z_410_502_qspi`: RST=P4_4 (table value), matches the table pin by pin.

Pad skeleton (replace macros with the selected group): high-speed pins `LCD_QSPI_D0..D3/CS/CLK` (plus D4..D7 for Octal) use
`PAD_PINMUX_MODE or PAD_SW_MODE + Pad_HighSpeedFuncSel(HS_Func0) + Pad_HighSpeedMuxSel(FROM_CORE_DOMAIN)`;
`TE` also gets a pair of high-speed selects; `RST/DCX` as regular GPIO outputs as needed.

---

## 3. 8080 / DBIB (Intel 8080 Parallel, Group0 Only)

**8080 only has Group0** (this table has no I8080 Group1 column), `lcdc_init.LCDC_GroupSel = 0` is fixed; **8-bit data D0–D7**.

| Signal (Full Name) | Driver Macro (Convention) | Pin |
|--------------|--------------|------|
| 8080_RD# (Read strobe, active low) | `LCD_8080_RD`  | **ADC3 (DWA_3)** |
| 8080_LCD_TE / Vsync (Tearing Effect)  | `LCD_TE_SYNC`  | P2_2 |
| 8080_CS# (Chip Select)           | `LCD_8080_CS`  | P2_3 |
| 8080_DCX (Data/Command Select D/C#, i.e. RS)  | `LCD_8080_DCX` | P2_4 |
| 8080_WR# (Write strobe, active low)| `LCD_8080_WR`  | P2_5 |
| 8080_D0..D7 (8-bit Data Bus)            | `LCD_8080_D0..D7` | P2_6, P2_7, P4_0, P4_1, P4_2, P4_3, P4_4, P4_5 |
| LCD_RESX (Reset, active low)               | `LCD_8080_RST` | P9_0 |

- **RD# on 8773E is ADC3(DWA_3)** (not P2_1, and not 8773G's P0_3); write-only panels mostly don't use RD#, so it can be left disabled.
- **8773E has no existing 8080 reference driver**: port the pad form from 8773G `st77916_360_360_dbib_8080.c`, and fill in the pins from the table above;
  high-speed pins similarly use `PAD_SW_MODE + Pad_HighSpeedFuncSel(HS_Func0) + Pad_HighSpeedMuxSel(FROM_CORE_DOMAIN)`.

---

## 4. Pin Muxing Quick Reference (Same Pad Across Different Interfaces)

| pad | RGB (Group0) | QSPI (Group0) | 8080 (Group0) |
|-----|--------------|---------------|----------------|
| ADC3 | CM         | —             | RD# |
| P2_2 | VSYNC      | LCD_TE        | TE(Vsync) |
| P2_3 | DE         | QSPI_CS       | CS# |
| P2_4 | HSYNC      | QSPI_DCX      | DCX |
| P2_5 | PCLK       | QSPI_CLK      | WR# |
| P2_6..P4_5 | D0..D7 | QSPI_SIO0..7 | D0..D7 |
| P9_0 | SD         | LCD_RESX      | RESX |

---

## 5. Differences from RTL8773G (Verified)

| Item | RTL8773G | RTL8773E |
|------|----------|----------|
| CM (Color Mode) | P0_3 | **ADC3 (DWA_3)**; P0_3 on 8773E is repurposed as BL |
| 8080 RD# (Read strobe) | P0_3 | **ADC3 (DWA_3)** |
| RGB Group1 SD+D18–D23 | SD=P2_1, D18=P9_6, D19–D23=P6_0–P6_4 | **SD=P6_0, D18–D23=P6_1–P6_6 (contiguous)** |
| QSPI group pins | —— identical to 8773E —— | same as left |

The rest (RGB Group0 data/control lines, 8080 8-bit layout, RESET/BL muxing, high-speed pad configuration style, eDPI divider rules) are identical between platforms.

---

## 6. Generation Steps & Self-Check

1. **RGB**: Confirm which group + OUTPUT (565/888); if 565, also confirm color map. Fill in `LCDC_DATAn`/VSYNC/HSYNC/PCLK/DE,
   `LCDC_GroupSel` = group number, divide into "unconditional D lines" and "`#if 24bit` D lines" based on color map. RESET/BL as separate GPIO.
2. **QSPI**: Confirm which group (quad uses SIO0–3; Octal can only use Group0). Fill in pin macros per group, `LCDC_GroupSel` = group number.
3. **8080**: `LCDC_GroupSel=0` fixed, 8-bit D0–D7 + CS/DCX/WR/RD(ADC3)/TE, port pad from 8773G reference.
4. All high-speed data/control pads use `Pad_HighSpeedFuncSel(HS_Func0) + Pad_HighSpeedMuxSel(FROM_CORE_DOMAIN)`.

**Self-Check**:
- [ ] Pin macros match this QFN88 table one by one, and **pin group matches `LCDC_GroupSel`** (Group0→0 / Group1→1).
- [ ] RGB565 D line set corresponds exactly to `eDPI_ColorMap`; 888 uses all D0–D23.
- [ ] CM is set to **ADC3** (don't mistakenly write P0_3); 8080 RD# is set to **ADC3** (don't mistakenly write P2_1/P0_3).
- [ ] Did not reference columns c19/c20 "Obsolete Display interface (Not supported)".
