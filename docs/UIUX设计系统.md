# UIUX 设计系统 / Console Design System

> 版本：v0.7.6 ｜ 日期：2026-11-17
> 来源：nextlevelbuilder/ui-ux-pro-max-skill（150.6k stars，MIT，2026-11-16 更新）
> 应用范围：console_web/ 的制作控制台。

## 1. 为什么选它

| 候选 | 星数 | 判断 |
|---|---:|---|
| nextlevelbuilder/ui-ux-pro-max-skill | 150.6k | **采用**：专门做 UI/UX 设计智能，含设计系统生成、120 UX 规则、80 风格、192 行业色板，维护活跃，MIT |
| anthropics/skills | 196k | 通用 Agent Skills，不是专门 UIUX，不选 |
| obra/superpowers | 318k | 方法论框架，不是 UIUX，不选 |
| wshobson/agents | 42.6k | 广泛 agent 合集，UI 只是其中一小块，不选 |
| master5d/claude-design-skills | 42 | 方向接近但星数/维护不足，不选 |

## 2. 生成方向

查询：

~~~text
developer dashboard admin panel desktop app dense data table kanban timeline project management
~~~

输出方向：

- Pattern：Real-Time / Operations（状态、指标、实时数据）
- Style：Glassmorphism（低透明度分层 + 背景模糊，控制用量）
- Typography：Fira Sans（正文）+ Fira Code（数字/代码）
- Color：Dark tech + status green
- Anti-patterns：慢更新、无自动化、浅色默认

## 3. 令牌

| 角色 | 值 | CSS 变量 |
|---|---|---|
| Background | #0F172A | --bg |
| Elevated | #131C2F / #1B2336 | --bg-2 / --bg-3 |
| Border | rgba(148,163,184,.18) | --line-soft |
| Text | #F8FAFC | --text |
| Muted | #94A3B8 | --muted |
| Primary/CTA | #22C55E | --accent |
| Secondary | #38BDF8 | --accent-2 |
| Warning | #F59E0B | --warn |
| Danger | #EF4444 | --danger |
| Success | #22C55E | --ok |
| Radius | 12px | --radius |
| Font | Fira Sans / Fira Code | --font-sans / --font-mono |

## 4. 落地

- 深色玻璃卡片：低透明度渐变 + 12px 模糊 + 1px 细边；
- 绿色主按钮/激活态；青色作为信息强调；
- 统一 focus-visible：2px 绿色外框；
- prefers-reduced-motion 关闭动画；
- 1280/900px 两档响应式；
- 自定义滚动条；
- 保留本地字体回退，不请求 Google Fonts。

## 5. 与 skill 建议的偏差

| 建议 | 我们的处理 | 原因 |
|---|---|---|
| 引入 Google Fonts Inter/Fira | 只写字体栈，本地回退 | 本地单机、零外部依赖 |
| 全站 Glassmorphism | 只用于卡片/顶栏 | 高密度文档需要可读性，避免全屏模糊 |
| 44px 触控目标 | 桌面按钮保持紧凑，键盘焦点强化 | 桌面优先；后续触摸屏再放大 |
| 浅色模式 | 暂不做 | 当前是夜间开发工具；令牌已预留语义层 |

## 6. 验收清单

- [x] 文本对比度 ≥4.5:1（主文本/背景）
- [x] focus-visible 可见
- [x] prefers-reduced-motion
- [x] 无 emoji 图标
- [x] 1280 / 900 响应式
- [x] 主按钮唯一强调色
- [ ] 真实键盘全流程走查
- [ ] 真实 44px 触控走查（触屏设备）

## 7. 参考

- Skill：https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- 生成脚本：.claude/skills/ui-ux-pro-max/scripts/search.py
- 规则：references/quick-reference.md
