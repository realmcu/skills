# Code Skeleton (for use when no reference driver is available)

When there is no same-interface reference driver to clone under `device/general/lcd/<chip>/`, take the complete code skeleton directly from here.
Replace template variables and it's ready to compile -- no need to depend on existing drivers in the repo.

> **When NOT to use this section**: When there is a reference driver (existing `.c/.h` with similar resolution) for the same chip and same interface in the repo, **clone the reference driver first**,
> because the reference driver has been verified on actual hardware. This section is a "fallback when no reference driver is available".

---

## Template Variables

| Variable | Replacement | Example |
|------|--------|------|
| `<PANEL>` | Panel model (all uppercase), RGB without resolution infix, QSPI with resolution infix | `TESTLCD` / `ST77916_360_360` |
| `<panel>` | Panel model (all lowercase) | `testlcd` / `st77916` |
| `<W>` | Width in pixels | `800` |
| `<H>` | Height in pixels | `480` |
| `<WIDTH>` | Width value (C expression) | `800` |
| `<HEIGHT>` | Height value (C expression) | `480` |
| `<DRV_PIXEL_BITS>` | Bits per pixel | `16` (RGB565) / `24` (RGB888) |
| `<INPUT_FORMAT>` | INPUT format macro | `LCDC_INPUT_RGB565` / `LCDC_INPUT_RGB888` |
| `<OUTPUT_FORMAT>` | OUTPUT format macro | `LCDC_OUTPUT_RGB565` / `LCDC_OUTPUT_RGB888` |
| `<COLORMAP>` | eDPI ColorMap macro | `EDPI_PIXELFORMAT_RGB888` / `EDPI_PIXELFORMAT_RGB565_2` |
| `<GROUP_SEL>` | Selected group | `0`(Group0) / `1`(Group1) |
| `<RST_PIN>` | Reset pin | `P7_3` |
| `<BL_PIN>` | Backlight pin (delete if unused) | `P0_3` |
| `<HSA>` `<HBP>` `<HFP>` | RGB horizontal timing | `48` `40` `40` |
| `<VSA>` `<VBP>` `<VFP>` | RGB vertical timing | `1` `31` `13` |
| `<CLOCK_DIV>` | eDPI clock divider | `8` |
| `<DMA_CH_NUM>` | DMA channel number | `0` |
| `<DMA_CH_IDX>` | DMA channel index | `LCDC_DMA_Channel0` |
| `<MSIZE>` | DMA Msize | `LCDC_DMA_Msize_64` |
| `<DMA_THRESHOLD>` | DMA Threshold | `64` |
| `<QSPI_GROUP>` | QSPI group number | `0`(G0) / `1`(G1) |
| `<SPEED_SEL>` | QSPI clock divider | `2` |
| `<CLK_SRC>` | QSPI clock source | `LCDC_BUS_CLK_200M` / `LCDC_BUS_CLK_280M` |

---

## 1. Common Header Template (All Interfaces)

```c
/*
 * Copyright(c) 2025, Realtek Semiconductor Corporation. All rights reserved.
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#ifndef _LCD_<PANEL>_<W>_<H>_<IFACE>_H_
#define _LCD_<PANEL>_<W>_<H>_<IFACE>_H_

#ifdef __cplusplus
extern "C" {
#endif
#include "stdint.h"
#include "stdbool.h"

/* === Header macros === */
/* QSPI / SPI / 8080 (with GRAM interface) use this set: */
#define <PANEL>_LCD_WIDTH                   <W>
#define <PANEL>_LCD_HEIGHT                  <H>
#define INPUT_PIXEL_BYTES                   2       /* framebuffer side: 2/3/4 */
#define OUTPUT_PIXEL_BYTES                  2       /* on the line: 2/3 */
#if   INPUT_PIXEL_BYTES == 2
#define <PANEL>_DRV_PIXEL_BITS              16
#elif INPUT_PIXEL_BYTES == 3
#define <PANEL>_DRV_PIXEL_BITS              24
#elif INPUT_PIXEL_BYTES == 4
#define <PANEL>_DRV_PIXEL_BITS              32
#endif
#define TE_VALID                            0       /* 0=no TE, 1=use TE */

/* RGB header simplified version (use this set below, delete the above):
#define <PANEL>_LCD_WIDTH                   <W>
#define <PANEL>_LCD_HEIGHT                  <H>
#define <PANEL>_DRV_PIXEL_BITS              <DRV_PIXEL_BITS>
*/

/* Enum */
typedef enum
{
    LCDC_TE_TYPE_NO_TE = 0x00,
    LCDC_TE_TYPE_HW_TE = 0x01,
    LCDC_TE_TYPE_SW_TE = 0x02,
} T_LCDC_TE_TYPE;

/* === Function declarations === */
void rtk_lcd_hal_init(void);
void rtk_lcd_hal_update_framebuffer(uint8_t *p_buf, uint32_t size);
void rtk_lcd_hal_clear_screen(uint32_t ARGB_color);
void rtk_lcd_hal_set_window(uint16_t xStart, uint16_t yStart, uint16_t w, uint16_t h);
void rtk_lcd_hal_start_transfer(uint8_t *buf, uint32_t len);
void rtk_lcd_hal_transfer_done(void);
uint32_t rtk_lcd_hal_get_width(void);
uint32_t rtk_lcd_hal_get_height(void);
uint32_t rtk_lcd_hal_get_pixel_bits(void);
bool rtk_lcd_hal_power_on(void);
bool rtk_lcd_hal_power_off(void);

/* DLPS related (optional, but most drivers have it) */
bool rtk_lcd_hal_dlps_check(void);
void rtk_lcd_hal_lcd_enter_dlps(void);
uint32_t rtk_lcd_hal_dlps_restore(void);
void rtk_lcd_dlps_init(void);
bool rtk_lcd_wake_up(void);

/* QSPI table-driven additional requirements */
#define <PANEL>_MAX_PARA_COUNT              60      /* Adjust based on actual max parameter count */
typedef struct
{
    uint8_t  instruction;                   /* Always write opcode 0x02 */
    uint8_t  index;                         /* Panel command byte */
    uint16_t delay;                         /* Delay after command in ms */
    uint16_t wordcount;                     /* Payload byte count */
    uint8_t  payload[<PANEL>_MAX_PARA_COUNT];
} <PANEL>_CMD_DESC;

void rtk_lcd_hal_set_TE_type(T_LCDC_TE_TYPE type);
T_LCDC_TE_TYPE rtk_lcd_hal_get_TE_type(void);

#ifdef __cplusplus
}
#endif
#endif /* _LCD_<PANEL>_<W>_<H>_<IFACE>_H_ */
```

