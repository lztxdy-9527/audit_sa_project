# 独立人类初判快照存储

实现版本 `TASK-036-human-initial-judgment-store-1.0`，范围 `STORED_SNAPSHOTS_ONLY`。本组件保存合成协议测试的四输入对象及冻结核心完整返回，不接运行层、不认证身份、不发现完整历史、不读取材料清单中的业务路径，不将物理快照当成真实初判业务状态。

## 接口和文件

仅两个公开业务API，无生产CLI：

```python
def save_human_initial_judgment_snapshots(submission, materials, expectations,
    *, prior_history=None, out_dir) -> dict: ...
def verify_human_initial_judgment_snapshots(record_dir) -> dict: ...
```

`out_dir` 实际签名为必需关键字参数，不存在默认路径。须为 `data/human_initial_judgment_records/` 的严格后代，从未存在（含空目录拒绝）；不由人类ID拼接路径。原始与解析后路径链均拒绝链接/reparse。成功叶恰 expectations.json、judgment_result.json、materials.json、prior_history.json、submission.json、manifest.json，无其他成员。

save与合法verify各调用冻结 `TASK-035-human-initial-judgment-core-1.1` 恰一次；核心Blocked保留field/reason并保留cause，内部Error保留stage/原因链。输入先深拷贝，核心验证前不序列化非法输入以掩盖字段拒绝。规范JSON均为UTF-8、ensure_ascii=False、sort_keys=True、紧凑分隔符、allow_nan=False，加恰一个LF。只保存对象快照和人类字符串原文，不承诺外部JSON原字节排版保真。

## Manifest与返回

manifest封闭九键：manifest_version/store_status/scope/identity/component_bindings/fingerprints/payloads/technical_registration/boundaries。版本为 TASK-036-human-initial-judgment-store-manifest-1.0，状态 HUMAN_INITIAL_JUDGMENT_SNAPSHOTS_STORED。identity恰batch_id/event_id/request_id，与快照及完整结果闭合。

六项组件绑定为核心、自身、协议、案例、正式契约、生效登记的确切文件SHA；五外部身份冻结，自身字节实读，不缓存跨调用读数。七项指纹为原submission、完整materials、删除其自身指纹后的九键正文、expectations、prior_history、record、record.binding的规范JSON SHA。五项payload按relative升序，每项relative/byte_size/file_sha256/object_fingerprint，长度严格整数，文件SHA与对象FP分别闭合；manifest不列自身摘要。

technical_registration恰registered_at_utc/source，保存程序生成UTC秒精度时间，source=PROGRAM_GENERATED_TECHNICAL，与人类decided_at_raw分开。verify只校验已存技术时间，不读取时钟产生新值。

成功返回恰十一键status/scope/identity/record_fingerprint/manifest_file_sha256/technical_registration/component_bindings/files/boundaries/snapshots/judgment_result。save为STORED，verify为VERIFIED相应完整状态常量；files六项另包含manifest实际FILE/长度/对象FP，snapshots四键，judgment_result完整两键，全部独立深拷贝。

存储边界恰九项且全false：workflow_connected/execution_allowed/next_step_allowed/ai_enabled/identity_authenticated/source_authenticity_proven/audit_conclusion_formed/final_judgment_recorded/complete_history_verified。核心记录原八项false、VALIDATED状态不改，尤其persisted不改true。

## 失败文件十键schema

实施前已在 `data/human_initial_judgment_store_tests/task036_prepare_01/failure_schema.json` 固定；实际失败对象仅以下十键：

1. failure_version：TASK-036-human-initial-judgment-store-failure-1.0。
2. scope：STORED_SNAPSHOTS_ONLY。
3. identity：batch_id/event_id/request_id三个已验证原字符串。
4. stage：实际操作阶段；包装核心Error保留其原stage。
5. classification：BLOCKED或ERROR。
6. field：BLOCKED为原精确非空字段，ERROR为null。
7. reason：原主错误说明。
8. exception_type：实际传播的存储异常类名。
9. cause_chain：非空列表，各成员仅exception_type/message，顺序跟随cause优先再context，首成员类型与exception_type一致，防止循环。
10. technical_registration：独立技术登记时间/source，规则同上，不填人类时间。

核心或路径前提拒绝不建事件叶。仅本次独占新叶建立后的失败才独占尝试写failure，实际句柄先关闭，不覆盖、不重试、不删除坏字节。诊断写失败在传播主异常的secondary_errors及说明中可见，保留原cause，未完成文件保留。verify原始路径检查后先查failure：有效失败优先于坏manifest/半写payload，坏格式failure也拒绝，均不调用核心、不写任何文件。

## 最后确认与复验

保存逐件用真实xb句柄写入并按本次缓冲精确读回，manifest最后写。verify操作开始固定六份字节，从同一缓冲解析对象/长度/SHA；校验自身封闭结构和内层绑定，再真实复算核心、比较完整两键返回，不只比自报指纹。

成功返回先构建，消费对象复核之后，末次有界实读六组件、六文件、目录集合及无failure，比较本次初始capture或writer缓冲；之后不再读取/刷新候选生成成功输出。代码变化使旧快照阻断，不迁移、补签或改manifest。

测试入口（待本卡完整交付时以执行回执为准）：

```powershell
.venv\Scripts\python.exe -B tests\test_store_demo_human_initial_judgment.py --out-dir data\human_initial_judgment_store_tests\task036_<新名>
```

测试只用已登记人类夹具和明确的技术投影；四个真实main新进程replay只核对收尾，不将历史观察当新调用。未提供的合法闰日/±14:00额外正例仍null+原因。不重跑纯核心156项或上游链。

本卡定稿证据为 `data/human_initial_judgment_store_tests/task036_run_03/`：68项检查、0失败，公开API34次（save17/verify17），真实冻结核心14次。返回5/Blocked26/Error3为存储API结果；核心返回10/Blocked3/Error1分列。输入真实引用在进入前、立即返回/异常后及API收尾分别实测，不以两份事后副本替代。正常十一键返回及六件确切字节由测试独立构造核对；十份成功核心返回另按协议独立重建。

verify守卫禁止任何写入（包括写相同字节）和读取当前时钟；I/O观察按父调用分列。网络/子进程/verify时钟三个真实受控探测证明守卫有效，生产守卫命中0。组件与末端字节故障由测试对自身具名副本通过保留的真实I/O入口注入，单列TEST_CONTROL_INJECTION，不能把这些故意写入算成生产权限。真实junction创建被OS拒绝（Access is denied，cmd退出1），物理reparse反例未执行，按null+原因保留，不称动态通过。

四个最终实际CLI正常/候选返回替换/台账晚漂移/checks晚漂移为0/1/1/1，新增save/verify/核心/其他业务函数调用均按项目原代码帧profile实测0。完整命令、原文输出、注入命中、源不变及进程返回见 `task036_finalization_03/closure_controls.json`；保护/交付身份以同根delivery.json和执行回执为准，当前仍待独立验收。

技术保存不批准任何批次。真实批准null、真实初判未保存、开发宿主0008、next/AI=false；运行接线、真实完整历史发现和AI均另卡决定和验收。
