# RTL87X3G：mpcli + 独立 RTS 复位参考

这是**按需加载的平台参考**，不是通用 workflow 的默认依赖。仅当目标环境确认同时满足以下条件时采用：

- RTL87X3G 使用 mpcli 下载；
- flash 与 console 共用一个 UART adapter；
- 另有独立 USB-UART adapter，以 RTS# 控制 nRESET；
- mpcli 必须在芯片复位后的短窗口内完成 loader handshake。

其他芯片、板载复位电路、J-Link/OpenOCD/DFU 或不同串口拓扑只借鉴状态机思想，不复制本页电平、marker 和接线。

## 1. 逻辑硬件角色

```text
flash_log adapter                target
  TX        -------------------> console/download RX
  RX        <------------------- console/download TX
  GND       -------------------- GND

reset adapter                    target
  RTS#      --[board-approved]--> nRESET/reset circuit
  GND       -------------------- GND
  TX/RX     normally unused
```

要求：

- flash/log 与 reset 使用不同 adapter，避免 mpcli 独占 flash port 时 reset backend 无法打开；
- 电压、共地、串阻、pull-up/down 和 reset waveform 必须由目标板原理图或实测确认；
- 不能假设 `rts=True` 的最终物理电平，反相器或晶体管会改变极性；
- 自动 pulse 前，工作区配置必须记录已确认的 reset assert/deassert 状态；
- COM/tty 不是持久身份，优先按 USB serial，或 VID/PID + physical location 解析；
- adapter 被替换时重新建立 role mapping，不只修改端口号。

Windows 可先只读枚举：

```powershell
[System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object
Get-CimInstance Win32_PnPEntity |
  Where-Object { $_.Name -match '\(COM\d+\)' } |
  Select-Object Name, Manufacturer, PNPDeviceID
```

## 2. mpcli 命令与 cwd

先在目标 workspace 中读取实际 mpcli runner、board runner 和工具说明。常见命令形态：

```powershell
west flash -d <absolute-build-dir> --runner mpcli \
  --port <discovered-flash-port>
```

runner 调用通常类似：

```text
mpcli -f <absolute-mptoolconfig.json> -a -M 5 \
  -T <ic-type> -c <discovered-flash-port> -r
```

注意：

- 某些 mpcli 版本从 executable cwd 查找 bundled `fw/`、`config/`，runner 可能主动切换 cwd；因此 build/config/image 路径应绝对化；
- `-T`、`-r`、image address、erase mode 和 success marker 必须以目标版本帮助与 runner 代码为准；
- 不能只凭 process exit 0 判断下载成功；同时核验本次 invocation 的成功 marker；
- flash 后仍要用应用日志中的 build ID 证明新镜像真正运行。

## 3. 两种 reset ownership

### Runner-owned reset

简单板卡可由 `west flash --auto --auto-reset-port <port>` 启动 autoreset helper。helper 负责一次 pulse，runner 负责 mpcli。

### Orchestrator-owned reset

需要根据 mpcli 实时状态 pulse、重试或长期持有 reset line 时，由 workspace orchestrator 独占 reset adapter；此时 `west flash` 不再传 `--auto`，避免两个 reset controller 同时操作硬件。

若两种机制都未启用，就只能按项目说明手工进入 loader，不能把该流程描述为全自动。

## 4. Marker-driven reset 状态机

固定 sleep 容易与 mpcli 启动、打开串口和第一轮 handshake 竞争。推荐让 flash backend 流式读取**本次** mpcli 输出：

```text
start mpcli
  -> wait for configured handshaking marker
  -> pulse reset using verified polarity/hold time
  -> retry only while still handshaking, with bounded count/deadline
  -> on configured connected marker: permanently stop all reset pulses
  -> erase/write
  -> require success marker + exit 0
  -> release flash port
  -> open capture
  -> verify application build ID
```

RTL87X3G/mpcli 的常见 marker 可从 runner/tool 输出确认，例如：

