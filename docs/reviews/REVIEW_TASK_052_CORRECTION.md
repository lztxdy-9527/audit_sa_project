# TASK-052 缺陷更正记录（人类使用反馈）

日期：2026-10-18。记录人：DSH Architect/Reviewer。触发：人类在浏览器中打开合并站点后反馈"下拉筛选没有反应、点击导出审阅记录没有反应"，并附截图。

## 1. 缺陷（已复现）

对 `data/runtime_initial_judgment_recording_tests/task052_merge_01/task049_site/all-ledger.html` 的页面脚本做语法检查：

```
node --check  ->  SyntaxError: Invalid or unexpected token
  download('审阅记录.csv', lines.join('
                                    ^
```

**原因**：生成器把 JS 里的 `lines.join('\n')` 写成了**字符串中的真实换行**，整段内嵌脚本因此语法错误；脚本未执行，`change`/`click` 事件未绑定——所以：

- 下拉"状态 / 审阅状态"选择后没有反应；
- 点击"导出审阅记录"没有反应；
- 关键词输入同样无效。

这不是操作问题，是交付缺陷。同类脚本出现在 `index.html`、`case-*.html`、`all-*.html`（`compare-*.html` 干脆没有脚本）；TASK-051 站点脚本虽能通过语法检查，但存在两个独立问题：

1. 关键词筛选：`body.filter-keyword` 从未被设置，输入关键词不会隐藏任何行；
2. 状态下拉的"待审阅"映射到 `body.filter-review tr.row:not(.review)`，而表格行没有 `.review` 类（`.review` 是审阅表单块的类），选"待审阅"会隐藏全部行。

## 2. 我的验收缺口

TASK-052 验收做了静态检查（控件存在、无外网/`eval`、链接、转义、合并负例、确定性），**没有执行页面脚本**（无浏览器自动化），因此漏掉了这个语法错误。责任在架构端验收方法，不在执行端"造假"——交付内容与回执一致，只是静态检查不足以证明交互可用。后续卡必须加入 `node --check` 与最小 DOM 冒烟。

## 3. 处置

- TASK-052 的**机器证据、合并逻辑、审阅记录 Excel、版本绑定**仍然有效（这些已独立验证）；**站点交互（筛选/导出）判定为缺陷**，由 TASK-053 修复。
- 本记录不修改已接受的基线快照与 review_result；作为缺陷更正单独归档，并在 TASK-053 验收通过后视为关闭。
- 修复前可用替代路径：Excel《审阅记录.xlsx》与《证据链底稿.xlsx》的**自动筛选**可用；合并命令可用（需手工准备审阅记录 JSON）。

## 4. 待修复清单（TASK-053）

1. 内嵌脚本语法正确（`lines.join('\n')` 转义），全站 `node --check` 通过；
2. 关键词筛选真实生效；
3. 状态下拉"待审阅"改为按 `rv-pending` 过滤（或从状态下拉移除，避免与审阅状态下拉重复）；
4. `compare-*.html` 若有筛选栏则必须有脚本，否则移除筛选栏；
5. 每个带审阅表单的页面都有可用的导出按钮；
6. 测试加入 `node --check` 与 Node 伪 DOM 冒烟（筛选、关键词、导出 JSON 的 source_version 与记录字段）。
