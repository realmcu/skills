# HAL Contract: `rtk_lcd_hal_*`

This contract applies uniformly to 8762G / 8773E / 8773G. Every panel driver must export these exact functions and enums; only function bodies differ by interface.

## 1. Header file macros

```c
#define <PANEL>_LCD_WIDTH        <W>     // <PANEL> = <MODEL>_<W>_<H> (see below)
#define <PANEL>_LCD_HEIGHT       <H>

#define INPUT_PIXEL_BYTES        2       // 2=RGB565, 4=ARGB8888
#define OUTPUT_PIXEL_BYTES       2       // 2=RGB565, 3=RGB888

#if   INPUT_PIXEL_BYTES == 2
#define <PANEL>_DRV_PIXEL_BITS   16
#elif INPUT_PIXEL_BYTES == 3
#define <PANEL>_DRV_PIXEL_BITS   24
#elif INPUT_PIXEL_BYTES == 4
#define <PANEL>_DRV_PIXEL_BITS   32
#endif

#define TE_VALID                 1       // 0=no TE, 1=use TE
```

- **WIDTH/HEIGHT always carry resolution infix**: `<MODEL>_<W>_<H>_LCD_WIDTH`, e.g. `ST77916_360_360_LCD_WIDTH`. No bare `ST77916_LCD_WIDTH`.
- **DRV_PIXEL_BITS infix follows interface**: QSPI includes it (`ST77916_360_360_DRV_PIXEL_BITS`), RGB omits it (`EK9716_DRV_PIXEL_BITS`).
- INPUT and OUTPUT are **independent** (e.g. INPUT=4 in memory, OUTPUT=2 on wire — LCDC handles conversion).
- `INPUT=3` (RGB888) requires `LCD_WIDTH` to be 4-pixel-aligned (row×3 must be 4-byte aligned), or DMA misaligns. Do NOT copy the obsolete `#error "LCDC DMA doesn't allow 3 bytes input"`.

## 2. Mandatory enum + function declarations

```c
typedef enum
{
    LCDC_TE_TYPE_NO_TE = 0x00,
    LCDC_TE_TYPE_HW_TE = 0x01,
    LCDC_TE_TYPE_SW_TE = 0x02,
} T_LCDC_TE_TYPE;

uint32_t rtk_lcd_hal_get_width(void);
uint32_t rtk_lcd_hal_get_height(void);
uint32_t rtk_lcd_hal_get_pixel_bits(void);
bool     rtk_lcd_hal_power_off(void);      // Always bool — do NOT copy legacy uint32_t
bool     rtk_lcd_hal_power_on(void);
void     rtk_lcd_hal_init(void);
void     rtk_lcd_hal_set_window(uint16_t xStart, uint16_t yStart, uint16_t w, uint16_t h);
void     rtk_lcd_hal_update_framebuffer(uint8_t *buf, uint32_t len);
void     rtk_lcd_hal_clear_screen(uint32_t ARGB_color);
void     rtk_lcd_hal_start_transfer(uint8_t *buf, uint32_t len);
void     rtk_lcd_hal_transfer_done(void);
void     rtk_lcd_hal_lcd_enter_dlps(void);
void     rtk_lcd_hal_set_TE_type(T_LCDC_TE_TYPE state);
T_LCDC_TE_TYPE rtk_lcd_hal_get_TE_type(void);
```

## 3. Pixel format `#if` blocks (must appear in `rtk_lcd_hal_init`)

```c
#if INPUT_PIXEL_BYTES == 4
    lcdc_init.LCDC_PixelInputFormat = LCDC_INPUT_ARGB8888;
#elif INPUT_PIXEL_BYTES == 3
    lcdc_init.LCDC_PixelInputFormat = LCDC_INPUT_RGB888;
#elif INPUT_PIXEL_BYTES == 2
    lcdc_init.LCDC_PixelInputFormat = LCDC_INPUT_RGB565;
#endif

#if OUTPUT_PIXEL_BYTES == 2
    lcdc_init.LCDC_PixelOutputFormat = LCDC_OUTPUT_RGB565;
#elif OUTPUT_PIXEL_BYTES == 3
    lcdc_init.LCDC_PixelOutputFormat = LCDC_OUTPUT_RGB888;
#endif
```

Same `#if` pattern used in `clear_screen` (pack per INPUT) and init sequence `0x3A` (select per OUTPUT: 565=0x55 / 888=0x77) — must be consistent.

## 4. `set_window` (QSPI/SPI/8080 with GRAM)

```c
void rtk_lcd_hal_set_window(uint16_t xStart, uint16_t yStart, uint16_t w, uint16_t h)
{
    uint16_t xEnd = xStart + w - 1;
    uint16_t yEnd = yStart + h - 1;
    lcdc_dbic_write_cmd_param4(0x2A, (xStart>>8)&0xFF, xStart&0xFF, (xEnd>>8)&0xFF, xEnd&0xFF);
    lcdc_dbic_write_cmd_param4(0x2B, (yStart>>8)&0xFF, yStart&0xFF, (yEnd>>8)&0xFF, yEnd&0xFF);
    uint32_t len_byte = w * h * OUTPUT_PIXEL_BYTES;
    lcdc_dbic_enter_data_output_mode(len_byte);
}
```

