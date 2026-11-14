# GitHub 发布指南

> 适用对象：本仓库的维护者（一个人，非程序出身）。｜ 当前状态：本地仓库已初始化（`main` 分支），并已发布到 https://github.com/ChenWenhui816/ue5-solo-game-skill （`v0.1.0`，CI 绿）。｜ 读完能做到：从零把仓库推到 GitHub、发第一个 Release、之后每周 30 分钟迭代、让使用者安装与升级。

本指南所有命令均为 **Windows 11 + PowerShell** 写法，可逐行复制执行。Web 界面按钮名称以你看到的 GitHub 页面为准；GitHub 会改版，找不到按钮时按关键词搜官方文档（链接见相关小节）。

> 已发布：<https://github.com/ChenWenhui816/ue5-solo-game-skill> ｜ Release：<https://github.com/ChenWenhui816/ue5-solo-game-skill/releases/tag/v0.1.0>

**最短路径**（已完成第 0 节准备时，5 条命令完成推送）：

```powershell
cd D:\AI_Project\Deepseek\Creat_Game\ue5-solo-game-skill
git status
git remote add origin https://github.com/ChenWenhui816/ue5-solo-game-skill.git
git branch -M main
git push -u origin main
```

推送成功后，按第 5 节打 tag、建 Release。**顺序不能颠倒**：先建远程仓库（第 2 节），再推送（第 3 节）。

---

## 0. 开始前：一次性准备（约 20 分钟）

### 0.1 账号与邮箱

| 检查项 | 怎么查 | 通过标准 |
|---|---|---|
| GitHub 账号存在 | 浏览器打开 https://github.com/ChenWenhui816 | 能看到个人主页 |
| 邮箱已验证 | https://github.com/settings/emails | 邮箱后面没有 "Unverified" 标记 |
| 能登录 | 右上角头像能点开菜单 | 能看到 Settings |

没有账号：打开 https://github.com/signup 注册，用户名用英文数字连字符，注册后到邮箱点验证链接。**邮箱不验证会影响提交记录与你账号的关联显示**，不影响 push 本身。

顺便确认两个工具可用（本仓库所有检查命令都靠它们）：

```powershell
git --version
python --version
```

- `git --version` 应输出 `2.56.x`（你已装 Git 2.56）。
- `python --version` 应输出 `Python 3.10` 或更高。若弹微软商店或提示找不到命令，说明只有 Windows 的商店占位符：到 https://www.python.org/downloads/windows/ 下载安装，安装时勾选 **Add python.exe to PATH**，装完重开 PowerShell 再查。

### 0.2 配置 Git（PowerShell 执行一次即可）

```powershell
git --version
git config --global user.name "ChenWenhui816"
git config --global user.email "<你的 GitHub 邮箱>"
git config --global init.defaultBranch main
git config --global core.autocrlf false
git config --global core.quotepath false
git config --global credential.helper manager
git config --global --list
```

| 命令 | 作用 | 写错的后果 |
|---|---|---|
| `user.name` | 提交记录里的作者名；用 GitHub 用户名 | 提交记录显示成别人/看不出是谁 |
| `user.email` | 提交记录里的邮箱；必须是你 GitHub 账号已验证的邮箱 | 提交不关联到你的主页，不显示绿格子 |
| `init.defaultBranch main` | 新仓库默认分支叫 main | 默认 master，和 GitHub 不一致 |
| `core.autocrlf false` | 行尾交给 `.gitattributes` 决定 | Windows 下整文件出现 CRLF 假改动 |
| `core.quotepath false` | `git status` 正常显示中文文件名 | 中文名显示成 `\344\270\255` 转义 |
| `credential.helper manager` | 用 Windows 凭据管理器保存账号 | 每次 push 都要重新输入 |

`git config --global --list` 里能看到上面设置的各项，说明生效。

**不想暴露真实邮箱**：GitHub → Settings → Emails → 勾 "Keep my email addresses private"，页面会显示一个 `数字+用户名@users.noreply.github.com` 的专用邮箱，把它填进 `user.email`。以页面实际显示为准。

### 0.3 网络

| 检查 | 方法 | 不合格怎么办 |
|---|---|---|
| 浏览器能开 GitHub | 打开 https://github.com，3 秒内出现页面 | 换网络；或用代理并给 Git 配代理（见下） |
| git 能连 | 推送时卡住/超时 | 先走 HTTPS + 代理；或 SSH 走 443 端口（见下） |

给 Git 配代理（端口按你代理软件的实际端口改，常见 7890）：

```powershell
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
# 用完后取消：
git config --global --unset http.proxy
git config --global --unset https.proxy
```

SSH 的 22 端口被网络拦截时，改走 443。在 PowerShell 里创建配置文件（文件不存在会自动新建）：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.ssh" | Out-Null
@"
Host github.com
  HostName ssh.github.com
  Port 443
  User git
"@ | Set-Content -Encoding ascii "$env:USERPROFILE\.ssh\config"
ssh -T git@github.com
```

看到 `Hi ChenWenhui816! You've successfully authenticated` 即成功。

### 0.4 可选：安装 gh CLI

`gh` 是 GitHub 官方命令行工具，能把"建仓库 + 推送"合成一条命令。**不装也完全能做完全部流程**，只是多点几下网页。

```powershell
winget install --id GitHub.cli --source winget
```

装完**关掉当前 PowerShell 窗口，重新打开一个**（PATH 才会生效），然后：

```powershell
gh --version
gh auth login
gh auth status
```

`gh auth login` 的选项按顺序选：`GitHub.com` → `HTTPS` → `Login with a web browser` → 复制终端显示的一次性代码 → 浏览器里粘贴并授权。`gh auth status` 显示 `Logged in to github.com account ChenWenhui816` 即成功。

### 0.5 HTTPS 还是 SSH：先选一条

