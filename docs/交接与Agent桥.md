# 交接包与 Agent 桥 / Handoff & Agent Bridge

> 中文为主 / English summary at the bottom.
> 目标：冻结后不让 agent“等用户重新解释”，而是立刻拿到下一阶段任务。

## 1. 冻结时发生什么

点击「冻结」后，控制台会：

1. 跑闸门；
2. 生成 stages/<阶段>/frozen/<时间>/ 快照；
3. 写 .gameconsole/handoff/<时间>_<from>_to_<to>.md；
4. 如果是 P0 → P1，自动把 P0 的事实写入 P1 文档（GDD 一句话/世界/主角/对抗者 + 美术/技术摘要）；
5. 返回交接包给网页，弹窗可直接复制给 agent。

当前项目 P0 已冻结但未生成交接包时，可手动：

~~~powershell
python scripts/gameconsole.py handoff --project D:\AI_Project\Game --stage P0
~~~

## 2. 交接包里有什么

- 上一阶段/下一阶段；
- P0 事实：项目名、一句话、平台、体量、世界、主角、对抗者、不做清单；
- 下一阶段文档清单与闸门命令；
- 任务步骤：更新文档、清【待填】、跑闸门、交交付单/证据、待决策≤3；
- 禁止项：不跳过冻结范围、不绕过闸门。

## 3. 让当前 agent 自动接手

先在项目里配置（桌面版启动时会自动读）：

~~~powershell
'{"command":"claude -p @HANDOFF_FILE@"}' | Set-Content .gameconsoleagent.json -Encoding utf8
~~~

把 command 换成你本机 agent 的 CLI。网页版请手动启动 agent_bridge。

### 方式 A：弹窗复制（最简单）

冻结后弹窗 → 「复制给 Agent」→ 粘贴到当前对话。

### 方式 B：agent 桥（自动）

启动一个 watcher：

~~~powershell
python scripts/agent_bridge.py watch --project D:\AI_Project\Game ^
  --command "claude -p @HANDOFF_FILE@"
~~~

或 Codex / DSH / 其他 CLI：

~~~powershell
python scripts/agent_bridge.py watch --project . --command "codex exec @HANDOFF_FILE@"
python scripts/agent_bridge.py watch --project . --command "dsh run @HANDOFF_FILE@"
~~~

说明：

- @HANDOFF_FILE@ 会替换成交接包路径；
- 已处理文件记录在 .gameconsole/handoff/.processed.json；
- 输出写 .gameconsole/agent-bridge.log；
- 一次只派发一个；可以用 --once 做测试。

> 具体 CLI 参数以你本机 agent 为准；如果命令不会读文件，可在 prompt 里写“读取该路径”。

## 4. P0 → P1 自动带过去什么

当前实现：

- GDD 标题项目名；
- 一句话；
- 单次游玩时长；
- 世界设定；
- 主角；
- 对抗者；
- 美术圣经/技术方案追加 P0 交接摘要；
- 其余【待填】保留，等 agent/你按模板展开。

不会覆盖：

- 已冻结文档；
- 用户已手改的内容（只替换仍为【待填】的字段/追加摘要）。

## 5. 后续可扩展

- P1 → P2：把 GDD 世界/角色/关卡目标种到剧本圣经；
- P2 → P4：把 SC/SH/LINE 种到分镜/美术/配音；
- P3 → P4：把灰盒比例/关卡表种到资产需求；
- 交接包记录到审计，支持重放。

## 6. 失败处理

- 闸门失败：不生成冻结快照，只返回失败项；
- 交接包生成失败：冻结仍成功，但网页提示手动运行 handoff；
- agent 桥重复派发：用 .processed.json 去重；
- agent 崩溃：看 .gameconsole/agent-bridge.log，交接包不会丢。

---

### English Summary

Freezing a stage writes a handoff package under .gameconsole/handoff/ and (for P0 to P1) seeds P1 docs from P0 facts.
The web modal can copy the prompt, or agent_bridge.py can watch the folder and invoke an external agent CLI.
Processed files are de-duplicated; failures are logged; frozen docs are never overwritten.
