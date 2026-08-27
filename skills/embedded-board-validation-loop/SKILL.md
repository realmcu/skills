---
name: embedded-board-validation-loop
description: >
  在用户工作区创建、修复或扩展项目专属的嵌入式 PC + 目标板自动化验证 workflow。
  覆盖环境勘察、build/flash/reset/log adapter、动态串口发现、build ID、workload 与环境门禁、
  PC C/SIM/反汇编/截图、A/B 性能统计、原始 log/SQLite/报告和 release-like 复测。
  含 mpcli + 独立 FTDI RTS 的参考模式，但要求适配 J-Link、OpenOCD、pyOCD、厂商 CLI、
  RTT/SWO、手工复位等实际平台。用于搭板级自动化、编译下载抓 log、RTS、mpcli benchmark、
  硬件 A/B、PC C/SIM 验证、性能数据库或移植现有板级流程。
metadata:
  version: 1.0.0
---

# 嵌入式开发板 + PC 自动化验证闭环

本 skill 的主要产物不是 skill 目录内的一套万能 runner，而是指导 agent 在**用户当前工作区**中建立、修复或扩展一套项目专属的 workflow 基建，把一次开发迭代组织为可审计实验。适用于性能优化，也适用于驱动 bring-up、稳定性修复和协议行为验证。

解析项目路径时，从目标工作区根目录开始；解析 skill 资源时，从本 skill 目录开始。不得硬编码个人机器的绝对路径、COM 号或工具安装目录。skill 自带的脚本和模板只是 bootstrap/reference；真实长期使用的 orchestrator、adapter、parser、数据库和测试应按目标项目约束落在工作区中，并由项目自己的测试和版本控制管理。

## 使用模式：先建设工作区 workflow，再运行实验

用户提出自动化或板级验证任务时，agent 默认完成以下工作，而不是仅返回一份说明：

1. **勘察**当前工作区已有的 build/flash/reset/log/test/report 能力、项目指令，以及实际子仓库的 git history/co-change 模式；
2. **复用优先**：已有 harness 能扩展就扩展，不另造平行工具；若工具已在持续使用且数据兼容敏感，先补 characterization tests，再渐进修改；
3. **识别缺口**：把 board-specific 能力与 backend-neutral 编排分开；
4. **提出最小实施方案**：说明准备复用/新增哪些工作区文件、哪些是本机 local state；如果会修改产品代码或固件 instrumentation，先区分永久代码与临时 patch；
5. **在工作区落地基建**：用户要求创建/完善自动化时，按需创建配置模板、本机覆盖、adapter、orchestrator、parser、selftest、数据 schema、报告生成器和文档；
6. **用真实环境打通一条 vertical slice**：doctor → PC test → build → flash/reset → capture → parse/gate → archive/report；
7. **故障驱动完善**：端口漂移、工具输出变化、串口独占、超时残留等实际失败出现时，agent 先自动 discovery 和诊断，再修复工作区 workflow；
8. **沉淀但不过拟合**：把可复用机制留在项目，机器临时值留在 local config，不把一次实验的偶然参数固化成通用规则。

若用户只要求规划，则只给实施方案，不修改工作区。若用户要求创建/完善但当前没有硬件，则生成最小 skeleton + selftest + 明确待接入点，不声称板级链路已打通。

## 核心目标与硬门禁

自动化流水线建议采用：

```text
preflight -> PC oracle/equivalence -> build -> inspect codegen
          -> flash/reset -> capture -> parse -> validate provenance
          -> validate workload/config -> aggregate -> compare -> archive
          -> release-like recheck -> cleanup
```

一项结果只有同时满足以下条件，才可称为“已验证”：

