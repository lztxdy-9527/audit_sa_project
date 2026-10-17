# TASK-024-R6 终审

日期：2026-10-14。结论：**NOT_ACCEPTED，仅剩顶层定点入口的末次终审失败支配问题。** B1 真实控制、三条隔离负向观察的范围口径、S1 历史越界留证处理均关闭；生产适配器继续冻结，不制定 TASK-025。

## 1. 身份与本轮复验

实际交付身份一致：测试 `8258581529e87385f47dcf3ec62c6c51053b224a695ebf37ef75c7a735149086`（686526 字节）；回执 `bc86e1708289d2ec80a3bfb8bf225d8d4794965aac3797437f684ce31ef457b3`（17474）；生产适配器 `d8ace42f965088460239192e2e32c29fc7bccdecce32afca37638de1758e34d9` 未变。

GPT 先读取 R6 执行端正常结果，**独立实读最终六载荷长度/SHA，均与台账一致**，实际 audit_ledger 通过。三条具名负向观察 `core-prepare::4/5/9` 分别送实际 evidence_audit，均被拒；正向收敛视图通过。实际 Blocked/Error API 记录及其异常字段确实存在。此项为读取既有证据后实跑审核 helper，并非重跑其接收/prepare。

随后在两个独立新根执行当前真正 `run_r5_only`：

- `data/human_gate1_decision_tests/task024r6_gpt_20261014_230011/`：只在**最末次顶层 audit_ledger** 调用真实 helper 后，把结果受控映射为非空问题。
- 同名 `_byte` 新根：真实 `disk_readback` 对最后一份 summary 返回原始成功读数后，给该 summary 只追加一个 LF，wrapper 返回原值。

两例均未改生产/测试文件、未运行历史大套件、未生成决定记录。它们各自实际执行 R6 最小入口（9 次 prepare、3 次接收），不是读取执行端的 PASS 代替运行。

## 2. 对请求裁决的三处口径

### §3.4：当前元数据补写后的终审不能接受

不能仅凭“最后按新字节重建台账，当前哈希一致”认定整个成功链有效。当前 `run_r5_only`（约 10469—10547 行）在早期 closure 后重写 checks/summary 和台账，并把 `final_ledger.content_audit` **直接写成常量 true**。它计算 `final_ledger_audit`、`final_disk_confirmation`、`final_entry_same_buffer` 后仅落盘，不把其失败加入 FAILURES，末尾仍只按此前 FAILURES 返回。

GPT 最末次审核映射实测：真实 helper 原结果 ok=true，注入恰 1 次后 `final_entry_ledger_audit.ok=false`，问题明确；**顶层仍返回 0、summary=PASS、failures=0**。完整结果见 `final_audit_failure_probe.json`。

GPT 末次读取后 LF 实测：注入恰 1 次，summary 台账 3516 字节、实际 3517，坏字节保留；**顶层仍返回 0、summary=PASS、failures=0**。完整结果见 `final_byte_failure_probe.json`。

因此本次不能接受。允许把前置收尾结果和最后报告定稿明确区分，但最终载荷一旦声明，必须以实际最终审核与末次原始字节确认决定对外成功；不能继承早期 PASS、填常量 true，或只登记最终失败而不改变返回码。不得用再次从坏候选生成预期“修平”差异。

### §8.2：三条隔离负向控制范围可接受

本次原始九条观察全部保留，三条负向条目明确登记、expected_mutation=false，各自确被真实 helper 拒绝；再把它们与六条正向观察分列进行收敛是合理的。GPT 已重新调用真实 helper 复核三条，详见 `existing_evidence_audit.json`。

该结论只针对本轮这三条实际控制，不是允许任意失败贴 negative_control 标签后跳过。原始登记/真实入口的九条闭合与正向六条收敛应保持各自 scope，不借此排除末次台账/字节失败。

### §8.3：映射方法允许，当前注入阶段不充分

保留真实 helper，再受控翻转为非空问题，是允许的映射控制；但现有 `run_r5_closure` 的 fault 在**写盘前 prepare_frozen** 已宣布失败，不能单凭它证明新增顶层最终读回审核的失败传播有效。

GPT 将相同方式放到实际最末次顶层 helper，已经证明该失败被忽略。下一卡应让真实顶层末次审核失败实际返回 1，并补末次必要消费后的字节控制。不得用前置 FAIL 或仅内部 helper 返回 1 代替真正顶层结果。

## 3. 不再派发的事项与非阻断记录

B1 的无登记晚变更和真实异常控制已关闭；窗口算法保持；S1 的 37 目录/326 文件继续原样保留、不追认、不作真实批准。R6 自身范围比较独立于 R5 的历史违规。

测试文件存在大量被后定义覆盖的重复辅助函数（collect_negative_controls / evaluated_evidence 各 30 份，build_r5_round_summary 31 份，两个 closure-check helper 各 25 份）。本轮按 AST 和实际 __code__ 定位最后生效定义；**重复本身不单独阻断**。下一次修复不要继续在文件尾叠加同名试错版本，可只清理当前收尾相关的无效副本，避免大重构。

回执中部分摘要哈希/自指解释不准确，按实际最终磁盘和明确自指排除登记即可，不因此要求重跑历史测试或重复全树扫描。

## 4. 最终保护与后续

依据 R5 NOT_ACCEPTED 快照（156114 项，`ea4b7cbcc887884e90761c1697e13384c52915a0655ac48b73006c1b1c85809c`）。

GPT 一次最终完整扫描实读 156312 文件，changed 仅测试文件；范围外变化、missing、读取错误、范围外新增均为 0，R6 scope_compliant=true。旧 R5 越界 326 文件逐项不变、未追认；旧 harness 未变，无恢复例外。两个前轮自指元数据按确切路径单列，不使用 reviews/data 前缀豁免。扫描后仅有限登记本轮评审文档和元数据，没有第二次项目树遍历。下一修复基线 SHA/项数及两个确切自指排除见 review_result。

下一步仅 `docs/tasks/TASK-024-R7_DRAFT.md`，只修末端终审。真实批准 null、开发宿主 0008、next/AI false；人类负责看板和业务判断。

本轮证据根：`data/reviews/task024_r6_gpt_20261014_230011/`。
