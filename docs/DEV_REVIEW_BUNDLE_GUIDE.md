# 开发态只读审阅包指南（TASK-018）

工具：`scripts/export_demo_review_bundle.py`（独立脚本，**不修改宿主、控制器与任何纯核心**）
测试入口：`tests/test_export_demo_review_bundle.py --out-dir data/review_bundle_tests/task018_<全新>`
状态：开发态只读导出与离线核验。**不推进工作流、不增加 `0009`、不生成判断或 AI 建议。**

---

## 1. 这是什么、不是什么

把已经核验到开发态 `0008` 的批次里**选定的审阅材料**整理成一个可离线阅读、可逐文件核对的包：

- 是：22 份来源文件的**确切字节**副本 + 冻结宿主公开 status 的完整返回 + 一份固定模板的 `README.md`
  + 一份逐项记录大小与 SHA-256 的 `manifest.json`；另有一个只读的离线核验入口。
- 不是：完整批次备份、可恢复宿主目录、身份认证或独立审计保证；不复制输入 Excel、normalized、
  数据库、代码快照或整个运行树；不重新筛查、不重新计算金额、不重写任何判断文本。
- 边界：**模拟初判已保存 ≠ 真实人类独立初判已保存**；真实 Gate 未批准；AI 未开放；
  离线核验只确认包内文件与清单一致，**不证明原始业务真实性，也不重新批准批次**。

## 2. 接口

```python
export_dev_review_bundle(batch_dir, out_dir) -> dict   # 成功返回打包摘要；失败抛异常
verify_dev_review_bundle(bundle_dir) -> dict           # 只读核验；成功状态 DEV_REVIEW_BUNDLE_VERIFIED
```

```powershell
$py = 'D:\harness work\audit_sa_project\.venv\Scripts\python.exe'
$tool = 'D:\harness work\audit_sa_project\scripts\export_demo_review_bundle.py'

& $py -B $tool export --batch-dir "$root\data\batches\<父>\<批次>" `
  --out-dir "$root\data\review_bundles\task018_<唯一>\<新子目录>"
