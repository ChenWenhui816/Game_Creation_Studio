# DeepSeek Harness 对接 / DSH Integration

> 目标：控制台冻结阶段后，把交接包直接交给 DSH agent，而不是让用户复制粘贴。
> 中文为主 / English summary at the bottom.

## 1. 链路

~~~text
控制台冻结 P0
  -> .gameconsole/handoff/<时间>_P0_to_P1.md
  -> 控制台 POST /api/handoff/run
  -> dsh_bridge.py
  -> DeepSeek Harness headless (studio-headless profile)
  -> 当前/新 DSH 会话按交接包展开 P1
  -> gamecheck gate spec
  -> 用户审核 -> 冻结 P1
~~~

## 2. 前置条件

- 安装 DeepSeek Harness 桌面版；
- 在 DSH GUI 已登录 DeepSeek 账号；
- 控制台从 DSH 环境启动时，DSH_SESSION_ID 会指向当前会话；
- 项目里有 .gameconsole/handoff/ 交接包。

## 3. profile

dsh_bridge.py 会在用户目录 .dsh/profiles/studio-headless 自动创建 profile：

- 复制 headless profile；
- 重新开启 credentials / authorization / deepseek-account；
- 默认模型 deepseek-account / deepseek-flash；
- 没有写任何 API key，复用 DSH 账号凭据。

第一次运行会创建该 profile；之后复用。

## 4. 使用

### 网页

冻结后弹窗 ->「让 DSH 继续」。

服务端调用：

~~~text
POST /api/handoff/run
{"path": ".gameconsole/handoff/xxx.md", "session": "current"}
~~~

session：

- current：尝试使用当前 DSH 会话（DSH_SESSION_ID）；
- new：新开一个 DSH 会话，避免打断当前对话；
- 其他值：按 session id 恢复。

当前 DSH 桌面会话可能运行在 `ptc` preset 下，headless 一次性 runner 无法接管；控制台会自动 fallback 到新会话，日志里会标 `FALLBACK`。

状态：

~~~text
GET /api/handoff/status
~~~

日志：

~~~text
.gameconsole/dsh-agent.log
~~~

### 命令行

~~~powershell
python scripts/dsh_bridge.py run --project D:/AI_Project/Game --handoff .gameconsole/handoff/20261117-133914_P0_to_P1.md --session current
~~~

新会话测试：

~~~powershell
python scripts/dsh_bridge.py run --project D:/AI_Project/Game --prompt "只回复 OK" --session new
~~~

## 5. 权限

- --permission-mode workspace-write
- --approval-policy never
- --add-dir <项目>

含义：agent 只能写项目目录，冻结动作本身视为用户授权。
在点「让 DSH 继续」前先 commit，避免 agent 改坏无法回滚。

## 6. 失败排查

| 现象 | 处理 |
|---|---|
| MISSING_CREDENTIAL | DSH GUI 未登录，或 studio-headless profile 未生成完成 |
| 找不到 DeepSeek Harness.exe | 设置 DSH_EXE |
| 找不到 CLI | 设置 DSH_BIN 指向 app.asar 内 bin.js |
| 一直 running | 看 dsh-agent.log；大任务可能 5-15 分钟，超时 1800 s |
| 当前会话被占用 | session: new，或等当前 turn 结束 |
| 写入被拒绝 | 确认项目在 --add-dir 内；不要改 .uasset 二进制 |

## 7. 设计约束

- DSH 只负责按交接包推进文档，不负责替用户冻结；
- 用户保留三类决策：范围/砍功能/审美方向；
- agent 必须先读交接包与管线 README，再改文档；
- 每次产出跑 gamecheck，证据写交付单；
- 不在 agent 运行时并发改同一文档。

## 8. 当前验证

- dsh_bridge.py --prompt "只回复 OK" --session new：通过；
- POST /api/handoff/run + status：通过；
- P1 文档由当前 agent 展开，gamecheck gate spec 23 通过 / 0 失败 / 0 警告。

---

### English Summary

Freezing a stage writes a handoff package. The console can POST it to /api/handoff/run, which invokes DeepSeek Harness headless through a generated studio-headless profile that reuses the signed-in DSH account. The agent writes only inside the project workspace; the user still approves freezes.
