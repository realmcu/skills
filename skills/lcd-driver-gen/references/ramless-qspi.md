# Ramless QSPI (RLSPI) — Subset of QSPI for Panels Without GRAM

Source: Reference driver `device/general/lcd/8762G/ST77903_400400_RLSPI.c` (`rtk_lcd_hal_init`, user-specified)
+ Hardware layer `hardware/lcdc/inc/rtl_ramless_qspi.h` (`LCDC_RLSPI_initTypeDef` / `RLSPI_Init`)
+ The **Ramless_QSPI** register table (base `0x4001_7A00`).

## What It Is / When to Use

- **RLSPI = Ramless QSPI**, a **subset of QSPI**, runs on DBIC (`LCDC_IF_DBIC`).
- Used for **panels without GRAM (Graphics RAM, on-panel framebuffer)**: the panel does not store frames itself; the host must
  **continuously push the entire frame line by line (infinite mode)**, and inject VSYNC/HSYNC commands at line/frame boundaries, inserting line/frame delays.
- So RLSPI = "QSPI physical layer + RGB-style timing drive". How to identify: **panel spec states no GRAM / ramless / RGB-over-SPI**.

## Differences from Regular QSPI (With GRAM)

| Aspect | Regular QSPI (With GRAM) | Ramless QSPI |
|--------|-------------------------|--------------|
| On-panel framebuffer | Yes, self-refresh after writing | No, host **continuously pushes every frame** (infinite mode) |
| Timing parameters | None (just push pixels after set_window) | Requires **VSA/VBP/VFP + width/height** + VSYNC/HSYNC commands + line/frame delays (like RGB) |
| LCDC key bits | `LCDC_RamlessEn = DISABLE` | **`LCDC_RamlessEn = ENABLE` + `LCDC_InfiniteModeEn = 1`** |
| Interface | `LCDC_IF_DBIC` | `LCDC_IF_DBIC` (same) |
| DMA | One frame at a time on demand | infinite / multiblock LLI, `LCDC_AutoWriteCmd` continuous output |
| Frame refresh | `start_transfer` pushes buffer | `LCDC_DMA_Infinite_Buf_Update(buf, buf+line_bytes)` swaps the buffer being pushed |
| set_window / transfer_done | Effective | **Empty implementation** (`return;`, relies on infinite mode auto-push) |
| Dedicated registers | None | `REG_RLSPI_*` full block (sync/hsync commands, porch, delays) |

## Platform Commonality Across 3 Platforms (Important)

**The RLSPI-specific initialization is identical across 8762G / 8773E / 8773G**, and can be copied directly from the reference driver:
`RLSPI_Init(...)` + `RAMLESS_QSPI->RLSPI_*` delay registers + `LCDC_RamlessEn/InfiniteModeEn` +
DBIC user-mode sending init command table + `framebuffer_init` infinite DMA.

**Only the peripherals are platform-dependent and need to be changed per target chip:**
- **Clock enable prefix**: Reference uses 8762G raw registers `PERIBLKCTRL_PERI_CLK->u_324.*`; 8773G/8773E should use respective
  `RCC_DisplayClockConfig(...)` (see `references/clock-8773g.md`, RLSPI uses DBIC → QSPI divider formula).
- **Pins & `LCDC_GroupSel`**: Reference's `LCDC_GroupSel = 2` is 8762G's group; 8773G uses QSPI Group0/1
  (`GroupSel=0/1`, see `references/pins-8773g-qspi.md`), pad config also follows that chip's QSPI convention.
- **Pad mode**: Reference uses `PAD_PINMUX_MODE + Pad_Dedicated_Config` (8762G style); 8773G QSPI uses
  `PAD_SW_MODE + Pad_HighSpeedFuncSel(HS_Func0) + Pad_HighSpeedMuxSel(FROM_CORE_DOMAIN)`.

## `rtk_lcd_hal_init` Skeleton (Following Reference Driver Order)

