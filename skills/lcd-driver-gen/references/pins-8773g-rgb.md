# RTL8773G RGB (eDPI/DPI) Pin Configuration

RGB interface (`LCDC_IF_DPI` + `LCDC_eDPICfgTypeDef`) has **2 pin groups**. Like QSPI, after selecting a group,
`lcdc_init.LCDC_GroupSel` must point to the same group: **Group0 → 0, Group1 → 1**.
(Verified by 8773G `st7701s_480480_rgb.c`: uses Group0, `LCDC_GroupSel = 0`.)

> Reference driver: `device/general/lcd/8773G/st7701s_480480_rgb.c`.

## Differences Between the Two Groups

Control signals (VSYNC/HSYNC/PCLK/DE/CM) and lower data bits **D0–D17 are identical between the two groups**, only **SD** and **D18–D23** differ:

| Signal | Group0 | Group1 |
|------|--------|--------|
| SD   | P9_0   | P2_1   |
| D18  | P9_1   | P9_6   |
| D19  | P9_2   | P6_0   |
| D20  | P9_3   | P6_1   |
| D21  | P9_4   | P6_2   |
| D22  | P9_5   | P6_3   |
| D23  | P9_6   | P6_4   |

Group1 moves D18–D23 to P6_x (+P9_6), freeing P9_1–P9_5 for other uses.

## All Pins (Shared + Differing Parts)

| Signal | Pin | Signal | Pin | Signal | Pin |
|------|------|------|------|------|------|
| VSYNC | P2_2 | D2 | P4_0 | D12 | P8_2 |
| HSYNC | P2_4 | D3 | P4_1 | D13 | P8_3 |
| PCLK  | P2_5 | D4 | P4_2 | D14 | P8_4 |
| DE    | P2_3 | D5 | P4_3 | D15 | P8_5 |
| CM    | P0_3 | D6 | P4_4 | D16 | P8_6 |
| D0    | P2_6 | D7 | P4_5 | D17 | P8_7 |
| D1    | P2_7 | D8 | P4_6 | **SD / D18–D23** | See "Differences" table above |
|       |      | D9 | P4_7 |  |  |
|       |      | D10 | P8_0 |  |  |
|       |      | D11 | P8_1 |  |  |

- **CM** (Color Mode, `eDPI_ColorModeEn`) and **SD** (Shutdown, `eDPI_ShutdnEn`) are optional eDPI signals. Most drivers disable them (`=0`), using the freed pins as GPIO.
- **RESET / BL are regular GPIO** (`Pad_Config(..., PAD_OUT_ENABLE, ...)`), not part of the eDPI data bus. **Their assignment varies by board** — they can land on the SD pin (P9_0) or on pins unrelated to display. **Do not blindly copy from any single reference driver.** Three verified RGB reference drivers:

  | Reference Driver | color map | RESET | BL |
  |------|-----------|-------|-----|
  | `st7701s_480480_rgb` | RGB565_2 | P9_0 (SD pin) | P0_3 |
  | `lcd_st7265_800480_rgb` | RGB888 | P9_0 | — |
  | `EK9716_800480_rgb` | RGB888 | **P7_3** (GPIO unrelated to display) | — |

## ⚠️ Key: Which D lines are used depends on OUTPUT format + color map

The RGB bus has up to 24 data lines (D0–D23), but **the actual number used depends on color depth**:

### OUTPUT = 3 byte (RGB888)
Use all **D0–D23**. `eDPI_ColorMap = EDPI_PIXELFORMAT_RGB888`.

### OUTPUT = 2 byte (RGB565)
Only use **16 lines**, but **which 16 depends on `eDPI_ColorMap` — the user must confirm which color map the board uses**.
Three 565 mappings in `edpi.h` (note: the macro names and comment numbering are reversed):