---

## 2. RGB (eDPI) Skeleton

### 2.1 8773G RGB

Complete code, just replace template variables.

```c
#include "<panel>_<w>_<h>_rgb.h"
#include "rtl_lcdc_edpi.h"
#include "rtl_lcdc.h"
#include "rtl876x_pinmux.h"
#include "rtl876x_rcc.h"
#include "rtl876x_gdma.h"
#include "platform_utils.h"
#include "mem_config.h"

/* ========== Pin definitions (Group0 RGB888, full coverage D0-D23) ========== */
/* If using Group1 or different colormap, refer to pins-8773g-rgb.md */
#define LCDC_DATA23         P9_6
#define LCDC_DATA22         P9_5
#define LCDC_DATA21         P9_4
#define LCDC_DATA20         P9_3
#define LCDC_DATA19         P9_2
#define LCDC_DATA18         P9_1
#define LCDC_DATA17         P8_7
#define LCDC_DATA16         P8_6
#define LCDC_DATA15         P8_5
#define LCDC_DATA14         P8_4
#define LCDC_DATA13         P8_3
#define LCDC_DATA12         P8_2
#define LCDC_DATA11         P8_1
#define LCDC_DATA10         P8_0
#define LCDC_DATA9          P4_7
#define LCDC_DATA8          P4_6
#define LCDC_DATA7          P4_5
#define LCDC_DATA6          P4_4
#define LCDC_DATA5          P4_3
#define LCDC_DATA4          P4_2
#define LCDC_DATA3          P4_1
#define LCDC_DATA2          P4_0
#define LCDC_DATA1          P2_7
#define LCDC_DATA0          P2_6
#define LCDC_RGB_WRCLK      P2_5     /* PCLK */
#define LCDC_HSYNC          P2_4
#define LCDC_VSYNC          P2_2
#define LCDC_CSN_DE         P2_3     /* DE */
#define LCDC_RESET          <RST_PIN>

#define LCDC_DMA_CHANNEL_NUM            <DMA_CH_NUM>
#define LCDC_DMA_CHANNEL_INDEX          <DMA_CH_IDX>

/* ========== pad_and_clk_init ========== */
static void lcd_pad_and_clk_init(void)
{
    Pad_Config(LCDC_DATA0,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA1,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA2,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA3,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA4,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA5,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA6,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA7,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA8,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA9,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA10, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA11, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA12, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA13, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA14, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA15, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA16, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA17, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA18, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA19, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA20, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA21, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA22, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_DATA23, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_RGB_WRCLK, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_HSYNC,     PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_VSYNC,     PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_CSN_DE,    PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_RESET,     PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);

    /* HighSpeedFuncSel -- all data lines + control lines */
    Pad_HighSpeedFuncSel(LCDC_DATA0,    HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA1,    HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA2,    HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA3,    HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA4,    HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA5,    HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA6,    HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA7,    HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA8,    HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA9,    HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA10,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA11,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA12,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA13,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA14,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA15,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA16,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA17,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA18,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA19,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA20,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA21,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA22,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_DATA23,   HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_RGB_WRCLK, HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_HSYNC,     HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_VSYNC,     HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_CSN_DE,    HS_Func0);

    /* HighSpeedMuxSel -- all data lines + control lines */
    Pad_HighSpeedMuxSel(LCDC_DATA0,    FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA1,    FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA2,    FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA3,    FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA4,    FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA5,    FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA6,    FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA7,    FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA8,    FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA9,    FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA10,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA11,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA12,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA13,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA14,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA15,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA16,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA17,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA18,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA19,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA20,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA21,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA22,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_DATA23,   FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_RGB_WRCLK, FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_HSYNC,     FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_VSYNC,     FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(LCDC_CSN_DE,    FROM_CORE_DOMAIN);

    platform_delay_ms(1);
}

/* ========== dma_init (LLI linked list infinite auto-transfer) ========== */
static void <panel>_dma_init(uint8_t *init_buffer)
{
    uint32_t one_row = <PANEL>_LCD_WIDTH * <PANEL>_DRV_PIXEL_BITS / 8;

    LCDC_DMA_InitTypeDef dma = {0};
    LCDC_DMA_StructInit(&dma);
    dma.LCDC_DMA_ChannelNum          = LCDC_DMA_CHANNEL_NUM;
    dma.LCDC_DMA_DIR                 = LCDC_DMA_DIR_PeripheralToMemory;
    dma.LCDC_DMA_SourceInc           = LCDC_DMA_SourceInc_Inc;
    dma.LCDC_DMA_DestinationInc      = LCDC_DMA_DestinationInc_Fix;
    dma.LCDC_DMA_SourceDataSize      = LCDC_DMA_DataSize_Word;
    dma.LCDC_DMA_DestinationDataSize = LCDC_DMA_DataSize_Word;
    dma.LCDC_DMA_SourceMsize         = <MSIZE>;
    dma.LCDC_DMA_DestinationMsize    = <MSIZE>;
    dma.LCDC_DMA_SourceAddr          = 0;
    dma.LCDC_DMA_Multi_Block_Mode    = LLI_TRANSFER;
    dma.LCDC_DMA_Multi_Block_En      = 1;
    dma.LCDC_DMA_Multi_Block_Struct  = LCDC_DMA_LINKLIST_REG_BASE + 0x50;
    LCDC_DMA_Init(LCDC_DMA_CHANNEL_INDEX, &dma);

    LCDC_SET_GROUP1_BLOCKSIZE(one_row);
    LCDC_SET_GROUP2_BLOCKSIZE(one_row);

    LCDC_DMALLI_InitTypeDef lli = {0};
    lli.g1_source_addr = (uint32_t)init_buffer;
    lli.g2_source_addr = (uint32_t)init_buffer + one_row;
    lli.g1_sar_offset  = one_row * 2;
    lli.g2_sar_offset  = one_row * 2;

    LCDC_DMA_Infinite_Buf_Update((uint8_t *)init_buffer,
                                 (uint8_t *)init_buffer + one_row);
    LCDC_DMA_LinkList_Init(&lli, &dma);

    LCDC_ClearDmaFifo();
    LCDC_ClearTxPixelCnt();
    LCDC_SwitchMode(LCDC_AUTO_MODE);
    LCDC_SwitchDirect(LCDC_TX_MODE);
    LCDC_SetTxPixelLen(<PANEL>_LCD_WIDTH * <PANEL>_LCD_HEIGHT);
    LCDC_ForceBurst(ENABLE);
    LCDC_Cmd(ENABLE);
    LCDC_DMA_SetSourceAddress(LCDC_DMA_CHANNEL_INDEX, (uint32_t)init_buffer);
    LCDC_DMA_MultiBlockCmd(ENABLE);
    LCDC_DMAChannelCmd(LCDC_DMA_CHANNEL_NUM, ENABLE);
    LCDC_DmaCmd(ENABLE);
    LCDC_AutoWriteCmd(ENABLE);
}

/* ========== rtk_lcd_hal_init ========== */
void rtk_lcd_hal_init(void)
{
    lcd_pad_and_clk_init();

    LCDC_Clock_Sel(LCDC_BUS_CLK_200M);

    LCDC_InitTypeDef lcdc_init = {0};
    lcdc_init.LCDC_Interface = LCDC_IF_DPI;
    lcdc_init.LCDC_PixelInputFormat = <INPUT_FORMAT>;
    lcdc_init.LCDC_PixelOutputFormat = <OUTPUT_FORMAT>;
    lcdc_init.LCDC_PixelBitSwap = LCDC_SWAP_BYPASS;
    lcdc_init.LCDC_GroupSel = <GROUP_SEL>;
    lcdc_init.LCDC_DmaThreshold = <DMA_THRESHOLD>;
    lcdc_init.LCDC_InfiniteModeEn = 1;
    LCDC_Init(&lcdc_init);
    LCDC_ClearINTPendingBit(LCDC_CLR_WAVEFORM_FINISH);

    /* RGB timing */
    uint32_t HSA = <HSA>, HFP = <HFP>, HBP = <HBP>, HACT = <PANEL>_LCD_WIDTH;
    uint32_t VSA = <VSA>, VFP = <VFP>, VBP = <VBP>, VACT = <PANEL>_LCD_HEIGHT;

    LCDC_eDPICfgTypeDef cfg = {0};
    cfg.eDPI_ClockDiv = <CLOCK_DIV>;
    cfg.eDPI_HoriSyncWidth  = HSA;
    cfg.eDPI_VeriSyncHeight = VSA;
    cfg.eDPI_AccumulatedHBP      = HSA + HBP;
    cfg.eDPI_AccumulatedVBP      = VSA + VBP;
    cfg.eDPI_AccumulatedActiveW  = HSA + HBP + HACT;
    cfg.eDPI_AccumulatedActiveH  = VSA + VBP + VACT;
    cfg.eDPI_TotalWidth          = HSA + HBP + HACT + HFP;
    cfg.eDPI_TotalHeight         = VSA + VBP + VACT + VFP;
    cfg.eDPI_HoriSyncPolarity   = 0;    /* active low */
    cfg.eDPI_VeriSyncPolarity   = 0;    /* active low */
    cfg.eDPI_DataEnPolarity     = 1;    /* active high */
    cfg.eDPI_LineIntMask  = 1;
    cfg.eDPI_ColorMap     = <COLORMAP>;
    cfg.eDPI_OperateMode  = 0;          /* video mode */
    cfg.eDPI_LcdArc      = 0;
    cfg.eDPI_ShutdnPolarity   = 0;
    cfg.eDPI_ColorModePolarity = 0;
    cfg.eDPI_ShutdnEn    = 0;
    cfg.eDPI_ColorModeEn = 0;
    cfg.eDPI_UpdateCfgEn = 0;
    cfg.eDPI_TearReq     = 0;
    cfg.eDPI_Halt        = 0;
    cfg.eDPI_CmdMaxLatency = 0;
    cfg.eDPI_LineBufferPixelThreshold = cfg.eDPI_TotalWidth / 2;
    EDPI_Init(&cfg);

    /* Reset waveform */
    Pad_Config(LCDC_RESET, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    platform_delay_ms(20);
    Pad_Config(LCDC_RESET, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_DOWN, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    platform_delay_ms(20);
    Pad_Config(LCDC_RESET, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    platform_delay_ms(120);

    /* === If panel register init (additional SPI) is needed, add write_command/write_data or #include "panel_rgb.txt" here === */

    /* Note: Do not fill the first frame or call update_framebuffer in rtk_lcd_hal_init -- init only does hardware initialization,
       the upper layer framework will call update_framebuffer to start the display at the right time. */
}

/* ========== update_framebuffer (build linked list on first frame, then swap address) ========== */
static bool flush_first = true;

void rtk_lcd_hal_update_framebuffer(uint8_t *buf, uint32_t len)
{
    if (flush_first)
    {
        <panel>_dma_init(buf);
        flush_first = false;
    }
    else
    {
        LCDC_DMA_Infinite_Buf_Update(buf,
                                     buf + <PANEL>_LCD_WIDTH * <PANEL>_DRV_PIXEL_BITS / 8);
    }
}

/* ========== HAL stubs (RGB data path does not use these) ========== */
void rtk_lcd_hal_start_transfer(uint8_t *buf, uint32_t len) { return; }
void rtk_lcd_hal_transfer_done(void)                         { LCDC_ClearINTPendingBit(LCDC_CLR_WAVEFORM_FINISH); return; }
void rtk_lcd_hal_set_window(uint16_t x, uint16_t y, uint16_t w, uint16_t h) { return; }
void rtk_lcd_hal_clear_screen(uint32_t ARGB_color)           { return; }

/* ========== getters ========== */
uint32_t rtk_lcd_hal_get_width(void)     { return <PANEL>_LCD_WIDTH; }
uint32_t rtk_lcd_hal_get_height(void)    { return <PANEL>_LCD_HEIGHT; }
uint32_t rtk_lcd_hal_get_pixel_bits(void) { return <PANEL>_DRV_PIXEL_BITS; }

/* ========== power ========== */
bool rtk_lcd_hal_power_off(void)
{
    flush_first = true;
    /* Pull all data lines + control lines low */
    Pad_Config(LCDC_DATA0,  PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_DOWN, PAD_OUT_DISABLE, PAD_OUT_LOW);
    Pad_Config(LCDC_DATA1,  PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_DOWN, PAD_OUT_DISABLE, PAD_OUT_LOW);
    /* ... same as DATA0 pattern for the rest ... */
    Pad_Config(LCDC_RESET,  PAD_SW_MODE, PAD_IS_PWRON, PAD_PULL_DOWN, PAD_OUT_DISABLE, PAD_OUT_LOW);
    return true;
}

bool rtk_lcd_hal_power_on(void)
{
    rtk_lcd_hal_init();
    return true;
}

/* ========== DLPS stubs ========== */
bool rtk_lcd_hal_dlps_check(void)              { return true; }
bool rtk_lcd_wake_up(void)                     { return true; }
uint32_t rtk_lcd_hal_dlps_restore(void)        { return 0; }
void rtk_lcd_dlps_init(void)                   { }
void rtk_lcd_hal_lcd_enter_dlps(void)          { }
```

