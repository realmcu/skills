# 测量协议、统计与数据留档

## 1. 先定义问题，再定义指标

每个优化至少要有三类指标：

1. **Primary/direct**：改动直接覆盖的 stage/kernel；用于判断候选本身。
2. **End-to-end**：latency、FPS、throughput、功耗等；用于判断可兑现收益。
3. **Workload**：calls、bytes、pixels、frames、packets、cache hits、retries 等；用于证明两轮做了同样的事。

若只看 end-to-end，局部收益会被其他阶段漂移淹没；若只看 direct metric，可能出现局部变快而系统稳定变慢。两者都要报告。

## 2. 时间窗口

设备侧推荐 snapshot API：

```c
typedef struct {
    uint32_t calls;
    uint64_t total_ticks;
    uint32_t max_ticks;
} bench_stage_t;

void bench_snapshot(bench_profile_t *out, bool reset);
```

关键约束：

- profile counters、真实 work units 和 window duration 同时 snapshot/reset；
- 使用单调时钟，处理 tick wrap；
- 中断与多线程更新需原子/临界区或 per-context counters；
- 计时开销先测量，细粒度 stage 可能受量化误差影响；
- 一秒并非固定要求，目标是每窗口足够工作量、日志开销低、总采集时间可接受。

## 3. Build provenance

推荐 build ID：

```text
sha256(tag | high-resolution timestamp | pid | source fingerprint)[0:8..16]
```

注入方式：

- generated header；
- `-DBENCH_BUILD_ID=...`；
- build system generated source；
- image manifest/metadata（仍应在 PERF log 中回显）。

验证：

- expected ID 的样本不足：fail；
- foreign ID 存在：fail，说明 stale flash 或混合 log；
- 一个 capture 中多个 ID：fail，说明中途重启/换镜像；
- `--no-build/--no-flash` 模式可 adopt 当前 ID，但必须标为 UNVERIFIED，不与正式 run 混称。
- instrumentation 清理后要记录产品源码 tree/blob hash并重建；最终 release-like 数字必须能对应到 cleanup 后的源码状态，不能只靠一个已删除的 generated build-ID header 追溯。

## 4. Protocol parser

解析器原则：

- prefix 定位，不要求该 log 行从 prefix 开始；
- key=value，字段顺序尽量不影响解析；
- triple 等复合字段严格校验完整性；
- protocol version 使用 allowlist；
- malformed 行保留错误 line number；
- 缺 mandatory field hard fail；
- 历史协议要么显式兼容，要么提供 migrator，不静默按新语义解释。

推荐主机侧 selftest 覆盖：

- current protocol；
- supported old protocol；
- unknown/missing version；
- malformed/truncated/interleaved line；
- stale/mixed build ID；
- too few samples；
- derived metric 公式；
- warmup 标记；
- database round-trip；
- fingerprint mismatch；
- workload mismatch；
- noise verdict；
- missing historical metric 的 reparse 提示。

## 5. 归一化公式

以 frame 为例：

```text
fps = frames * 1000 / window_ms
stage_us_per_frame = stage_total_us / frames
stage_calls_per_frame = stage_calls / frames
stage_us_per_call = stage_total_us / stage_calls
```

其他 workload 替换 frame 即可。

不要重复计数 nested stage。例如 `load` 内部已经包含 `parse + layout`，总 pipeline 成本不能再写成 `load + parse + layout`。为每个派生指标写清楚 numerator/denominator 和互斥/包含关系。

分母必须从真实执行数据得到。例如：输入有 240 个字符，但 layout/clip 后只真正处理 180 个；用源码输入数会系统性低估 per-op cost。

## 6. 聚合与噪声

默认：

- 采集 `warmup + N` 个窗口；
- 丢弃前 warmup；
- 对每项用 median；
- 同时保存 min/max 与 `spread=(max-min)/median`；
- 对比时可用两轮 spread 均值作为窗口内噪声参考。

但要区分：

- **同一 binary 内窗口抖动**：spread 能看到；
- **重新编译产生的 code layout/cache alignment 漂移**：spread 看不到。

