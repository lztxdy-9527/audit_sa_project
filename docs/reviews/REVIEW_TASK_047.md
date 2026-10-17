# TASK-047 独立验收（DSH Architect）

结论：**ACCEPTED**。2026-10-17，DSH 架构/测试验收端对"离线静态 HTML 演示报告"独立复验。生成器只读渲染、确定性、转义、无外链、边界横幅与四相符内容均成立；架构端自跑复现。本报告只是既有合成证据的可读视图，不是审计结论、不是验收证据的替代。

## 1. 交付身份（实读同缓冲）

| 交付 | 长度 | SHA-256 |
| --- | --- | --- |
| `scripts/build_demo_report_html.py` | 25546 B | `d0cc74081a1cdf3bda93f7dfe9b977b753a16951144985121f377e5d9874d734` |
| `tests/test_demo_report_html.py` | 11939 B | `37f0f7fe4bae37f39bd73ab22b85de2718319049e5869a0975697e8cb39da9c0` |
| `docs/DEMO_REPORT_HTML_GUIDE.md` | 5337 B | `4d30999fac57464bcf8496a2e8bebef7e23277e7e227494ae781409db773d787` |
| `docs/EXEC_REPORT_047.md` | 6322 B | `3aeceaeb61d202bf98228330148c7c3c988cdb3b9c17ec427f0e6d0556db5e6a` |

起点 TASK-046 接受身份与卡 `4656db94…`、决策 `5415c006…` 一致；本卡纯新增，既有文件 changed=0。

## 2. 架构端独立运行（不复用执行端结论）

- **正常生成**（新根 `task047_dsh_01_b`）：exit 0；`index.html` 与 `report_source.json` 存在；`report_source` 登记 **7 个输入文件**（demo_summary、input_registry、voucher_report、reconcile_report、fact_packet、judgment、record_manifest）逐长度/SHA。
- **内容标记**（渲染文本实读）：`ALL_MATCHED`、**账证 8 / 8 项 MATCHED**、差异 0、账有证无 0；**账实 3 / 3 匹配**（`REFERENCE_INDEX`）、OUT 1000000 vs 已结算付款 1000000（差 0）、IN 100000 vs 退款 100000（差 0）；R02 一条（400000 分 = 4000.00 元）；初判 `RT_HUMAN_INITIAL_JUDGMENT_VERIFIED`；边界 false；"核对结论由人填写"提示存在。
- **静态安全**：无 `<script>`、无 `http://`/`https://`、无外链标签；含 A4 打印样式；动态文本 HTML 转义（测试含 `<b>x</b>` 注入用例）。
- **确定性**：同一 `--run-root` 两次生成，`index.html` 与 `report_source.json` **字节相同**。
- **负例内容**：从 `task046_demo_v1_neg` 生成（新根 `task047_dsh_v1neg_b`）：exit 0（渲染成功），HTML 显示 **账证 6 / 8**、差异 2、账有证无 2，`MISSING_VOUCHER` 在明细表高亮。
- **测试复跑**（新根 `task047_dsh_test_01_b`）：exit 0、8/8 PASS。
- **只读**：我的生成/测试前后，`task046_demo_01`、`task046_demo_v1_neg` 运行根、对应业务根（事实包/初判/清单）与 `data/evidence_inputs/` 全部字节不变。

## 3. 保护与历史

执行端一次全树扫描：基线 176350 项 / `3c520328…`，`changed=0`、missing 0、读取错误 0、新增 197 项全登记；架构端独立扫描复核（`data/reviews/task047_dsh_20261017_01/protection_result.json`）。139 历史损失、27 恢复、326 越界、19 命名、TASK-030 41 B 锁继续冻结，不追认。

## 4. 边界

未把 HTML 接入演示主流程（另行评估）；未做账表/账账、影像/OCR、外部查验、函证/盘点、AI、终判、真实数据/强认证。本报告只读展示既有合成证据；不证明凭证/流水真实；不构成审计结论；核对结论由人填写。

## 5. 接受与使用

发布新接受基线 `data/reviews/task047_dsh_20261017_01/source_hashes_after.json` 与 `review_result.json`。使用方式：先跑一次演示（如 `task046_demo_01`），再执行

```powershell
.venv\Scripts\python.exe -B scripts\build_demo_report_html.py --run-root data\runtime_initial_judgment_recording_tests\task046_demo_01 --out-dir data\runtime_initial_judgment_recording_tests\task047_report_02
```

双击 `index.html` 用浏览器打开或打印 PDF。真实批准 `null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`。