### 2.2 8773E RGB

Differences from 8773G:
- CM pin is not P0_3 -> it is **ADC3**
- Clock uses `RCC_DisplayClockConfig` instead of `LCDC_Clock_Sel`
- Pin group definitions are **identical** to 8773G (Group0/1 mapping is the same)

Just replace the clock section and CM pin in the 8773G skeleton:

```c
/* CM pin (if needed) -- 8773E uses ADC3, not 8773G's P0_3 */
#define LCDC_CM_PIN          ADC3

/* Replace the LCDC_Clock_Sel line in lcd_pad_and_clk_init for clock init: */
    RCC_DisplayClockConfig(DISPLAY_CLOCK_SOURCE_PLL1, DISPLAY_CLOCK_DIV_1);  /* PLL1=200M */
```

Rest is the same as the 8773G skeleton.

### 2.3 8762G RGB

Main differences from 8773G:
- **No `Pad_HighSpeedFuncSel` / `Pad_HighSpeedMuxSel`** -> use `Pad_Dedicated_Config(pin, ENABLE)` instead
- Data pin assignments differ (see `pins-8762g.md`), and **RGB has only one group** (`GroupSel=1` fixed)
- Clock writes bitfields directly (no `LCDC_Clock_Sel` API)

```c
#include "<panel>_<w>_<h>_rgb.h"
#include "rtl_lcdc_edpi.h"
#include "rtl_lcdc.h"
#include "rtl876x_pinmux.h"
#include "rtl876x_rcc.h"
#include "rtl876x_gdma.h"
#include "platform_utils.h"
#include "mem_config.h"

/* ========== Pin definitions (8762G RGB single port, QFN88) ========== */
/* Refer to pins-8762g.md -- following are RGB565 Config1/2/3 or RGB888 all pins */
/* TODO: Replace with actual pin table */
#define LCDC_DATA23         P6_4     /* 888 only */
/* ... full D0-D23 see pins-8762g.md ... */
#define LCDC_RESET          <RST_PIN>

#define LCDC_DMA_CHANNEL_NUM            <DMA_CH_NUM>
#define LCDC_DMA_CHANNEL_INDEX          <DMA_CH_IDX>

/* ========== pad_and_clk_init (8762G version, no HighSpeed*) ========== */
static void lcd_pad_and_clk_init(void)
{
    /* Clock: write bitfields directly (RTL8762G has no clock API) */
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.disp_ck_en = 1;
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.disp_func_en = 1;
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_mux_clk_cg_en = 1;
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_div_en = 1;
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_clk_src_sel0 = 0;   /* 0=PLL1(125M), 1=PLL2(160M) */
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_clk_src_sel1 = 1;   /* 0=crystal, 1=PLL */
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_div_sel = 1;        /* divider ratio */

    /* Pad config: 8762G has no Pad_HighSpeed*, use Pad_Dedicated_Config instead */
    Pad_Config(LCDC_DATA0,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    /* ... same Pad_Config pattern as 8773G for remaining D lines + control lines ... */
    Pad_Dedicated_Config(LCDC_DATA0, ENABLE);
    Pad_Dedicated_Config(LCDC_DATA1, ENABLE);
    /* ... every D line + control line needs Pad_Dedicated_Config(ENABLE) ... */

    platform_delay_ms(1);
}

/* ========== dma_init (same as SS 2.1 8773G version, paste and replace macros) ========== */
/* ... identical, see SS 2.1 ... */

/* ========== rtk_lcd_hal_init (8762G version) ========== */
void rtk_lcd_hal_init(void)
{
    lcd_pad_and_clk_init();

    LCDC_InitTypeDef lcdc_init = {0};
    lcdc_init.LCDC_Interface = LCDC_IF_DPI;
    lcdc_init.LCDC_PixelInputFormat = <INPUT_FORMAT>;
    lcdc_init.LCDC_PixelOutputFormat = <OUTPUT_FORMAT>;
    lcdc_init.LCDC_PixelBitSwap = LCDC_SWAP_BYPASS;
    lcdc_init.LCDC_GroupSel = 1;        /* 8762G RGB fixed GroupSel=1 */
    lcdc_init.LCDC_DmaThreshold = <DMA_THRESHOLD>;
    lcdc_init.LCDC_InfiniteModeEn = 1;
    LCDC_Init(&lcdc_init);
    LCDC_ClearINTPendingBit(LCDC_CLR_WAVEFORM_FINISH);

    /* RGB timing (same as SS 2.1) */
    uint32_t HSA = <HSA>, HFP = <HFP>, HBP = <HBP>, HACT = <PANEL>_LCD_WIDTH;
    uint32_t VSA = <VSA>, VFP = <VFP>, VBP = <VBP>, VACT = <PANEL>_LCD_HEIGHT;
    LCDC_eDPICfgTypeDef cfg = {0};
    cfg.eDPI_ClockDiv = <CLOCK_DIV>;
    /* ... rest of eDPI config same as SS 2.1 ... */
    EDPI_Init(&cfg);

    /* Reset + init sequence (same as SS 2.1, do not add first frame fill/update_fb) */
    /* ... */
}

/* ========== Remaining HAL functions same as SS 2.1 (update_fb/getters/power/stubs) ========== */
/* Directly copy the corresponding functions from SS 2.1, just replace macro names */
```