小收益需做成对多构建：A1/B1/A2/B2，或 ABBA；报告每对差值和总体 median。若未改阶段跨构建有 ±2.5% 漂移，低于该量级的总量收益不能凭单对 A/B 定论。

## 7. Fingerprint

每个 run 保存：

- board/hardware revision；
- git HEAD 与 dirty flag（所有相关 repo）；
- toolchain executable/version；
- build type/flags/Kconfig/defconfig；
- build system实际消费的 generated config、compiler command/response file、linker script/map、链接库版本，以及 linker/post-build 输入；只 hash 源配置不一定代表最终生效配置；
- target clock、电压、power mode；
- cache/MPU/memory placement/heap；
- workload source/hash、输入资源 hash；
- feature flags、format、size、mode；
- source file hashes；
- lab adapter stable ID（用于诊断，可不作为性能可比项）；
- ambient/thermal/power information（相关时）。

把 fingerprint 分成：

- **record-only**：优化目标文件 hash、git dirty、端口号等；
- **comparison gate**：board、toolchain、workload、clock、cache、关键配置等。

目标文件变化本就是 A/B 的目的，不能因其 hash 不同而自动拒绝比较；但必须记录以便审计。

## 8. Workload gate

为每项 workload metric 设定容差：

- 理论固定计数：要求完全相等或浮点派生误差极小；
- scheduler/traffic 相关：按协议定义合理百分比；
- dropped/error/retry：通常要求 0 或明确上限。

一旦 mismatch：

```text
INVALID COMPARISON: runs performed different work
```

仍可展示数据用于诊断，但不能给 BETTER/WORSE 结论。

## 9. 存储模型

设备 log、tag、run ID 和外部工具输出都跨越信任边界。parser 只能用显式字段语法和安全类型转换，禁止 `eval`、shell 插值和不安全 pickle/YAML；限制单行、字段、样本和 artifact 大小。任何由外部值生成的文件名必须 sanitize，并在写入前验证 resolved path 仍位于 data 根目录内。

### JSONL（事实源）

每次 run 一行：record + samples + fingerprint + artifact references。append-only；元数据误标时新增 correction record，不改原事实。

### Raw log（事实源）

保存未经筛选的 UART/RTT/SWO bytes 或文本。capture 期间应增量写入临时 raw 文件，定期 flush（对断电恢复有要求时 `fsync`）；完整 run 成功后原子改名。即使 timeout、parser、gate 或数据库写入失败，也保留带失败状态的 raw log 供诊断。支持协议升级后 reparse；原始 log 不应被“清洗后覆盖”。

### SQLite（派生索引）

至少三表：

```text
runs(run_id, ts, tag, provenance, verified, fingerprint, meta, log_path, ...)
metrics(run_id, key, median, min, max, spread)
samples(run_id, idx, used, data)
```

允许 schema migration；可从 JSONL/raw rebuild。

### Markdown（人读视图）

单 run 报告 + SUMMARY。SUMMARY 每次从 DB 整体重建，不 append，避免 reparse/delete 后残留 stale row。手工说明写在独立开发日志，不写入自动生成 SUMMARY。

## 10. Run 状态

建议显式状态：

- `valid`：所有 gate 通过；
- `diagnostic`：如 distribution profiling，有 observer effect，只看分布；
- `invalid-stale-image`；
- `invalid-workload`；
- `invalid-config`；
- `invalid-too-few-samples`；
- `unverified-reused-image`；
- `failed-build/flash/capture/parse`。

失败 run 也可保存 build/flash/raw log 供排查，但默认不进入性能趋势。

## 11. 报告规范

必须包含：

- run ID/tag/time/build ID/verified/status；
- sample used/total/warmup；
- primary 和 end-to-end 绝对值；
- delta 与 noise；
- workload/config gate；
- correctness evidence；
- raw/artifact path；
- 不可归因异常；
- retain/revert/repeat 决策。

百分比的方向要明确。例如 latency `-10%` 与 throughput `+11.1%` 不是同一百分比，不能混写。