| 对比 | HTTPS + 浏览器登录 | HTTPS + PAT | SSH |
|---|---|---|---|
| 首次配置 | 几乎为 0 | 生成 token，2 分钟 | 生成密钥 + 上传公钥，5 分钟 |
| 日常使用 | push 时弹浏览器授权 | 输入一次后由凭据管理器记住 | 无感 |
| 会过期吗 | 凭证会失效，重新授权即可 | token 有有效期，到期要重生成 | 不主动删就一直有效 |
| 适合 | 只想偶尔推一次 | 需要在不弹窗的环境用 | 长期维护、每天 push |

**建议：长期维护选 SSH（第 3.3 节）；不想碰密钥选 HTTPS + 浏览器登录（第 3.1 节）。** PAT（第 3.2 节）保留给"公司机器/无法弹浏览器"的场景。

---

## 1. 检查本地仓库（2 分钟）

```powershell
cd D:\AI_Project\Deepseek\Creat_Game\ue5-solo-game-skill
git status
git log --oneline -5
git tag
git remote -v
```

| 命令 | 正常情况下看到 | FAQ |
|---|---|---|
| `git status` | `On branch main` + `nothing to commit, working tree clean` | 有未提交文件：`git add -A` → `git commit -m "chore: 初始版本"` |
| `git log --oneline -5` | 至少 1 行，第一行是首个提交 | 输出 `fatal: your current branch 'main' does not have any commits yet`：仓库还没首次提交，先完成提交再继续 |
| `git tag` | 有 `v0.1.0` 或什么都不输出 | 都有，第 5 节按"已有 tag"处理 |
| `git remote -v` | **什么都不输出**（远程尚未创建，正常） | 已有 origin：第 3.0 节用 `set-url` 而不是 `add` |

再确认作者信息正确：

```powershell
git config user.name
git config user.email
```

输出应为 `ChenWenhui816` 和你的 GitHub 邮箱。不对就回 0.2 节重设。

> 看到 `fatal: not a git repository` 说明 git 仓库还没初始化。本指南假设仓库已由维护者初始化；确实没有时执行 `git init -b main`，再 `git add -A`、`git commit -m "chore: 初始化 v0.1.0"`，然后继续第 2 节。

---

## 2. 创建远程仓库（Web 界面，5 分钟）

**前提：远程仓库还不存在。** 所以必须先建空仓库，再推送。两边都有内容时会出现 `rejected (fetch first)`。

### 2.1 八步操作

| 步 | 点哪里 | 输入/选择 | 看到什么算成功 |
|---|---|---|---|
| 1 | 浏览器登录 GitHub 后，右上角 `+` → **New repository**（或直接打开 https://github.com/new） | — | 出现 Create a new repository 表单 |
| 2 | Owner | 选 `ChenWenhui816` | 下拉框显示用户名 |
| 3 | Repository name | `ue5-solo-game-skill`（与本地目录大小写完全一致） | 右侧出现绿色对勾 |
| 4 | Description | `面向 UE5 单角色单机 3D 闯关游戏的 AI agent 全流程 skill：6 阶段 + 6 道可执行闸门 + 13 份模板。` | 输入框有内容 |
| 5 | 可见性 | 选 **Public** | Public 单选被选中 |
| 6 | Initialize this repository with | **三个都不要勾**（Add a README / Add .gitignore / Choose a license） | 三个复选框全空 |
| 7 | 点 **Create repository** | — | 跳到 "Quick setup" 页面，显示仓库地址 |
| 8 | 复制地址 | `https://github.com/ChenWenhui816/ue5-solo-game-skill.git` | 地址栏是 github.com/ChenWenhui816/ue5-solo-game-skill |

**为什么第 6 步全不勾**：本地已经有 `README.md`、`.gitignore`、`LICENSE`，远程再生成一份就会和本地冲突，首次 push 直接被拒。GitHub 的默认勾选是给"从零开始"的仓库用的。

**不要**点 Quick setup 页面上的 "uploading an existing file"——那是网页上传，会绕过 git 历史。用第 3 节的命令推送。

### 2.2 gh CLI 等价命令（装了 gh 才用）

```powershell
cd D:\AI_Project\Deepseek\Creat_Game\ue5-solo-game-skill
gh repo create ue5-solo-game-skill --public --source=. --remote=origin --push --description "面向 UE5 单角色单机 3D 闯关游戏的 AI agent 全流程 skill：6 阶段 + 6 道可执行闸门 + 13 份模板。"
```

这条命令**已经包含推送**，等于自动完成第 3 节，之后直接跳到第 4 节。注意：

- 远程仓库已存在时会报 `already exists`，改用 `git remote add origin ...` 手动绑定。
- 执行前确认 `git remote -v` 为空，否则 `--remote=origin` 会冲突。

### 2.3 命名与 Topics 建议

| 项 | 建议 | 约束（以 GitHub 文档为准） |
|---|---|---|
| 仓库名 | `ue5-solo-game-skill` | 小写字母、数字、连字符；URL 里出现，避免中文与空格 |
| 描述 | 上面第 4 步那句 | 100 字符以内更易完整显示 |
| Topics | `game-dev`、`unreal-engine`、`ai-agent`、`skill`、`gamedev-workflow` | 每个 topic 只能小写字母、数字、连字符，≤50 字符；建议 5–10 个 |
| 可见性 | 起步用 Public | Private 也能用 CI 与 Release，但别人搜不到；改可见性：Settings → General → Danger Zone → Change visibility |

Topics 在第 4 节填。

---

## 3. 推送（5–15 分钟）

### 3.0 绑定远程仓库并确认分支名

```powershell
cd D:\AI_Project\Deepseek\Creat_Game\ue5-solo-game-skill
git remote add origin https://github.com/ChenWenhui816/ue5-solo-game-skill.git
git remote -v
git branch -M main
git branch --show-current
```

