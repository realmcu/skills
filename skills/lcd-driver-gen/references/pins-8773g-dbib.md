# RTL8773G DBIB / 8080 Pin Out

Source: Reference driver `device/general/lcd/8773G/st77916_360_360_dbib_8080.c/.h`.

**DBIB** = Display Bus Interface Type B (MIPI DBI Type-B), i.e., **Intel 8080 parallel** MCU interface.

## Key Findings (Different from QSPI/RGB)

- **8080 on RTL8773G only has Group0 pins** (the pinout data has no I8080 Group1 mapping), so
  `lcdc_init.LCDC_GroupSel = 0` is fixed — unlike QSPI/RGB, there's no need to ask the user which group.
- **Data bus is 8-bit (D0–D7 only)**: the pinout only has 8 8080 data lines, and `LCDC_DBIBCfgTypeDef`
  has no bus width field — the bus width is determined by how many D lines are configured. 888 panels use multiple transfers over 8080, not 16/18 lines.
- **Clock source = 40MHz domain**. Reference driver uses
  `RCC_DisplayClockConfig(DISPLAY_CLOCK_SOURCE_40MHZ, DISPLAY_CLOCK_DIV_1)` + `DBIB_Clock_Divider=2`
  → 40/(2×2)=**10MHz** WR clock. See divider formula in `references/clock-8773g.md` (DBIB section).

## Pin Mapping Table (Full Name + Driver Macro + Physical Pin)

| Signal (Full Name) | Description | Driver Macro | Physical Pin (ALL Pin out) |
|-----------|------|-----------|------------------------|
| 8080_CS# (Chip Select, active low)      | Chip Select          | `LCD_8080_CS`  | P2_3 |
| 8080_DCX (Data/Command select, i.e. RS/Register Select) | Data/Command Select | `LCD_8080_DCX` | P2_4 |
| 8080_WR# (Write strobe, active low)     | Write Strobe        | `LCD_8080_WR`  | P2_5 |
| 8080_RD# (Read strobe, active low)      | Read Strobe (often unused for write-only displays) | `LCD_8080_RD`  | P0_3 (ADC_3) |
| 8080_D0..D7 (Data bus bit0..7)      | 8-bit Data Bus     | `LCD_8080_D0..D7` | P2_6, P2_7, P4_0, P4_1, P4_2, P4_3, P4_4, P4_5 |
| 8080_LCD_TE (Tearing Effect)        | Tearing Effect Input       | `LCD_TE_SYNC`  | P2_2 |
| LCD_RESX (Reset, active low)            | Reset               | `LCD_8080_RST` | P9_0 |

Data line details: D0=P2_6, D1=P2_7, D2=P4_0, D3=P4_1, D4=P4_2, D5=P4_3, D6=P4_4, D7=P4_5.

> This table **matches exactly** the macros in reference driver `st77916_360_360_dbib_8080.h` — meaning the reference driver uses the datasheet's I8080 Group0.
> When changing panels, these pins are typically **used as-is**, only needing changes if the customer's board has different wiring.

## Pin Muxing (Watch for Conflicts When Changing Panels / Layout)

