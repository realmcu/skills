# RTL8773G RGB(eDPI) Timing Parameters (HSA/HFP/HBP/HACT + VSA/VFP/VBP/VACT)

Source: Reference file `device/general/lcd/8773G/st7701s_480480_rgb.c` (eDPI configuration section)
+ Hardware layer `rtl_lcdc_edpi.c` / `rtl_lcdc_edpi.h`.

Only the **RGB / eDPI interface** requires these parameters; QSPI / SPI / DBIB do not involve them.

## Full Name Reference (always use full names when communicating with developers)

RGB(DPI) timing = division of "Sync Pulse + Back Porch + Active Area + Front Porch" in both horizontal and vertical directions within one frame.

**Horizontal direction (unit = pixel-clock period):**

| Abbr | Full Name | Chinese | Description |
|------|-----------|---------|-------------|
| HSA  | Horizontal Sync (pulse) width | Horizontal sync pulse width | HSYNC active width |
| HBP  | Horizontal Back Porch  | Horizontal back porch | From HSYNC end to active pixel start |
| HACT | Horizontal Active (area) | Horizontal active pixel count | **= Panel width LCD_WIDTH** (determined by resolution, no need to ask separately) |
| HFP  | Horizontal Front Porch | Horizontal front porch | From active pixel end to next HSYNC |

**Vertical direction (unit = horizontal scan line):**

| Abbr | Full Name | Chinese | Description |
|------|-----------|---------|-------------|
| VSA  | Vertical Sync (pulse) width/height | Vertical sync pulse height | Number of rows VSYNC is active |
| VBP  | Vertical Back Porch  | Vertical back porch | From VSYNC end to active row start |
| VACT | Vertical Active (area) | Vertical active row count | **= Panel height LCD_HEIGHT** (determined by resolution, no need to ask separately) |
| VFP  | Vertical Front Porch | Vertical front porch | From active row end to next VSYNC |

Other related full names: **PCLK** = Pixel Clock; **DE** = Data Enable;
**HSPOL/VSPOL/DEPOL** = HSync / VSync / Data-Enable Polarity.

> Total line period = HSA + HBP + HACT + HFP; Total frame lines = VSA + VBP + VACT + VFP.
> Frame rate ≈ PCLK / (TotalWidth × TotalHeight).

## Which 6 parameters need to be filled by the customer

Among the 8 parameters, **HACT/VACT are the known resolution** (HACT = width, VACT = height), so only **6** actually need to be asked:
`HSA / HBP / HFP` and `VSA / VBP / VFP`.

## How to obtain (recommended approach)

**Primary input = Customer reads the panel module spec and provides these 6 values directly.** Same processing logic as clock / initialization sequence:

- These values are in the module datasheet's **"RGB/DPI Interface Timing"** or **"AC Characteristics"** table,
  often given together with PCLK (some tables call them thb/thpw/thbp/thfp, tvb/tvpw/tvbp/tvfp).
- **Spec documents (PDF/MD) are only optional aids**: candidate values from documents can be **suggested** to the customer, but must be **confirmed by the customer** before writing into code;
  never silently adopt auto-parsed values -- incorrect sync/blanking zones cause tearing, flickering, shifting, or no display.
- **Fallback when no spec is available**: you can use porch values from a **same-resolution** reference driver as a bring-up starting point
  (porch is more tolerant and tunable than clock ceiling), but must mark as "temporary, pending customer spec verification" and verify on actual hardware for no tearing.

Single-ask example (always include full names):