| 命令 | 通过标准 | 常见报错与处理 |
|---|---|---|
| `git remote add` | `git remote -v` 显示两行 fetch/push | `remote origin already exists` → 用 `git remote set-url origin <地址>` |
| `git branch -M main` | 无输出 | 当前已在 main 时也正常 |
| `git branch --show-current` | 输出 `main` | 输出为空说明处于 detached HEAD，先 `git switch main` |

### 3.1 方式 A：HTTPS + 浏览器登录（最省事）

```powershell
git push -u origin main
```

首次会弹出一个 Git Credential Manager 窗口：

1. 选 **Sign in with your browser**（或 GitHub → Sign in with browser）。
2. 浏览器打开授权页，点 **Authorize**。
3. 回到 PowerShell，看到 `branch 'main' set up to track 'origin/main'`。

成功判据：命令输出里有 `* [new branch]      main -> main` 和 `branch 'main' set up to track 'origin/main'`。刷新 GitHub 页面，能看到 README 渲染出来。

### 3.2 方式 B：HTTPS + PAT（经典 token）

**GitHub 已不允许用账号密码 push**，必须用 PAT（Personal Access Token）。以官方文档为准：https://docs.github.com/zh/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

1. 浏览器打开 https://github.com/settings/tokens
2. 点 **Generate new token** → **Generate new token (classic)**
3. Note 填 `ue5-skill-push-2026`（写清用途，方便到期时认出来）
4. Expiration 选界面允许的最长有效期（到期会失效，见第 9.6 节）
5. Scopes 只勾 **`repo`** 整块（其余留空）
6. 点 **Generate token**，页面只显示一次，**立即复制**保存到密码管理器
7. 回到 PowerShell 执行：

```powershell
git push -u origin main
```

弹窗或命令行提示时输入：

| 提示 | 输入 |
|---|---|
| Username for 'https://github.com' | `ChenWenhui816` |
| Password for 'https://ChenWenhui816@github.com' | **粘贴 PAT**（不是账号密码，粘贴时屏幕不显示，正常） |

不想每次输入：确认 `git config --global credential.helper` 输出 `manager`，凭据会存进 Windows 凭据管理器。

> 更细粒度的 Fine-grained token 也能用，但需要给该仓库 **Contents: Read and write** 权限并选中本仓库；对 solo 维护者来说 classic + repo 更省事。

### 3.3 方式 C：SSH（长期维护推荐）

**第一步：生成密钥**（已有 `$env:USERPROFILE\.ssh\id_ed25519` 就跳过）

```powershell
ssh-keygen -t ed25519 -C "ChenWenhui816@users.noreply.github.com"
```

提示 `Enter file in which to save the key` 直接回车；提示 passphrase 可留空直接回车（留空=不用输密码，安全性靠电脑本身）。生成两个文件：

| 文件 | 用途 |
|---|---|
| `C:\Users\<你的用户名>\.ssh\id_ed25519` | **私钥，绝不外传、绝不提交** |
| `C:\Users\<你的用户名>\.ssh\id_ed25519.pub` | 公钥，上传给 GitHub |

**第二步：复制公钥**

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | Set-Clipboard
```

**第三步：上传到 GitHub**：浏览器 → https://github.com/settings/keys → **New SSH key** → Title 填 `Windows-11-工作机` → Key 框粘贴 → **Add SSH key**。看到列表里出现这条 key 即成功。

**第四步：测试连接**

```powershell
ssh -T git@github.com
```

首次会问 `Are you sure you want to continue connecting (yes/no)?`，输入 `yes` 回车。成功显示：

```text
Hi ChenWenhui816! You've successfully authenticated, but GitHub does not provide shell access.
```

看到这句话就是成功，后半句只是说明 GitHub 不提供 shell，正常。

**第五步：切换远程地址并推送**

```powershell
git remote set-url origin git@github.com:ChenWenhui816/ue5-solo-game-skill.git
git remote -v
git push -u origin main
```

### 3.4 认证失败排查（401 / 403 / 404）

| 现象 | 最可能的原因 | 修复 |
|---|---|---|
| `Authentication failed` / 401 | PAT 复制错、已过期、用了账号密码 | 重新生成 PAT；清旧凭据（控制面板 → 凭据管理器 → Windows 凭据 → 删除 `git:https://github.com`）后重试 |
| `remote: Permission to ... denied` / 403 | PAT 没勾 `repo`；登录的是另一个账号；仓库属于别人 | 检查 `git remote -v` 的账号；`gh auth status`；重新生成并勾 `repo` |
| `Repository not found` / 404 | 仓库名或用户名拼错、仓库还没创建、私有仓库无权限 | 浏览器打开远程地址确认存在；对照 `git remote -v` 逐字符核对大小写 |
| `Support for password authentication was removed` | 密码框里填了账号密码 | 改用 PAT（3.2）或 SSH（3.3） |
| `Host key verification failed` | SSH 首次连接没确认指纹 | 重新 `ssh -T git@github.com` 并输入 `yes` |

---

## 4. 仓库设置（5 分钟）

打开 https://github.com/ChenWenhui816/ue5-solo-game-skill ，逐项做：