& $py -B $tool verify --bundle-dir "$root\data\review_bundles\task018_<唯一>\<子目录>"
```

退出码：`0` 成功；`1` 协议／前提／路径不符（`DevReviewBundleBlocked`）；
`2` 运行或 I/O 失败（`DevReviewBundleError`，保留 cause 链）。失败**不返回成功字典**。
本工具不是宿主子命令：**不新增宿主第十子命令**，也不调用宿主的保存／标准化／装载／筛查／复算／
底稿／初判核心。

## 3. 导出前提

1. 源批次必须是宿主支持的路径（`data/batches/<父>/<批次>`），且**真实调用**冻结宿主的公开
   `inspect_dev_batch` 后满足：`status=READY`、恰为合法 `0001`—`0008`、
   `SIMULATED_INITIAL_JUDGMENT_RECORDED`、`FACT_PACKET_RECORDED`、完整 `MATCHED`
   （`matched=true`、`difference_count=0`、无未匹配维度）、`mode=DEVELOPMENT_TEST_ONLY`、
   `real_approvals=0`、`next_step_allowed` 与 AI 动作实际许可严格 `false`。
   不信任调用方传入的 status 字典，也不在新工具里重写宿主的绑定／失败诊断／链核验协议。
2. `out_dir` 解析后必须位于 `data/review_bundles/<本轮根>/` 之下、且**从未存在**
   （既有目录与空目录一并拒绝，不覆盖）；必须拒绝等于源批次或外置数据库、与它们互为祖先／后代、
   或越出导出根的路径。路径判断以解析后的绝对路径为准，不用字符串前缀。检查通过后才独占创建。
3. 宿主的协议／前提阻断按 `DevReviewBundleBlocked`（退出 1）传播，宿主的运行失败按
   `DevReviewBundleError`（退出 2）传播，两者都在异常链中保留原始宿主异常。

## 4. 固定白名单（22 份来源）

包内 `evidence/` 下按原相对层级保留：

| 组 | 文件 |
| --- | --- |
| 接收与 Gate1（3） | `batch_manifest.json`、`checks/quality_report.json`、`gate1_packet.md` |
| 宿主清单（1） | `workflow/host_manifest.json` |
| checkpoint（8） | `workflow/checkpoints/0001.json`—`0008.json` |
| 报告（2） | `workflow/screening/screening_report.json`、`workflow/crosscheck/crosscheck_report.json` |
| 事实底稿（4） | `workflow/fact_packet/{started.json,fact_packet.json,fact_packet.md,artifacts.json}` |
| 模拟初判（4） | `workflow/initial_judgment/{started.json,submission.json,initial_judgment.json,artifacts.json}` |

成功包恰为 `manifest.json`、`README.md`、`host_status.json` 与上述 22 份共 25 个文件、
清单 24 项 payload。**不扫描复制任意目录**；每份来源一次读取同一缓冲，从该缓冲取长度、SHA-256 与
需要的 JSON 对象，输出复制**确切字节**：JSON 不重排、Markdown 不换行转换、不加 BOM、不改 banner
与判断原文。文件字节哈希与 packet／record 的**对象规范指纹分列**，不相互冒充。

**初始预期只来自第一次真实合法 status**（其 `verified_files`、`host_manifest`、`checkpoints`、
`screening`／`crosscheck`／`fact_packet`／`initial_judgment` 摘要已给出这 22 份的文件哈希），
逐项明确映射、严格比较后才复制；所有哈希要求完整 64 位小写十六进制。

## 5. 收尾顺序与失败现场

1. 路径检查 + 第一次真实公开 status + 白名单读取与初始预期校验（**前提失败不创建输出**）。
2. 独占创建输出，用独占 writer 保存 24 份 payload，写后读回与**确切待写字节**比较。
3. 末次真实公开 status 必须仍成功并与第一次完整返回**严格规范相等**（不接受用最新读数替换初始预期）。
4. 在末次 status 与全部必要对象消费之后，**实读** 22 份源文件与外置数据库字节并与初始绑定预期比较，
   再复核输出 24 份 payload（禁止缓存自比）。
5. 最后独占保存 `manifest.json` 并读回严格等值；返回成功前再核对 payload／manifest 实际字节、
   源 22 份与数据库初始字节、包内固定文件集合、无 `failure.json`。

输出创建之后发生的任何失败，**只在新输出目录**留 `failure.json`
（版本 `TASK-018-dev-review-bundle-failure-1.0`：`stage=export`、目标退出码、异常类型／原因／完整链、
已完成步骤）；不修改源批次、不向宿主写失败诊断、不清理半写输出、不重试覆盖。诊断本身也写失败时，
如实保留原异常与诊断错误，**不改报成功**。前提阶段没有新输出时不写外部失败文件。

## 6. manifest

版本固定 `TASK-018-dev-review-bundle-1.0`，包含：`batch_id`、源批次身份、宿主版本与实测代码哈希
（含 `initial_judgment_core`）、导出工具实测哈希、`0008` 初始文件哈希、packet／record 规范指纹、
开发与模拟边界（真实批准 `null`、`real_approvals=0`、`human_initial_judgment=null`、
`ai_suggestion=null`、`final_judgment=null`、`next_step_allowed`／`ai_suggestion_allowed` 严格 false）、
以及 24 份 payload 的固定相对路径、确切字节数与文件 SHA-256（复制项另记原批次相对路径与初始绑定文件哈希）。
清单**不内嵌自身哈希**，也**不写入导出目标的绝对路径**，不含当前时间或随机 ID；相同源与代码重复
导出到不同新目录时，24 份 payload 与 manifest 的字节应确定性相同。

## 7. 离线核验（`verify`）

只读包内固定文件，**不读取原批次、数据库或运行宿主/核心**：严格检查 manifest 协议／类型／固定边界、
包内固定文件集合（缺件、未知文件、`failure.json` 均拒绝）、24 项逐项字节数与 SHA-256、
清单路径不得重复／越界／含绝对路径、指纹不接受后缀；并核对 status 与 `0008`／packet／record 的身份一致性
（`0008.workflow` 与 `0007` 严格规范相等、记录规范指纹与清单一致、真实批准仍为 `null`）。
成功返回 `DEV_REVIEW_BUNDLE_VERIFIED`，`scope=COPIED_BYTES_ONLY`。
包内 status 是导出时的**历史快照**，不能当作当前宿主状态或真实批准。

## 8. 收尾与来源身份闭合（TASK-018-R1）

- **导出收尾**：manifest 保存并读回、末次公开 status、22 份来源与外置数据库复测等**全部必要消费**
  之后，返回成功前再次**实读** 24 份 payload 与 manifest 的确切字节，与本次待写缓冲比较（manifest
  的预期即其 writer 返回的读回哈希，清单不内嵌自身哈希）；同时确认固定文件集合与无失败诊断。
- **离线核验**：所有必要 JSON 对象都与**通过清单哈希检查的同一字节缓冲**绑定（一次读取、同缓冲解析），
  返回成功前在全部必要身份/对象消费之后再做一次有限最终确认：25 个固定文件的磁盘字节与初次缓冲预期
  比较、固定文件集合、无失败诊断。不拿后来两次读数自比，也不等下一次核验才拒绝。
- **来源/身份闭合**（只读包内字节与同缓冲对象，不读取原批次/DB、不调用冻结核心复算）：
  22 份复制件的实际 SHA 与清单文件哈希、初始绑定哈希、历史 status 固定映射必须一致；manifest 的文件
  字节哈希/规范指纹/数据库哈希与实际产物、历史 status 及 0008.operation 声明一致；批次身份在 manifest、
  host_status、host_manifest、batch_manifest、0008、record.source、record.simulated_initial_judgment、
  submission 间同属一批次；0008 前驱哈希等于包内 0007 实际文件哈希、0008.workflow 与 0007 严格规范相等；
  宿主版本/代码哈希/绑定摘要与包内已有声明一致；开发/模拟/契约未建立/真实批准 null/next 与 AI 严格 false
  在 manifest、status、0008、record 间一致。已声明为严格整数的 revision/计数使用严格类型（布尔与浮点不
  被接受）。非法结构为可定位的协议阻断（退出 1，指出矛盾字段）；运行/I-O 仍为运行失败（退出 2，保留
  cause）。这些核对只说明**包内自洽**，不构成身份认证、来源业务真实性或真实批准。

## 9. 有界测试

入口 `tests/test_export_demo_review_bundle.py --out-dir data/review_bundle_tests/task018_<全新>`，
七组：正常导出与确定性、前提与路径、末次 status 之后的晚变更、写入失败（半写与 manifest 完整后 sentinel）、
离线核验反例、只读与停止点、证据与保护收尾。可加 `--only export|preconditions|late|writefaults|verifyneg|readonly|evidence|smoke` 定点执行；
未执行证据收尾时把相关计数记 `null`，不填默认零。

### TASK-018-R1 定点模式（`--only r1`）

只读复用既有合法批次（**不新建 batches/SQLite、不重建上游链**），依次执行：一个正常包（六真实下游守卫下
真实导出一次、正常核验与新进程 CLI）、导出收尾两个有限目标（README 与 manifest 的晚变更）、离线最后缓冲
消费反例、四个来源/身份反例、登记与观察收尾（测试直接宿主调用逐次登记；工具内部嵌套 status 与直接调用
分列；另做一次已登记的真实宿主缺失批次调用）、证据/保护/停止点收尾。
