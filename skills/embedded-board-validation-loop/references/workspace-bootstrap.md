# 在用户工作区建设 workflow 基建

本参考是 skill 的核心执行说明。目标不是把一个固定 `board_lab.py` 复制到所有仓库，而是让 agent 根据当前工作区形成一套项目能长期维护的自动化。

## 1. 勘察清单

先搜索和阅读，不立刻创建文件。若当前目录是 west workspace、repo/manifest、多 worktree 或多仓库聚合根，顶层可能没有 `.git`；agent 应识别真正拥有目标文件的子仓库，分别检查 history/status，不因 workspace 根 `git status` 失败就放弃。

- 项目/全局 `CLAUDE.md`、README、build 文档、保密与提交要求；
- 相关子仓库的 recent log、目标 commit、file co-change 和既有测试模式；不要只依赖未提交的临时文档；
- 用户提到的历史 workflow 可能尚未提交：结合工作树 diff、`.claude/` 进度文档、patch、raw log、数据库和脚本还原，但不擅自覆盖或清理；
- build system：west/CMake/Ninja/SCons/Make/Bazel/vendor IDE；
- runner/flash 脚本、board config、download image/address/config；
- serial/RTT/SWO/log 工具和现有端口配置；
- reset/power/relay/GPIO 工具与接线文档；
- benchmark/test/profiling 宏、设备日志协议；
- host C tests、SIM、golden output、截图工具；
- data/report/database 和历史开发日志；
- CI、自测、gitignore；
- 当前 dirty state，避免覆盖未提交实验。

随后输出一张 capability map：

| 能力 | 现有实现 | 是否已验证 | 缺口 | 计划落点 |
| --- | --- | --- | --- | --- |
| build | | | | |
| flash | | | | |
| reset | | | | |
| capture | | | | |
| parser | | | | |
| provenance | | | | |
| correctness | | | | |
| store/report | | | | |

## 2. 选择落点

优先级：

1. 扩展当前工作区已有的 benchmark/harness 或相近工具；
2. 扩展现有 test runner / board farm 框架；
3. 小项目用单文件 CLI + tests；
4. 只有多板、多 backend 或团队共享需求明确时才拆 package/plugin。

不要把 skill 目录当运行时依赖。skill 可以被更新、安装在不同位置，同事也不一定有相同绝对路径。工作区基建应自包含，或显式声明常规 Python/package 依赖。

若工作区已有正在使用的 benchmark 数据库/CLI，不做一次性大重写。先给现有 parser、run schema、compare verdict 和关键 failure log 补 characterization fixtures，锁定兼容行为；再逐层加入 discovery、adapter 或 gate，并保留旧数据的 reparse/migration 路径。

## 3. 从 vertical slice 开始

若需要新建，agent 先从 skill 的 backend-neutral template 取材，并在复制后的工作区文件中调整 `project.root`（相对该配置文件解析）、命令与 backend；不要直接运行含 `REPLACE_*`/`DISCOVER_*` 的模板。RTL87X3G 模板只有确认使用相同 mpcli + UART2 共口 + 独立 RTS 拓扑时才可选。

如果用户希望同事直接复用，除代码外还要把依赖安装、环境变量、USB/driver 权限、接线角色映射、首次 discovery、local config 创建、预期 smoke 输出和失败恢复写入 README；一条从 clean checkout/新 shell 开始的 bootstrap 命令应可重复执行（idempotent），且不会覆盖已有 local state。

第一版只需打通一个真实场景：

```text
lab doctor
lab run --tag smoke
lab list
lab compare <baseline> <candidate>
```

最低产物：

- 一个可共享配置模板；
- 一个 gitignored local override 或 discovery cache；
- build/flash/reset/capture 编排；
- build ID；
- 最小版本化 parser；
- raw log；
- 一种结构化记录（JSONL 或 SQLite）；
- selftest fixtures；
- README 中的首次接线和故障恢复。

若已有 `bench.py` 已经完成大部分，直接增强，不要生成第二个 `lab.py`。

## 4. Adapter 边界

项目代码应把下面各层独立：

```python
class BuildBackend:
    def build(self, context): ...

class FlashBackend:
    def flash(self, artifact, events): ...

class ResetBackend:
    def open(self): ...
    def pulse(self): ...
    def close(self): ...

class CaptureBackend:
    def open(self): ...
    def read(self): ...
    def close(self): ...

class Protocol:
    def parse(self, raw): ...

class Store:
    def record(self, run): ...
```

这不是要求过度 OO；单文件可用函数或 dataclass。关键是编排层不要写死 mpcli marker、RTS 极性或 UART parser。

## 5. 端口和硬件动态识别

### 每轮开始