| 项 | 位置 | 怎么设 | 通过标准 |
|---|---|---|---|
| 描述 | 主页右侧 **About** 旁的齿轮（Edit repository details） | Description 填第 2 节那句 | About 区显示描述 |
| Topics | 同上弹窗的 **Topics** 框 | 逐个输入第 2.3 节的 5 个 topic，回车确认 | About 区显示 5 个标签 |
| Website | 同上 | 可留空；有演示页再填 | — |
| Issues | Settings → General → Features | 确保 **Issues** 勾选 | 顶部出现 Issues 标签 |
| Discussions | Settings → General → Features | 勾选 **Discussions**（可选） | 顶部出现 Discussions 标签 |
| Releases | 不需要开启 | 用 tag + Release 页面 | 主页右侧出现 Releases |
| License 识别 | 仓库根有 `LICENSE` | 无需操作，GitHub 自动识别 | 主页右侧显示 `MIT license` |
| 默认分支 | Settings → General → Default branch | 应为 `main` | 主页顶部显示 main |
| README 展示 | 根目录 `README.md` | 无需操作 | 主页直接渲染 README 与徽章 |
| 分支保护 | Settings → Branches（新版界面可能在 Settings → Rules → Rulesets） | **solo 建议：不要求 PR**；只勾 "Do not allow force pushes" 与 "Do not allow deletions" | 误操作时强推被拒 |
| Actions 权限 | Settings → Actions → General | 保持默认（允许运行 workflow） | 第 7 节能看到运行记录 |

**为什么不给自己开"必须先提 PR"**：一个人维护时，改个错别字也要走 PR 会把每周 30 分钟的节奏拖死。用"直接 push main + CI 兜底 + tag 发布"就够了；真正需要保护的是"不能强推、不能删分支"。

---

## 5. 第一个 Release（10 分钟）

### 5.1 SemVer 在本仓库怎么用

版本号写成 `MAJOR.MINOR.PATCH`（如 `0.1.0`）。**0.x 阶段是"接口未稳定"阶段，允许在 minor 号里做破坏性改动，但必须在 Release 说明里写清迁移办法。**

| 位 | 什么时候升 | 本仓库的例子 |
|---|---|---|
| MAJOR | 首次发布 1.0.0，或承诺"文件结构与命令稳定"之后的不兼容改动 | 1.0.0 = 完整跑通一个游戏项目后的稳定版 |
| MINOR | 新增阶段/模板/闸门/检查项；改模板章节名；重命名或删除文件；改命令语义 | 0.1.0 → 0.2.0 新增"性能验收单" |
| PATCH | 错别字、失效链接、示例数字修正、说明补充；不改变判定结果与文件路径 | 0.1.0 → 0.1.1 修正 G2 闸门表笔误 |

三条硬规则：

1. **已发布的版本内容永不变**。发现错误发补丁版本，不回改 tag。
2. **破坏性改动必须写迁移说明**：改了什么文件、使用者要改哪行、旧项目怎么办。
3. **一个版本只对应一个 tag**，tag 名与 Release 标题一致（都写 `v0.1.0`）。

SemVer 规范（中文）：https://semver.org/lang/zh-CN/

### 5.2 打 tag 并推送

先看本地有没有 tag：

```powershell
cd D:\AI_Project\Deepseek\Creat_Game\ue5-solo-game-skill
git tag
```

**情况 A：已经有 `v0.1.0`**（维护者预先打过）

```powershell
git show v0.1.0 --stat
git push origin v0.1.0
```

确认 `git show` 指向首个提交，再推送。

**情况 B：没有 tag**

```powershell
git status
git tag -a v0.1.0 -m "v0.1.0: 首个公开版本（六阶段 + 六道闸门 + 十三份模板）"
git tag -l
git push origin v0.1.0
```

成功判据：`git tag -l` 输出 `v0.1.0`；`git push` 输出 `* [new tag]         v0.1.0 -> v0.1.0`。刷新 GitHub 的 Tags 页面（`/tags`）能看到它。

> tag 推送后**不要删除重建**。使用者可能已经把 `v0.1.0` 写进自己的技术方案，tag 变了等于内容变了。要修就发 `v0.1.1`。

### 5.3 在 GitHub 建 Release

1. 浏览器打开 https://github.com/ChenWenhui816/ue5-solo-game-skill/releases
2. 点 **Draft a new release**（或 **Create a new release**）
3. **Choose a tag**：下拉选 `v0.1.0`（列表里已有，因为第 5.2 节推送过）；Target 选 `main`
4. **Release title**：`v0.1.0 — 首个公开版本`
5. **Describe this release**：从 `CHANGELOG.md` 的 `[0.1.0]` 段复制 Added 列表，末尾加两行：

```text
升级方式：git pull 或重新下载 Source code (zip) 覆盖旧目录。
破坏性改动：无（首个版本）。
```

6. **附件（可选）**：本仓库没有二进制，GitHub 会为每个 Release 自动生成 **Source code (zip)** 与 **(tar.gz)**，够用。想要一个带正确目录名的 ZIP，本地生成后拖进 "Attach binaries" 区域：

```powershell
git archive --format=zip --prefix=ue5-solo-game-skill/ -o ..\ue5-solo-game-skill-v0.1.0.zip HEAD
```

7. 确认勾选 **Set as the latest release**，点 **Publish release**

成功判据：Releases 页面出现 `v0.1.0`；点进去能下载 ZIP；安装到游戏项目里能跑通 `gamecheck.py --help`。

### 5.4 Release 说明模板（以后每次复制改）

```text
## v0.x.y — 一句话主题

### Added
- 新增了什么（一句话，带文件名）

### Changed
- 改了什么判定（旧规则 → 新规则）

### Fixed
- 修了什么错（原来会怎样，现在怎样）

### 迁移（有破坏性改动时必填）
- 重命名：旧路径 → 新路径
- 使用者要做：重新 clone / 改 AGENTS.md 里的路径

### 升级方式
git pull 或下载 Source code (zip) 覆盖；
锁版本：git checkout v0.x.y
```

---

## 6. 后续迭代工作流

### 6.1 每周 30 分钟最小流程

目标：**每周只做一次同步 + 一次提交 + 一次推送**，让仓库始终可发布。