1. **正确镜像**：设备 log 中的 build ID 与本轮构建一致；仅看到新时间戳或正常输出不够。
2. **相同工作量**：每窗口/每帧/每操作的关键计数一致；更快但少做工作不是优化。
3. **相同环境**：board、toolchain、关键宏、时钟、memory/cache、workload、输入数据等指纹一致；优化目标文件本身应记录但不阻断比较。
4. **统计显著**：丢弃 warmup，以 median 为主；delta 超出测量噪声和跨构建波动。
5. **输出正确**：算法由 reference/candidate 比较，GUI/图像必要时 bitmap diff + 截图；编译成功不能证明结果正确。
6. **可重复**：重要收益至少独立 rebuild/flash/re-capture 一次；小收益必须做交替或成对构建。
7. **原始证据保留**：raw log 与 append-only 记录不可因后续解析口径变化而被改写。

任何门禁失败时，记录 run 为 invalid/diagnostic，**不得把数字用作收益证据**。

## 1. Discovery 与工作区勘察

新项目或新同事首次使用时，先读取 [workspace-bootstrap.md](references/workspace-bootstrap.md) 与 [config-schema.md](references/config-schema.md)，勘察后将模板/必要 bootstrap 落到用户工作区。随后从工作区运行项目自己的入口；在基建尚未生成时，可临时用 skill 脚本辅助 discovery：

```powershell
python <skill-dir>/scripts/board_lab.py discover
# 创建并填写 <workspace-config.json> 后：
python <workspace-lab.py> doctor --config <workspace-config.json>
```

至少确认：

- workspace/repository、app、build directory；
- build command、产物和成功标记；
- flash backend、命令、成功/连接标记、timeout；
- console port、baud、line ending、编码；
- reset backend、端口/极性/hold 时间、是否须在握手期间触发；
- flash 与 console 是否共用串口；flash 与 reset 是否可由同一 adapter 并发占用；
- 串口稳定身份（优先 serial；或 VID/PID + location），不要只记 COM 号；
- workload 启动、warmup、sample 数和停止条件；
- log protocol、build ID 注入方式、关键工作量计数；
- 需要记录和需要阻断比较的环境指纹。

**先保存模板，再保存本机覆盖**：可共享配置只含逻辑角色和能够获得的稳定硬件身份；易漂移的 COM/tty 号只作提示或放在 gitignored local config。每轮 workflow 开始都允许重新 discovery：若同一 stable identity 出现在新端口，自动采用并提示漂移，不应要求人工先改硬编码；若 adapter 本身变化、没有唯一稳定身份或角色不清，agent 应结合设备描述、接线、flash handshake 与 console 输出主动探测，只有涉及复位极性、下载 strap、flash address 等可能损坏设备且无法验证的参数才询问用户，绝不猜测。

## 2. 建立最小而完整的验证矩阵

先写一页 experiment contract：

- 假设：什么代码变化会影响哪个直接指标；
- 输入域：真实 workload 覆盖哪些路径，哪些路径没有覆盖；
- correctness oracle：bit-exact、容差、协议状态还是截图；
- primary metric：最接近改动的直接指标；
- end-to-end metric：系统层收益；
- workload invariants；
- configuration invariants；
- baseline reference；
- retain/revert 判据。

不要一开始追求全矩阵。先覆盖当前真实路径，再为共享代码补受影响范围。每轮只改变一个独立假设；若两个改动必须一起做，要说明为何无法拆分。

## 3. 固件 instrumentation 与日志协议

### 3.1 低扰动采集

- 热路径只累计 count/total/max 或 histogram；低频 snapshot + reset。
- 不在 per-pixel、per-IRQ、allocator 等热路径直接 `printf`。
- 设备输出 `total`，不要输出截断后的 `avg` 再由主机反推总量。
- 计数和时间必须来自**同一窗口**；不要混用不同 timer 的 FPS/帧数。
- 第一窗口通常包含启动、cache cold、窗口未对齐，设备端或主机端明确丢弃 warmup。
- profiling 有 observer effect；用于定位和同配置局部 A/B，最终用 profiling off 的 release-like 构建复测。

### 3.2 推荐机器协议