> ⚠️ 8762G's `power_off` does not need to pull data lines low -- some drivers don't operate power_off at all, just return `true`.

---

## 3. QSPI Skeleton

### 3.1 8773G QSPI

```c
#include "<panel>_<w>_<h>_qspi.h"
#include "rtl_lcdc.h"
#include "rtl_lcdc_dbic.h"
#include "rtl876x_pinmux.h"
#include "rtl876x_rcc.h"
#include "rtl876x_gdma.h"
#include "platform_utils.h"
#include "mem_config.h"

/* ========== Pin definitions (select Group, then refer to pins-8773g-qspi.md to fill) ========== */
#define LCD_QSPI_CS         P9_2     /* Change based on selected group */
#define LCD_QSPI_CLK        P9_4
#define LCD_QSPI_DATA0      P9_3     /* SIO0/SD0 */
#define LCD_QSPI_DATA1      P9_1     /* SIO1/SD1 */
#define LCD_QSPI_DATA2      P9_0     /* SIO2/SD2 */
#define LCD_QSPI_DATA3      P9_5     /* SIO3/SD3 */
#define LCD_RESET           <RST_PIN>
/* TE / RS / BL / PWR_EN: add macros if needed, delete if not */

#define LCDC_DMA_CHANNEL_NUM            <DMA_CH_NUM>
#define LCDC_DMA_CHANNEL_INDEX          <DMA_CH_IDX>

/* ========== pad_and_clk_init ========== */
static void lcd_pad_and_clk_init(void)
{
    Pad_Config(<CS_pin>,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(<CLK_pin>, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(<D0_pin>,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(<D1_pin>,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(<D2_pin>,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(<D3_pin>,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCD_RESET, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);

    Pad_HighSpeedFuncSel(<CS_pin>,  HS_Func0);
    Pad_HighSpeedFuncSel(<CLK_pin>, HS_Func0);
    Pad_HighSpeedFuncSel(<D0_pin>,  HS_Func0);
    Pad_HighSpeedFuncSel(<D1_pin>,  HS_Func0);
    Pad_HighSpeedFuncSel(<D2_pin>,  HS_Func0);
    Pad_HighSpeedFuncSel(<D3_pin>,  HS_Func0);

    Pad_HighSpeedMuxSel(<CS_pin>,  FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(<CLK_pin>, FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(<D0_pin>,  FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(<D1_pin>,  FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(<D2_pin>,  FROM_CORE_DOMAIN);
    Pad_HighSpeedMuxSel(<D3_pin>,  FROM_CORE_DOMAIN);

    platform_delay_ms(1);
}

/* ========== Command table write function ========== */
static void <panel>_reg_write(const <PANEL>_CMD_DESC seq[])
{
    uint16_t i = 0;
    while (1)
    {
        if (seq[i].instruction == 0x00 && seq[i].index == 0)
            break;  /* SEQ_FINISH_CODE */

        lcdc_dbic_write_cmd_param4(seq[i].instruction, seq[i].index, 0, 0, 0);
        if (seq[i].wordcount)
            lcdc_dbic_write_data_byte(seq[i].payload, seq[i].wordcount);
        if (seq[i].delay)
            platform_delay_ms(seq[i].delay);
        i++;
    }
}

/* ========== set_window (QSPI version) ========== */
void rtk_lcd_hal_set_window(uint16_t xStart, uint16_t yStart, uint16_t w, uint16_t h)
{
    uint16_t xEnd = xStart + w - 1;
    uint16_t yEnd = yStart + h - 1;

    lcdc_dbic_write_cmd_param4(0x02, 0x2A, (xStart >> 8) & 0xFF, xStart & 0xFF,
                               (xEnd   >> 8) & 0xFF, xEnd & 0xFF);
    lcdc_dbic_write_cmd_param4(0x02, 0x2B, (yStart >> 8) & 0xFF, yStart & 0xFF,
                               (yEnd   >> 8) & 0xFF, yEnd & 0xFF);

    uint32_t len_byte = w * h * OUTPUT_PIXEL_BYTES;
    lcdc_dbic_enter_data_output_mode(len_byte);
}

/* ========== dma_init (QSPI version) ========== */
static void <panel>_dma_init(uint8_t *buf, uint32_t len)
{
    LCDC_DMA_InitTypeDef dma = {0};
    LCDC_DMA_StructInit(&dma);
    dma.LCDC_DMA_ChannelNum          = LCDC_DMA_CHANNEL_NUM;
    dma.LCDC_DMA_DIR                 = LCDC_DMA_DIR_MemoryToPeripheral;
    dma.LCDC_DMA_SourceInc           = LCDC_DMA_SourceInc_Inc;
    dma.LCDC_DMA_DestinationInc      = LCDC_DMA_DestinationInc_Fix;
    dma.LCDC_DMA_SourceDataSize      = LCDC_DMA_DataSize_Word;
    dma.LCDC_DMA_DestinationDataSize = LCDC_DMA_DataSize_Word;
    dma.LCDC_DMA_SourceMsize         = <MSIZE>;
    dma.LCDC_DMA_DestinationMsize    = <MSIZE>;
    dma.LCDC_DMA_SourceAddr          = (uint32_t)buf;
    dma.LCDC_DMA_DstAddr             = (uint32_t)0x20000000;   /* SPIC target address */
    dma.LCDC_DMA_Length              = len;
    LCDC_DMA_Init(LCDC_DMA_CHANNEL_INDEX, &dma);
    LCDC_DMAChannelCmd(LCDC_DMA_CHANNEL_NUM, ENABLE);
}

/* ========== rtk_lcd_hal_init (QSPI version) ========== */
void rtk_lcd_hal_init(void)
{
    lcd_pad_and_clk_init();

    LCDC_Clock_Sel(<CLK_SRC>);

    LCDC_InitTypeDef lcdc_init = {0};
    lcdc_init.LCDC_Interface = LCDC_IF_DBIC;
    lcdc_init.LCDC_PixelInputFormat = (INPUT_PIXEL_BYTES == 2) ? LCDC_INPUT_RGB565 : LCDC_INPUT_RGB888;
    lcdc_init.LCDC_GroupSel = <QSPI_GROUP>;
    lcdc_init.LCDC_DmaThreshold = <DMA_THRESHOLD>;
    lcdc_init.LCDC_PixelBitSwap = LCDC_SWAP_BYPASS;
    LCDC_Init(&lcdc_init);

    LCDC_DBICCfgTypeDef dbic = {0};
    LCDC_DBIC_StructInit(&dbic);
    dbic.DBIC_SPEED_SEL = <SPEED_SEL>;
    dbic.DBIC_PhaseSel  = 0x2;       /* Same as most QSPI drivers */
    LCDC_DBIC_Init(&dbic);

    /* Reset */
    Pad_Config(LCD_RESET, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    platform_delay_ms(10);
    Pad_Config(LCD_RESET, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_DOWN, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    platform_delay_ms(10);
    Pad_Config(LCD_RESET, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    platform_delay_ms(120);

    /* Send initialization sequence table */
    <panel>_reg_write(<PANEL>_POWERON_SEQ_CMD);
}

/* ========== start_transfer / transfer_done (QSPI version) ========== */
void rtk_lcd_hal_start_transfer(uint8_t *buf, uint32_t len)
{
    <panel>_dma_init(buf, len);
    LCDC_DMACmd(ENABLE);
}

void rtk_lcd_hal_transfer_done(void)
{
    while (LCDC_GetDmaTxStatus() != 0);       /* Wait for DMA completion */
    LCDC_ClearINTPendingBit(LCDC_CLR_WAVEFORM_FINISH);
}

/* ========== update_framebuffer (QSPI version) ========== */
void rtk_lcd_hal_update_framebuffer(uint8_t *buf, uint32_t len)
{
    /* QSPI's update_fb = directly initiate one DMA transfer */
    rtk_lcd_hal_start_transfer(buf, len);
}

/* ========== clear_screen (QSPI version) ========== */
void rtk_lcd_hal_clear_screen(uint32_t ARGB_color)
{
    /* Pack clear screen color according to INPUT format */
#if INPUT_PIXEL_BYTES == 2
    uint16_t color = (uint16_t)ARGB_color;
    for (uint32_t i = 0; i < <PANEL>_LCD_WIDTH * <PANEL>_LCD_HEIGHT * INPUT_PIXEL_BYTES / 2; i++)
        ((uint16_t *)<framebuffer>)[i] = color;
#else
    uint32_t color = ARGB_color;
    for (uint32_t i = 0; i < <PANEL>_LCD_WIDTH * <PANEL>_LCD_HEIGHT * INPUT_PIXEL_BYTES / 4; i++)
        ((uint32_t *)<framebuffer>)[i] = color;
#endif
}

/* ========== getters ========== */
uint32_t rtk_lcd_hal_get_width(void)      { return <PANEL>_LCD_WIDTH; }
uint32_t rtk_lcd_hal_get_height(void)     { return <PANEL>_LCD_HEIGHT; }
uint32_t rtk_lcd_hal_get_pixel_bits(void) { return <PANEL>_DRV_PIXEL_BITS; }

/* ========== TE ========== */
static T_LCDC_TE_TYPE g_te_type = LCDC_TE_TYPE_NO_TE;
void rtk_lcd_hal_set_TE_type(T_LCDC_TE_TYPE type) { g_te_type = type; }
T_LCDC_TE_TYPE rtk_lcd_hal_get_TE_type(void)      { return g_te_type; }

/* ========== power (QSPI, reference drivers mostly have weak stubs) ========== */
bool rtk_lcd_hal_power_on(void)  { return true; }
bool rtk_lcd_hal_power_off(void) { return true; }

/* ========== DLPS stubs ========== */
bool rtk_lcd_hal_dlps_check(void)              { return true; }
bool rtk_lcd_wake_up(void)                     { return true; }
uint32_t rtk_lcd_hal_dlps_restore(void)        { return 0; }
void rtk_lcd_dlps_init(void)                   { }
void rtk_lcd_hal_lcd_enter_dlps(void)          { }
```

