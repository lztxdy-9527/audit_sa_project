# TASK-022-R3 评审：完整观察绑定有效，仅剩规范类型相等判定

日期：2026-10-14。结论：**NOT_ACCEPTED**。暂不关闭TASK-022系列，不推进Gate1；只转 `docs/tasks/TASK-022-R4.md` 的**B类测试判定修正**。生产存储、P1、契约、宿主继续冻结，GPT未修改实现。

## 1. 身份与非阻断交接差异

实际测试SHA `43884b406b1f70293d31d9dadac0b925021e7bc37b36e015b06d4e32fe26d817`（105015字节）、指南SHA `3d3805f42444f3e6f06b3a77e55744dcf9c3849252e105c9f67078067ae2582f`（20165字节）与交接一致。冻结存储模块仍为 `594e42d0cf8bb89a48416a29ca461c2b32a10d51643ecfbe77d750355b5048e7`（41353字节）。

回执实际实读为 **11766字节、SHA `5aa6fc69d951fa68f274a37271eefe1c9dca4f44c52f3a76a33aaca48f2e02ca`**，不同于交接的11664字节/`32b004fb…68df8`。保存实际副本与两种身份，不替执行端改旧回执；测试/指南及运行证据不受该文档身份差异影响，单列为非阻断记录。

## 2. GPT实际复验通过部分

评审根 `data/reviews/task022_r3_gpt_20261014_000920/`。所有脚本本轮新增，只操作本轮新容器；未执行旧容器脚本，历史文件不动。

GPT实际运行当前公开CLI到新正常根 `task022r3_gpt_normal_20261014_000920`：**进程0、134项检查、0失败、API51、真实嵌套P1/入口观察26、直接0、守卫0**。

在三个分离新根，包装真实 `_audited_read` 并保持真实返回：

- `empty`：第一次终审读取前将一条真实返回改为{}，ID/计数保留 → **套件1、FAIL**，内容比较拒绝。
- `reason`：同位置改返回reason并正确重算record_fingerprint，候选形状/内部指纹自洽 → **套件1、FAIL**，内容比较拒绝。
- `checks`：终审真实缓冲返回后对checks.json追加LF → **套件1、FAIL**，字节漂移拒绝。

各故障命中1、各实际P1=26，完整现场保留。来源 `run_verification.py`、`verification_summary.json`、各result/stdout及对应完整套件根。本轮前四次运行共104次P1，正常与故障分列，不把预期失败算作正常回归。

另外有限实读执行端与GPT两个正常容器：各13项最终台账字节/SHA一致，content_compare/core/api均ok，API51/核心26与入口观察闭合。真实观察深拷贝、固定时点、输入现场和三时点均保留；R3修复对空返回/正常字符串内容替换确实有效，不重开。

## 3. 唯一阻断：Python宽松相等被当作规范JSON相等

`_field_diff`的叶节点使用 `expected != candidate`，`_content_compare`用“没有field_diff”决定equal/ok。Python中False==0、0==0.0成立，但既定canonical JSON中的false/0/0.0不同。因此规范SHA已不同，仍可能标equal=true。

隔离真实helper实测两例：

- 将一条返回中的 `result.record.boundaries.persisted` 从False改为整数0。
- 将 `quality_summary.structural_blockers_count` 的整数0改为浮点0.0。

两例保留所有记录/ID/计数/其他字段，独立规范字节均不同，真实_content_compare却均ok=true。证据 `evidence_audit.json`；这不是新业务枚举或新增安全要求，而是R3已经承诺的完整规范对象比较。

随后GPT在新 `task022r3_gpt_type_20261014_000920` 运行一次真实套件。仅在第一次终审读取前，把core-001上述persisted改为0，不改实际观察预期/ID/计数。真实reader继续返回本次对象和SHA，结果：

- **套件0、summary PASS、134项0失败、failures=[]**。
- core内容比较 **equal=true**。
- 候选规范SHA `a8ff88335beae25cc510b5a140c7ce7c2da5f6d8c6d67cd321bbaf170e2d7456`，预期规范SHA `68f0990c3ff9d76cc950a53c5d5cc511397eb082de5d1c089501e4eb9bc26fcd`，明确不相等。

该故障额外实际P1=26，与前四次运行分列；证据 `canonical_type_fault.py` / `canonical_type_fault_result.json` / stdout及新现场。脚本退出0表示取证完成，套件返回0是错误行为。

此处影响最终PASS有效性，仍属B类；不能因为仅几行测试条件就由GPT越过现有执行所有权接管实现。修正可直接以完整canonical字节严格相等作为主判据，field_diff只负责诊断并正确报告类型差异，不需要再改预期来源或存储算法。

## 4. 范围与后续

R4仅修改本任务测试，指南不强制修改，新增回执及新测试根；生产模块和所有上游冻结。最小定点为False/0、整数/浮点拒绝，字典键顺序不同但canonical相同仍可接受；一个真实类型替换故障必须1/FAIL，再一次正常入口。不重跑刚通过的三次完整故障或历史链。

## 5. 保护与交接

GPT本轮一次最终全树保护扫描，基线为 `task022_r2_gpt_20261013_234348/source_hashes_after.json`（136714项，SHA `5d2223763562e9e0a0d27e2e6ddd3984c1d84eac5d613e24407132505cbbdbc6`）。实扫 **138879 文件**：**changed恰为测试/指南两项；范围外变化=[]、missing=[]、读取错误=[]、范围外新增=[]**。生产存储和其他上游未变。执行端新回执/显式容器、前轮两个自指元数据、本轮评审及五个新运行根按确切路径分列。junction保留；扫描后仅有限刷新评审身份，不再次全树扫描。结果见protection_result.json，R4完整基线SHA/项数及两个确切自指排除路径见review_result.json。



当前真实批准null、宿主0008、next=false、AI未开放；本次验收不批准任何批次。