```text
[BENCH BUILD] id=<build_id> proto=1 board=<board> workload=<name> ...
[BENCH PERF] proto=1 id=<build_id> seq=<n> units=<n> win=<ms> \
  stage_a=<count>/<total_us>/<max_us> stage_b=... work_x=<count> ...
```

要求：

- 每一条 PERF 都带 build ID；不能只靠启动 banner，因为 flash 和 log 共口时会错过 banner。
- 协议必须版本化；未知版本 hard fail，不能尽力猜字段语义。
- 单行可独立解析，允许 UART 与其他日志粘连时通过 prefix 搜索恢复。
- 若设备会重启，`seq`、build ID 和 boot counter 可检测跨镜像/跨启动混入。
- log 必须包含工作量计数；没有 workload evidence 的性能结果只能标为 provisional。

build ID 每次 build 前写入生成头或编译定义；推荐短 SHA256（tag + timestamp + pid/nonce），并确保其变化会触发目标对象重编。

## 4. PC 侧先证明正确，再花硬件时间

对算法、codec、blend、DSP、协议编码等改动：

1. 保留优化前 reference，不要把 reference 与 candidate 同时重写成同一抽象。
2. 对中间结果和最终结果分层比较，例如 bit buffer 与 final framebuffer 都比较。
3. 覆盖边界、全零、全一、单 bit、对齐/非对齐、最小/最大、固定种子随机。
4. 对数学重排显式验证溢出上界、舍入、饱和、endianness、alignment。
5. 每个新 kernel 配一个**专属 negative control**，并选择必定暴露该错误的输入。若 broken 实现未被拒绝，harness 不可信。
6. 返回非零退出码，并在输出中报告 checks/failures/negative-control detections。

PC 模型无法编译目标 intrinsic 时，模拟 lane 语义；但仍需用真实 SDK 构建和目标硬件运行验证 intrinsic 可用性。不得用另一套 compiler/header 推断目标 toolchain 能力。

GUI/图像验证：优先 framebuffer/bitmap diff；颜色、位置、透明度、重叠或动画无法由数据充分判断时，运行 SIM/PC GUI 并截图肉眼确认。Windows 可使用 `PrintWindow`，流程见项目全局截图规则。

## 5. 构建与 codegen 检查

### 5.1 构建

- 使用项目真实 toolchain、配置和 cwd；不要在另一个工具链上“证明”目标 intrinsic 可编译。
- build directory 是否可任意放置必须通过项目脚本确认；有相对路径 post-build 时放在 app 内。
- flash 命令的 build/config/image 路径尽量绝对化；厂商 CLI 常切换 cwd 以寻找 bundled firmware。
- 把完整 build log 保存到 run artifacts；同时定义明确 success marker（如链接完成）和 exit code。marker 必须从**本次 invocation** 的输出/产物中重新观察，不能复用旧 log 或仅凭旧 artifact 存在判断成功。

### 5.2 反汇编先于烧板

若假设依赖指令数、vectorization、inline、spill、predicate hoist 或访问宽度：

1. 只重编目标 object（项目支持时）；
2. 用实际 SDK 对应 objdump 反汇编；
3. 比较 reference/candidate 热循环；
4. 检查 vector/scalar 指令、spill/reload、寄存器压力、关键依赖链、常量/`vmsr` 是否移出循环；
5. 机器码未改善或出现 spill 时，先回退，不浪费 flash/capture 时间。

源码操作少不代表更快；标量指令也可能与向量 dual-issue。最终仍以硬件直接指标为准。

## 6. mpcli + RTS backend（按需加载的 RTL87X3G 参考）

只有 workspace discovery 确认使用 RTL87X3G + mpcli + UART/RTS 拓扑时，才读取并执行 [mpcli-rtl87x3g.md](references/mpcli-rtl87x3g.md)。其他平台跳过本节，不把 FTDI、RTS 电平、mpcli marker 或 UART 共口假设带入通用 orchestrator。

