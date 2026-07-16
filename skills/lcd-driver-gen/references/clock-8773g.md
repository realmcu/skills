# RTL8773G Clock Configuration (QSPI / RGB / DBIB)

Source: Hardware header files
`rtl_lcdc_dbic.h` / `rtl_lcdc_edpi.h` / `rtl_lcdc_dbib.h`.

## Three-Interface Divider Overview

| Interface | Divider Field (Struct) | Frequency Formula | Divider Value Range | Clock Source Selection API |
|-----------|-----------------------|------------------|---------------------|----------------------------|
| QSPI     | `LCDC_DBICCfgTypeDef.DBIC_SPEED_SEL` | `src / (2 x SEL)` | Integer, default 1 | `LCDC_Clock_Sel(200M/280M)` |
| RGB/eDPI | `LCDC_eDPICfgTypeDef.eDPI_ClockDiv`  | `src / DIV` (See ⚠️) | **Integer factor, input IS the divider value (no +/-1)** | `RCC_DisplayClockConfig(...)` |
| DBIB/8080| `LCDC_DBIBCfgTypeDef.DBIB_Clock_Divider` | `src / (2 x DIV)` | 2-64 | `RCC_DisplayClockConfig(...)` |

- Source + divider are determined by **the customer panel spec**: **as close to typical as possible, not exceeding max**.
- ⚠️ **"The two sources 200M/280M, selected via `LCDC_Clock_Sel`" is how QSPI (DBIC) works**. RGB / DBIB select the source via
  `RCC_DisplayClockConfig`, and the code has used **PLL1=200M** and **40MHz** (see below), not limited to 200/280.
  When generating code, use the source that appears in the reference driver for the same interface.

## QSPI (DBIC)

- Source is one of two: `LCDC_Clock_Sel(LCDC_BUS_CLK_200M)` / `LCDC_Clock_Sel(LCDC_BUS_CLK_280M)`.
- **QSPI clock = src / (2 x DBIC_SPEED_SEL)** (consistent between `rtl_lcdc_dbic.h:147` and the MD).
- Convention: most drivers use `200M + SEL=2` -> **50 MHz**.

Achievable frequency quick reference (`freq = src / (2xSEL)`):

| SEL | 200M | 280M | | SEL | 200M | 280M |
|-----|------|------|-|-----|------|------|
| 1 | 100.0 | 140.0 | | 4 | 25.0 | 35.0 |
| 2 | 50.0  | 70.0  | | 5 | 20.0 | 28.0 |
| 3 | 33.3  | 46.7  | | 6 | 16.7 | 23.3 |

```c
LCDC_Clock_Sel(LCDC_BUS_CLK_200M);
LCDC_DBICCfgTypeDef dbic_init = {0};
dbic_init.DBIC_SPEED_SEL = 2;      /* Calculated by clock_calc.py --iface qspi from panel spec */
```

## RGB (eDPI)

- **PCLK = src / eDPI_ClockDiv**. **`eDPI_ClockDiv` IS the divider value itself: whatever you write is what it divides by, no +1, no -1.**
  Path: `EDPI_Init` writes `eDPI_ClockDiv` **as-is** into `REG_EDPI_DIV_PAR.edpi_div_par` (`rtl_lcdc_edpi.c:65`, no conversion),
  the hardware divides directly by that value.
- **Usage: write the integer divider directly**, e.g. `eDPICfg.eDPI_ClockDiv = 8;`. All current RGB drivers write raw integers this way:
  8773G/8773E `st7701s_480480_rgb.c = 0x8`, 8773G `EK9716_800480_rgb.c = 8`,
  8773G/8773E `lcd_st7265_800480_rgb.c = 8`, 8773E `hx8369_480480_rgb.c = 0x4`,
  8762G `NV3047_480272_rgb.c = 11`, `ST7282_480272_rgb.c = 11`. Template `st7701s_480480_rgb.c` uses `0x8` which is **200/8 = 25MHz**.
- The named macros `EDPI_CLOCKDIV2..8` **have now been fixed to = 2..8** (value = name = divider ratio), interchangeable with raw integers;
  but actual dividers are often > 8 (e.g. 11), beyond the range of these macros, so **writing raw integers is the simplest approach**.
  (History: these macros previously had value = name - 1, an off-by-one pitfall; now fixed, see end of document.)
- **Minimum divider = 2**: `EDPI_Init` now clamps values, `eDPI_ClockDiv <= 2` will be changed to 2.
- The divider is an integer (>= 2), the field is 16-bit (`edpi_div_par[15:0]`) with a large upper limit; the actual value is determined by the panel PCLK.
  Common values for PLL1=200M:

| Divider | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 10 | 11 | 12 |
|---------|---|---|---|---|---|---|---|----|----|----|
| PCLK(MHz) | 100 | 66.7 | 50 | 40 | 33.3 | 28.6 | 25 | 20 | 18.2 | 16.7 |

