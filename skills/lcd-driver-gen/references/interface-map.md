# Interface Mapping: Type → Hardware Layer Header → Style → Recommended Reference Driver

Hardware layer headers are in `hardware/lcdc/inc/`. The transfer interface determines which header to use, how the init sequence is written, and how start_transfer is set up.

## Lookup Table

| Interface | Hardware Layer Header | Init Sequence Style | How Panel Commands Are Sent |
|-----------|----------------------|---------------------|----------------------------|
| **QSPI** | `rtl_lcdc_dbic.h` + `rtl_ramless_qspi.h` + `rtl_lcdc_dma.h` | **Table-driven** `CMD_DESC[]` | Write opcode fixed at 0x02, panel command in `index` field |
| **RGB**  | `rtl_lcdc_edpi.h` + `rtl_lcdc_dphy.h` + `rtl_lcdc_dma.h` | Inline `write_command/write_data` | Send command bytes directly |
| **SPI**  | `rtl_lcdc.h` (LCDC SPI) + `rtl_lcdc_dma.h` | Inline `xxx_cmd/xxx_cmd_paramN` | Send command bytes directly |
| **8080/DBIB** | `rtl_lcdc_dbib.h` + `rtl_lcdc_dma.h` | Inline `xxx_write_cmd/xxx_write_data` | Send command bytes directly |
| **Ramless-QSPI (RLSPI)** | `rtl_lcdc_dbic.h` + `rtl_ramless_qspi.h` + `rtl_lcdc_dma.h` | **Table-driven** (write opcode often 0xDE, command in `index`) | Via DBIC + `LCDC_RamlessEn=ENABLE` |

> Two styles: **Table-driven** (QSPI) uses `seq_convert.py --style qspi-table`; **Inline** (RGB/SPI/8080) uses `--style inline`.
> **Ramless-QSPI is a subset of QSPI** for **panels without GRAM (on-panel framebuffer)**, requiring the host to continuously push entire frames like RGB.
> Requires additional timing parameters (VSA/VBP/VFP + width/height + VSYNC/HSYNC commands). See `ramless-qspi.md`.

## Recommended Reference Drivers Per Chip Directory

Pick the one with the **same interface and closest resolution** as a template.

> If the target chip directory has no reference driver with the same interface, use the code skeleton from `references/code-skeletons.md`,
> take the corresponding complete code snippet by interface+chip, and replace the template variables.

### 8773G (`device/general/lcd/8773G/`)
- QSPI：`lcd_st77916_360_360_qspi.c` / `lcd_sh8601z_410_502_qspi.c` / `lcd_c05300_390_450_qspi.c` / `nv3041A_480_272_qspi.c`
- RGB：`st7701s_480480_rgb.c` / `EK9716_800480_rgb.c` / `lcd_st7265_800480_rgb.c`
- SPI：`st7789_170_320_lcdc_spi.c`
- 8080：`st77916_360_360_dbib_8080.c`

### 8773E (`device/general/lcd/8773E/`)
- QSPI：`lcd_st77916_360_360_qspi.c` / `SH8601Z_454454_qspi.c` / `lcd_c05300_390_450_qspi.c` / `nv3041A_480_272_qspi.c`
- RGB：`st7701s_480480_rgb.c` / `hx8369_480480_rgb.c` / `lcd_st7265_800480_rgb.c`

### 8762G (`device/general/lcd/8762G/`)
- QSPI：`co5300_390x390_qspi.c` / `icna3311_280x456_qspi.c`
- RGB：`st7701s_480480_rgb.c` / `NV3047_480272_rgb.c` / `ST7282_480272_rgb.c` / `EK9716_800480_rgb.c`
- SPI：`st7789_170_320_lcdc_spi.c` / `NV3030B_76x284_spi.c`
- 8080/DBIB：`st7789_320_240_8080.c` / `st7796_320320_dbib.c` / `nt35510_480800_dbib.c`
- RLSPI：`ST77903_400400_RLSPI.c`

## QSPI Init Table Structure (Reference for Adaptation)