该参考的关键经验是：reset 必须由 flash backend 的真实状态事件驱动，进入 loader 后停止 pulse；flash/log 共口要串行移交；timeout 清理完整 process tree；最终用 PERF build ID 证明新镜像运行。具体接线、电平和 marker 都在参考文档中，实际代码由 agent 在目标工作区定位或生成。

## 7. 在用户工作区生成的推荐结构

根据项目规模裁剪，不要求一次性生成全部文件。优先沿用当前工作区已有的 benchmark、scripts 或测试目录；没有约定时建议：

```text
tools/board_lab/
  README.md                  # 接线、依赖、首次 bring-up、故障恢复
  lab.example.json          # 可共享逻辑角色/backend/marker
  lab.local.json            # gitignored，本机临时 override
  lab.py                    # CLI 编排：doctor/run/list/compare/reparse
  backends/
    build_<system>.py
    flash_<tool>.py
    reset_<method>.py
    capture_<transport>.py
  protocol.py               # 版本化日志 parser
  env.py                    # source/config/toolchain/workload fingerprint
  store.py                  # raw/JSONL/SQLite
  report.py                 # 单 run 和 SUMMARY
  selftest.py               # 无板 parser/gate/db/backend mock 测试
  tests/
    fixtures/               # 成功、截断、旧镜像、混合 ID 等 log
```

落地顺序遵循最小 vertical slice：

1. 配置 + discovery/doctor；
2. build adapter；
3. flash/reset/capture adapter；
4. build ID + 最小协议 parser；
5. raw log + JSONL/SQLite；
6. workload/fingerprint gate；
7. compare/report；
8. PC/SIM correctness 和项目特有扩展。

每增加一个真实故障修复，就补一个无硬件 fixture/selftest（端口漂移本身可用 synthetic port list 测试）。不要把 skill 目录内的 `board_lab.py` 当最终架构，也不要在未运行真实 vertical slice 时声称自动化已建立。

## 8. 可替换 backend 的接口

编排层只能依赖这些语义，不依赖 `mpcli` 名字：

```text
BuildBackend.build(config) -> artifact + build_id + build_log
ResetBackend.open/deassert/pulse/close()
FlashBackend.start(artifact) -> output stream
FlashBackend.connected(line) -> bool
FlashBackend.success(output, exit_code) -> bool
CaptureBackend.open/read/close()
Parser.parse(raw) -> samples + errors + provenance
Store.record(run, samples, raw, artifacts)
```

替换 backend 时，保持不变的是：provenance、workload/config gate、warmup/aggregation、原始证据、比较和复测规则。变化的是进入 bootloader 的动作、连接 marker、烧写命令、串口占用拓扑和成功条件。

常见替换：

- J-Link/OpenOCD/pyOCD：可能无需 UART reset handshake；flash 与 log 可并行。
- DFU/USB bootloader：设备重枚举，端口身份需要 VID/PID/serial/path，并等待 disappear/reappear。
- vendor CLI：通过 command template 和 marker 配置；仍应 kill process tree。
- manual backend：自动化停在明确提示，用户操作后继续；run 标记 `manual_step=true`。

## 9. 抓取、解析、聚合与数据层

### 9.1 抓取

- 以“得到 N 个**匹配 build ID 的完整样本**”为停止条件，不以固定 sleep 为准。
- 新建工作区 workflow 时，capture 应持续增量落盘 raw bytes（临时文件 + `flush`/必要时 `fsync`）；成功后原子改名为 run artifact。解析、gate、DB 或报告失败也必须保留 `.failed` raw log，不能只在 RAM 中攒到成功后才写。扩展现有 harness 时若当前仍为内存 buffer，先记录这个可靠性缺口，再用最小改动补齐。
- 原始 bytes 无损保存；显示文本可用 UTF-8 replacement decode。
- 对 malformed/truncated/interleaved 行计数并报告；严重到影响样本数则 fail。
- 检出 foreign build ID、多个 build ID、boot counter 变化时拒绝入库或标 invalid。

### 9.2 归一化

