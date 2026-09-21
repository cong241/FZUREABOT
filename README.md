# FZUREABOT QQ 值班提醒机器人

这是一个 Windows 中文桌面程序。它按照排班日期自动轮换值班人，每天 20:00 通过 NapCat OneBot HTTP 在指定 QQ 群真正 @ 第二天的值班成员。

## 已配置环境

- 机器人 QQ：`3851479069`
- 目标群：`1094289617`
- NapCat HTTP：程序从本机 NapCat 配置自动读取，默认使用已启用的 `3002` 服务
- 排班：`roster.json` 已包含 2026 年秋季名单，并可在窗口里继续添加

程序不会启动 QQ 或 NapCat，也不会监听群消息。这样可以避免重复启动 QQ 导致账号被踢下线。

## 第一次安装

1. 安装 Python 3.10 或更高版本，并勾选“Add Python to PATH”。
2. 在本目录打开 PowerShell，执行：

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. 使用 NapCat 的 `launcher-win10.bat` 启动命令行版 NapCat，并登录机器人 QQ。
4. 双击 `启动值班机器人.bat`。

## 窗口操作

- “继续排班”：默认选择现有名单之后的下一个工作日，再填写 QQ 和姓名。
- “修改选中”“删除选中”：调整已有排班。
- “保存排班”：写入 `roster.json`，下次启动继续使用。
- “检查连接”：确认 NapCat 在线且机器人账号正确。
- “立即提醒明天值班人”：马上执行一次，已经提醒过则自动跳过。
- “强制重发”：二次确认后允许重复发送。
- “启动自动提醒”“停止自动提醒”：控制每天 20:00 的自动任务。

窗口启动后自动提醒默认开启。关闭窗口或关闭 NapCat 后，自动提醒都会停止。

## 命令行排查

只查看明天是谁，不发送：

```powershell
python QQBot.py --dry-run
```

立即提醒明天值班人：

```powershell
python QQBot.py --send-now
```

明确强制重发：

```powershell
python QQBot.py --send-now --force
```

## 数据文件

- `roster.json`：排班名单。
- `settings.json`：机器人 QQ、群号、发送时间和 NapCat 配置路径。
- `sent_reminders.json`：已经成功提醒的值班日期，用于防止重复。

NapCat 访问令牌不会复制到本项目，程序运行时才从 NapCat 配置读取。

## 常见问题

- “无法连接 NapCat”：先启动命令行版 NapCat，完成 QQ 登录，确认 OneBot HTTP 已启用。
- “机器人账号不符”：NapCat 当前登录的不是 `3851479069`。
- “没有排班”：在窗口点击“继续排班”，添加对应日期后保存。
- 双击后一闪而过：在 PowerShell 中运行 `python QQBot.py` 查看具体错误。

## 开发测试

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -v
```

测试全部使用离线替身，不会向真实 QQ 群发送消息。
