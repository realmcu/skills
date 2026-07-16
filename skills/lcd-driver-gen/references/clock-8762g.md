# RTL8762G Clock Configuration (QSPI / RGB / DBIB)

Source: Measurements from active 8762G drivers.

> **Relationship to 8773G**: **Each interface's divider method is identical to 8773G** (same struct fields, same formulas),
> See [`clock-8773g.md`](clock-8773g.md). This document only covers **two points unique to 8762G**: 1) Clock source frequencies differ;
> 2) Source selection is not via API, but by **writing directly to a register bitfield** `PERIBLKCTRL_PERI_CLK->u_324.BITS_324`.
> For divider details, always refer back to the 8773G document.

## Clock Sources (8762G-specific frequencies)

| Source | Frequency | Selected by which bitfields |
|----|------|----------------|
| XTAL (Crystal) | **40 MHz**  | `r_disp_clk_src_sel1 = 0` |
| PLL1         | **125 MHz** | `r_disp_clk_src_sel1 = 1` and `r_disp_clk_src_sel0 = 0` |
| PLL2         | **160 MHz** | `r_disp_clk_src_sel1 = 1` and `r_disp_clk_src_sel0 = 1` |

> ⚠️ 8762G's PLL1 is **125 MHz**, not 8773E/8773G's 200 MHz. Do not copy frequencies across platforms.

## Source Selection = Writing a Register Bitfield (Key Difference Between 8762G and 8773E/G)

8762G **does not have APIs like `RCC_DisplayClockConfig` / `LCDC_Clock_Sel`**, it directly writes
`PERIBLKCTRL_PERI_CLK->u_324.BITS_324` bitfields. Field meanings:

| Bitfield | Function | Value |
|------|------|------|
| `disp_ck_en`          | Display clock master switch          | Fixed `1` |
| `disp_func_en`        | Display function enable            | Fixed `1` |
| `r_disp_mux_clk_cg_en`| Mux clock gating enable        | Fixed `1` |
| `r_disp_div_en`       | Divider enable              | `1` when PLL selected |
| `r_disp_clk_src_sel1` | **PLL / Crystal**          | `1`=PLL, `0`=Crystal(40M) |
| `r_disp_clk_src_sel0` | **PLL1 / PLL2** (meaningful only when sel1=1) | `0`=PLL1(125M), `1`=PLL2(160M) |
| `r_disp_div_sel`      | Top-level divider selection            | Source document recommends **always writing 1** (divider handled by each interface) |

**Standard configuration for PLL1 = 125 MHz** (used by most drivers):

```c
/* Enable display clock */
PERIBLKCTRL_PERI_CLK->u_324.BITS_324.disp_ck_en          = 1;
PERIBLKCTRL_PERI_CLK->u_324.BITS_324.disp_func_en        = 1;
PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_mux_clk_cg_en = 1;

/* Select source PLL1 = 125MHz */
PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_div_en       = 1;
PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_clk_src_sel0 = 0;  /* 0=PLL1(125M), 1=PLL2(160M) */
PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_clk_src_sel1 = 1;  /* 1=PLL,       0=XTAL(40M)   */
PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_div_sel      = 1;  /* Divider handled by each interface */
```

- **If you only need 40M Crystal**: Simply delete the entire "source selection" section (`r_disp_div_en` and below); the default is XTAL 40M.
- **Select PLL2 = 160MHz**: Change `r_disp_clk_src_sel0` to `1` (sel1 stays 1).

Active driver measurements (`device/general/lcd/8762G/`):
- **PLL2=160M (sel0=1)**: `co5300_390x390_qspi`, `icna3311_280x456_qspi`, `ST77903_400400_RLSPI`.
- **PLL1=125M (sel0=0)**: All the rest -- RGB (`EK9716`, `NV3047`, `ST7282`, `st7701s_*`),
  SPI/QSPI (`NV3030B`, `st7789_170_320`), DBIB (`st7789_320_240_8080`, `st7796_320320`).

> Note: `co5300` / `icna3311` have two source selection code sections (`drv_lcd_power_on` and `rtk_lcd_hal_init`),
> **the `rtk_lcd_hal_init` section takes precedence** (consistent with pin group analysis conclusions).
>
> Observation: `r_disp_div_sel` is 0 or 1 in active drivers (source document recommends 1). Since actual division is handled by each interface,
> **new drivers should write `1` as per the source document**, and coordinate with the selected interface's divider field.

## Per-Interface Divider (Identical to 8773G, Only Source Frequencies Replace with Table Above)

| Interface | Divider field (struct) | Frequency formula | Divider value |
|------|----------------------|----------|----------|
| QSPI (DBIC)     | `LCDC_DBICCfgTypeDef.DBIC_SPEED_SEL`     | `Source / (2 × SEL)` | Integer, default 1 |
| RGB (eDPI)      | `LCDC_eDPICfgTypeDef.eDPI_ClockDiv`      | `Source / DIV` (input is the divider coefficient, no ±1, minimum 2) | Integer ≥2 |
| DBIB (8080)     | `LCDC_DBIBCfgTypeDef.DBIB_Clock_Divider` | `Source / (2 × DIV)` | 2–64 |

- For details on divider field value ranges, usage, and the eDPI "value is the divider coefficient" pitfall, **see all in [`clock-8773g.md`](clock-8773g.md)**, not repeated here.
- Common conversions (PLL1=125M): QSPI `SEL=2 → 31.25MHz`; RGB `ClockDiv=11 → 11.4MHz` (`NV3047`/`ST7282` current values).
  Common conversions (PLL2=160M): QSPI `SEL=2 → 40MHz`.

## Input Source / Selection Rules / Calculator Tool

Same as 8773G (see [`clock-8773g.md`](clock-8773g.md)): Main input = the **interface maximum clock frequency**
(max, optionally typical) confirmed by the customer reading the panel spec; actual frequency ≤ max, if typical is given, pick the closest to typical. Use
`scripts/clock_calc.py --chip 8762g --iface <qspi|rgb|dbib> --max <MHz>` to calculate the divider value and directly output
8762G's source selection code (`BITS_324` bitfield block, including `src_sel0/1`); `--chip 8762g` limits candidate sources to PLL1=125M/PLL2=160M/40M.
To narrow to a single source, add `--src 125`/`--src 160`/`--src 40`.
