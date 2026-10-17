# TASK-024-R7 终审：尚未通过

日期：2026-10-14。评审者：GPT Architect / Reviewer。结论：**NOT_ACCEPTED**；TASK-024 系列暂不关闭，不制定 TASK-025。生产 Gate1 适配器本轮未改，以下问题均在测试入口的末端收尾，按 B 类交 DSH 定点处理。

## 1. 核验范围与已确认事项

实际文件优先于交接声明。实读测试 `59a47508faa9117128b03c3717ddd93a8006caa40f6d460dc29abc87467058e1`（235369 字节）、回执 `d41640bc6dfd15207d24d24b71e9904ef315df1eb4155a49cbb87ddc01cdf867`（12006 字节）、生产适配器 `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9`，均与交接相符。

GPT 读取 R7 已有正常证据，独立核对六份载荷的确切字节：全部与台账 entries 及写前 final_entry_basis 相符；实际调用当前 `audit_ledger` 和正向 scope 的 `evidence_audit` 均通过。原始核心 9 条、正向 6 条、隔离负向 3 条分列；三条负向各由真实 helper 拒绝。读取既有证据不计为重新执行 prepare/接收器。相关同名函数各只剩一份，清理结果确认。

GPT 另执行当前真实 `run_r5_only` 收尾三次（正常、末次审核映射失败、末次确认后字节变化），并为两个反例各启动新 Python 进程，经当前 `main()` 的真实 argparse → `run_r5_only` 路径再次核对进程退出。为避免重复业务链，仅将早期 `build_r5_round_summary` 替换为明确标注的 R7 旧观察读取器；当前 `main/run_r5_only/run_r5_round_entry/run_r5_entry` 判定代码均保持原样。GPT 本轮实际 prepare/接收器/P1/store 调用数为 0，执行的是当前收尾代码；旧源证据未改。

证据根：`data/reviews/task024_r7_gpt_20261014_234640/`。主脚本 `verify_entry.py`，两个新进程结果 `cli_final_audit_probe.json`、`cli_post_confirmation_probe.json`；正常对照 `normal_probe.json`；已有证据审核 `existing_evidence_audit.json`。脚本会创建具名新目录，不应直接重跑覆盖本次根。

## 2. B1：内部失败仍未支配最外层返回

位置：当前测试 `run_r5_round_entry`（约 2865 行）和 `run_r5_only` 最后一行（3055 行）。`clean_payloads` 使正常末次收尾使用局部 failures 副本，内部失败写入该副本及根目录；最外层却只检查全局 `FAILURES`，忽略最终正常 verdict。

定点先观察：正常目录的真实 `audit_ledger` 被调用两次，第一次来自所谓 dry-run，第二次是实际末次重放。GPT 只在第二次真实 helper 返回后受控映射一次：真实 ok=true → mapped ok=false。结果：内部正常 verdict=1/FAIL，根 summary=FAIL、磁盘 failures=1；但全局 failures=0，`main()` 返回 **0**，新进程也退出 **0**。控制未在写盘前宣布失败，恰命中一次。

这仍是 R6/R7 要求修复的实际入口误报成功，不能用两个内部故障副本的返回 1 代替证明。最外层必须直接消费实际最终 verdict，并使真正命令行进程非零；预期故障控制与最终正常根发生的异常失败应分列。

## 3. B2：最终原始字节确认后仍有未复测的文件消费

位置：`run_r5_entry` 的 `late_confirmation` 之后，约 2727—2753 行。成功分支重新读取/解析 `summary.json`，随后又读其字节做写入判定；这些消费发生在声称的最终确认之后。

GPT 调用真实 `Path.read_bytes`，在实际末次正常重放中、`late_confirmation` 与 `disk_failed` 已完成后，成功分支读取 summary 返回原值，再仅给当前根 `checks.json` 追加一个 LF，不同步任何哈希。结果：本次 `main()` / 新进程仍 **0**、summary **PASS**、failures **0**；checks 的坏字节保留，独立实读与台账哈希不符。恰命中一次，未改 helper 结论或观察标记。

应把所有必要对象消费/摘要构造放在终端确认前，终端仅按已绑定缓冲确认原始字节，之后不再读候选文件或自动重写已声明成功载荷。无需增加第三、第四遍审核。

## 4. E1 与回执 §8 的三项裁决

1. **干跑/重放：当前不接受。** `run_r5_entry` 虽有 `dry_run` 参数，函数体未消费该参数；真实观察显示正常根的六载荷和台账各被写入两次，checks 与台账的两次字节不同。回执“干跑不写盘、不改全局状态”“最终载荷一次写盘、同源同值”与实际不符。不是禁止一切前置试验，而是前置试验不得写正式最终候选，再覆盖为最终证据。本项与 B1 的两次正常收尾同根，需一并收敛。
2. **`expect_failure`：有条件接受。** 仅表示既有失败登记是否如实保留，不能把真实最终失败变成成功，也不能扩大三条具名隔离负向的排除范围。当前六载荷内容由真实 content readback 与 expectation compare 约束，实际正常字节相符。台账 `content_audit.ok = not expectation_compare.ok` 是反向信息字段，正常时 false，含义易误读；当前不作为新增阻断，不得继续称其为通过判据。
3. **受控映射方法：接受；通过范围仅到已实测层级。** 保留真实 helper 原始返回、末次写盘后映射一次，是有效的失败传播注入。R7 两个内层故障副本确实 1/FAIL；但 B1 证明真正最外层仍 0，故不能据此宣称全链传播已关闭。无需再更换故障方法或新增业务判断。

## 5. 保护与下一步

GPT 一次最终全树实读 156537 文件，changed 仅测试文件；范围外变化、missing、读取错误、范围外新增均为 0，scope_compliant=true。旧 R5 越界 326 文件逐项不变、未追认；旧 harness 未变，无恢复例外。前轮两个自指元数据按确切路径单列，无前缀豁免。扫描后仅有限核对冻结身份与定稿本轮评审元数据，没有第二次全树扫描。新基线 SHA/项数与两个确切自指排除见同根 review_result.json。

保持此前已关闭的生产语义、窗口清理、三条真实负向、scope 和历史恢复结论；不重新测试业务大链。只交 `TASK-024-R8_DRAFT.md` 修复本报告两处末端缺口及同根的双写问题。R5 越界现场继续留证、不追认，不以本次读取承认为合规生成。

真实批准仍 null，宿主开发态 0008，next/AI false。本技术结论不构成批次批准或人类审计判断；看板仍由人类操作。