| `eDPI_ColorMap` macro | Value | Bit mapping (edpi.h comment) | D lines actually used |
|--------------------|----|----------------------|-----------------|
| `EDPI_PIXELFORMAT_RGB565_1` | 0x1 | R[D15:D11] G[D10:D5] B[D4:D0] | **D0–D15** (lower 16 contiguous) |
| `EDPI_PIXELFORMAT_RGB565_2` | 0x2 | R[D20:D16] G[D13:D8] B[D4:D0] | **D0–4, D8–13, D16–20** |
| `EDPI_PIXELFORMAT_RGB565_3` | 0x3 | R[D21:D17] G[D13:D8] B[D5:D1] | **D1–5, D8–13, D17–21** |

**Reference driver `st7701s_480480_rgb.c` uses `RGB565_2`** — its unconditionally configured D lines are exactly `D0–4, D8–13, D16–20`,
while the rest (D5–7,14,15,21–23) are placed inside `#if ..._DRV_PIXEL_BITS == 24` and only configured for 888. **The configured D line set must exactly match the color map.**

> Note: group0/group1 only differ at **D18 and above**. Therefore:
> - `RGB565_1` (uses only D0–D15) → data lines are identical between groups, group selection only affects the SD pin;
> - `RGB565_2/565_3` / `RGB888` → use D18+, so the group must be confirmed.

## Generation Steps (RGB Driver)

1. Ask the user to confirm: **Group0 or Group1**, **OUTPUT 565 or 888**, and if 565 then **which color map**.
2. Fill in `LCDC_DATAn` / VSYNC / HSYNC / PCLK / DE pin macros according to the selected group (following the naming convention `LCDC_DATA0..23`).
3. `lcdc_init.LCDC_GroupSel` = 0 (Group0) / 1 (Group1), consistent with the pin group.
4. **INPUT format / OUTPUT format / color map are three independent choices**, don't hardcode them as a pair:
   - `LCDC_PixelInputFormat` (framebuffer side) is determined by the format stored in memory; `LCDC_PixelOutputFormat` (physical bus side) is determined by the panel;
     `eDPI_ColorMap` determines which 16 D lines are used for 565 (888 always uses `EDPI_PIXELFORMAT_RGB888`).
   - Reference driver `st7701s`: `#if DRV_PIXEL_BITS==16 → both INPUT/OUTPUT are 565 + colormap 565_2; #else → both 888` — **this is a simplified approach where INPUT == OUTPUT**.
   - ⚠️ **Mixed formats are common**: Example `EK9716_800480_rgb` = **INPUT `LCDC_INPUT_RGB565` (framebuffer stores 565) + OUTPUT `LCDC_OUTPUT_RGB888` (bus is 888) + colormap `EDPI_PIXELFORMAT_RGB888`**,
     `DRV_PIXEL_BITS = 16` (follows the INPUT/framebuffer side). In this case, D lines should use **all D0–D23 for 888** (based on OUTPUT, not INPUT).
   - When generating, fill in the "framebuffer format / panel bus format" as given by the user separately, don't force-bind the two together with a single `#if`.
5. Pad configuration: **Unconditionally configure the D lines used by the color map**, and place the remaining D lines only used by 888 inside `#if DRV_PIXEL_BITS == 24`.
   (Reference driver divides based on RGB565_2; if a different map is selected, the unconditional section should use that map's D line set.)
6. Configure RESET / BL as GPIO separately with `Pad_Config`; see `reset-sequence.md` for reset waveform.

## Pin Configuration Skeleton (Group0, RGB565_2, Reference Driver)

```c
/* Data lines: first configure D0-4/D8-13/D16-20 used by 565(RGB565_2) */
Pad_Config(LCDC_DATA0,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
/* ... D1-4, D8-13, D16-20 same as above ... */
#if <PANEL>_DRV_PIXEL_BITS == 24        /* RGB888: fill in remaining D lines */
Pad_Config(LCDC_DATA5,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
/* ... D6,7,14,15,21,22,23 ... */
#endif
/* Control lines */
Pad_Config(LCDC_RGB_WRCLK, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH); /* PCLK */
Pad_Config(LCDC_HSYNC,     PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
Pad_Config(LCDC_VSYNC,     PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
Pad_Config(LCDC_CSN_DE,    PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
/* Each pad also needs Pad_HighSpeedFuncSel(pin, HS_Func0) + Pad_HighSpeedMuxSel(pin, FROM_CORE_DOMAIN) */
```
