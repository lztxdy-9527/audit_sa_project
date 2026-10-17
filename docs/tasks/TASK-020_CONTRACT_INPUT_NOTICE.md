# TASK-020补充输入通知：主理人正式V1契约已建立并确认生效

日期：2026-10-13；GPT整理。与原`TASK-020_DRAFT.md`并读。只补充新的外部输入和评审端产物身份，**不改变TASK-020文档范围，不授权P1实现**。

## 1. 最新事实

主理人已在本会话明确确认：“我已手动建立正式契约 V1，确认按文件记载时间生效。本确认不批准任何批次。”

实际正式文件为`docs/AUDIT_CONTRACT.md`，版本V1，状态已生效，13289字节，文件SHA-256=`174a021b6a2111a8b0ced2bbd8c30cde230d44cb6995981eeec9d982f36940ad`。采用确切文件字节，不用候选SHA替代。正式契约作为人类提供的新只读输入，执行端不得修改。

生效登记见`docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md`。其中时间原文为`2026-10-1317:12:30+8:00`，未作机器格式规范化；当前契约生效事实已由人类明确确认。拟定Gate协议的时间校验不可据此放宽，也不能倒过来用尚未实施的协议否定本次文档生效。

原卡“尚未见正式文件”及旧纪要“待建立”是此前时点事实，不再作为当前缺口。P0的正式契约部分已完成，协议与案例仍按TASK-020提交验收。

## 2. 保护比较补充分列

原基线`data/reviews/task020_handoff_20261013_164109/source_hashes_before.json`继续使用，SHA=`dd12d188b4a49bb7faf378a93a2d3402d8a36f946e0f20a6b2831b1afb02d24c`，133294项，不重新制作或回写。

相对该基线，下列确切路径是本次人类新输入/架构端登记，不是TASK-020执行端新增产物；扫描时单列，不计为范围外新增，但必须实读并核对可获得的身份：

- `docs/AUDIT_CONTRACT.md`（人类正式文件，必须匹配上述完整SHA）。
- `docs/decisions/AUDIT_CONTRACT_V1_EFFECTIVE_RECORD_20261013.md`。
- `docs/tasks/TASK-020_CONTRACT_INPUT_NOTICE.md`（本通知）。
- `data/reviews/contract_v1_registered_20261013_171458/register_contract.py`。
- `data/reviews/contract_v1_registered_20261013_171458/inspection.json`。
- `data/reviews/contract_v1_registered_20261013_171458/registration.json`。

各登记文件SHA见registration.json；该JSON不内嵌自身哈希。未知新文件仍按原卡阻断，不能豁免整个reviews目录。原基线自排除的两个交接元数据仍按原卡分列。

正式文件及本次记录读取后再次核对原字节。执行端报告中明确区分人类新输入、架构端新增、TASK-020允许新增；禁止把正式文件创建归功于执行端，禁止回写旧快照或用生效确认冒充批次批准。

## 3. 不变的停止点

TASK-020仅形成Gate记录协议、案例和回执，不写实现、不运行核心、不生成真实Gate/初判或0009，不开放AI/终判。文档验收通过后，GPT再按已授权范围制定P1有界任务；无需重新申请D2/D3。