| 步 | 做什么 | 命令 | 时间 | 判据 |
|---|---|---|---|---|
| 1 | 同步远程 | `git pull` | 30 秒 | 输出 Up to date 或正常快进 |
| 2 | 跑测试 | `python -m unittest discover -s tests -v` | 1 分钟 | 末行 `OK`（或 `OK (skipped=…)`） |
| 3 | 改 1–3 个文件（只改这一件事） | 编辑器 | 15 分钟 | 改动范围与提交信息一致 |
| 4 | 提交 | `git add -A` → `git commit -m "docs: ..."` | 1 分钟 | `git status` 干净 |
| 5 | 推送并看 CI | `git push` → 打开 Actions | 2 分钟 | 最新 run 是绿勾 |

完整命令：

```powershell
cd D:\AI_Project\Deepseek\Creat_Game\ue5-solo-game-skill
git pull
python -m unittest discover -s tests -v
git add -A
git commit -m "docs: 补充 G2 白模闸门的机器基线"
git push
```

**只改一个文件也要走这 5 步。** 流程的价值在于"每次改动都有测试和记录"，不在于改动大小。

### 6.2 什么时候开分支

| 改动 | 直接 push main | 开分支 + PR |
|---|---|---|
| 错别字、失效链接、示例修正 | ✅ | — |
| 单个模板的填写说明 | ✅ | — |
| 改模板固定 H2 章节名 | — | ✅ |
| 改 `gamecheck.py` 判定逻辑/退出码 | — | ✅ |
| 新增模板、新增闸门检查项 | — | ✅ |
| 重命名/删除文件 | — | ✅ |
| 改 CI、LICENSE、发布流程 | — | ✅ |

分支命令与 PR 自审清单见 `CONTRIBUTING.md` 第 4 节。**PR 必须 CI 绿、模板七节填完、至少隔 24 小时再合并**（solo 也给自己冷静期）。

### 6.3 提交信息前缀

| 前缀 | 用于 | 例子 |
|---|---|---|
| `feat` | 新增模板/规则/闸门 | `feat: 新增性能验收单模板` |
| `fix` | 修事实错误、跑不通的命令 | `fix: 修正 G2 盲测人数` |
| `docs` | 只改说明与措辞 | `docs: 补充资产 30 分钟计时口径` |
| `test` | 只改测试 | `test: 补充章节顺序颠倒用例` |
| `chore` | CI、发布、目录整理 | `chore: 发布 v0.1.1` |

详细规范（含破坏性改动写法）见 `CONTRIBUTING.md` 第 3 节。

### 6.4 发布节奏

| 项 | 规则 |
|---|---|
| 频率 | 每 2–4 周发一次 patch/minor；没有使用者可感知的变化就不发 |
| 发版前 | main CI 绿；`CHANGELOG.md` 已把 `[Unreleased]` 整理成版本段；README 徽章版本号同步 |
| 发版动作 | 提交 `chore: 发布 v0.x.y` → 打 tag → push tag → 建 Release（第 5.3 节） |
| 发版后 | 在 Release 说明里写升级方式；自己按第 8.2 节升级一次，确认能装 |

只有"新增阶段/模板/闸门"或"改判定标准"才值得发 minor；纯文字修正攒 2–3 个一起发 patch。

### 6.5 回滚

| 场景 | 命令 | 注意 |
|---|---|---|
| 刚 push 的错误提交 | `git revert <commit-hash>` → `git push` | 生成一个反向提交，历史保留，最安全 |
| 还没 push 的错误提交 | `git reset --soft HEAD~1` | 只动本地，改动回到暂存区 |
| 想临时回到某个 release 看代码 | `git switch --detach v0.1.0` | 看完 `git switch main` 回来，不要在这个状态提交 |
| 已发布版本有严重问题 | 不发新 tag 覆盖；发 `v0.1.1` 修 | Release 说明里标"v0.1.0 存在某某问题，请升级" |
| 误提交了密钥/大文件 | 先更换密钥 → 移除文件 → 必要时用 `git filter-repo` 重写历史 → 强推 | 见第 9.8 节；重写后所有克隆都要重新拉 |

---

## 7. 自动校验（CI）

仓库自带 `.github/workflows/ci.yml`：**每次 push 到 main、每次 PR 都会自动跑单元测试**，在 Windows 与 Ubuntu 两个平台各跑一遍。

| 项 | 内容 |
|---|---|
| 触发 | push 到 main、向 main 提 PR（以 `ci.yml` 的 `on:` 为准） |
| 环境 | windows-latest + ubuntu-latest；Python 3.12（以 ci.yml 的 matrix 为准） |
| 步骤 | checkout 代码 → 配置 Python 3.12 → 运行 `python -m unittest discover -s tests -v` → 校验 `SKILL.md` 的 frontmatter（步骤名以 `ci.yml` 为准） |
| 结果 | 全绿 = 所有测试通过；红叉 = 有测试失败 |

**怎么在网页上看结果**：

1. 打开仓库 → 顶部 **Actions** 标签
2. 左侧选 **CI**（或 workflow 文件名对应的项）
3. 点最近一次运行 → 点对应平台 job → 展开运行测试的那一步（名称以 `ci.yml` 为准，通常是 Run tests）
4. 绿色对勾 = 通过；红色叉 = 失败，日志最后 20 行通常直接指出哪个断言失败

**PR 必须绿**：如果开了分支保护，把 CI 设为 required status check；没开保护时自己看到绿勾再合并。

**本地复现**（CI 红时先本地跑）：

```powershell
python -m unittest discover -s tests -v
```

| 现象 | 最可能原因 | 处理 |
|---|---|---|
| Windows 绿、Ubuntu 红 | 路径大小写或分隔符不一致 | 用 `pathlib` / 正斜杠；文件名大小写与引用一致 |
| 两边都红 | 改坏了逻辑或测试 | 读失败断言，先修代码再提交 |
| Ubuntu 报编码错误 | 文件不是 UTF-8 | 用编辑器另存为 UTF-8（无 BOM） |
| Actions 没触发 | workflow 文件在默认分支之外，或 Actions 被禁用 | 先合并到 main；Settings → Actions 检查 |