```c
typedef struct _<PANEL>_CMD_DESC {
    uint8_t  instruction;                 // Always the write opcode, e.g. 0x02
    uint8_t  index;                       // Panel command byte (e.g. 0xF0)
    uint16_t delay;                       // Post-command delay ms
    uint16_t wordcount;                   // Payload byte count
    uint8_t  payload[<PANEL>_MAX_PARA_COUNT];
} <PANEL>_CMD_DESC;

static const <PANEL>_CMD_DESC <PANEL>_POWERON_SEQ_CMD[] = {
    {0x02, 0xF0, 0,   1, {0x28}},
    {0x02, 0x3A, 0,   1, {0x55}},         // 0x55=565, 0x66=666(888)
    {0x02, 0x11, 120, 0, {0x00}},         // sleep out + 120ms
    {0x02, 0x29, 20,  0, {0x00}},         // display on + 20ms
    {0x00, 0,    0,   0, {0}},            // SEQ_FINISH_CODE termination row
};
```

Inside the driver, a `<PANEL>_Reg_Write(seq)` iterates the table, sending a QSPI frame for each row and delaying by `delay`.

### 8773G QSPI Pin Groups
When generating a QSPI driver for 8773G, the pins cannot be copied verbatim from the reference driver — RTL8773G QSPI has multiple pin groups,
the group must be selected per target board and `LCDC_GroupSel` set accordingly. See `pins-8773g-qspi.md`.

### 8773E Pins
When generating a 8773E driver, see `pins-8773e.md` (QFN88, combined RGB/QSPI/8080 table). Key points: **RGB and QSPI each have 2 groups**
(select group and set `LCDC_GroupSel` accordingly), **8080 only has Group0**. Key difference from 8773G: **CM=ADC3, 8080 RD#=ADC3 (neither is P0_3)**;
the two QSPI pin groups share the same pins as 8773G (`SH8601Z_454454_qspi.c`=Group1, `lcd_st77916/nv3041A`=Group0).

### 8762G Pins
When generating a 8762G driver, see `pins-8762g.md` (QFN88, combined RGB/QSPI/8080 table). Key points:
- **RGB single parallel port** + RGB888 / RGB565 Config1/2/3 four color mappings; all RGB templates **`LCDC_GroupSel=1`**.
- **QSPI 3 groups** (Group1/2/3, Group3 supports Octal), **`LCDC_GroupSel = group number`** (G1→1/G2→2/G3→3, determined by pin group);
  **Don't copy the `//QFN88 2 - QFN68 1` comment from drivers** (it contradicts actual pins, e.g., co5300 uses Group3/`GroupSel=3`).
- **8080/DBIB 3 groups**; `st7789_320_240_8080.c` / `st7796_320320_dbib.c` both use **Group2** and **don't set `LCDC_GroupSel` (defaults to 0)**.
- **Pad style differs from 8773E/8773G**: `Pad_Config(pin, PAD_PINMUX_MODE, ...)` + `Pad_Dedicated_Config(pin, ENABLE)`, **no `Pad_HighSpeed*`**.
- Critical mux pin **P3_6**: RGB uses as CM, QSPI/8080 Group1/2 uses as RESX, Group3 uses as data (SIO3/D3) — when using Group3, reset must use a different pin.

## DMA / Color Depth Notes (QSPI, `rtk_lcd_hal_start_transfer`)

- **`DataSize` must be Word**: `LCDC_DMA_SourceDataSize` / `DestinationDataSize` must always be
  `LCDC_DMA_DataSize_Word`, the hardware does not support Byte/Half-Word, don't change these fields based on color depth.
- **`Msize + DmaThreshold = 128`**: `SourceMsize` / `DestinationMsize` (Msize, burst length) and
  `DmaThreshold` in `LCDC_Init` must **sum to 128, and not exceed 128** — it is the hardware FIFO limit.
  Example: `DmaThreshold = 64` with `Msize_64` (64 + 64 = 128); `DmaThreshold = 32` with `Msize_...`
  such that their sum is 128. Changing either requires updating the other to keep the sum at 128.
- What actually changes with color depth is **`OUTPUT_PIXEL_BYTES`** (determines `len_byte = w * h * OUTPUT_PIXEL_BYTES` in `set_window`),
  as well as framebuffer line byte width / DMA transfer length; `DataSize`, `Msize` do not change with color depth.
- `OUTPUT_PIXEL_BYTES` determines `len_byte = w * h * OUTPUT_PIXEL_BYTES` in `set_window`.
