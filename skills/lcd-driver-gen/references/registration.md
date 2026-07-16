# Registration: Kconfig / CMakeLists.txt / SConscript (Three Locations)

A new driver must be registered in **three** build entry points, and the `CONFIG_` symbol must be **identical verbatim** across all three.

> ⚠️ Historical bug: Kconfig writes `REALTEK_LCD_ST7265_800_480_RGB` (resolution with underscores),
> CMake writes `CONFIG_REALTEK_LCD_ST7265_800480_RGB` (without) — condition never matches, driver not compiled.
> After generation, always read back all three and compare verbatim.

Convention: `REALTEK_LCD_<MODEL>_<W>_<H>_<IFACE>` (resolution separated by underscores, e.g. `REALTEK_LCD_ST77916_360_360_QSPI`).
Once a spelling is chosen, copy it verbatim to all three locations without modification.

## 1) Repository Root `Kconfig`

Append after existing `config REALTEK_LCD_*` blocks:

```kconfig
config REALTEK_LCD_<MODEL>_<W>_<H>_<IFACE>
	bool "Enable Realtek LCD Device Driver <MODEL> <W> <H>"
	default n
	help
		This config for realtek display lcd device driver <MODEL>
```

## 2) Target Directory `CMakeLists.txt`

Append after `set(SOURCES "")` and before `# Determine if we should create a library`:

```cmake
    if(CONFIG_REALTEK_LCD_<MODEL>_<W>_<H>_<IFACE>)
        list(APPEND SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/lcd_<model>_<W>_<H>_<iface>.c")
    endif()
```

(The filename must exactly match the actual generated `.c` file.)

## 3) Target Directory `SConscript`

Append after `src = Split(...)` and before `group = DefineGroup(...)`:

```python
if GetDepend(['CONFIG_REALTEK_LCD_<MODEL>_<W>_<H>_<IFACE>']):
    src += ['lcd_<model>_<W>_<H>_<iface>.c']
```

## Verification Steps (Execute after generation)

1. `grep -rn "REALTEK_LCD_<MODEL>_<W>_<H>_<IFACE>"` should appear in all three locations: **Kconfig / CMakeLists.txt / SConscript**, with identical spelling.
2. The `.c` filename referenced in CMakeLists and SConscript == actual generated filename.
3. Header files `.h` don't need to be in SOURCES (CMake auto-collects them via `file(GLOB HEADERS "*.h")`).