先确定正确 work unit：per frame、per operation、per byte、per packet、per pixel、per character 等。总量通常不可跨窗口比较。

推荐同时派生：

- direct stage cost per unit；
- call count/work amount per unit；
- per-call cost（区分算法变快与工作量变化）；
- end-to-end latency/throughput；
- median/min/max/spread；需要时 P95/P99。

分母必须从真实执行计数得到，不能仅数输入源；layout、clip、cache、retry 都可能改变实际工作量。

### 9.3 三层证据存储

建议：

```text
data/
  logs/<run_id>.log       # 原始串口，immutable
  artifacts/<run_id>/     # build/flash log、fingerprint、asm、截图、diff
  runs.jsonl              # append-only 审计源
  bench.db                # SQLite 派生索引，可重建
  reports/<run_id>.md     # 单次人读报告
  SUMMARY.md              # 从 DB 整体重建
```

- reparse 只更新 SQLite/Markdown，不改 raw log/JSONL。
- schema 增加派生指标后，可从 raw/JSONL backfill。
- 删除或标 invalid 必须保留审计原因；不要静默篡改历史 tag/note。
- 数据可能大且含硬件/内部信息；按仓库保密与 gitignore 规则决定是否提交。
- 解析前将原始 log 视为不可信数据：禁止对日志字段使用 `eval`、shell 拼接或不安全反序列化；限制单行长度、字段数量、样本量与数据库事务大小，防止损坏日志造成无界内存/磁盘增长。
- `tag`、build ID 和设备输出不得直接成为路径；先做 allowlist/sanitize，并确认最终路径仍在 data/artifact 根目录内，防止路径穿越与覆盖任意文件。

## 10. 比较与决策规则

比较顺序必须固定：

1. provenance/build ID；
2. parser/version/sample quality；
3. environment fingerprint；
4. workload invariants；
5. primary direct metric；
6. end-to-end metric；
7. noise/rebuild variability；
8. correctness evidence。

判断：

- direct metric 明确变差，即使 FPS 偶然变好，也按局部优化失败处理。
- direct metric 变好、end-to-end 在噪声内：可称“目标阶段收益”，不能声称系统收益。
- 局部 profile 变好但 profiling off 的完整 workload 稳定变慢：默认回退或关闭该路径。
- 未改阶段跨 rebuild 大幅漂移：不归因给候选；用 A/B/A、B/A/B 或成对多构建估计 layout noise。
- 工作量/config 不同：不比较百分比，先重新建匹配基线。
- 无明确收益立即回退候选，记录失败假设；不要堆叠多个无结论改动。

## 11. 标准执行循环

### Phase A：准备

- 检查各子仓库 status/diff，不覆盖用户已有 dirty 改动。
- 检查工作区是否已有 workflow 基建；若没有，先从本 skill 模板生成项目专属 skeleton，若已有则补缺口而非另建一套。
- `discover` + `doctor`；按 stable identity 自动解析当前端口，检测到 COM/tty 漂移就使用新值继续；需要检查占用且已确认 open 不会触发危险控制线时，才用 `doctor --probe-port flash`，并按需重复指定角色。该 probe 不发送 payload，但 USB-UART 驱动仍可能切换 RTS/DTR；身份或角色有歧义才阻断并诊断。
- 应用本地 profiling patch 前先 `git apply --check`；记录 patch base/hash。
- 运行 parser/db/orchestrator selftest。
- 写 experiment contract 和 baseline tag。

### Phase B：正确性

- PC C/reference-candidate/negative-control 测试。
- SIM build/run；GUI 变更按需截图或 framebuffer diff。
- 失败先修正确性，不上硬件测性能。

### Phase C：baseline

- build ID stamp；clean/pristine 仅在必要时。
- build，保存 log；需要时反汇编；fingerprint 优先记录构建系统实际消费的 generated config、compiler command/response file、linker inputs，而不只记录源配置文件。
- flash/reset/capture；自动执行 serial RTS/DTR/GPIO/relay reset 前，配置必须记录已实测的极性/安全状态，不能仅因模板给了字段就 pulse。
- 通过 provenance、sample、workload、fingerprint gate。
- 入库，独立重建并复测 baseline，确认平台噪声。