---

## 8. 安装与升级 skill

### 8.1 装到不同 agent

先拿到一份仓库（任意位置都行，路径建议纯英文）：

```powershell
New-Item -ItemType Directory -Force D:\AI_Project\skills | Out-Null
git clone https://github.com/ChenWenhui816/ue5-solo-game-skill.git D:\AI_Project\skills\ue5-solo-game-skill
```

| 环境 | 放哪里 | 命令 | 验证 |
|---|---|---|---|
| **DSH** | profile 的技能目录（本机 profile 根目录在 `C:\Users\<用户名>\.dsh\profiles\` 下，具体路径以 DSH 界面/官方文档为准） | 见下方代码块 | 重启会话后技能列表中能看到 `ue5-solo-game` |
| **Claude Code**（全局） | `C:\Users\<用户名>\.claude\skills\ue5-solo-game\` | 见下方代码块 | 会话里能看到 skill 描述 |
| **Claude Code**（项目级） | `<游戏项目>\.claude\skills\ue5-solo-game\` | 把仓库复制进去即可 | 同上 |
| **Codex** | 把 `AGENTS.md` 复制到游戏项目根 | 见下方代码块 | 新会话自动读取项目规则 |
| **Cursor** | 项目根放 `AGENTS.md`；或在 `.cursor/rules/` 加一条指向它（支持情况以 Cursor 官方文档为准） | 复制 `AGENTS.md` | Cursor 对话中能引用到流程 |
| **其他 agent** | 让 agent 先读 `SKILL.md` | — | agent 能说出当前阶段与下一步命令 |

**DSH**（profile 名以本机 `~/.dsh/profiles` 下的实际目录为准，常见为 `desktop`）：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.dsh\profiles\desktop\skills" | Out-Null
Copy-Item -Recurse -Force D:\AI_Project\skills\ue5-solo-game-skill "$env:USERPROFILE\.dsh\profiles\desktop\skills\ue5-solo-game"
Get-ChildItem "$env:USERPROFILE\.dsh\profiles\desktop\skills"
```

部分 DSH 版本不扫描用户 skills 目录，这时走"项目规则"路线：把仓库 `AGENTS.md` 里的路径改成你的实际路径，复制到游戏项目根，效果等同。

