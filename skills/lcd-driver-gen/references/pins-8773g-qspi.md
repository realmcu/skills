# RTL8773G QSPI Pin Groups

RTL8773G QSPI has **2** pin groups on different physical pins. When initializing the driver:
1. Configure the pins of the selected group using `Pad_Config` / `Pad_HighSpeedFuncSel` / `Pad_HighSpeedMuxSel`;
2. Set `LCDC_GroupSel` in `LCDC_InitTypeDef` to the corresponding value.

> Pin configuration and `LCDC_GroupSel` must **point to the same group**, otherwise the signal routing will not match the actual board wiring and the display won't light up.

## Pin Mapping Table

| Signal | Driver Macro (Convention) | **Group0** (`GroupSel=0`) | **Group1** (`GroupSel=1`) |
|------|----------------|--------|--------|
| LCD_RST (Reset)  | `LCD_QSPI_RST` | P9_0 | P4_4 |
| LCD_TE (VSYNC)   | `LCD_QSPI_TE`  | P2_2 | P2_2 |
| QSPI_SIO0        | `LCD_QSPI_D0`  | P2_6 | P9_3 |
| QSPI_SIO1        | `LCD_QSPI_D1`  | P2_7 | P9_1 |
| QSPI_SIO2        | `LCD_QSPI_D2`  | P4_0 | P9_0 |
| QSPI_SIO3        | `LCD_QSPI_D3`  | P4_1 | P9_5 |
| QSPI_SIO4–SIO7   | (Octal mode only) | P4_2, P4_3, P4_4, P4_5 | — (Group1 only has quad SIO0–3) |
| QSPI_DCX (RS/DC) | `LCD_QSPI_RS`  | P2_4 | P4_5 |
| QSPI_CLK         | `LCD_QSPI_CLK` | P2_5 | P9_4 |
| QSPI_CS          | `LCD_QSPI_CS`  | P2_3 | P9_2 |

> Note: `P9_0` serves as RST in Group0 and SIO2 in Group1 — the same pin carries different signals in different groups, but only one group is activated.
> **Group0 supports up to Octal (SIO0–7)**: regular quad displays only use SIO0–3; reference driver `nv3041A_480_272_qspi.c` uses all SIO0–7 (BL lands on the unused ADC_3). Group1 is quad only.
> RST/TE/DCX are regular GPIOs, their assignment varies by board (e.g., `lcd_sh8601z_466_466_qspi.c` RST=P3_0, `lcd_st77916` TE=P3_1/RST=P5_2/BL=P5_0); only the high-speed SIO/CLK/CS must strictly match the selected group.

## `LCDC_GroupSel` Value Mapping (Verified)

**`Group0 → LCDC_GroupSel = 0`, `Group1 → LCDC_GroupSel = 1`** (the group number is the value).

Verification basis (high-speed pins of existing st77916 QSPI drivers in the repository match this table one by one):

| Driver | Data/CLK/CS pins | Match | `LCDC_GroupSel` |
|------|-----------------|------|-----------------|
| `device/general/lcd/8773E/lcd_st77916_360_360_qspi.c` | D0=P2_6 D1=P2_7 D2=P4_0 D3=P4_1 CLK=P2_5 CS=P2_3 | **Group0** | `= 0` ✓ |
| `device/general/lcd/8773G/lcd_st77916_360_360_qspi.c` | D0=P9_3 D1=P9_1 D2=P9_0 D3=P9_5 CLK=P9_4 CS=P9_2 | **Group1** | `= 1` ✓ |

> The comment `//value of 1 or 2` in header `rtl_lcdc.h:450` is outdated/inaccurate; refer to this table and actual drivers.
> RST / TE / DCX are regular GPIOs. Some existing drivers may differ slightly from this table for these pins (board-level variation),
> but **high-speed QSPI pins SIO/CLK/CS must strictly match the selected group** — they determine the `Pad_HighSpeedMuxSel` routing.

## Generation Template

### Group1 (P9_* group, 8773G st77916 active configuration, can be used directly)

```c
#define LCD_QSPI_RST   P4_4
#define LCD_QSPI_TE    P2_2
#define LCD_QSPI_D0    P9_3    /* SIO0 */
#define LCD_QSPI_D1    P9_1    /* SIO1 */
#define LCD_QSPI_D2    P9_0    /* SIO2 */
#define LCD_QSPI_D3    P9_5    /* SIO3 */
#define LCD_QSPI_RS    P4_5    /* DCX  */
#define LCD_QSPI_CLK   P9_4
#define LCD_QSPI_CS    P9_2

/* At LCDC initialization: */
lcdc_init.LCDC_GroupSel = 1;   /* Group1 */
```

### Group0 (P2_*/P4_* group, 8773E st77916 configuration)

```c
#define LCD_QSPI_RST   P9_0
#define LCD_QSPI_TE    P2_2
#define LCD_QSPI_D0    P2_6    /* SIO0 */
#define LCD_QSPI_D1    P2_7    /* SIO1 */
#define LCD_QSPI_D2    P4_0    /* SIO2 */
#define LCD_QSPI_D3    P4_1    /* SIO3 */
#define LCD_QSPI_RS    P2_4    /* DCX  */
#define LCD_QSPI_CLK   P2_5
#define LCD_QSPI_CS    P2_3

/* At LCDC initialization: */
lcdc_init.LCDC_GroupSel = 0;   /* Group0 */
```

### Pad Configuration Skeleton (Common to both groups, just replace the macros above)

```c
static void qspi_pad_config(void)
{
    const uint8_t hs_pins[] = {LCD_QSPI_D0, LCD_QSPI_D1, LCD_QSPI_D2, LCD_QSPI_D3,
                               LCD_QSPI_CS, LCD_QSPI_CLK};
    for (uint32_t i = 0; i < sizeof(hs_pins); i++)
    {
        Pad_Config(hs_pins[i], PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
        Pad_HighSpeedFuncSel(hs_pins[i], HS_Func0);
        Pad_HighSpeedMuxSel(hs_pins[i], FROM_CORE_DOMAIN);  /* Active QSPI drivers all use this value; ≡ FROM_HS_MUX = 1 */
    }
    Pad_Config(LCD_QSPI_TE, PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_DOWN, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_HighSpeedFuncSel(LCD_QSPI_TE, HS_Func0);          /* TE also needs FuncSel (following lcd_sh8601z_410_502_qspi.c) */
    Pad_HighSpeedMuxSel(LCD_QSPI_TE, FROM_CORE_DOMAIN);
    /* RST / RS(DCX) are typically regular GPIO outputs, configure with Pad_Config as OUT mode as needed */
}
```

## Rules When Generating 8773G QSPI Driver

1. Ask the user to confirm whether the target board uses **Group0** or **Group1** (by default, refer to the active driver for the same model: 8773G currently uses Group1).
2. Fill in pin macros according to the selected group; set `lcdc_init.LCDC_GroupSel` to the same number (0 or 1).
3. High-speed pins SIO/CLK/CS must strictly match the group; for RST/TE/DCX, if the board has special wiring, follow the user's specification.
