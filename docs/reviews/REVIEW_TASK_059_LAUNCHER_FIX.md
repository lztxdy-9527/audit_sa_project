# TASK-059 启动器缺陷更正（`一键对账.cmd` 编码/换行）

日期：2026-10-18。记录人：DSH Architect。触发：人类双击 `一键对账.cmd` 时报错：

```
'⑬' is not recognized as an internal or external command...
The system cannot find the path specified.
```

## 1. 原因

交付的 `一键对账.cmd` 是 **UTF-8 + LF 换行**，且含中文 `echo` 文案。Windows `cmd.exe`：

- 批处理按 **CRLF** 解析；LF-only 会导致行/字节切分异常；
- 在默认代码页（936）下，UTF-8 中文被错误解码，首行/中文行被当成命令（即截图里的乱码 `'⑬'`）；
- `chcp 65001` 在第二行才执行，救不了第一行的解析。

所以不是“按钮坏了”，是这个 `.cmd` 的文件格式不适合 cmd。

## 2. 修复（已应用）

改为 **ASCII + CRLF**，内容：

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Running one-click audit reconcile (machine checks + HTML output)...
".venv\Scripts\python.exe" -B scripts\run_all.py --open
echo.
echo Done. Output folder: outputs\RUN_ID\index.html
pause
```

- 去掉中文文案（避免代码页问题），保留 `chcp 65001` 供 Python 输出；
- `cd /d "%~dp0"` 保证双击时工作目录正确；
- `pause` 保留，窗口不闪退。

## 3. 验证

用同内容副本（`--no-open`、`pause` 换 `exit /b`）在项目根执行：

```
{"status": "SUCCESS", "run_id": "run_20261018_124821",
 "outputs": "...\\outputs\\run_20261018_124821", "failed_step": null}
exit 0
```

七步全成功、`index.html` 生成。

## 4. 影响与基线

- 只改启动器；`run_all.py`、生成器、核对器、输入均未动。
- 该文件在 TASK-059 接受基线中记录的是旧版；本次为**紧急修复**，将在下一次验收扫描中按新身份登记并复核（或由 TASK-059-R2 正式重交）。旧版问题不影响机器核对结果，只影响双击启动。