> RGB panel requires the following timing parameters (fill in according to the module spec's RGB/DPI Timing table, units in parentheses):
> - HSA = Horizontal Sync width (pixel clocks)
> - HBP = Horizontal Back Porch (pixel clocks)
> - HFP = Horizontal Front Porch (pixel clocks)
> - VSA = Vertical Sync height (rows)
> - VBP = Vertical Back Porch (rows)
> - VFP = Vertical Front Porch (rows)
> (HACT = panel width, VACT = panel height are already determined by resolution, no need to fill.)

## 6 raw values → eDPI accumulation register fields (key conversion)

The driver structure `LCDC_eDPICfgTypeDef` stores **accumulated values**, not raw HFP/HBP. The reference file `st7701s_480480_rgb.c`'s conversion (just copy these formulas):

```c
uint32_t HSA = 10, HFP = 50, HBP = 50, HACT = <PANEL>_LCD_WIDTH;   /* fill HSA/HFP/HBP from spec */
uint32_t VSA = 10, VFP = 20, VBP = 20, VACT = <PANEL>_LCD_HEIGHT;  /* fill VSA/VFP/VBP from spec */

eDPICfg.eDPI_HoriSyncWidth       = HSA;
eDPICfg.eDPI_VeriSyncHeight      = VSA;
eDPICfg.eDPI_AccumulatedHBP      = HSA + HBP;                  /* accumulated H back porch  */
eDPICfg.eDPI_AccumulatedVBP      = VSA + VBP;                  /* accumulated V back porch  */
eDPICfg.eDPI_AccumulatedActiveW  = HSA + HBP + HACT;           /* accumulated active width  */
eDPICfg.eDPI_AccumulatedActiveH  = VSA + VBP + VACT;           /* accumulated active height */
eDPICfg.eDPI_TotalWidth          = HSA + HBP + HACT + HFP;     /* full line period          */
eDPICfg.eDPI_TotalHeight         = VSA + VBP + VACT + VFP;     /* full frame lines          */
eDPICfg.eDPI_LineBufferPixelThreshold = eDPICfg.eDPI_TotalWidth / 2;
eDPICfg.eDPI_LineIntMask         = 1;
```

Polarity (per panel spec; reference file = HSYNC/VSYNC active low, DE active high, the most common convention):

```c
eDPICfg.eDPI_HoriSyncPolarity = 0;   /* 0 = active low  */
eDPICfg.eDPI_VeriSyncPolarity = 0;   /* 0 = active low  */
eDPICfg.eDPI_DataEnPolarity   = 1;   /* 1 = active high */
```

## Register semantics (eDPI register table, for cross-reference)

`LCDC_eDPIInit` writes the above accumulated fields into these registers:

| Address | Register | Field (bit) | Meaning | Corresponding eDPICfg field |
|---------|----------|-------------|---------|-----------------------------|
| 0x0004 | REG_EDPI_SYNC_WIDTH  | hsw [27:16] / vsh [10:0]   | HSA / VSA                         | HoriSyncWidth / VeriSyncHeight |
| 0x0008 | REG_EDPI_ABACK_PORCH | ahbp [27:16] / avbp [10:0] | HSA+HBP / VSA+VBP                 | AccumulatedHBP / AccumulatedVBP |
| 0x000C | REG_EDPI_AACTIVE     | aaw [27:16] / aah [10:0]   | HSA+HBP+HACT / VSA+VBP+VACT       | AccumulatedActiveW / AccumulatedActiveH |
| 0x0010 | REG_EDPI_TOTAL       | totalw [27:16] / totalh [10:0] | Full line / Full frame         | TotalWidth / TotalHeight |
| 0x0014 | REG_EDPI_SYNC_POL    | hspol[31] / vspol[30] / depol[29] | 0=active low, 1=active high | HoriSyncPolarity / VeriSyncPolarity / DataEnPolarity |
| 0x0050 | REG_EDPI_DIV_PAR     | edpi_div_par [15:0]        | PCLK divider (see `clock-8773g.md`)  | eDPI_ClockDiv |

**Bit width limits (will cause truncation/corruption if exceeded; must check):**

- Horizontal fields are all 12-bit `[27:16]` → each **accumulated horizontal value ≤ 4095** (pixel clocks), i.e., `TotalWidth ≤ 4095`.
- Vertical fields are all 11-bit `[10:0]` → each **accumulated vertical value ≤ 2047** (rows), i.e., `TotalHeight ≤ 2047`.

> PCLK (`eDPI_ClockDiv` / `REG_EDPI_DIV_PAR`) is not among these timing parameters; it belongs to clock configuration, see `references/clock-8773g.md`
> (`eDPI_ClockDiv` **input = division factor, no ±1**, write bare integer such as `= 8`, minimum 2; naming macro `EDPI_CLOCKDIV<n>` has been corrected to = n, interchangeable).

## Self-check

- [ ] 6 raw values (HSA/HBP/HFP + VSA/VBP/VFP) come from customer-confirmed spec, not guesswork/naked copy
- [ ] HACT=LCD_WIDTH, VACT=LCD_HEIGHT, consistent with resolution
- [ ] Accumulated fields calculated by the formulas above, `TotalWidth ≤ 4095`, `TotalHeight ≤ 2047`
- [ ] Polarity HSPOL/VSPOL/DEPOL matches panel spec (default: HSYNC/VSYNC active low, DE active high)
- [ ] `LineBufferPixelThreshold = TotalWidth/2`
- [ ] Frame rate ≈ PCLK/(TotalWidth×TotalHeight) falls within panel's acceptable range
