# 当前小版本独立冒烟回归与输出保护修复

结论：**修复后演示冒烟通过**。2026-10-17（Asia/Singapore）。覆盖本机合成固定批次的完整演示、初判保存/运行恢复、单条只读消费和本次输出保护修复；不等于重新执行全部历史矩阵、证明生产就绪或开放AI/终判。正式本轮保护和接受身份由 `data/reviews/project_smoke_gpt_20261017_183235/review_result.json` 发布，只有唯一最终扫描通过才发布该结果。

## 1. 起点、授权与实际身份

从 `docs/FINAL_ACCEPTANCE_ENTRY.md` 实读TASK-040→040-R1→041→042交付链、最后DSH评审与最终指南。DSH接受快照173685项，SHA `43f49d75240e0087f37616a04bab392893209a605a9ae97adb5a899fa7d3ef9d`。此前ACCEPTED是本次起点身份，不用它代替本轮实际运行。旧评审、接受快照和最终入口不回写。

人类本次明确要求测试当前小版本，并授权测试发现bug时调用子Agent修复；据此只对演示脚本定点修复。唯一既有改动 `scripts/run_runtime_demo.py`：23474 B / `472b54c35ee9acdd9fb4971cdc61c4a24c25f2ef2e134855e3eb2433608c5427` → **27332 B / `abc25c4b0e779f94959623428671669a10025f56b64dda8b67d3fd95f85639af`**。原件完整保存在agent_fix/demo_before.bin。

新增定点测试 `tests/test_runtime_demo_output_safety.py`：10616 B / `643cad92cfed546c8333e7dcc89c514534a94e85b48e7f881b46403e488833b5`。运行适配器仍404971 B / `f5c7c3967abc8257f1eff5c55487f6ff88c68d0879161e715dc43c95e0fad4b7`；19业务API/17代码/40 Gate1材料保持。演示脚本不在17项代码清单中，本修复没有改变适配器/冻结算法身份或改签历史凭证。

## 2. 实际发现并闭合的bug

旧inspect_record只禁止inspect-out写进目标记录叶，没有禁止运行封装等保护域；且在写出前就算好zero_write。用本轮新复制的六快照/三封装场景实际调用CLI，将inspect-out指向该场景context.json：**exit0、zero_write=true，但context原字节已被覆盖**。这不是推测或仅静态发现。

证据 `isolated_output_bug.json`、`isolated_context_bad.bin`；仅新复制场景被注入，原DSH源九文件未变。已保全原字节，并精确恢复本轮单个context，未删移或清理现场。

按授权交子Agent修复：输出仅允许data/reviews或data/runtime_initial_judgment_recording_tests下、既存普通父目录内的全新JSON；原路径链检查先于消段，拒绝危险路径/设备名/ADS/reparse；用O_EXCL独占创建，不能覆盖已有证据。实际写出后再做末次保护快照，变化则主入口失败；已独占创建且仍持句柄的新证据记录zero_write=false和真实末次读数，不重开旧文件覆盖。

独立AST差异核对：既有函数只改inspect_record，增加两个有限输出辅助函数和import stat；normal run_demo/render等函数AST不变。运行适配器、冻结core/store/history、原交付测试/指南/契约均未改。没有把这项修复泛化成强认证或抵抗同权限恶意文件系统写入的保证。

## 3. 本轮实际运行

第一条新链task042_gpt_smoke_183235_01，以真实脚本__main__及原代码profile观察完整运行，**exit0**。12个直接公开调用全部返回；其中save内部再次调用公开prepare，不能把12直接步骤当作全部嵌套调用数。原代码观察确认标准化、SQLite装载、SQL筛查、独立复算、事实build各实际1次；不是复用旧观察或把期望数当实测。

修复后再用新目录task042_gpt_smoke_183235_02直接运行完整脚本，**exit0，125.478秒**；stdout PASS、RT_HUMAN_INITIAL_JUDGMENT_VERIFIED、九权限严格false、R01/R02/R03/R04=0/1/0/0。该耗时是本机小样单次整链，不是基准测试。HR展示宜提前准备结果。

