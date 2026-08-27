# 正确性验证阶梯

性能优化必须先回答“仍然正确吗”，再回答“快了吗”。不同层覆盖不同问题，不能互相替代。

## Level 0：静态边界与契约

- 输入范围、整数乘加溢出、alignment、endianness；
- ownership/lifetime、DMA/cache coherence、ISR/thread context；
- API/ABI 和编译条件；
- reference 的语义是否真是现有行为，而不是理想化规范。

对数学重排写出上界证明。例如 packed-field/SWAR 必须证明字段不会 carry 到相邻 lane，不能只用随机测试“看起来没错”。

## Level 1：Host parser/orchestrator selftest

不需要硬件，验证自动化本身：

- config merge/path/template；
- protocol parse/version/error；
- stale image；
- workload/config mismatch；
- aggregation/noise；
- DB round-trip/reparse；
- negative status 不进入 valid trends。

若 harness 的判定逻辑未经测试，后面的硬件数字不可信。

## Level 2：PC C reference/candidate equivalence

适用于纯算法、像素、codec、CRC、packet layout、DSP kernel。

### Reference 独立性

reference 保留优化前结构。不要把两侧同时抽成同一个 helper 后只比较 helper 的两个调用；那会共同复制同一 bug。

### 测试输入

- 0、max、boundary、single-bit；
- alignment 前后、lane 前后、tail 0/1/N-1；
- 最小/最大 width/height/length；
- structured patterns + fixed-seed random；
- 合法域内 exhaustive（范围可控时）；
- 非法输入另测 error handling，不拿 UB 做 equivalence。

### 分层输出

算法 pipeline 同时比较中间与最终结果。例如 raster：1-bit buffer 与灰度 output 都比较；blend：lane 结果与 framebuffer/guard region 都比较。

### Negative control

每个候选配一个最可能的 broken 版本：shift ±1、lane 顺序交换、漏 carry、off-by-one、错误饱和、错误 tail。构造输入使其**必然失败**。harness 要报告 broken detection count；若为 0，整个测试失败。

## Level 3：PC/SIM 构建和运行

验证：

- 非目标平台 fallback 能编译；
- strict warning；
- UI/application 路径能启动；
- sanitizer（项目支持时）；
- 文件/资源相对路径和实际 cwd。

SIM 不能证明 target intrinsic 或 cache/DMA 行为，但能快速覆盖逻辑、生命周期与视觉。

## Level 4：Bitmap/framebuffer diff

对渲染算法，优先自动 diff：

- baseline 与 candidate 同输入；
- 比较像素、stride padding 和 guard；
- clip/rotation/mirror/opacity/format/cache first-hit；
- 如果允许误差，预先定义 per-channel tolerance、不同像素数上限和原因；默认 bit-exact。

截图肉眼相似不能代替 bit-exact diff；但 diff 也可能漏掉窗口组合、资源、动画等系统问题。

## Level 5：GUI 截图

当颜色、位置、透明度、重叠、字体、动画首帧等不能从日志断言时：

1. 从正确 cwd 启动 Windows simulator；
2. 等待 2～3 s；
3. 使用 Win32 `PrintWindow` 捕获目标窗口；
4. 读取 PNG 肉眼检查；
5. 关闭进程，删除临时 log/png，确认未污染 status。

检查点应针对改动：bearing、1 px 边界、clip、mirror、bold、cache 首帧/后续、RAMLESS section 重影等。

## Level 6：真实 SDK codegen

- build target object；
- objdump/size/map；
- intrinsic 是否真的生成目标指令；
- 是否 fallback 到 helper/scalar；
- 是否出现 spill/reload；
- constant/predicate 是否 hoist；
- hot loop 的 branch 和 dependency chain。

另一版本 GCC 能编译不代表项目 SDK 能编译；objdump 无法解码某些新指令时，要用已知 encoding 对照或更新工具，不能断言指令不存在。

## Level 7：目标板功能与性能

- build ID；
- flash 成功；
- workload counters；
- primary/end-to-end metrics；
- repeat build；
- power/cache/memory/clock 等目标特性。

## Level 8：release-like 回归

关闭 profiling、distribution counter、debug logging，重新 A/B：

- correctness 结果仍适用；
- end-to-end 方向与局部 A/B 一致；
- ROM/RAM/stack 等资源可接受；
- 最终产品 diff 不含本地仪器化和 lab 配置。

## 如何选择层级

| 改动 | 最低建议 |
| --- | --- |
| parser/report 脚本 | L1 |
| 纯 C 算法 | L0 + L2 + target build |
| SIMD/MVE/DSP kernel | L0 + L2 + L6 + L7 + L8 |
| GUI pixel path | L2 + L3 + L4；必要时 L5；再 L7/L8 |
| driver bring-up | L0 + build + target functional log；视觉/波形按接口补充 |
| 性能配置/cache/clock | L7 多基线 + fingerprint + repeat |

只声明实际执行的层级；例如“host model 通过”不等于“真实 intrinsic 路径通过”。