1. 枚举当前 serial/USB devices；
2. 使用已保存 stable identity 解析当前 COM/tty；
3. 唯一匹配且 device 改变：自动采用并打印 drift；
4. 端口正被占用：识别 owner 或给出关闭 monitor/孤儿进程指引；
5. identity 不存在：检查拔插、驱动、hub、电源；
6. 出现新 adapter：根据项目安全约束主动识别角色。

### 主动角色识别

安全、只读的探测优先：

- PNP/USB description、VID/PID/serial/location；
- 打开候选 console 只读短时间，匹配已知 boot/log prefix；
- 观察设备插拔前后差集；
- 检查现有 runner/local config 和用户接线文档；
- flash 工具能否非破坏地 enumerate/probe。

复位 pulse、擦写、切电等不是只读探测。只有目标角色和极性已由文档或用户确认后才能执行。若两个同型号 FTDI 无法从稳定信息区分，可指导用户逐个拔插一次建立映射，再保存 serial；不需要每次询问 COM 号。

### Local state

自动发现结果可保存为：

```json
{
  "roles": {
    "flash_log": {"serial": "SERIAL_A", "last_device": "COM_CURRENT_A"},
    "reset": {"serial": "SERIAL_B", "last_device": "COM_CURRENT_B"}
  }
}
```

`last_device` 仅用于显示和诊断，不参与持久身份匹配。adapter 替换时更新 serial 并记录时间/原因；不要只把一个 COM 号机械改成另一个。

## 6. 故障自动修复闭环

典型顺序：

```text
run fails
 -> classify phase (doctor/build/flash/capture/parse/gate)
 -> collect evidence
 -> perform safe remediation
 -> update workflow + add regression fixture/test
 -> retry only failed phase when safe
 -> rerun end-to-end vertical slice
```

例子：

- COM 漂移：stable identity 重新映射，更新 local cache，补 drift selftest；
- mpcli marker 改名：保存失败 flash log，兼容新 marker，补 fixture；
- orphan 占口：补 process-tree cleanup，补模拟 timeout test；
- parser 遇到粘连行：保存匿名 fixture，修 prefix recovery；
- stale image：PERF 行加入 build ID 并补 mixed-ID test；
- 工作量意外为 0：协议补 operation count，新增 workload gate。

不要在 workflow 中加入无限 retry 或“忽略所有错误”；自动修复必须能解释根因并留下回归测试。

## 7. 多环境演进

当第二块板或第二种 flash 工具出现时：

- 先添加 adapter/config，不复制整套 orchestrator；
- 共用 parser/store/report，除非协议确实不同；
- 用 capability flags 描述共口、reset handshake、USB re-enumeration 等；
- 每个 backend 至少一个 mock/fixture selftest；
- hardware smoke 测试按实验台可用性选择运行，不阻塞无硬件开发。
- CI 分层：普通 CI 只跑 parser/config/store/backend-mock selftest；真实烧写放到有锁和超时恢复的 lab runner，避免多个任务同时操作同一块板或串口。

## 8. 团队共享与维护

- README 分开记录可共享硬件拓扑和本机动态 discovery，不提交个人 COM/tty；
- 依赖使用项目已有包管理/requirements/lockfile，bootstrap 不悄悄全局安装工具；
- schema/protocol/backend 版本显式化，升级提供 migration/reparse；
- 真实实验台资源用 lock（文件锁、CI resource lock 或 lab scheduler）互斥；
- 定期以新同事/clean shell 流程演练，过期工具路径、driver 和 adapter mapping 及时修正文档；
- 保密数据、vendor binary、内部 log 是否共享遵循项目分级，不能因自动化方便而外发。

## 9. 完成定义

根据用户本次目标区分状态，不能把“基建文件已生成”和“实验台已打通”混为一谈：

### `workflow scaffolded`

- 工作区 skeleton、配置模板和 README 已落地；
- 无硬件 selftest 通过；
- 未验证项和待接入 backend 已明确。

### `workflow host-validated`

- 上述项目通过；
- discovery/doctor、parser/store/report 的 host 测试通过；
- build adapter 至少完成 dry-run，能验证路径和 argv。

### `workflow hardware-validated`

- 当前硬件 discovery/doctor 通过；
- 至少一次真实 build；
- 至少一次真实 flash/reset/capture；
- build ID 和 workload gate 通过；
- raw/structured/report 记录可读取；
- README 足以让同事在同平台复现；
- 已说明仍未验证的 backend/平台。

没有硬件或用户未要求实际跑板时，可以准确说“基建 skeleton 已建立”或“host 侧已验证”，不要声称板级 vertical slice 已打通。若用户明确要求完整自动化机制，则以 `hardware-validated` 为完成标准。