The same physical pad carries different signals across interfaces (only the selected interface's set is activated):

| Pin | 8080 | QSPI Group0 | RGB888 Group0 |
|------|------|-------------|----------------|
| P0_3 | RD#  | CM (often used as backlight BL) | CM |
| P2_3 | CS#  | QSPI_CSN    | DE |
| P2_4 | DCX  | QSPI_DCX    | HSYNC |
| P2_5 | WR#  | QSPI_CLK    | PCLK |
| P2_6..P4_5 | D0..D7 | QSPI_SIO0..7 | D0..D7 |
| P9_0 | RESX | LCD_RESX    | SD |

- **P0_3 conflict note**: 8080 uses P0_3 as RD#; elsewhere it is often used as **CM/backlight BL**. If the target board has BL connected to P0_3
  and the panel is write-only, consider not enabling RD# (write doesn't need read), freeing P0_3 for backlight — **must be confirmed with the customer**.

## Pad Configuration Notes

The reference driver uses **`HS_Func0` + `FROM_CORE_DOMAIN`** for high-speed pins D0–D7 / CS / DCX / RD / WR
(`st77916_360_360_dbib_8080.c:394-417`). This is consistent with 8773G QSPI/RGB drivers —
**not specific to 8080**: `FROM_CORE_DOMAIN` and `FROM_HS_MUX` have the same value (=1), as seen in the code:
`#define FROM_CORE_DOMAIN 1` (`st7701s_480480_rgb.c:347`) and `#define FROM_CORE_DOMAIN FROM_HS_MUX`
(`lcd_st7265_800480_rgb.c:237`) and the comment `//1: FROM_CORE_DOMAIN & FROM_HS_MUX`
(`lcd_st77916_360_360_qspi.c:96`). Just use `FROM_CORE_DOMAIN` as the reference does.

```c
static void dbib_pad_config(void)
{
    const uint8_t hs_pins[] = {LCD_8080_D0, LCD_8080_D1, LCD_8080_D2, LCD_8080_D3,
                               LCD_8080_D4, LCD_8080_D5, LCD_8080_D6, LCD_8080_D7,
                               LCD_8080_CS, LCD_8080_DCX, LCD_8080_RD, LCD_8080_WR};
    for (uint32_t i = 0; i < sizeof(hs_pins); i++)
    {
        Pad_Config(hs_pins[i], PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
        Pad_HighSpeedFuncSel(hs_pins[i], HS_Func0);
        Pad_HighSpeedMuxSel(hs_pins[i], FROM_CORE_DOMAIN);
    }
    /* RST as regular GPIO output; TE see below */
}
```

Reset (reference driver): `Pad_Config(LCD_8080_RST, ..., PAD_OUT_ENABLE, PAD_OUT_HIGH/LOW)` for three-stage waveform.
TE (optional): HW TE uses `LCD_TE_SYNC`(P2_2), with `Pad_Config` + `Pad_HighSpeedMuxSel(FROM_CORE_DOMAIN)`.

## LCDC Initialization Key Items (8080)

```c
RCC_DisplayClockConfig(DISPLAY_CLOCK_SOURCE_40MHZ, DISPLAY_CLOCK_DIV_1);
LCDC_InitTypeDef lcdc_init = {0};
lcdc_init.LCDC_GroupSel   = 0;               /* 8080 only has Group0 */
lcdc_init.LCDC_Interface  = LCDC_IF_DBIB;
lcdc_init.LCDC_PixelInputFormat  = LCDC_INPUT_RGB565;   /* based on color depth */
lcdc_init.LCDC_PixelOutputFormat = LCDC_OUTPUT_RGB565;
LCDC_DBIBCfgTypeDef dbib_init = {0};
dbib_init.DBIB_Clock_Divider = 2;            /* 40/(2×2)=10MHz, calculated from panel spec using clock_calc.py --iface dbib */
/* Other GuardTime/WRDelay follow reference driver defaults (DBIB_WR_HALF_DELAY etc.) */
```

## Rules When Generating 8773G 8080/DBIB Driver

1. Pins **default to the reference driver/table** (Group0), unless the customer board has different wiring. `LCDC_GroupSel = 0` is fixed.
2. Confirm whether RD# is needed (most write-only displays don't use it); if P0_3 is used by backlight, confirm trade-off with the customer.
3. Panel commands use **inline** `xxx_write_cmd/xxx_write_data` (`seq_convert.py --style inline`),
   CS/DCX timing follows the reference driver (pull CS for commands, `DBIB_SendCmd`; write data `DBIB_SendData`).
4. High-speed pins uniformly use `HS_Func0 + FROM_CORE_DOMAIN` (same as QSPI/RGB); DMA uses `LCDC_DBIB_SetCmdSequence({0x2C})` + auto mode.
5. Clock: use `clock_calc.py --iface dbib` based on panel spec to derive `DBIB_Clock_Divider` (see `clock-8773g.md`).

## Self-Check

- [ ] `LCDC_GroupSel = 0`, `LCDC_Interface = LCDC_IF_DBIB`
- [ ] 8-bit bus D0–D7 = P2_6/P2_7/P4_0..P4_5; CS=P2_3 DCX=P2_4 WR=P2_5 RD=P0_3 RST=P9_0 TE=P2_2
- [ ] High-speed pins use `HS_Func0 + FROM_CORE_DOMAIN` (follows reference; same as QSPI/RGB, `FROM_CORE_DOMAIN`≡`FROM_HS_MUX`=1)
- [ ] P0_3(RD#) conflict with backlight BL confirmed with customer
- [ ] WR clock calculated from `DBIB_Clock_Divider` ≤ panel spec (source 40MHz domain)
