# 配置规范与环境移植

## 1. 分层配置

建议使用两层 JSON：

```text
board-lab.example.json   # 可提交：命令模板、逻辑角色、稳定硬件 ID、marker
board-lab.local.json     # 不提交：必要的本机 override、个人安装路径、临时 timeout
```

稳定 USB identity 可用时，共享配置中的 `device` 可省略；workflow 每次运行时自动解析当前 COM/tty。只有设备没有 serial/location 或工具强制要求静态端口时，才在 local config 暂存 `device` 提示值。团队共享实验台如果必须保存 role→USB serial 映射，可以提交不含凭据的 lab inventory；个人端口、安装路径和临时 override 仍留在 local config。

将 bootstrap 复制/改造成工作区入口后，调用时后者覆盖前者：

```powershell
python tools/board_lab/lab.py doctor \
  --config tools/board_lab/board-lab.example.json \
  --local tools/board_lab/board-lab.local.json
```

把 `board-lab.local.json`、数据库、raw log、固件和截图是否纳入版本管理作为显式项目决策。不得把 token、密码、API key 写入配置；使用环境变量或系统凭据存储。

## 2. 模板选择

- [board-lab.example.json](../templates/board-lab.example.json) 是 backend-neutral 起点，build/flash/reset/capture 都要求 agent 根据工作区替换；它不会默认假设 mpcli、串口或 RTS。
- [rtl87x3g-mpcli-lab.json](../templates/rtl87x3g-mpcli-lab.json) 只用于已确认与本实验台拓扑相同的 RTL87X3G：mpcli、UART2 flash/log 共口、独立 FTDI RTS# 复位。它描述完整 workspace orchestrator 所需状态；skill 的 `board_lab.py command` 只会运行命令，不会实现 marker-driven reset，不能单独完成自动烧写。

模板中的 `DISCOVER_*`/`REPLACE_*` 都是待勘察占位符。真实 hardware identity 应在当前工作区的 lab config/local state 中记录；若同一实验台更换 adapter，agent 应重新识别角色并更新该状态。不得因为当前工作区以 mpcli 为主，就把 mpcli 字段复制到不相关项目。

最小 backend-neutral 配置形态：

```json
{
  "project": {
    "root": ".",
    "work_dir": ".",
    "data_dir": "tools/board_lab/data"
  },
  "build": {
    "backend": "command",
    "command": ["REPLACE_BUILD_COMMAND"],
    "build_dir": "build"
  },
  "flash": {"backend": "manual"},
  "reset": {"backend": "manual"},
  "capture": {"backend": "manual"},
  "measurement": {
    "protocol_version": 1,
    "samples": 15,
    "warmup": 3,
    "primary_metric": "REPLACE_WITH_DIRECT_METRIC",
    "workload_keys": ["REPLACE_WITH_ACTUAL_WORK_UNIT_COUNT"]
  }
}
```

勘察后再将 relevant section 替换成项目的 command、serial、RTT、J-Link、OpenOCD、DFU、relay 或 vendor backend。

## 3. command template 变量

在新项目中，先把 `scripts/board_lab.py` 复制/改造成工作区自己的 bootstrap，或在现有 harness 中实现相同机制；不要把 skill 安装目录当长期运行时依赖。skill 自带 `scripts/board_lab.py command` 支持将以下 token 替换进命令数组：

- `{root}`：配置文件中 project.root 解析后的绝对路径；
- `{work_dir_abs}`：项目工作目录绝对路径；
- `{build_dir_abs}`：build directory 绝对路径；
- `{flash_port}`：按 flash.port 的 stable identity 动态解析出的当前设备名；
- `{log_port}`：按 capture.port 动态解析出的当前设备名；
- `{reset_port}`：按 reset.port 动态解析出的当前设备名；
- `{artifact}`：命令行 `--artifact`；
- `{build_id}`：命令行 `--build-id`；
- `{tag}`：命令行 `--tag`。

命令使用 JSON string array，不通过 shell 拼接，避免空格、转义和注入问题。bootstrap 会拒绝以 `cmd` / PowerShell / `sh` / `bash` 作为通用入口。必须确需 shell pipeline 时，在仓库内写受审查的脚本，再把脚本作为单个 command 调用。

## 4. 串口身份策略

