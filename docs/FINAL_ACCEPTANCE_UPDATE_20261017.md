# 当前演示版本回归补充入口（2026-10-17）

本文件接续 `docs/FINAL_ACCEPTANCE_ENTRY.md` 所索引的DSH TASK-042历史交付。本轮人类要求实跑当前小版本，并明确授权发现bug时用子Agent修复；原入口和全部旧接受身份保持历史原件。

本轮结果：**修复后完整演示、只读消费及输出保护冒烟通过**。不是AI/终判实施或全部历史能力的重新认证。

当前权威入口：

- `docs/reviews/REVIEW_DEMO_SMOKE_20261017.md`：实际运行、复现、修复、独立复验与限制。
- `data/reviews/project_smoke_gpt_20261017_183235/review_result.json`：本轮保护通过后发布的正式范围/基线/身份。
- 同根 `smoke_result.json`：完整演示exit0、125.478秒，十维复算、R01—R04=0/1/0/0及400000分、负例与恢复等实际结果。
- 同根 `source_hashes_after.json` / `protection_result.json` / `finalization.json`：一次全树扫描及有限自身元数据；以review_result中的实读数量/SHA为准。
- `docs/JOB_DEMO_PLAYBOOK_20261017.md`：业务逻辑、项目价值、HR演示位置/命令、常见追问和诚实简历表述。

本轮唯一既有修改：`scripts/run_runtime_demo.py`，27332 B / SHA `abc25c4b0e779f94959623428671669a10025f56b64dda8b67d3fd95f85639af`。解决inspect-out可覆盖context且提前声称zero_write的问题；原件、坏字节和精确恢复证据保留。新增定点测试 `tests/test_runtime_demo_output_safety.py`（10616 B / `643cad92cfed546c8333e7dcc89c514534a94e85b48e7f881b46403e488833b5`），最终22/22。

适配器仍404971 B / `f5c7c3967abc8257f1eff5c55487f6ff88c68d0879161e715dc43c95e0fad4b7`，19 API/17代码/40 Gate1材料不变。修复前TASK-042脚本SHA是历史身份，后续演示请核本轮新身份，不改旧回执或凭证来适配。

可以直接打开给HR看的材料：

1. `data/runtime_initial_judgment_recording_tests/task042_gpt_smoke_183235_02/demo_readme.md`。
2. `data/runtime/task042_gpt_smoke_183235_02/normal.facts/fact_packet.md`。
3. `data/human_initial_judgment_records/task042_gpt_smoke_183235_02/bound/rec_0001/judgment_result.json`，仅解释保存与绑定，不把夹具原文当真实审计结论。

演示为本地Windows CLI+Markdown/JSON，没有部署网址。完整新运行约两分钟，建议面试前先跑好；单条只读回看本轮约半秒。每次新演示使用从未存在的根，不清理旧产物。

139历史损失和既有偏差继续单列；真实批准null、真实初判未保存、0008、next/AI=false。AI建议/人类终判/真实数据/强认证仍未实施。本次没有发布下一任务卡或擅自扩展目标。