```c
/* 8773G RGB clock: LCDC_Clock_Sel is sufficient (verified on baseboard, e.g., EK9716) */
LCDC_Clock_Sel(LCDC_BUS_CLK_200M); /* Select LCDC bus source = 200MHz */
eDPICfg.eDPI_ClockDiv = 8;   /* PCLK = 200/8 = 25MHz; write the divider factor directly (minimum 2), or use EDPI_CLOCKDIV8 (now fixed to = 8) */
```

> Note: Some drivers also call `RCC_DisplayClockConfig` (e.g., st7701s), but `LCDC_Clock_Sel` is sufficient for 8773G RGB.
> Both approaches have shipped in production and are not bugs. `RCC_DisplayClockConfig` is a more explicit PLL configuration path; adding it when needed does not affect functionality either way.

## DBIB (8080)

- **clock = src / (2 x DBIB_Clock_Divider)**, `DBIB_Clock_Divider` range **2-64** (`rtl_lcdc_dbib.h:136`).
- Source via `RCC_DisplayClockConfig(...)`; template `st77916_360_360_dbib_8080.c` uses
  `RCC_DisplayClockConfig(DISPLAY_CLOCK_SOURCE_40MHZ, DISPLAY_CLOCK_DIV_1)` + `DBIB_Clock_Divider = 2` -> **10 MHz**.
  (Note that the source here is **40MHz**, not 200/280.)

```c
RCC_DisplayClockConfig(DISPLAY_CLOCK_SOURCE_40MHZ, DISPLAY_CLOCK_DIV_1);
dbib_init.DBIB_Clock_Divider = 2;   /* 40 / (2*2) = 10MHz */
```

## How Inputs Are Provided (Important, Common Across All Three Interfaces)

The only clock-related information needed from the spec is the **panel's maximum interface clock frequency** (fSCL / PCLK max /
write cycle, etc. from the AC timing table), preferably along with the typical value.

**Primary input = the value (max, and optionally typical) confirmed by the customer after reading the spec.** Rationale: overclocking causes no-display or instability, this is a
**safety-critical value**; a person reading the timing table is far more reliable than automated parsing; the input is minimal (1-2 numbers).
What should be automated is the "frequency to register value" conversion.

**Spec documents (PDF/MD/TXT) are only an optional aid**: the document can be read to find candidate values as **suggestions** for the customer, but must be **confirmed** before use,
never silently trusting automated parsing. (Same handling logic as the initialization sequence.)

## Calculation Tool

```
python .claude/skills/lcd-driver-gen/scripts/clock_calc.py --chip 8773g --iface <qspi|rgb|dbib> --max <MHz> [--typical <MHz>] [--src <MHz,...>]
```
(`--chip` defaults to `8773g`; for 8773E/8762G see their respective clock documents `clock-8773e.md` / `clock-8762g.md`)
Calculates register values in reverse from the formula and divider range of the selected interface, outputs directly pasteable code lines, and lists candidates on stderr for manual verification.
RGB mode outputs the **raw integer divider factor** (`eDPI_ClockDiv` input IS the divider value, minimum 2; the named macros now equal the factor too, but values >8 can only be written as raw integers);
For RGB/DBIB, the source defaults to values seen in existing code, and can be overridden with `--src`.

## Selection Rule

Actual frequency <= max; if typical is provided, pick the value closest to typical, otherwise pick the highest value <= max.

## SDK Fix Record (eDPI Divider, 2026-07-09)

The SDK previously had an off-by-one issue in the eDPI divider that could make people think "the divider needs +1 / must use the named macros". It has now been fixed so that "value = divider factor":

| Location | Original (Misleading) | Changed To |
|----------|----------------------|------------|
| `rtl_lcdc_edpi.h:106-112` `EDPI_CLOCKDIV2..8` | value = name - 1 (`DIV2=0x1` ... `DIV8=0x7`), writing `DIV8` actually divides by 7 | value = name = divider factor (`DIV2=0x2` ... `DIV8=0x8`) + explanatory comment at top |
| `rtl_lcdc_edpi.h:114-117` `IS_EDPI_CLOCKDIV` | only accepted 0x1..0x7, would reject real driver values 8/11 | range check `((DIV)>=2 && (DIV)<=0xFFFF)` |
| `rtl_lcdc_edpi.h:48` `eDPI_ClockDiv` comment | only said "a value of @ref ..." | now clearly states "value IS the divider factor, e.g., 8 means divide by 8, minimum 2, raw integers allowed" |
| `rtl_lcdc_edpi.h:519` default value table | `\ref EDPI_CLOCKDIV1` (macro does not exist) | `\ref EDPI_CLOCKDIV2` (consistent with `EDPI_StructInit`) |
| `rtl_lcdc_edpi.c` `EDPI_Init` | no lower bound protection | added clamp: `if (eDPI_ClockDiv <= 2) eDPI_ClockDiv = 2;` |

Conclusion (after fix): **`eDPI_ClockDiv` input IS the divider value, no +/-1**; writing raw integers is simplest (and supports >8, e.g. 11),
the named macros are now equivalent and interchangeable; `rtl_lcdc_edpi.c:65` still writes the value **as-is** into the register, now with the "minimum 2" clamp in front.