**Claude Code**（全局）：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse -Force D:\AI_Project\skills\ue5-solo-game-skill "$env:USERPROFILE\.claude\skills\ue5-solo-game"
```

注意：Claude Code 要求技能目录根下有 `SKILL.md`。本仓库的 `SKILL.md` 已带 `name: ue5-solo-game` 与 `description`，可直接用；目录名与 `name` 不一致时以 `name` 为准（以 Claude Code 官方文档为准）。

**Codex / Cursor**：

项目级的 `AGENTS.md` 由 `gamecheck.py init` 自动生成，不需要从仓库根复制（仓库根的 `AGENTS.md` 是维护本仓库用的，不是游戏项目规则）。生成后打开项目根的 `AGENTS.md`，把引用 skill 的相对路径改成你的实际安装路径（或直接写绝对路径），agent 不支持 skill 目录时也能读到流程。

```powershell
# init 已生成 D:\games\my-game\AGENTS.md；如需重新生成，用 --force（会覆盖同名文件）
python D:\AI_Project\skills\ue5-solo-game-skill\scripts\gamecheck.py init --dir D:\games\my-game --name "我的游戏"
```

**验证安装成功**：

```powershell
python D:\AI_Project\skills\ue5-solo-game-skill\scripts\gamecheck.py --help
python --version
```

- DSH/Claude Code：新会话里说"用 ue5-solo-game skill 帮我推进项目"，能说出阶段路由即成功。
- 任意 agent：能正确执行 `gamecheck.py init` 并在项目里生成 `docs/` 与 `gamecheck.json`。

### 8.2 升级

| 安装方式 | 升级命令 | 注意 |
|---|---|---|
| git clone 后复制进 skills | `cd D:\AI_Project\skills\ue5-solo-game-skill` → `git pull` → 先 `Remove-Item -Recurse -Force <目标技能目录>`，再重新执行 8.1 的 `Copy-Item` | 覆盖会替换旧文件；自己改过的文件会丢，先备份；先删目标目录可避免嵌套成 `ue5-solo-game\ue5-solo-game-skill` |
| 只用 git clone 的目录 | `git pull` | 最省事 |
| 下载 ZIP | 下载最新 Release 的 Source code (zip) → 解压覆盖旧目录 | 覆盖前备份自己改过的文件 |

升级后必验：

```powershell
cd D:\AI_Project\skills\ue5-solo-game-skill
git log --oneline -1
python -m unittest discover -s tests -v
python scripts/gamecheck.py --help
```

看 `CHANGELOG.md` 里有没有 "迁移" 说明；有破坏性改动时按说明改自己项目里的路径。

### 8.3 锁定版本

- git 方式：`git checkout v0.1.0`（进入 detached HEAD，**此状态不能 git pull**；升级时 `git switch main` 再 pull）。
- ZIP 方式：只下载对应版本的 Source code (zip)，不覆盖。
- 在自己游戏项目的 `docs/03_技术方案.md` 或 `AGENTS.md` 里记一行：`skill 版本：v0.1.0`。半年后能查清用的是哪版规则。

---

## 9. 常见问题

### 9.1 中文路径与用户名

- **克隆到纯英文路径**（如 `D:\dev\ue5-solo-game-skill`）。Git 本身支持中文路径，但 Python 脚本、UE、部分编辑器的工具链在含中文/空格的路径下更易出问题。
- `git status` 显示 `\344\270\255` 转义：`git config --global core.quotepath false`。
- 本仓库的模板文件名带中文（如 `01_游戏设计文档.md`），这是设计的一部分，**不要改名**——改名要同步改 `gamecheck.py` 与所有引用。
- 项目路径尽量不用空格；非用不可时命令里加引号：`python "D:\My Game\scripts\gamecheck.py" --help`。

### 9.2 CRLF / LF 换行

`.gitattributes` 已规定：文本一律 `LF`。Windows 上再做一步，避免编辑器把文件改成 CRLF：

```powershell
git config --global core.autocrlf false
```

| 现象 | 原因 | 修复 |
|---|---|---|
| 只改了一个字，`git diff` 却整个文件都变 | 行尾从 LF 变成 CRLF | 设 `core.autocrlf false`，编辑器设 LF；`git add --renormalize .` 后提交 |
| 提交后 GitHub 显示整个文件 diff | 同上的历史遗留 | `git add --renormalize .` → `git commit -m "chore: 统一行尾"` |
| `git diff` 提示 `LF will be replaced by CRLF` | 本地配置与 `.gitattributes` 冲突 | 按上面设 `false`，忽略该提示前先确认 `.gitattributes` 存在 |

### 9.3 大文件与 Git LFS

| 阈值 | GitHub 行为（以官方文档为准） |
|---|---|
| 单个文件 > 50 MB | 推送时警告 |
| 单个文件 > 100 MB | **拒绝推送** |
| 仓库长期 > 1 GB | 建议清理或使用 LFS |

本仓库只有文本文件，正常不会触发。素材（psd/blend/fbx）属于**游戏项目**，不要提交进 skill 仓库。

确实需要版本管理大文件时：

```powershell
git lfs install
git lfs track "*.psd"
git add .gitattributes
git commit -m "chore: 启用 LFS 跟踪 psd"
```

免费额度有限，超出会计费，具体以 GitHub 文档为准：https://docs.github.com/zh/repositories/working-with-files/managing-large-files/about-git-large-file-storage

### 9.4 404 / Repository not found

1. 浏览器直接打开 `git remote -v` 里显示的地址，确认仓库存在。
2. 逐字符核对用户名与仓库名（大小写不敏感于 URL，但拼错就是 404）。
3. 私有仓库：确认当前登录账号有权限；`gh auth status` 看登录的是哪个账号。
4. 远程仓库还没建：回到第 2 节。

### 9.5 权限不足（403）

- PAT 的 scope 只有 `public_repo` 或没勾 `repo` → 重新生成并勾整块 `repo`。
- 用的是组织仓库但没授权 SSO → 在 token 页面点 "Configure SSO" 授权（个人仓库不涉及）。
- 登录账号不是仓库 owner → 检查 `git remote -v` 地址里的用户名。

### 9.6 PAT 过期

现象：昨天还能 push，今天报 `Authentication failed` 或 403。

1. 打开 https://github.com/settings/tokens 看 token 的有效期；过期就 **Generate new token (classic)**，勾 `repo`，复制。
2. 清掉旧凭据：控制面板 → 凭据管理器 → **Windows 凭据** → 找到 `git:https://github.com` → 删除。
3. 再 `git push`，按提示输入新 PAT。

建议在日历里给 token 到期日提前 7 天设提醒；或者干脆用 SSH（不会过期）。

### 9.7 push 被拒（non-fast-forward / fetch first）

```text
! [rejected]        main -> main (fetch first)
error: failed to push some refs to '...'
```

原因：远程有本地没有的提交（例如你在 GitHub 网页上改过文件，或换了机器提交过）。处理：

```powershell
git pull --rebase origin main
git push
```

出现冲突时：打开冲突文件，保留正确内容，删掉 `<<<<<<<` / `=======` / `>>>>>>>` 标记，`git add <文件>` → `git rebase --continue`。

**不要**直接 `git push --force`：会覆盖远程提交。只有在"确定远程提交是误操作且只有你一个人用"时才用 `git push --force-with-lease`。

### 9.8 误提交了不该提交的东西

| 情况 | 处理 |
|---|---|
| 提交了 `__pycache__/`、`out/`、`sample/` 等，**还没 push** | `git rm -r --cached <路径>` → 确认 `.gitignore` 已包含 → `git commit --amend --no-edit` |
| 同上，**已经 push** | 同样 `git rm -r --cached` + 新提交移除；历史里仍有，体积大时再考虑重写 |
| 把带 `.git` 的目录整个复制进来（嵌套仓库） | `Remove-Item -Recurse -Force <子目录>\.git` → 再 `git add` |
| 提交了密钥/token | **立刻去 GitHub 撤销该 token**；再 `pip install git-filter-repo` → `git filter-repo --path <泄露文件> --invert-paths`（提示找不到命令时用 `python -m git_filter_repo`；该工具默认删掉 origin 远程，重写后要 `git remote add origin <地址>` 再 `git push --force-with-lease`）；所有克隆重新拉 |
| 提交了超大文件 | 同上用 `git filter-repo` 从历史移除；否则仓库体积永远降不下来 |

重写历史会改变所有提交哈希，**只有你自己的仓库、且没有别人克隆时**才可接受；做完通知使用者重新 clone。以 GitHub 文档为准：https://docs.github.com/zh/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository

### 9.9 仓库改名 / 转移

1. Settings → General → **Repository name** 改名 → Rename。
2. 旧仓库地址会自动跳转到新地址（GitHub 行为，以官方文档为准），但 README 徽章、文档里的写死链接不会自动改。
3. 本地更新地址：

```powershell
git remote set-url origin https://github.com/ChenWenhui816/<新仓库名>.git
git remote -v
```