```c
void rtk_lcd_hal_init(void)
{
    /* 1. Enable DISP clock (platform-specific: 8773G uses RCC_DisplayClockConfig, see clock-8773g.md) */
    RCC_PeriphClockCmd(APBPeriph_DISP, APBPeriph_DISP_CLOCK, ENABLE);
    /* ...display clock source/div setup... */

    /* 2. Pad config (platform-specific: per target chip QSPI pin group) */
    xxx_pad_config();

    /* 3. RLSPI timing struct (★platform-independent★) */
    LCDC_RLSPI_initTypeDef rlspi = {0};
    rlspi.VSA = <PANEL>_VSA;   rlspi.VBP = <PANEL>_VBP;   rlspi.VFP = <PANEL>_VFP;
    rlspi.VSYNC_CMD  = <PANEL>_VSYNC_CMD;   rlspi.VSYNC_CMD_ADDR = <PANEL>_VSYNC_ADDR;
    rlspi.HSYNC_CMD_VBP     = <PANEL>_VBP_CMD;      rlspi.HSYNC_CMD_VBP_ADDR     = <PANEL>_VBP_ADDR;
    rlspi.HSYNC_CMD_VACTIVE = <PANEL>_VACTIVE_CMD;  rlspi.HSYNC_CMD_VACTIVE_ADDR = <PANEL>_VACTIVE_ADDR;
    rlspi.HSYNC_CMD_VFP     = <PANEL>_VFP_CMD;      rlspi.HSYNC_CMD_VFP_ADDR     = <PANEL>_VFP_ADDR;
    rlspi.DUMMY_CMD = <PANEL>_DUMMY_CMD;
    rlspi.width  = <PANEL>_WIDTH;   rlspi.height = <PANEL>_HEIGHT;
    RLSPI_Init(&rlspi);
    RAMLESS_QSPI->RLSPI_LINE_DELAY_IN_VACTIVE  = 800;      /* Intra-line delay (display_clock), adjustable */
    RAMLESS_QSPI->RLSPI_LINE_DELAY_OUT_VACTIVE = 8000;     /* Extra-line delay */
    RAMLESS_QSPI->RLSPI_FRAME_DELAY_INFINITE   = 250000;   /* Inter-frame delay (infinite mode) */

    /* 4. LCDC_Init (★key bits★) */
    LCDC_InitTypeDef lcdc_init = {0};
    lcdc_init.LCDC_Interface        = LCDC_IF_DBIC;
    lcdc_init.LCDC_RamlessEn        = ENABLE;              /* ← Enable ramless */
    lcdc_init.LCDC_InfiniteModeEn   = 1;                  /* ← Infinite frame output */
    lcdc_init.LCDC_PixelInputFormat = LCDC_INPUT_RGB888;
    lcdc_init.LCDC_PixelOutputFormat= (PIXEL_BYTES==3)? LCDC_OUTPUT_RGB888 : LCDC_OUTPUT_RGB565;
    lcdc_init.LCDC_PixelBitSwap     = LCDC_SWAP_BYPASS;
    lcdc_init.LCDC_GroupSel         = <platform/board>;    /* 8762G=2; 8773G uses QSPI group 0/1 */
    lcdc_init.LCDC_DmaThreshold     = 64;
    LCDC_Init(&lcdc_init);

    /* 5. DBIC config (QSPI physical layer) */
    LCDC_DBICCfgTypeDef dbic_init = {0};
    dbic_init.DBIC_SPEED_SEL = 1;    /* Calculated by clock_calc.py --iface qspi per panel spec */
    dbic_init.SCPOL = DBIC_SCPOL_LOW;  dbic_init.SCPH = DBIC_SCPH_1Edge;
    DBIC_Init(&dbic_init);
    DBIC->TXFTLR = <PANEL>_WIDTH;

    /* 6. Reset waveform (reference: LOW 100ms → HIGH 20ms → LOW 120ms, per panel spec) */
    /* 7. Switch to DBIC user/TX, send init command table xxx_init_cmds() */
    /* 8. Prepare framebuffer (PSRAM), xxx_framebuffer_init() start infinite DMA + LCDC_AutoWriteCmd(ENABLE) */
}
```

## `LCDC_RLSPI_initTypeDef` Fields → Register Mapping (Full Names)

