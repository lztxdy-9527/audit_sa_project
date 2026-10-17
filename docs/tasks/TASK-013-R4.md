# TASK-013-R4：只修 F01 的共同触发点

## 当前状态与唯一目标

项目：`D:\harness work\audit_sa_project`。GPT 验收端已确认宿主正常、R3 的 F02/F03 证据改进可保留。只剩 F01 的三个探针没有命中原任务指定的共同边界。

先读本卡及 `docs/reviews/REVIEW_TASK_013_R3.md`。无需重新读取整段对话，不推进 TASK-014。

唯一可改既有文件：`tests/test_screen_demo_workflow.py`，起点 SHA-256 `fb018aa9dbea598563ccc91edb1d75bbd6b4a9525c8556daa2513560f2eb1998`。新增本轮回执 `docs/EXEC_REPORT_013_R4.md` 与全新验证容器/批次/SQLite 目录。

冻结：宿主 `ae5b7e24dd946a0a2186b8741b79af4173e091c362c4c210d8186e92d2cab4e2`；指南 `c7963c5857580ae9f3d75e0b6c9e9d448f988b5c561745df63f60b1a92060cf5`；上游、旧测试、历史产物均不改。主保护基线：`data/reviews/task013_r3_20261012_112209/source_hashes_after.json`，只允许当前测试 1 项变化、缺失 0。

## 不再设计观察器，直接复用已验证的边界

参考 GPT 已实际运行通过的脚本：

`data/reviews/task013_r3_20261012_112209/focused_review.py`

重点看其中三个探针循环的 `reader`、`control` 和 try/finally 部分。也可查前一轮 `data/reviews/task013_r2_20261012_080320/independent_review.py` 的同一方法。参考源码即可，不从历史 QA 模块导入执行代码。

**三个目标统一用第二次 `_read_screen_outputs` 完整返回后的边界，不能分别按目标文件的读取次数选位置。**

实现顺序固定：

1. 保存 `real_reader = host._read_screen_outputs` 和真实 `check_dev_action`。
2. reader wrapper 先调用 `result = real_reader(batch_dir, stage)`；只有该真实调用成功返回后，才增加本次调用的返回计数并记事件。
3. 计数等于 2 且尚未注入时，改本项唯一目标文件一次，然后**原样返回 result**。不重新调用 reader、不改 result、不改其他文件。
4. 同时包装真实 `check_dev_action`，先执行真实函数，再保存完整实参/返回及实际事件序号。与 reader/注入事件使用同一递增序号，真实统计注入后调用数。
5. `try: host.inspect_dev_batch(...)`，`finally` 撤销两个 wrapper。不要拦 `io.open`，不要在宿主读取句柄前预读/seek，不按调用栈推断消费点。原底层观察器如仍供其他诊断使用，可以保留；不做大规模清理或重构。

造样只有三种：

- 报告：把合法 JSON 的 findings 改为空列表，其他文件不改。
- load_report：原始字节末尾追加一个换行，其他文件不改。
- 0001：原始字节末尾追加一个换行，**不得同步 0002 或任何后继引用**。0001 是否再次被消费与触发点无关；检测点必须指向 `workflow/checkpoints/0001.json`，不能接受提前出现的 `0003.previous_file_sha256` 代替。

用 C06b 小样。本次公开调用必须达到两个 reader 返回、命中 1 次、注入后 reader/控制器调用均为 0，返回对象保持原始值。本次 WorkflowHostBlocked 的原因分别指向三个目标路径；撤销 wrapper、保留文件变更后新进程 CLI=1；只恢复该目标原始字节后 CLI=0。

## 沿用现有记录，最小同步

保留已通过的 after 取值顺序、完整异常和文件引用。after 在调用结束/撤销 wrapper 后、恢复文件前取得；目录差异只应包含本项目标文件。实际 args/kwargs、原始返回、事件顺序、命中数、当前/后续/恢复对照完整保存；不把预设空列表当作控制器测量结果。

只调整 F01 的时点判定及自测：仅有第一次 reader 返回、缺注入、注入后仍有 reader 返回或控制器调用，均为不合格；真实第二次返回后注入且后续两类调用为 0 才合格。不要用“单个目标文件只读一次”放宽此条件。自测单列。

F01 三项命中次数单列、可由记录导出；全局故障计数如保留，明确其范围，不能把旧轮数字写成本轮全部故障数。新增组的 CLI 推导次数按该组实际成功命令统计，或明确注明为全局范围。

## 本轮只提交定向验证

使用项目 Python 3.11，`-B` 编译源文本，再用**现有 `--only-g10`** 在新容器做最终定向验证。本卡不要求再跑完整入口、不重跑 MAIN/G1—G9，不另增测试模式或生产接口。定向失败先单独验证对应 wrapper，不连续重建整套七阶段来诊断局部代码错误。

回执给测试最终完整 SHA-256、真实命令和退出码、三项探针/时点自测证据、保护比较、三条产物路径，标明“本轮只跑 G10，未重跑完整入口”；引用 R3 `task013r3_run_03` 已保存的完整回归，不冒充本轮重跑。回执自身最终哈希在文件写完后输出到交接消息，避免正文自引用。

完成后停在 DEV_GATE2_APPROVED + RULE_SCREEN_RECORDED，无 0006、真实批准 0。不得执行独立复算/事实底稿/AI、填写人类判断、提交正式契约或真实 Gate，不推进 TASK-014。若这段已验证方法仍失败，只报具体异常与现场，不扩大为新的读取框架。
