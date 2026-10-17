# 决策记录：采用方案 A（离线静态 HTML 演示报告）

记录编号：`DSH-SCOPE-20261017-03`。日期：2026-10-17（Asia/Singapore）。记录人：DSH Architect/Reviewer。依据：人类在本会话中的直接选择（原文见 §1）。

## 1. 人类授权原文

> 那我们采用方案A

方案 A 指：**离线静态 HTML 演示报告**——由脚本读取一次已完成的演示运行证据，渲染为单个 HTML 文件；只读渲染，不开服务器、不装依赖、不做写操作。

## 2. 决定

**D-UI-1 只做只读静态报告。** 不建立 Web 应用、不启服务、不做上传/登录/审批界面；HTML 由脚本从既有证据生成，双击浏览器打开，可直接打印为 PDF。

**D-UI-2 证据同源。** HTML 的所有数字与文本必须来自本次运行证据文件（`demo_summary.json`、`input_registry.json`、`voucher_match_report.json`、`bank_reconcile_report.json`、`fact_packet.json`、`judgment_result.json`/`manifest.json`），不得手工抄写或另存"美化版"数字；生成时记录输入文件身份（路径/长度/SHA）到 `report_source.json`。

**D-UI-3 无新依赖、无网络、无时钟。** 仅 Python 标准库；HTML 内联 CSS，无外部链接/CDN/字体/脚本；输出确定性（同一输入两次生成字节相同），不写时间戳/随机数。

**D-UI-4 只读与边界。** 生成器不写运行根、业务根、输入根或既有证据；输出只写本轮新证据根。HTML 顶部固定边界横幅：合成数据、非批次批准、非身份认证、`real_approval=null`、不开放 AI/终判；"核对结论"列保持空并注明由人填写。

**D-UI-5 不改变任何业务口径。** 不新增 API、不改适配器/核对器/测试/指南；HTML 不是验收证据的替代，只是同一证据的可读视图。

## 3. 边界

`real_approval=null`、真实初判未保存、0008、`next_step_allowed=false`、`ai_enabled=false`；全部合成数据；静态报告不证明凭证/流水真实，不构成审计结论。看板不变，`done` 由人类办理。