⚠️ Check GRAM offset — some panels' visible area doesn't start at (0,0).

> RGB(eDPI) does NOT use this — see §5.

## 5. RGB(eDPI): Same API, Different Data Path

RGB exports the same function set, but with different implementations:

| Function | RGB(eDPI) | Why |
|----------|-----------|-----|
| `set_window` | empty `return;` | No GRAM, no window addressing |
| `clear_screen` | empty `return;` | Upper layer clears framebuffer directly |
| `start_transfer` | empty `return;` | **NOT** the RGB data path (QSPI uses it for DMA) |
| `transfer_done` | empty `return;` | Same — RGB doesn't use it |
| `update_framebuffer` | **Real data entry**: first call inits DMA, later calls swap address | This IS the RGB data path |

**Data path = `<panel>_dma_init()` LLI linked list + `update_framebuffer` address swap:**

```c
#define LCDC_DMA_CHANNEL_NUM     0
#define LCDC_DMA_CHANNEL_INDEX   LCDC_DMA_Channel0

static void <panel>_dma_init(uint8_t *buf)
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
    dma.LCDC_DMA_SourceMsize         = LCDC_DMA_Msize_64;
    dma.LCDC_DMA_DestinationMsize    = LCDC_DMA_Msize_64;
    dma.LCDC_DMA_SourceAddr          = 0;
    dma.LCDC_DMA_Multi_Block_Mode    = LLI_TRANSFER;
    dma.LCDC_DMA_Multi_Block_En      = 1;
    dma.LCDC_DMA_Multi_Block_Struct  = LCDC_DMA_LINKLIST_REG_BASE + 0x50;
    LCDC_DMA_Init(LCDC_DMA_CHANNEL_INDEX, &dma);

    LCDC_SET_GROUP1_BLOCKSIZE(one_row);
    LCDC_SET_GROUP2_BLOCKSIZE(one_row);

    LCDC_DMALLI_InitTypeDef lli = {0};
    lli.g1_source_addr = (uint32_t)buf;
    lli.g2_source_addr = (uint32_t)buf + one_row;
    lli.g1_sar_offset  = one_row * 2;
    lli.g2_sar_offset  = one_row * 2;

    LCDC_DMA_Infinite_Buf_Update(buf, buf + one_row);
    LCDC_DMA_LinkList_Init(&lli, &dma);

    LCDC_ClearDmaFifo();
    LCDC_ClearTxPixelCnt();
    LCDC_SwitchMode(LCDC_AUTO_MODE);
    LCDC_SwitchDirect(LCDC_TX_MODE);
    LCDC_SetTxPixelLen(<PANEL>_LCD_WIDTH * <PANEL>_LCD_HEIGHT);
    LCDC_Cmd(ENABLE);
    LCDC_DMA_SetSourceAddress(LCDC_DMA_CHANNEL_INDEX, (uint32_t)buf);
    LCDC_DMA_MultiBlockCmd(ENABLE);
    LCDC_DMAChannelCmd(LCDC_DMA_CHANNEL_NUM, ENABLE);
    LCDC_DmaCmd(ENABLE);
    LCDC_AutoWriteCmd(ENABLE);
}

static bool flush_first = true;
void rtk_lcd_hal_update_framebuffer(uint8_t *buf, uint32_t len)
{
    if (flush_first) {
        <panel>_dma_init(buf);
        flush_first = false;
    } else {
        LCDC_DMA_Infinite_Buf_Update(buf, buf + <PANEL>_LCD_WIDTH * <PANEL>_DRV_PIXEL_BITS / 8);
    }
}

void rtk_lcd_hal_set_window(uint16_t x, uint16_t y, uint16_t w, uint16_t h) { return; }
void rtk_lcd_hal_clear_screen(uint32_t c) { return; }
void rtk_lcd_hal_start_transfer(uint8_t *b, uint32_t l) { return; }
void rtk_lcd_hal_transfer_done(void) { LCDC_ClearINTPendingBit(LCDC_CLR_WAVEFORM_FINISH); return; }
```

- `rtk_lcd_hal_init`: `LCDC_IF_DPI` + `InfiniteModeEn=1` → `EDPI_Init` → reset → init seq → `update_framebuffer`.
- **RGB header is minimal**: only `LCD_WIDTH/HEIGHT` + `DRV_PIXEL_BITS`. No `INPUT/OUTPUT_PIXEL_BYTES` — formats set inline in init.
- **If RGB needs separate SPI for register init**: user provides SPI config; skill leaves call sites only. **No hardcoded periph/pin**.
- Clock: `LCDC_Clock_Sel(LCDC_BUS_CLK_200M)` (EK9716) or `RCC_DisplayClockConfig` (st7701s) — both valid for 8773G.