COM 号和 `/dev/ttyUSBn` 会变化。解析优先级：

1. USB serial number（可叠加 VID/PID 校验）；
2. physical location + VID/PID；
3. 唯一且项目已验证的 friendly name/description 规则；
4. device name（COMn）只作提示或无 stable identity 时的本机 fallback。

VID/PID 本身通常只表示设备型号，不足以区分多个同型号 adapter；匹配到多个时必须再用 serial/location 或一次受控拔插建立角色映射。

运行 `discover` 获取 Windows PNPDeviceID 或 Unix sysfs/pyserial 信息。配置同时含 stable identity 和旧 `device` 时，以 stable identity 为准：若唯一匹配落在新端口，自动采用新端口并报告 drift，不失败也不要求先改配置。skill 自带 bootstrap 只实现 device/VID/PID/serial/location 匹配；若项目要按 friendly name、USB topology 或自定义 probe 识别，agent 应在工作区 adapter 中实现并补 selftest。匹配到 0 或多个设备时，agent 应先重新枚举、检查 USB 插拔变化和现有端口占用，并结合角色特征主动诊断；只有无法安全、唯一地区分时才要求人工确认，绝不自动选“第一个”。

Windows FTDI 的 PNPDeviceID 示例：

```text
FTDIBUS\VID_0403+PID_6001+SERIAL123A\0000
```

其中末段前的 `SERIAL123A` 是设备稳定身份；设备管理器显示的 COM 号只是当次枚举结果。

## 5. Backend 配置原则

### Build

必须指定命令、cwd、timeout、artifact 路径或 artifact discovery 规则。仅 return code 为 0 通常足够；若项目 post-build 有已知无害/误导错误，应优先修脚本，或显式记录成功 marker 与例外，不能笼统忽略失败。marker 必须来自本次 invocation 的新输出/新 artifact；读取日志文件的工具要在启动前截断、记 offset/inode，或按 run 使用独立文件，防止旧 marker 造成假成功。

### Flash

至少声明：

- command；
- port 占用；
- 是否需要 reset 与何时 pulse；
- handshake/connected/success/failure marker；
- timeout；
- timeout 后需要清理的 process tree；仅当 vendor child 确实会 orphan、且实验机保证没有其他同名任务时，才显式设置 `kill_process_names_on_timeout=true` 和 process name sweep；
- flash 完成后设备是否自动 reset。

### Reset

不要假设 RTS=True 的物理意义。配置必须明确 active level、是否有 transistor inversion、open/close 默认电平以及能否全程持有。自动 pulse 前应要求工作区配置带 `polarity_verified=true`（或等价的显式确认状态）；没有该状态只允许 discovery/doctor，不执行复位。

### Capture

必须明确 baud/format、RTS/DTR 初态、flash 共口关系、open retry、停止条件和 raw byte 保存策略。

## 6. 环境变量覆盖

团队可约定：

```text
BOARDLAB_FLASH_PORT
BOARDLAB_LOG_PORT
BOARDLAB_RESET_PORT
BOARDLAB_CONFIG
BOARDLAB_LOCAL_CONFIG
```

若脚本实现环境变量覆盖，打印最终解析值但不打印秘密。CI/实验室机宜按硬件 serial 绑定，不按静态 COM 绑定。

## 7. 配置验收清单

- [ ] 所有路径可从仓库根或 config 所在位置解析；
- [ ] build/flash 路径在包含空格时仍作为单独 argv；
- [ ] flash、log、reset 三种角色的串口关系明确；
- [ ] reset 极性经过万用表或实际复位验证；
- [ ] 能获得 stable identity 时，共享配置不依赖固定 COM/tty；
- [ ] 仅 device 漂移时自动解析并继续；stable identity 找不到或冲突时 doctor 阻断；需检查被占用、且已确认 open 不会造成危险控制线动作时，才显式运行 `doctor --probe-port flash`（按需重复指定角色）；普通 discovery 不打开串口；
- [ ] timeout 后无孤儿进程占口；
- [ ] success marker 与真实成功日志一致；
- [ ] local config 已 gitignore；
- [ ] `doctor` 已拒绝所有 `REPLACE_*` / `DISCOVER_*` 占位符，实际 run 不会携带模板值；
- [ ] 配置不含凭据与受限内部材料。
