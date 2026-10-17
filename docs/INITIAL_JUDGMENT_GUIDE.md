# 开发态模拟初判记录纯核心指南（TASK-016）

版本：`TASK-016-initial-judgment-1.0`（纯核心，未接宿主）
文件：`scripts/build_demo_initial_judgment.py`
测试入口：`tests/test_build_demo_initial_judgment.py --out-dir <全新证据容器>`
状态：开发态纯内存核心。**不保存真实人类判断、不认证身份、不解锁 AI。**

---

## 1. 这是什么、不是什么

它把**调用方明确提供的模拟初判文本**与**一份已保存的事实包**做校验和绑定，返回一个内存记录。

- 是：确定性的输入校验、事实包/批次/来源指纹绑定、模拟身份的显式记录、边界说明。
- 不是：不推导、不生成、不预填任何判断；不计算候选等级、重要性或审计结论；不读取聊天倾向；
  不读取或写入文件、数据库、Excel；不调用上游、控制器、宿主、答案册、LLM、网络或子进程；
  不自动生成事件 ID、身份、时间或判断。
- 返回状态只有 `DEV_INITIAL_JUDGMENT_VALIDATED`（本次输入成立），**不是** `SAVED`、
  `HUMAN_APPROVED` 或 `AI_READY`；它不改变事实包中“尚未保存人类判断”的冻结说明。

导入本模块不触发任何文件、网络、子进程、时间或随机操作（测试用守卫核对命中 0）。

## 2. 唯一业务入口

```python
build_initial_judgment_record(batch_id, fact_packet, submission, *,
                             expected_packet_sha256) -> {"record": {...}, "record_sha256": "..."}
```

- `batch_id`：调用方给出的非空字符串；保留原值，不转数字、不自动 strip 后存储。
- `fact_packet`：已保存事实包的对象（调用方自行读取；本核心不读文件）。
- `submission`：见第 4 节。
- `expected_packet_sha256`：64 位小写十六进制；必须等于 `fact_packet` 的规范指纹。
- 返回：外层严格为 `record` 与 `record_sha256` 两个键；`record` 不内嵌自身指纹。
- 异常：`InitialJudgmentBlocked`（输入/协议/绑定不符，指出字段与原因）与
  `InitialJudgmentError`（意外内部错误，保留 cause 链）。异常不会包装成成功记录。
- 无 CLI、退出码或文件保存接口。

## 3. 指纹口径

规范 JSON 统一为：UTF-8、`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`、
`allow_nan=False`；**规范指纹 = 该字节串的 SHA-256**。

- 事实包的文件字节指纹（磁盘 JSON 文件 SHA-256）与**对象规范指纹**是两个不同口径，不可互换；
  绑定与 `expected_packet_sha256` 用的是**对象规范指纹**。
- **指针格式必须完整匹配**：任何指纹（四项来源、`expected_packet_sha256`、
  `submission.fact_packet_sha256`）都必须**恰为 64 位小写十六进制字符**，整个字符串完整匹配。
  带尾随换行（LF/CRLF）、前后空格或大写字母都不是合法指纹，会以
  `InitialJudgmentBlocked` 拒绝并指出对应字段；核心**不做** `strip`、截断、转小写或忽略后缀等
  静默修正（例如 `…<64位>+"\n"` 是 65 字符，必须拒绝）。
- `record_sha256` 是对整个 `record` 计算的对象规范指纹；记录本身不再内嵌它。
- 相同输入必须返回规范 JSON 等值且指纹相同（确定性）。

## 4. 模拟提交协议（`submission`）

`submission` 必须是 dict。**必填键**（缺少即拒绝）：

| 键 | 要求 |
| --- | --- |
| `submission_version` | 必须等于 `TASK-016-initial-judgment-submission-1.0` |
| `event_id` | 调用方给出的非空字符串；本核心不生成、不跨调用持久去重 |
| `batch_id` | 必须严格等于本次 API 的 `batch_id` |
| `fact_packet_sha256` | 必须严格等于本次已验证的事实包规范指纹 |
| `scope` | 必须等于 `BATCH_FACT_PACKET`（整份事实包粒度） |
| `actor_kind` | 必须等于 `SIMULATED_HUMAN`（不接受真实 `HUMAN`/`AI` 身份） |
| `actor_id` | 非空字符串（本核心不认证其真实归属） |
| `simulation` | 必须等于 `SIMULATED_TEST_ONLY` |
| `occurred_at` | 调用方给出的含时区 ISO8601 日期时间（如 `2026-10-13T09:30:00+08:00`）；本核心不读系统时钟、不补造时间 |
| `assessment` | 调用方给出的非空字符串（去空白后非空） |
| `reason` | 调用方给出的非空字符串（去空白后非空） |

**可选键**（仅这两个；未知键一律拒绝，不静默忽略 `ai_suggestion`、`final_judgment` 等越界字段）：

- `needed_evidence`：非空字符串列表，可为空；本核心不自动添加条目。
- `finding_notes`：列表，每项只允许 `finding_id` 与 `note`（均非空）；`finding_id` 必须存在于当前
  事实包且不得重复。允许只写部分线索备注或空列表；**未写备注不等于已判断**。

规范化：两个可选键省略时按对应空列表存入记录；`assessment`、`reason`、`actor_id`、`occurred_at`
等文字按**原字符串完整保留**（含空格、换行、ID、中文、类指令字符串），不改写、不解释、不执行。
`bool` 不能冒充字符串或 ID。

### 有效的“暂不能判断”

允许且必须由调用方给出非空 `reason`，例如：

```
assessment = "【模拟测试】暂不能判断，需要补充证据"
reason     = "【模拟测试】现有线索不足以形成确定结论，需补充银行流水原件后再判断。"
```