```text
handshake request
start to loader ram patch
Download : Success
MPCLI exit: success
```

marker 文本可能随工具版本变化，必须保存在 backend config 并用真实失败/成功 log 建 fixture。connected 后继续 pulse 可能中断 erase/write，因此该状态转换是硬门禁。

## 5. Reset line 生命周期

若 reset adapter close 后会让 nRESET 悬空，orchestrator 应：

1. 在 flash 前打开 reset adapter；
2. 在 open 前设置已验证的 deassert 状态，并关闭不需要的 flow control；
3. 只在 handshaking 状态 pulse；
4. connected 后保持 deassert；
5. flash 与 capture 期间继续持有；
6. finally 中先 deassert，再 close。

这不是所有板卡的默认要求。板载 pull-up、专用 reset controller 或可靠的 autoreset 电路可能允许 fire-and-forget；由目标硬件决定。

pyserial 的安全初始化形态应在目标板上验证：

```python
ser = serial.Serial()
ser.port = reset_port
ser.rtscts = False
ser.dsrdtr = False
ser.timeout = 0.2
ser.rts = verified_deassert_value
ser.dtr = verified_dtr_value
ser.open()
```

不要先 `Serial(port, baud)` 打开，再补设 RTS/DTR；open 过程中可能产生控制线瞬态。

## 6. Flash 与 console 共口

当 mpcli 与 console 共用一个 adapter：

- mpcli 运行时 capture 不能同时独占该 port；
- flash process 完全退出并释放 handle 后再打开 capture；
- Windows 可对 handle 释放做短暂、有上限的 retry；
- capture 可能错过 boot banner，所以每条完整 benchmark sample 都应携带 build ID；
- serial monitor、terminal 和 IDE 插件不得同时占口；
- capture open 前设置已验证的 RTS/DTR 状态，避免意外复位。

若 flash 与 console 使用不同 transport，则可并行 capture，但仍要检测重启、混合 build ID 和截断样本。

## 7. Timeout 与进程清理

只 kill `west` parent 可能留下继续持有串口的 mpcli child。优先：

1. 创建独立 process group/job；
2. 记录并终止本轮完整 process tree；
3. 等待串口 handle 释放；
4. 只有工具确实会 orphan 且实验机不存在其他同名合法任务时，才显式启用按 process name sweep。

Windows 兜底示例：

```text
taskkill /T /F /PID <parent-pid>
taskkill /F /IM mpcli.exe   # 仅专用实验机、显式授权时
```

共享服务器不得默认按名字清理，否则可能终止其他人的烧写任务。硬件实验台还应有资源锁，避免并发操作同一板卡。

## 8. 故障判断

| 现象 | 处理 |
| --- | --- |
| 持续 handshaking，无 connected marker | 检查 reset 极性、pulse 时机、下载 strap、adapter 角色 |
| port 不存在或变化 | 重新 discovery，按 stable identity 解析，不直接套旧 COM/tty |
| PermissionError / busy | 检查 monitor、孤儿 process、重复 reset owner |
| connected 后 erase/write timeout | 禁止再 pulse；检查 reset line 稳定、供电、image/config |
| 下载成功但应用 build ID 旧 | 拒绝入库；检查 stale artifact、stamp/rebuild 和实际启动镜像 |
| 正常 console 但没有 benchmark sample | 检查 workload 启动、协议 prefix/version、baud/transport |
| capture open 导致 reset | 检查 open 前 RTS/DTR 状态和硬件控制线拓扑 |

## 9. 目标工作区应核验的文件

agent 不依赖固定仓库路径，而是在当前 workspace 定位并阅读：

- mpcli runner 实现与测试；
- board runner defaults；
- mpcli binary/config/firmware 的安装方式；
- autoreset helper；
- application build/flash artifact 规则；
- console transport 与 benchmark protocol；
- 当前实验台 role mapping 和 reset polarity 记录。

确认这些事实后，再在工作区实现或完善 mpcli backend、reset backend、capture handoff 和回归 fixtures。
