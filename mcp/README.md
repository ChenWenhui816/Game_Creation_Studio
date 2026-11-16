# MCP Gateway（本地工具总线）

> 中文为主 / English summary at the bottom.
> 目标：让 agent 通过一个稳定、可审计的本地入口操作 UE / Blender / AI / 文件系统，而不是各自乱连 MCP。

## 1. 为什么需要 Gateway

- 统一发现工具、版本、健康和权限；
- 权限分级 + 人工审批 + 审计；
- 任务队列/重试/超时；
- 屏蔽不同 MCP server 的协议差异；
- 让 UE / Blender / AI 工具可以随时替换，不影响 agent。

## 2. UE 5.8 的底座

UE 5.8 起官方内置 MCP server 与 AI toolsets。建议：

1. 首选：UE 5.8 原生 MCP + 需要的官方/社区扩展；
2. 扩展：VibeUE（原生 MCP 扩展 + AgentSkill）或 db-lyon/ue-mcp（guardrails + 大工具集）；
3. 备选：EngineWire（独立原生 C++ 插件，UE 5.0–5.8）；
4. 兜底：UnrealMCPBridge（Python API）。

具体选型与理由见 docs/ADR/0001-UE-MCP.md。

## 3. 配置

复制：

~~~powershell
Copy-Item mcp\servers.example.json mcp\servers.json
~~~

编辑 mcp/servers.json 的 command/url。不要把 token、证书、账号写进仓库。

## 4. 命令

~~~powershell
python scripts/mcp_gateway.py doctor
python scripts/mcp_gateway.py list
python scripts/mcp_gateway.py tools ue-mcp
python scripts/mcp_gateway.py call ue-mcp project.get_status --args "{}"
python scripts/mcp_gateway.py call ue-mcp asset.list --args '{"path":"/Game/Characters"}'
~~~

写操作默认由 permissions 拒绝或要求 --yes；POC 见 mcp/permissions.json。

## 5. 安全边界

- 只监听本机；
- 不允许 agent 任意 shell/python；
- 路径限制在项目内；
- 删除/覆盖/打包/发布必须人工审批；
- 每次调用写 .gameconsole/mcp-audit.jsonl；
- MCP server 固定版本，升级前跑回归。

## 6. 下一步

- HTTP/stdio 双栈；
- namespace dispatch（ue_query(action, params)）；
- checkpoint/rollback；
- 资产注册表联动；
- 任务队列与 UI 状态面板。

---

### English Summary

A local MCP Gateway for a solo UE5 studio: one auditable entrypoint for UE, Blender, AI and filesystem tools.
UE 5.8 native MCP is the base; VibeUE / db-lyon / EngineWire / UnrealMCPBridge are options.
Writes, deletes, packaging and publishing require approval; all calls are logged.