### 3.2 8773E QSPI

Differences from 8773G QSPI:
- Pin mapping is **identical** (two groups Group0/1 match 8773G)
- Clock uses `RCC_DisplayClockConfig` instead of `LCDC_Clock_Sel`

Change the clock part of 8773G QSPI skeleton to:

```c
    /* 8773E clock: PLL1=200M */
    RCC_DisplayClockConfig(DISPLAY_CLOCK_SOURCE_PLL1, DISPLAY_CLOCK_DIV_1);
```

Everything else is the same as SS 3.1.

### 3.3 8762G QSPI

Main differences from 8773G QSPI:
- **No HighSpeed*** -- use `Pad_Dedicated_Config(pin, ENABLE)` instead
- **3 QSPI groups** (Group1/2/3), pin mapping in `pins-8762g.md`
- Clock writes bitfields
- `LCDC_GroupSel = group number` (Group1->1, Group2->2, Group3->3)
- `power_on/off` use `bool` return type consistently

```c
#include "<panel>_<w>_<h>_qspi.h"
#include "rtl_lcdc.h"
#include "rtl_lcdc_dbic.h"
#include "rtl876x_pinmux.h"
#include "rtl876x_rcc.h"
#include "rtl876x_gdma.h"
#include "platform_utils.h"
#include "mem_config.h"

/* ========== Pin definitions (8762G QSPI, refer to pins-8762g.md based on selected group) ========== */
/* Group1: CS=P0_0, CLK=P0_1, D0=P0_2, D1=P0_3, D2=P3_7, D3=P3_3 */
/* Group2: CS=P3_1, CLK=P3_0, D0=P3_2, D1=P0_7, D2=P3_6, D3=P3_5 */
/* Group3: CS=P2_5, CLK=P2_4, D0=P2_3, D1=P2_2, D2=P2_1, D3=P2_0 (Group3 P2_1 shares with RGB CM, note) */
/* TODO: Replace macros below for the actual group */
#define LCD_QSPI_CS         P0_0
#define LCD_QSPI_CLK        P0_1
#define LCD_QSPI_DATA0      P0_2
#define LCD_QSPI_DATA1      P0_3
#define LCD_QSPI_DATA2      P3_7
#define LCD_QSPI_DATA3      P3_3
#define LCD_RESET           <RST_PIN>

#define LCDC_DMA_CHANNEL_NUM            <DMA_CH_NUM>
#define LCDC_DMA_CHANNEL_INDEX          <DMA_CH_IDX>

/* ========== pad_and_clk_init (8762G version, no HighSpeed*) ========== */
static void lcd_pad_and_clk_init(void)
{
    /* Clock bitfields */
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.disp_ck_en = 1;
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.disp_func_en = 1;
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_mux_clk_cg_en = 1;
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_div_en = 1;
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_clk_src_sel0 = 0;  /* PLL1=125M */
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_clk_src_sel1 = 1;  /* PLL */
    PERIBLKCTRL_PERI_CLK->u_324.BITS_324.r_disp_div_sel = 1;

    /* Pad config */
    Pad_Config(LCD_QSPI_CS,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCD_QSPI_CLK, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCD_QSPI_DATA0, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCD_QSPI_DATA1, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCD_QSPI_DATA2, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCD_QSPI_DATA3, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCD_RESET,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);

    /* Pad_Dedicated_Config -- replaces HighSpeed* */
    Pad_Dedicated_Config(LCD_QSPI_CS, ENABLE);
    Pad_Dedicated_Config(LCD_QSPI_CLK, ENABLE);
    Pad_Dedicated_Config(LCD_QSPI_DATA0, ENABLE);
    Pad_Dedicated_Config(LCD_QSPI_DATA1, ENABLE);
    Pad_Dedicated_Config(LCD_QSPI_DATA2, ENABLE);
    Pad_Dedicated_Config(LCD_QSPI_DATA3, ENABLE);

    platform_delay_ms(1);
}

/* ========== Remaining functions same as SS 3.1 (reg_write/set_window/dma_init/hal_init/start_transfer/...) ========== */
/* Directly copy the corresponding functions from SS 3.1, main change: LCDC_GroupSel = group number in LCDC_Init */
/* Note: clock part is already included in pad_and_clk_init above, don't forget LCDC_Clock_Sel */
```

