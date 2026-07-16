# RTL8773E Clock Configuration (QSPI / RGB / DBIB)

Source: Verified on active 8773E drivers.

> **Relationship with 8773G**: **Each interface's divider method is exactly the same as 8773G** (same struct fields, same formulas),
> see [`clock-8773g.md`](clock-8773g.md). This doc only covers **two points unique to 8773E**: ① clock source frequency differs;
> ② source selection API usage differs. For divider details, always refer back to the 8773G doc.

## Clock Sources (8773E-Specific Frequencies)

| Source Enum (`RCC_DisplayClockConfig` 1st param) | Frequency | Description |
|---------------------------------------------------|-----------|-------------|
| `DISPLAY_CLOCK_SOURCE_PLL1`  | **200 MHz** | Default source for active drivers |
| `DISPLAY_CLOCK_SOURCE_PLL2`  | **160 MHz** | Alternative |
| `DISPLAY_CLOCK_SOURCE_40MHZ` | **40 MHz**  | Crystal oscillator (XTAL), used for low-speed interfaces |

> ⚠️ **PLL3 does not exist on 8773E, absolutely do not select it.**
> ⚠️ Do not blindly copy 280 MHz from 8773G — that is another chip in the 87x3g series. The second PLL on 8773E is **160 MHz**.

## Source Selection API (Key difference between 8773E and 8773G)

**On 8773E, all three interfaces (QSPI/RGB/DBIB) uniformly use `RCC_DisplayClockConfig` for source selection**,
unlike 8773G where QSPI uses `LCDC_Clock_Sel` and RGB/DBIB use `RCC_DisplayClockConfig`.
`DIV` is fixed to `DISPLAY_CLOCK_DIV_1` (no top-level divider), **actual division is handled by each interface itself** (same as 8773G).

Standard usage (all 8773E drivers use these two lines):

```c
RCC_DisplayClockConfig(DISPLAY_CLOCK_SOURCE_PLL1, DISPLAY_CLOCK_DIV_1);   /* Source 200MHz, DIV fixed to 1 */
RCC_PeriphClockCmd(APBPeriph_DISP, APBPeriph_DISP_CLOCK, ENABLE);         /* Enable display clock */
```

Verified on active drivers (`device/general/lcd/8773E/`): QSPI (`lcd_c05300`, `lcd_sh8601z`,
`lcd_st77916_360_360`, `nv3041A`, `SH8601Z`), RGB (`lcd_st7265_800480`) all use
`RCC_DisplayClockConfig(DISPLAY_CLOCK_SOURCE_PLL1, DISPLAY_CLOCK_DIV_1)` + PLL1=200M.

> ⚠️ **Two legacy usages to avoid**: `hx8369_480480_rgb.c:396`, `st7701s_480480_rgb.c:398` are written as
> `RCC_DisplayClockConfig(DISPLAY_CLOCK_DIV_1, ENABLE)` — this is the old misaligned 2-parameter signature
> (first parameter stuffed DIV, second parameter stuffed ENABLE), only worked because it defaulted to PLL1=200M by luck.
> **All new drivers must use `(DISPLAY_CLOCK_SOURCE_xxx, DISPLAY_CLOCK_DIV_1)` as the correct form.**

## Per-Interface Division (exactly the same as 8773G, just replace source frequencies with the table above)

| Interface | Divider field (containing struct) | Frequency formula | Divider value range |
|-----------|-----------------------------------|-------------------|---------------------|
| QSPI (DBIC)     | `LCDC_DBICCfgTypeDef.DBIC_SPEED_SEL`     | `Source / (2 x SEL)` | Integer, default 1 |
| RGB (eDPI)      | `LCDC_eDPICfgTypeDef.eDPI_ClockDiv`      | `Source / DIV` (input is the divider coefficient, no +/-1, minimum 2) | Integer >= 2 |
| DBIB (8080)     | `LCDC_DBIBCfgTypeDef.DBIB_Clock_Divider` | `Source / (2 x DIV)` | 2–64 |

- When using PLL1=200M as source, common values: QSPI `SEL=2 -> 50MHz`; RGB `ClockDiv=8 -> 25MHz`.
- For details on divider field ranges, usage, and the eDPI "value-is-divider-coefficient" pitfall, **see [`clock-8773g.md`](clock-8773g.md)**; not repeated here.

## Input Source / Selection Rules / Calculation Tool

Consistent with 8773G (see [`clock-8773g.md`](clock-8773g.md)): Main input = maximum interface clock frequency confirmed by customer reading the panel spec
(max, optional typical); actual frequency <= max, if typical is provided, pick the closest to typical. Use
`scripts/clock_calc.py --chip 8773e --iface <qspi|rgb|dbib> --max <MHz>` to back-calculate register values and directly output
8773E source selection code (`RCC_DisplayClockConfig(...)`); `--chip 8773e` limits candidate sources to PLL1=200M/PLL2=160M/40M,
add `--src 200`/`--src 160`/`--src 40` to narrow down to a single source.