独立内容检查：六快照/三封装集合、长度/FILE，record对象FP、manifest FILE、receipt对context/started的FILE、prepared request对象FP、原submission与材料/预期快照及已登记人类六原文均闭合；十个复算维度executed/matched严格true、差异空。原工作簿同缓冲读取，2供应商/1应付/3付款退款/3分摊，独立算AP01：应付500000分，付款1000000分，退款100000分，净额900000分，超额400000分，与事实包一致。

父端修复后独立负例与恢复：覆盖context、receipt、namespace新文件、既有输出，以及复用同一演示目录均实际非零拒绝，全部本轮保护字节不变。给本轮judgment_result加一个LF后单条核验实际拒绝，坏字节保留；仅精确恢复该文件后再次exit0。没有改旧DSH原件或清失败现场。

只读模式独立观察：**exit0，0.538秒**（含父端profile），9个受观察文件前后长度/FILE相同；实际运行适配器入口和五类业务算法入口均0，允许冻结store/core单条验证。该模式只核单条存储快照，不替代完整运行verify对当前Gate/事实/声明历史的核验。新整链本身已实际完成完整运行verify。

子Agent定点回归最终22/22，正常stdout和新证据输出exit0，真实独占冲突及写出后晚变更控制exit1；失败JSON准确zero_write=false。父端实读审核其102个新增身份及唯一修改身份，并独立执行上述整链和负例，未仅采纳子AgentPASS。regression_01过程现场保持；最终以regression_02为准。详见agent_evidence_audit、independent_fix_review、final_full_assertions、final_readonly_assertions及各command/stdout/stderr。

## 4. 保护和诚实限制

局部定稿后一次全树扫描，相对DSH173685项基线，唯一允许既有变化为演示脚本；新增测试、评审/求职说明及自有场景逐确切路径登记。DSH基线之外的source_hashes_after/review_result/readback_r3/final_readback四项既有声明扫描后元数据单列，不以目录前缀豁免。实际scope、新missing/读取错误/范围外新增/身份漂移及有限扫描后读回由protection_result、finalization、review_result给出；不以预填PASS代替扫描。

139历史损失与本轮missing分开，27恢复、R5越界326、R1命名19和TASK-03041 B原锁保持，不重建/删移/追认。扫描后只写本轮确切元数据。没有修改既有指南、FINAL_ACCEPTANCE_ENTRY或看板；新补充入口与求职说明见本轮新增文档。

本轮不是全部规则正例/全部原生Windows并发能力验收；大数据性能、物理junction/symlink、双进程真实竞争、同权限恶意篡改、真实数据、强认证、AI和终判均不新增通过结论。子Agent物理symlink被WinError1314拒绝，未绕权限或计为通过。DSH对旧适配器290568B正文缺本地副本的历史限制不被本次测试消除。

本轮独立检查脚本曾把openpyxl sheet.values属性写成方法，在生产整链exit0之后报TypeError；仅修正本轮review helper，复用已保存成功现场继续只读核验，未为此重复业务链。过程记录见process_notes，不属于生产bug。

## 5. 对外表述

当前可以演示的是“合成采购付款CAAT审计辅助，从已接收核验批次到人类声明初判保存和只读恢复”，没有网页产品或真实ERP任意Excel接入。后置AI只有只读消费设计和示例，未调用大模型；未来接入仍要授权与适配，不能承诺永久零返工。

当前人类夹具的“通过/无明显不一致且合规”是预登记原文回放，不能据此认定R02已查清或人类结论正确。真实批准仍null、真实初判未保存、开发宿主0008、next/AI=false；线索不是舞弊/损失/审计结论。不要用主观完成百分比、未经测量提效或真实客户成果包装作品。求职讲解、演示位置/命令、简历表述及常见追问详见 `docs/JOB_DEMO_PLAYBOOK_20261017.md`。
