# 自动化失败诊断树

## 1. Discovery / doctor

### Port 不存在

- 重新枚举；COM 号可能变化；
- 按 VID/PID/serial/location 匹配；
- 检查 USB hub、电源、驱动和设备管理器；
- 不把历史 COM 直接改成系统里“看起来像”的第一个口。

### Port 存在但打不开

仅在确认打开该端口不会触发危险的 RTS/DTR/boot/reset 动作后，用 workspace doctor 的 role-specific open probe（skill bootstrap 为 `doctor --probe-port <role>`）确认占用。

- 关闭 VSCode serial monitor、PuTTY、Tera Term 等；
- 检查残留 west/mpcli/python；
- flash/log 共口时确认 flash 进程已退出，短暂 retry；
- reset 与 flash 若同 adapter，重新设计接线/所有权，不能并发 open。

### pyserial 缺失

项目是否允许 dependency：

```text
python -m pip install pyserial
```

skill 自带 `discover` 在 Windows 可退化到 CIM 枚举，但 serial open/capture/reset 仍需 pyserial 或项目自己的 serial backend。

## 2. Build

### 编译失败

- 保存完整 stdout/stderr；
- 区分 source compile、link、post-build；
- 确认使用真实 SDK、环境脚本、cwd；
- pristine build 不是默认“修复”，先找 stale config/dependency 根因。

### link 已成功但 post-build 失败

如果项目已知 `mp.ini`/VERSION 等路径从 `<build_dir>/../` 推导，build dir 必须放 app 内。不要把所有 nonzero exit 都宣称为 C 编译失败；也不能反过来一概忽略 post-build，因为 flash artifact 可能未生成。

### intrinsic 独立示例能编，项目不能编

- 比较实际 compiler version、`arm_mve.h`、flags、CPU/FPU；
- 只相信项目 SDK build；
- 不混用独立 toolchain header/lib。

## 3. Flash / reset

### 一直 handshake，未 connected

- 端口角色是否正确；
- reset 极性和接线；
- 下载模式 strap；
- pulse 是否发生在 handshake marker 之后；
- reset helper 是否打开了 flash 同一口；
- 板上应用是否快速重配 UART/pin；
- timeout 不是根治：先确认状态机。

### 固定 delay 偶发成功

这是 race，不是稳定设计。改为按 flash tool stdout/event 触发；connected 后禁止 pulse。

### erase/write 中途 timeout

- 检查 reset line 是否因 close 后悬空；
- 电源/线缆/共地；
- 不应在 connected 后还有 retry pulse；
- image/config/address/IC type；
- 失败后镜像可能部分擦除，不能假设旧 app 仍完整。

### timeout 后下一轮 PermissionError

parent 被 kill、child 仍占口。kill process tree，确认 mpcli 消失，再开始新 run。不要无脑 sleep/retry掩盖 orphan。

### mpcli `Write timeout`

优先排查 COM 已消失/变号和被占用；mpcli 的错误未必直接说“port not found”。运行 discovery + open probe。

## 4. Capture

### 打开 log port 导致板子 reset

RTS/DTR 必须在 `open()` 前设为 deassert，且 flow control off。若 reset pin 接的是同一 UART adapter 的 RTS，最好改用独立 reset adapter，或确认 capture 永不碰 RTS。

### 有日志但没有 benchmark sample

- benchmark Kconfig/macro 是否启用；
- workload 是否触发真实操作；
- prefix/protocol 版本；
- UART 和 baud；
- app 是否进入 standby；
- timer 是否挂在会被调度的对象/线程；
- log 是否因无换行粘连（parser 应能 prefix 搜索）。

### Sample 全 0，但 FPS 正常

主循环/FPS 不一定代表目标 draw/workload 真执行。检查调用计数；按需刷新 UI 需要显式 invalidation/`gui_fb_change()`。这类 run 作废，不是“极快基线”。

### Foreign build ID

flash 未生效、旧 app 仍在跑、stamp 未触发重新编译，或 capture 接错板。拒绝入库；不要因为输出格式正常而采纳。

### 多 build ID

设备中途 reset/换镜像或串口混入。整轮 fail；raw log 保留。

## 5. Measurement

### 性能突然改善但 workload 减少

先处理 workload mismatch。可能是 clip/layout/cache/feature disabled/error path/提前 return。不能把“少画/少处理”当优化。

### 分布 profile 明显变慢

observer effect。只用分布比例决定方向；关闭详细统计后重新建正式 baseline。

### Primary 变慢，FPS 变快

按 primary 判断局部候选失败；FPS 受其他阶段和 layout noise 影响。记录冲突，不 cherry-pick 有利指标。

### 目标 stage 变快，整体稳定变慢

重复 build 确认。若成立，默认关闭/回退；局部计时可能有 observer effect、code size/layout、register save 或 cache 副作用。

### 未改 stage 跨 build 漂移

这是 build/layout noise 候选，不归因。做独立 rebuild、A/B/A/ABBA；必要时固定 alignment 或用更强直接指标。

### Delta 落在 noise 内

结论是“未检测到收益”，不是“等价”或“略快”。增加样本只能降低窗口统计不确定性，不能自动消除跨构建 layout noise。

## 6. Parser / Database

### 协议字段新增后旧 run 缺 metric

从 raw log reparse，更新派生 DB/report，不改 JSONL/raw。若旧协议根本没记录该字段，明确 `not compared`，不能填 0。

### Tag 找不到但 run 已入库

先 `list` 核对完整 run ID，再 `compare`。run 命令的 `--compare-to` 失败不应删除已完成 run，但必须明确提示比较没执行。

### SUMMARY 与 DB 不一致

SUMMARY 应从 DB 整体重建，不 append。检查 reparse/delete 后是否忘记 regenerate。

### Metadata/tag 写错

不要篡改 raw事实；增加 correction/invalid note。数字可作诊断，但不进入正式序列。

## 7. SIM / GUI

### SIM 在错误 cwd 启动，资源缺失

确认资源路径是相对 executable 还是 cwd。从项目文档指定目录启动；不能把“窗口出来了”当资源正确。

### 编译通过但画面错

预期行为：编译仅证明语法/link。执行 framebuffer diff；使用 `PrintWindow` 截图检查具体视觉风险。

### 截图黑屏/空白

等待渲染完成；检查窗口 handle、尺寸、`PrintWindow` flag；必要时切换 offscreen dump 或普通截图。清理临时进程和图片。

## 8. 清理

实验结束后：

- 关闭 serial/capture/reset handle；
- kill 自己创建的 GUI/flash child；
- 删除临时 exe/asm/png/log（正式 artifact 除外）；
- 检查每个相关 repo status；
- 不恢复用户已有 dirty 文件；
- profiling patch 反向应用前 `--check`，冲突时人工核对；
- 产品提交不得夹带 local COM、build ID、benchmark 数据或大资源，除非仓库明确要求。