4. 全仓搜旧名并替换：编辑器里搜索 `ue5-solo-game-skill`（或旧名），逐个确认；重点看 `README.md` 徽章、`docs/GitHub发布指南.md`、`.github/ISSUE_TEMPLATE/config.yml`。
5. 转移仓库（Settings → General → Danger Zone → Transfer）后，本地地址同样要 `set-url`。

### 9.10 其他常见提示

| 现象 | 原因 | 处理 |
|---|---|---|
| `detected dubious ownership` | 仓库在一个 Windows 认为"不属于当前用户"的目录 | `git config --global --add safe.directory <仓库绝对路径>` |
| `fatal: refusing to merge unrelated histories` | 两边各自有首个提交 | 确认远程是空仓库再 push；确需合并时 `git pull --allow-unrelated-histories` |
| `error: src refspec main does not match any` | 本地还没有提交，或分支不叫 main | 先 commit；`git branch -M main` |
| `git push` 没有任何输出、一直卡住 | 网络或代理问题 | 见 0.3；换 HTTPS/SSH 试 |
| Actions 里没有 CI | workflow 没在默认分支上，或 Actions 被禁用 | 先合并到 main；Settings → Actions 检查 |

---

## 10. 上线检查清单

### 10.1 创建远程仓库前

- [ ] `git status` 干净（working tree clean）
- [ ] `git log --oneline` 至少 1 个提交，提交信息带前缀
- [ ] `git config user.name` / `user.email` 正确
- [ ] `.gitignore` 存在，`git status --ignored` 里 `__pycache__/` 等显示为 ignored
- [ ] 没有单文件 > 10 MB：`git ls-files | ForEach-Object { Get-Item $_ } | Sort-Object Length -Descending | Select-Object -First 10 Name,Length`
- [ ] `README.md` / `LICENSE` / `CHANGELOG.md` / `SKILL.md` 都在仓库根
- [ ] 本地测试绿：`python -m unittest discover -s tests -v`

### 10.2 首次推送前

- [ ] 远程仓库已创建，且**没勾** README / .gitignore / license
- [ ] `git remote -v` 指向 `ChenWenhui816/ue5-solo-game-skill`
- [ ] `git branch --show-current` 输出 `main`
- [ ] 认证方式至少一种可用（浏览器 / PAT / SSH）
- [ ] 网络能访问 github.com

### 10.3 发 Release 前

- [ ] main 上 CI 绿
- [ ] `CHANGELOG.md` 已把 `[Unreleased]` 整理成 `## [0.x.y] - YYYY-MM-DD`
- [ ] README 顶部徽章的版本号与 tag 一致
- [ ] `git tag -l` 有目标版本，且 `git show <tag> --stat` 指向正确提交
- [ ] tag 已 push（`git ls-remote --tags origin` 能看到）
- [ ] Release 说明含"升级方式"；有破坏性改动时含"迁移"
- [ ] 发布后自己按第 8.2 节升级一次并跑通

### 10.4 每次更新前（30 分钟流程的入口）

- [ ] `git pull` 已同步
- [ ] 本地测试绿
- [ ] 本次只改本次要改的文件（`git status` 核对）
- [ ] 新增/改动同步了 `SKILL.md` 路由与 `CHANGELOG.md`
- [ ] push 后 Actions 绿

---

## 附：命令速查表

### 日常（每周 30 分钟）

| 目的 | 命令 |
|---|---|
| 进仓库 | `cd D:\AI_Project\Deepseek\Creat_Game\ue5-solo-game-skill` |
| 同步 | `git pull` |
| 看状态 | `git status` |
| 跑测试 | `python -m unittest discover -s tests -v` |
| 提交 | `git add -A` → `git commit -m "docs: 说明"` |
| 推送 | `git push` |
| 看历史 | `git log --oneline -10` |

### 发布

| 目的 | 命令 |
|---|---|
| 打 tag | `git tag -a v0.1.1 -m "v0.1.1: 一句话"` |
| 推 tag | `git push origin v0.1.1` |
| 看 tag | `git tag -l` / `git show v0.1.1 --stat` |
| 生成 ZIP | `git archive --format=zip --prefix=ue5-solo-game-skill/ -o ..\pkg-v0.1.1.zip HEAD` |
| 回滚提交 | `git revert <hash>` → `git push` |
| 切到某版本 | `git switch --detach v0.1.0` |

### 排障

| 目的 | 命令 |
|---|---|
| 看远程地址 | `git remote -v` |
| 改远程地址 | `git remote set-url origin <地址>` |
| 同步并变基 | `git pull --rebase origin main` |
| 清行尾 | `git add --renormalize .` |
| 大文件排查 | `git count-objects -vH` 看仓库体积；按文件排序的命令见 10.1 节 |
| 测试 SSH | `ssh -T git@github.com` |
| 认证状态 | `gh auth status` |
| 看分支 | `git branch -a` |

### 官方文档

| 主题 | 链接 |
|---|---|
| 创建仓库 | https://docs.github.com/zh/repositories/creating-and-managing-repositories/creating-a-new-repository |
| 推送已有仓库 | https://docs.github.com/zh/get-started/importing-your-projects-to-github/importing-source-code-to-github/adding-locally-hosted-code-to-github |
| PAT | https://docs.github.com/zh/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens |
| SSH 连接 | https://docs.github.com/zh/authentication/connecting-to-github-with-ssh |
| Release | https://docs.github.com/zh/repositories/releasing-projects-on-github/managing-releases-in-a-repository |
| 分支保护 / Rulesets | https://docs.github.com/zh/repositories/configuring-branches-and-merges-in-your-repository |
| 大文件与 LFS | https://docs.github.com/zh/repositories/working-with-files/managing-large-files |
| SemVer（中文） | https://semver.org/lang/zh-CN/ |