### Phase D：单项候选

- 最小代码改动。
- 重跑 PC correctness 和 codegen check。
- 完整硬件 run，对比直接前身与固定原始 baseline。
- 检查绝对值、delta、noise、工作量和配置。
- retain / revert / needs-repeat 三选一，记录理由。

### Phase E：最终确认

- 关闭 profiling、分布统计和高频诊断日志。
- 用相同 workload 做 release-like A/B。
- 若输出可视，执行 bitmap/screenshot 验证。
- 检查产品 diff，移除 build ID、硬件 local config、临时 patch、数据库、二进制和截图，除非项目明确要保留。
- **将 instrumented 性能 run 与 cleanup 后源码绑定**：记录产品源码 tree/blob hash，并在清理后重新 build；至少证明最终 binary 来自该 clean source state。若清理会影响 timing/code layout，则必须以清理后的 release-like run 作为最终数字，不能只引用 instrumentation 尚在时的结果。
- 未经用户明确要求不 commit/push。

## 12. 失败排查优先级

遇到故障按层定位，不要直接重跑：

1. **host**：工具、Python module、PATH、配置、权限；
2. **port identity/ownership**：COM 号漂移、VSCode monitor、孤儿 mpcli；
3. **reset electrical/timing**：极性、共地、悬空、pulse 落点；
4. **loader/flash**：是否看到 handshake/connected/success marker；
5. **application boot**：是否有 expected build ID；
6. **workload**：是否真的执行目标路径，而不是空闲主循环；
7. **measurement**：窗口、warmup、observer effect、UART 干扰；
8. **analysis**：单位、分母、环境/工作量漂移、错误 baseline reference。

更多具体症状见 [failure-diagnosis.md](references/failure-diagnosis.md)。

## 13. 输出与记录模板

每次实验至少输出：

```markdown
### <实验名>（YYYY-MM-DD）

**假设**：
**唯一改动**：
**覆盖路径 / 未覆盖路径**：
**正确性验证**：
**机器码检查**：
**Baseline run**：
**Candidate run**：
**环境与工作量门禁**：PASS / FAIL（差异）

| 指标 | Baseline | Candidate | Delta | Noise |
| --- | ---: | ---: | ---: | ---: |
| primary direct metric | | | | |
| end-to-end metric | | | | |

**异常与不可归因项**：
**结论**：保留 / 回退 / 待复测。
**下一步**：
```

不得只写“测试通过”；写实际运行的命令类别、样本数、build ID 是否校验、关键 checks/failures 和未执行项目。

## 14. 随 skill 提供的资源

- [workspace-bootstrap.md](references/workspace-bootstrap.md)：agent 在用户工作区勘察、落地、修复和演进 workflow 的核心流程。
- [config-schema.md](references/config-schema.md)：backend-neutral 配置、动态端口解析、local override 与秘密处理。
- [mpcli-rtl87x3g.md](references/mpcli-rtl87x3g.md)：可选 RTL87X3G/mpcli 平台参考；其他平台不要加载其接线和 marker 假设。
- [measurement-and-data.md](references/measurement-and-data.md)：协议、指纹、统计、数据库设计。
- [correctness-ladder.md](references/correctness-ladder.md)：PC C、SIM、bitmap、截图和硬件验证层次。
- [failure-diagnosis.md](references/failure-diagnosis.md)：常见失败树。
- [experiment-record.md](templates/experiment-record.md)：实验记录模板。
- `scripts/board_lab.py`：标准库实现的配置合并、Windows CIM/Unix device-glob discovery、doctor 与 command backend smoke runner；安装可选 `pyserial` 后可获得跨平台 VID/PID/serial/location 发现。复制/改造成工作区 bootstrap 后使用，不是完整 orchestrator，也不实现 reset/capture/parser/database。