---

## 4. 8080 (DBIB) Skeleton

### 4.1 8773G DBIB

8773G 8080 is Group0 only, 8-bit D0-D7, `LCDC_GroupSel=0` (default).

```c
#include "<panel>_<w>_<h>_dbib.h"
#include "rtl_lcdc.h"
#include "rtl_lcdc_dbib.h"
#include "rtl876x_pinmux.h"
#include "rtl876x_rcc.h"
#include "rtl876x_gdma.h"
#include "platform_utils.h"
#include "mem_config.h"

/* ========== Pin definitions (8773G DBIB Group0) ========== */
#define LCDC_D0             P2_6
#define LCDC_D1             P2_7
#define LCDC_D2             P4_0
#define LCDC_D3             P4_1
#define LCDC_D4             P4_2
#define LCDC_D5             P4_3
#define LCDC_D6             P4_4
#define LCDC_D7             P4_5
#define LCDC_WR             P4_6      /* WR# / WR */
#define LCDC_RD             P0_3      /* RD# / RD (note: may conflict with backlight BL) */
#define LCDC_RS             P4_7      /* RS / D/C */
#define LCDC_RESET          <RST_PIN>

#define LCDC_DMA_CHANNEL_NUM            <DMA_CH_NUM>
#define LCDC_DMA_CHANNEL_INDEX          <DMA_CH_IDX>

/* ========== pad_and_clk_init (8773G DBIB) ========== */
static void lcd_pad_and_clk_init(void)
{
    Pad_Config(LCDC_D0,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_D1,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_D2,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_D3,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_D4,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_D5,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_D6,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_D7,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_WR,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_RD,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_RS,  PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);
    Pad_Config(LCDC_RESET, PAD_PINMUX_MODE, PAD_IS_PWRON, PAD_PULL_UP, PAD_OUT_DISABLE, PAD_OUT_HIGH);

    Pad_HighSpeedFuncSel(LCDC_D0, HS_Func0);
    /* ... D1-D7, WR, RD, RS same as above ... */
    Pad_HighSpeedFuncSel(LCDC_WR, HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_RD, HS_Func0);
    Pad_HighSpeedFuncSel(LCDC_RS, HS_Func0);

    Pad_HighSpeedMuxSel(LCDC_D0, FROM_CORE_DOMAIN);
    /* ... all same pattern ... */

    platform_delay_ms(1);
}

/* ========== set_window (8080/DBIB version) ========== */
void rtk_lcd_hal_set_window(uint16_t xStart, uint16_t yStart, uint16_t w, uint16_t h)
{
    uint16_t xEnd = xStart + w - 1;
    uint16_t yEnd = yStart + h - 1;
    lcdc_dbib_write_cmd(0x2A);
    lcdc_dbib_write_data((xStart >> 8) & 0xFF);
    lcdc_dbib_write_data(xStart & 0xFF);
    lcdc_dbib_write_data((xEnd   >> 8) & 0xFF);
    lcdc_dbib_write_data(xEnd & 0xFF);
    lcdc_dbib_write_cmd(0x2B);
    lcdc_dbib_write_data((yStart >> 8) & 0xFF);
    lcdc_dbib_write_data(yStart & 0xFF);
    lcdc_dbib_write_data((yEnd   >> 8) & 0xFF);
    lcdc_dbib_write_data(yEnd & 0xFF);
    lcdc_dbib_write_cmd(0x2C);
}

/* ========== dma_init (DBIB version) ========== */
static void <panel>_dma_init(uint8_t *buf, uint32_t len)
{
    LCDC_DMA_InitTypeDef dma = {0};
    LCDC_DMA_StructInit(&dma);
    dma.LCDC_DMA_ChannelNum          = LCDC_DMA_CHANNEL_NUM;
    dma.LCDC_DMA_DIR                 = LCDC_DMA_DIR_MemoryToPeripheral;
    dma.LCDC_DMA_SourceInc           = LCDC_DMA_SourceInc_Inc;
    dma.LCDC_DMA_DestinationInc      = LCDC_DMA_DestinationInc_Fix;
    dma.LCDC_DMA_SourceDataSize      = LCDC_DMA_DataSize_Word;
    dma.LCDC_DMA_DestinationDataSize = LCDC_DMA_DataSize_Word;
    dma.LCDC_DMA_SourceMsize         = <MSIZE>;
    dma.LCDC_DMA_DestinationMsize    = <MSIZE>;
    dma.LCDC_DMA_SourceAddr          = (uint32_t)buf;
    dma.LCDC_DMA_DstAddr             = (uint32_t)0x20000000;
    dma.LCDC_DMA_Length              = len;
    LCDC_DMA_Init(LCDC_DMA_CHANNEL_INDEX, &dma);
    LCDC_DMAChannelCmd(LCDC_DMA_CHANNEL_NUM, ENABLE);
}

/* ========== rtk_lcd_hal_init (8773G DBIB) ========== */
void rtk_lcd_hal_init(void)
{
    lcd_pad_and_clk_init();
    RCC_DisplayClockConfig(DISPLAY_CLOCK_SOURCE_PLL1, DISPLAY_CLOCK_DIV_1);

    LCDC_InitTypeDef lcdc_init = {0};
    lcdc_init.LCDC_Interface = LCDC_IF_DBIB;
    lcdc_init.LCDC_PixelInputFormat = LCDC_INPUT_RGB565;
    lcdc_init.LCDC_GroupSel = 0;            /* 8080 Group0 only */
    lcdc_init.LCDC_DmaThreshold = <DMA_THRESHOLD>;
    LCDC_Init(&lcdc_init);

    LCDC_DBIBCfgTypeDef dbib = {0};
    LCDC_DBIB_StructInit(&dbib);
    dbib.DBIC_Clock_Divider = 2;
    LCDC_DBIB_Init(&dbib);

    /* Reset + init sequence */
    /* ... same as QSPI reset pattern ... */
}

/* ========== start_transfer / transfer_done / update_fb / getters / power ========== */
/* Same pattern as QSPI version (SS 3.1), only change interface-specific lcdc_dbib_write_* calls */
```

### 4.2 8773E DBIB

> Differences from 8773G: **RD# pin is ADC3** (not P0_3), clock uses `RCC_DisplayClockConfig` (same usage as 8773E).

### 4.3 8762G DBIB

> Differences from 8773G:
> - **No HighSpeed***, use `Pad_Dedicated_Config(ENABLE)`
> - Pin mapping differs (see `pins-8762g.md` -- 8080 has 3 groups, template uses Group2/default 0)
> - Clock writes bitfields

---

## 5. Usage / Execution-time Usage

When no reference driver is available, change step 2 of SKILL.md main flow to:

```
2. **Select skeleton**: No reference driver -> read `references/code-skeletons.md`, take the corresponding code block by interface+chip.
   Replace all template variables with parameters provided by the user.
```

Step 4 remains unchanged (replace template variables), but instead of cloning from a reference driver, paste from the skeleton.
