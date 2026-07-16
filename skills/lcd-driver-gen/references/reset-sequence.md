# LCD Reset Timing

After panel power-up, the RST pin must be pulled to generate a reset pulse, restarting the panel to a known state before running the init sequence.

## Waveform Structure (Fixed, skill generates directly)

```
RST = HIGH  →  delay t1  →  RST = LOW  →  delay t2  →  RST = HIGH  →  delay t3  →  Init
                (Stabilize)    (Assert reset)  (Low pulse width)  (Release reset)   (Wait for ready)
```

- **t1**: High-level stabilization time, not critical, a few ms is sufficient.
- **t2 = Low pulse width**: From spec's *reset low pulse width*, a **minimum constraint** (most controllers ≥ 10 µs).
- **t3 = Post-release wait**: From spec's *reset complete / reset cancel time*, typically **~120 ms**;
  during this period the panel's internal registers reset; commands sent too early are dropped → panel won't light up.

## How Values Are Obtained

The three reset delays are **min/typical constraints from the spec, not precise vendor data**, and have industry-recognized safe defaults.
Therefore, unlike clock and init sequence:

| Source | Value Nature | Spec Reading Required? |
|--------|-------------|----------------------|
| Clock | Safety-critical, overclocking won't display | ✅ Required (customer confirms max) |
| Init Sequence | Precise vendor register data | ✅ Required (datasheet section) |
| **Reset timing** | Min/typical constraints, has safe defaults | ❌ Defaults are fine, reading spec only for optimization/edge cases |

**Default strategy**: The skill auto-generates the waveform + **safe default delays**, no need to consult the customer.
Only ask the customer to read the spec when ① optimizing boot time (shortening t3 to spec minimum) or ② encountering a panel with unusually long reset requirements.

### Safe Defaults
- `t1 = 10 ms`, `t2 = 10 ms` (far exceeding the 10 µs minimum), `t3 = 120 ms` (covers most panels).

### Repository Measured Reference (All conservative working values)
- `lcd_st77916_360_360_qspi.c`：100 / 50 / 130 ms
- `lcd_c05300_390_450_qspi.c`：20 / 20 / 120 ms

## Generation Template (This repo uses `Pad_Config` for level control, not GPIO_WriteBit)

```c
static void lcd_reset(void)
{
    Pad_Config(LCD_QSPI_RST, PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_NONE, PAD_OUT_ENABLE, PAD_OUT_HIGH);
    platform_delay_ms(10);   /* t1 */
    Pad_Config(LCD_QSPI_RST, PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_NONE, PAD_OUT_ENABLE, PAD_OUT_LOW);
    platform_delay_ms(10);   /* t2 = reset low pulse width (spec min) */
    Pad_Config(LCD_QSPI_RST, PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_NONE, PAD_OUT_ENABLE, PAD_OUT_HIGH);
    platform_delay_ms(120);  /* t3 = reset complete wait (spec typ) */
}
```

In `rtk_lcd_hal_init` / `power_on`, **call `lcd_reset()` first, then run the init sequence**.

## Edge Cases

- **No RST pin**: Some panels reset via software commands (e.g., 0x01 SWRESET). If the pin table has no RST, the skill skips hardware
  reset and instead keeps 0x01 + delay at the start of the init sequence (if the datasheet requires it).
- **RST active low**: This section assumes active low (LOW resets); if a panel uses active high, invert the levels and note it during generation.
- The reset pulse must be sent **after panel power is stable** (configure power enable pin + stabilization delay first, then reset).
