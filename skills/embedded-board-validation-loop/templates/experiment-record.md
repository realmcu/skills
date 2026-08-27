# <实验系列名称>

## 固定环境

- 日期：YYYY-MM-DD
- 目标板 / revision：
- flash backend：
- flash/log/reset 端口稳定身份：
- toolchain：
- build config：
- clock / voltage / power mode：
- memory/cache/heap：
- workload：
- protocol version：
- samples / warmup：
- primary metric：
- end-to-end metric：
- correctness oracle：
- baseline run：

## Experiment contract

**问题**：

**假设**：

**唯一允许变化项**：

**工作量 invariants**：

**环境 fingerprint gates**：

**保留判据**：

**回退判据**：

## 实验 N：<名称>（YYYY-MM-DD）

**改动范围**：

**覆盖路径**：

**未覆盖路径**：

**PC correctness**：

- 命令：
- checks / failures：
- negative control detections：

**SIM / bitmap / screenshot**：

**Build / codegen**：

- build ID：
- build 结果：
- object/asm：
- 热循环变化：
- spill / register pressure：

**Hardware runs**：

- Baseline：
- Candidate：
- Repeat：
- raw log / artifact：
- 产品源码 tree/blob hash：
- 最终 binary/build manifest：

**门禁**：

- provenance：PASS / FAIL
- protocol/sample：PASS / FAIL
- workload：PASS / FAIL
- fingerprint：PASS / FAIL
- correctness：PASS / FAIL

| 指标 | Baseline | Candidate | Delta | Noise |
| --- | ---: | ---: | ---: | ---: |
| primary direct metric | | | | |
| per-call metric | | | | |
| end-to-end latency | | | | |
| throughput/FPS | | | | |

**未改阶段异常与不可归因项**：

**Release-like 复测**：

**结论**：保留 / 回退 / 待复测 / 仅诊断。

**结论边界**：

**下一步**：

## 失败实验索引

| 实验 | 假设 | 直接结果 | 处置 | 不要重复的原因 |
| --- | --- | ---: | --- | --- |
| | | | | |

## 最终清理

- [ ] profiling / distribution counters 已关闭或移除
- [ ] local hardware config 未进入产品 diff
- [ ] build ID / benchmark resources 未进入产品 diff
- [ ] 临时 exe / asm / png / log 已清理或归档
- [ ] 所有相关 repo status 已检查
- [ ] release-like correctness 与性能已执行
- [ ] 最终 binary 已绑定 cleanup 后源码 hash/manifest
- [ ] 未经要求未 commit / push