| Struct Field | Full Name | Unit | Corresponding Register (Ramless_QSPI sheet) |
|-----------|------|------|-------------------------------|
| `VSA` | Vertical Sync Active height | scan lines | 0x0034 `vsa` [10:0] |
| `VBP` | Vertical Back Porch | scan lines | 0x0038 `a_vbp` (accumulates VSA+VBP) |
| `VFP` | Vertical Front Porch | scan lines | 0x0040 `total_height` (accumulates VSA+VBP+VACT+VFP) |
| `height` | Active lines (= panel height) | scan lines | 0x003C `a_vactive` (accumulates VSA+VBP+height) |
| `width`  | Active Width | pixels | 0x0044 `active_width` [11:0] |
| `VSYNC_CMD` / `_ADDR` | Command/address sent to panel during vertical sync | — | 0x0000 / 0x0004 |
| `HSYNC_CMD_VBP` / `_ADDR` | Back porch line sync command/address | — | 0x0008 / 0x000C |
| `HSYNC_CMD_VACTIVE` / `_ADDR` | Active area line sync command/address (command to push pixels per line) | — | 0x0010 / 0x0014 |
| `HSYNC_CMD_VFP` / `_ADDR` | Front porch line sync command/address | — | 0x0018 / 0x001C |
| `DUMMY_CMD` | Dummy command for timing fine-tuning | — | — |
| `line_delay_in_vactive` | Intra-active line delay | display_clock | 0x0024 |
| `line_delay_out_vactive` | Extra-active line delay | display_clock | 0x0020 |
| `frame_delay` | Inter-frame delay in infinite mode | display_clock | 0x0028 |

> `RLSPI_Init` internally accumulates raw `VSA/VBP/VFP/height` into registers `a_vbp / a_vactive / total_height`
> (same accumulation logic as eDPI). The delay fields in the reference are not filled into the struct but **written directly to registers** after `RLSPI_Init` — either approach works.
> **Bit width limits**: vertical fields 11-bit → `total_height ≤ 2047`; `active_width` 12-bit → `≤ 4095`.
> Note: In spec, when `total_height == a_vactive`, VFP can be ignored.

## Init Command Table Format (Different from Regular QSPI Table)

RLSPI panel commands use QSPI "command+address" phase: `instruction` is the panel's QSPI write opcode (ST77903 uses **0xDE**,
not regular QSPI's 0x02), the command byte goes in the **address middle segment**:

```c
typedef struct { uint8_t instruction; uint8_t index; uint16_t delay; uint16_t wordcount; uint8_t payload[N]; } cmd_struct;
/* When sending: sdat[0]=instruction(0xDE); sdat[1]=0; sdat[2]=index(command byte); sdat[3]=0; sdat[4..]=payload */
```

After generating with `seq_convert.py --style qspi-table`, change `instruction` to the panel's ramless write opcode
(e.g., 0xDE), and keep 0x11(sleep-out)+120ms, 0x29(display-on), 0x3A(color depth: 565=0x05 / 888=0x07).
The last row typically includes `0x2C` (memory write, enter pixel stream).

## How to Obtain Timing Parameters (Same Logic as RGB)

- Customer must confirm per panel ramless/QSPI spec: **VSA / VBP / VFP, width/height**, and
  **VSYNC/HSYNC command bytes and addresses per phase** (`*_CMD` / `*_ADDR`), DUMMY_CMD. Commands/addresses are defined by the panel vendor,
  **must follow spec**, cannot be guessed.
- **Line/frame delays** (`RLSPI_LINE_DELAY_*` / `RLSPI_FRAME_DELAY_INFINITE`) affect frame rate and stability,
  start with reference values (800 / 8000 / 250000) for bring-up, then tune per target frame rate/spec; mark as adjustable temporary values.
- Acquisition strategy matches `references/rgb-timing.md`: **Customer reads spec to confirm numbers; spec document is for reference only, do not silently trust auto-parsing**.

## Self-Check

- [ ] Confirm panel is indeed **no GRAM** (otherwise use regular QSPI)
- [ ] `LCDC_Interface=LCDC_IF_DBIC` + `LCDC_RamlessEn=ENABLE` + `LCDC_InfiniteModeEn=1`
- [ ] RLSPI struct fields complete (VSA/VBP/VFP, width/height, per-phase *_CMD/*_ADDR, DUMMY_CMD), commands/addresses from spec
- [ ] `total_height ≤ 2047`, `active_width ≤ 4095`
- [ ] Init command table `instruction` uses panel ramless write opcode (e.g., 0xDE), command byte in `index`; keep 0x11/0x29/0x3A
- [ ] Framebuffer in DMA-able memory (PSRAM), `LCDC_DMA_Infinite_Buf_Update` swaps frames, `LCDC_AutoWriteCmd(ENABLE)` continuous push
- [ ] Three platform-dependent items updated per target chip: clock enable (RCC_DisplayClockConfig), pad, `LCDC_GroupSel`
- [ ] `set_window`/`start_transfer`/`transfer_done` are empty implementations for RLSPI (don't fill like regular QSPI)
- [ ] DBIC clock `DBIC_SPEED_SEL` per panel spec (clock_calc.py --iface qspi), not exceeding max
