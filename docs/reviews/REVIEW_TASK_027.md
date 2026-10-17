# TASK-027 评审：NOT_ACCEPTED

评审时间：2026-10-15。以工作区实际文件为准。执行端的 54 项 PASS 为其自报并有既有现场，本轮未重跑该完整入口。GPT 实际执行了公开 API 定点复验及复用观察的独立收尾副本；没有修改生产、测试或旧证据。

交付身份已逐项确认：

- `scripts/runtime_gate1.py`：98928 B，`e44743f943cba02d46f45e2be6d0d049e7123a638c197183ad2a83ff24bd0371`。
- `tests/test_runtime_gate1_decision.py`：58236 B，`5a1cb9e17c355195d094cd98eb95124d3097da840ee86485f6abcdbdac2d5152`。
- 指南：9702 B，`052d107f78b904d5412a27a531c98b3a6d56f6f4bafcb0d90ca8e7126e5e3340`。
- 回执：9422 B，`a52e81a8ac98fd3a6bfaa01f759ba6f4e8e025ae90ade359fba2f0e82174db8b`。

证据根：`data/reviews/task027_gpt_20261015_161614/`，完整调用在 `api_records.json`，摘要在 `probe_summary.json`，补充关系反例在 `relation_probes.json`。当前 TASK-026 GPT 测试及指南仍是已验收身份。正常新 scope 的 save/verify 成功，既有正常事件只读 verify 返回 effective=true，原批次及既有事件字节不变。

## B1：save 将变更后的快照当作本次正确输出，且漏登记叶最终集合

GPT 包装实际使用的冻结 store.save：先真实保存、取得原返回，再只给新事件 `snapshots/submission.json` 追加 LF，返回原 store 值。命中一次，save 仍返回成功；撤销包装后的 verify 拒绝 `store.manifest.payloads[4].byte_size`。

原因：save 在 store 返回后才取六快照作为预期，未将五 payload 的实际长度/SHA 与已绑定的 store manifest 核对。后续拿这些新读数自比，不能证明它们就是该次 store 保存的字节。manifest 的实际 SHA 必须先与本次真实 store 返回绑定，再用其封闭 payload 清单约束五文件，且与本次请求/提交/历史/完整记录关系闭合。

另一独立新 scope 在实际 store 返回后只给运行登记叶新增 `failure.json`。save 仍成功，后续 verify 拒绝该 failure。save 收尾缺少登记叶固定二文件集合；最终确认也须覆盖批次顶层及四个固定子目录集合。原卡明确要求无失败、未知项阻断。

## B2：封套关系与失败边界未闭合

以下均为 GPT 实测，变更仅在本轮新建事件，verify 没有写诊断：

- `context.boundaries=[]`，同步 receipt 的 context 文件 SHA 后，verify 泄漏原生 `AttributeError`，没有可定位 Blocked。应先验证对象/封闭键/严格类型，再消费 `.items()`。
- 将 context 的 source_batch_relative/runtime_relative 改成 OTHER 字符串，registry_file_sha256 改为 64 个 0，仅同步外层 receipt.context_file_sha256，verify 仍 effective=true。三个字段没有与显式参数/登记实读值闭合。
- 在上述副本继续将 context.store_result.record_fingerprint 改为 64 个 0并同步 context 字节绑定，verify 仍 effective=true。保存返回与恢复返回除状态常量外的稳定字段须完整核对。
- 真正的 receipt writer 完整写入后抛 `ReviewReceiptSentinel`（一次、受控测试异常），save 泄漏该原生异常，事件没有本层 failure；随后 verify 竟 effective=true。原测试的“receipt sentinel”实际是追加 LF，不是抛异常，不能作为原卡要求的该分支证据。

写后错误须映射 Error、保留原 cause/坏字节、在已有事件内独占写五键 failure。不能仅靠 `created_event` 在 store 正常返回后置 true 判断现场是否已产生；冻结 store 写后失败时实际事件也可能存在。没有事件时仍不得为诊断造事件。

## B3：锁仅核对内容，未核对取得时的身份

在本轮独立技术锁上取得锁后，保全原目录至同级新路径，再于原锁路径创建字节相同的新目录/lock.json；目录 st_ino 不同。真实 `_release_own_lock` 返回 None 并删除了替代锁。原锁目录已保全。

原卡要求只释放本次实际创建且身份/内容未变化的锁。应记录并核对取得时目录及锁文件身份、逐级路径与内容；取得锁失败和主操作失败后的释放分支也不能盲删或吞掉次错误。无需引入分布式锁或新依赖。

## B4：测试终审仍可接受被替换或缺失的观察

GPT 仅将执行端已保存观察加载到独立内存，调用实际 `finish`，新目录保存候选，不再接收或调用业务核心：

- 正常：0/PASS/空 failures。
- 初始 writes 中只给 checks.json 追加 LF，终审前候选字节已不同于待写缓冲：仍 0/PASS。台账从变更后的磁盘采集，掩盖字节漂移。
- 写入候选 API 返回及候选 expected_observations 时同步替换同一返回字段，保留独立内存预期原值：仍 0/PASS。审核信任候选磁盘 expected，而非定稿内存预期。
- API 候选删除 call_047，独立预期仍 47 条：46 条仍 0/PASS。审核没有 expected→candidate 的完整反向核对。
- 原检查自身为 false 的对照实际 1/FAIL，说明本轮没有把所有失败传播一概否定。

上述问题已在 TASK-026 GPT 修正版中处理，本轮复用了较早收尾逻辑。还存在源码可直接确认的证据缺口：nested caller_api 指向上一条已完成 API（当前 API 调用后才 append）；P1 未观察；仅检查各 API profile ≥1，未分列直接调用/内部 prepare 并闭合；禁用函数名部分是模块名；`--replay` 会写传入旧目录，未强制新 out-dir。应移植已验收的小收尾原则，保持当前业务场景，不扩建观察框架。

## 范围、过程及裁决

允许保留开发阶段因代码版本改变而失效的现场，明确标为历史且不作为当前版本正向证据即可。不能改旧批次绑定迎合新代码。历史损失139项继续单列，27项确切恢复和旧R5越界326项继续保护；当前保护实测见本根 `protection_result.json`。

执行端关于“唯一删除为释放自锁”的声明与测试源码不符：原测试删除了未知文件及 failure 两个探针文件。这是本轮新建探针的范围偏离，须在新回执如实更正；不追认，也不要求重建已删除文件。后续用独立坏副本/新 scope 保留现场，禁止清理探针目标。不能为本评审再执行原完整入口。

GPT 首个定点脚本在锁控制处误用字典键 bytes（实际 buffer），退出1；该过程脚本及其新现场保留。修正仅在新脚本 `verify_current_02.py`，新运行根 run02 完整执行并落盘，首轮输出不冒充完整证据。额外关系核对没有重新建业务链。两轮均未改旧批次、生产、测试或历史证据。

本轮不接受，不关闭 TASK-027，不推进 TASK-028。下发 TASK-027-R1（B 类，按既定架构定点修正）。本评审不授予任何批次批准；effective 的技术核验也不构成执行许可，宿主仍开发态0008、真实批准null、next/AI false。