**零条线索也不得自动填“无问题”**：PACKET 没有命中时，`assessment`/`reason` 仍必须由调用方提供，
核心不会自动产生“通过”“无异常”一类结论。

## 5. 事实包核验范围（只核验实际消费字段）

- `packet_version=TASK-008-fact-packet-1.1`、`batch_status=DEV_FACT_PACKET_READY`、
  `mode=DEVELOPMENT_TEST_ONLY`、`next_step_allowed` 严格 `false`。
- `entity`：`company=澄明商贸有限公司`、`period=2026-09-01`—`2026-09-30`、
  `cutoff_date=2026-09-30`、`currency=人民币（CNY）`（按冻结 packet 的实际展示字段核验）。
- `bindings`：`workbook_sha256`、`normalized_payload_sha256`、`screening_report_sha256`、
  `crosscheck_report_sha256` 均为 64 位小写十六进制。
- `findings`：必须是 list；每项 `finding_id` 非空字符串且唯一，`rule_id` 属于 `R01`—`R04`。

仅为引用与记录范围核验：**不重算金额、不复制冻结事实核心的全部校验逻辑**。

## 6. 返回记录结构

| 键 | 值 |
| --- | --- |
| `record_version` | `TASK-016-initial-judgment-record-1.0` |
| `batch_status` | `DEV_INITIAL_JUDGMENT_VALIDATED` |
| `mode` | `DEVELOPMENT_TEST_ONLY` |
| `contract_status` | `DRAFT_NOT_IN_FORCE` |
| `next_step_allowed` | `false` |
| `ai_suggestion_allowed` | `false` |
| `gate1_approval` / `gate2_approval` | `null` |
| `human_initial_judgment` | `null`（本核心不保存真实人类判断） |
| `ai_suggestion` / `final_judgment` | `null` |
| `source` | `batch_id`、`fact_packet_sha256`、`packet_version`、`entity`（深拷贝）、四项来源指纹、`finding_ids`（事实包原序） |
| `simulated_initial_judgment` | 已核验 `submission` 的深拷贝与两可选键确定性规范化 |
| `boundaries` | 固定边界说明（开发模拟、内存校验尚未持久化、身份未认证、人类判断先于 AI、真实判断与批准由人类作出） |

`source` 不含“文件已验证”“数据库已实读”之类声明：事实包本身**不含可独立认证的 `batch_id`**，
本 API 的 `batch_id` 是调用方绑定声明。

## 7. 边界与后续责任

- 本核心**不保存**：没有持久化、没有独占写入、没有 0008、不建立正式契约或真实 Gate。
- 本核心**不认证**：`actor_id`/`occurred_at`/`event_id` 都是调用方声明；不校验身份归属，
  也不声称能从文本识别“是否独立思考”或“是否使用了 AI”。
- 本核心**不解锁 AI**：`ai_suggestion_allowed=false`；人类独立初判必须先于任何 AI 对照建议。
- 调用方同时重新声明全部指纹，不是本纯内核能够阻止的同权限篡改；不宣称防伪。
- 以下由**后续宿主卡**承担（本卡不做）：事实包/凭证恢复、真实 `0007` 文件与数据库实读、
  身份来源与事件去重、独占保存模拟初判、以及是否正式建立契约、开放真实 Gate。

## 8. 最小调用示例

```python
import json
from pathlib import Path

from scripts.build_demo_initial_judgment import (
    build_initial_judgment_record, canonical_json_sha256,
)

packet = json.loads(Path("data/batches/<batch>/workflow/fact_packet/fact_packet.json")
                    .read_text(encoding="utf-8"))
fingerprint = canonical_json_sha256(packet)          # 对象规范指纹（不是文件字节指纹）
submission = {
    "submission_version": "TASK-016-initial-judgment-submission-1.0",
    "event_id": "EV-SIM-0001",
    "batch_id": "<batch>",
    "fact_packet_sha256": fingerprint,
    "scope": "BATCH_FACT_PACKET",
    "actor_kind": "SIMULATED_HUMAN",
    "actor_id": "sim-analyst-01",
    "simulation": "SIMULATED_TEST_ONLY",
    "occurred_at": "2026-10-13T09:30:00+08:00",
    "assessment": "【模拟测试】暂不能判断，需要补充证据",
    "reason": "【模拟测试】现有线索不足以形成确定结论。",
}
result = build_initial_judgment_record("<batch>", packet, submission,
                                       expected_packet_sha256=fingerprint)
print(result["record"]["batch_status"], result["record_sha256"])
```

## 9. 有界测试与证据

入口 `tests/test_build_demo_initial_judgment.py --out-dir <全新证据容器>`（容器必须在
`data/initial_judgment_tests/` 之下且为新/空目录，否则退出 2；`--only` 默认 `all`）：

- `--only all`：七组完整检查——正常与“暂不能判断”对照、三份已保存事实包（MAIN 12 条 / C06b 1 条 /
  C03 零条）、绑定反例、协议反例、确定性与无别名、纯内存守卫（文件/网络/子进程入口命中 0）、
  证据登记与保护比较。
- `--only r1`：TASK-016-R1 定点模式——合法对照（C06b/MAIN/C03）、四项来源各追加一个 LF 的严格
  指纹反例、CRLF/尾随空格/大写/`expected` 与 `submission` 尾随 LF 边界、守卫调用 1 次并登记、
  调用与登记一致性、证据与保护收尾。

每次 API 直接调用登记完整返回或完整异常+原因链；守卫内那一次真实调用也会进入统一登记
（在解除守卫后落盘，不为补记录再次调用核心）。`missing`/`unregistered`/调用与登记一致性/保护比较
均为**已执行**结果并进入正式 failures；未执行的动作写 `null`，不填未测得的 0。
