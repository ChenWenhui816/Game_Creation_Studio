# ADR 0001：UE MCP 选型（UE 5.8）

- 状态：Accepted（POC）
- 日期：2026-11-17
- 决策：UE 5.8 官方原生 MCP 为底座 + 我们的 Studio MCP Gateway；按需接 VibeUE/db-lyon/EngineWire。

## 背景

一人工作室需要 agent 操作 UE Editor：关卡、Blueprint、材质、Niagara、Sequencer、资产导入、截图、构建。
GitHub 上 UE MCP 很多，但成熟度/维护/安全差异大。

## 候选（2026-11-17 查询）

| 仓库 | 星 | 最近 | 许可 | 结论 |
|---|---:|---|---|---|
| Epic UE 5.8 原生 MCP | 官方 | 5.8 | Epic EULA | 首选底座 |
| db-lyon/ue-mcp | 504 | 2026-11-15 | MIT | 首选扩展：3,714 actions、guardrail、checkpoint、rollback |
| ChiR24/Unreal_mcp (EngineWire) | 1,041 | 2026-11-16 | MIT | 备选独立插件：原生 C++、token、HTTP/stdio、5.0–5.8 |
| kevinpbuckley/VibeUE | 837 | 2026-11-15 | MIT | 原生 MCP 扩展 + AgentSkill，适合 UE 5.8+ |
| tumourlove/monolith | 372 | 2026-10-18 | MIT | 架构参考：namespace discover/describe，节省上下文 |
| prajwalshettydev/UnrealGenAISupport | 686 | 2026-04-28 | MIT | AI/音频/3D 服务参考，更新较慢 |
| appleweed/UnrealMCPBridge | 64 | 2026-11-11 | MIT | Python API 兜底 |
| chongdashu/unreal-mcp | 2,118 | 2025-04-22 | 无 | 过时，不用 |
| flopperam/unreal-engine-mcp | 1,119 | 2026-06-26 | 无 | 已归 Aura，不用 |

## 决策

1. 不 fork 任何编辑器桥；不把 3,000+ 工具直接暴露给 agent。
2. 先验证 UE 5.8 原生 MCP 能力；缺口用 VibeUE 或 db-lyon 补。
3. 我们只做 Gateway + 稳定工具契约 + 权限/审计/队列。
4. 工具采用 namespace + discover/describe，控制上下文。
5. 写操作 checkpoint/rollback，删除/打包/发布人工审批。
6. 版本锁定：UE 5.8；5.9/6.0 升级前跑回归；保留 fallback。

## 后果

- 正：不维护编辑器桥；可替换后端；安全/审计可控；上下文小。
- 负：依赖第三方 MCP 稳定性；需要适配层；UE 5.8 原生 MCP 仍需实测。
- 下一步：在真实 UE 5.8 项目跑通 project.status / asset.import / screenshot / build 四个工具。
