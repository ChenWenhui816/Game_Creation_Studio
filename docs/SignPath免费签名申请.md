# SignPath 免费签名申请 / SignPath Foundation

> 目标：不买证书，让公开发布的 Windows 安装包用可信证书签名。
> 证书由 SignPath Foundation 签发，发布者显示 SignPath Foundation。
> 项目必须开源；本仓库为 MIT。

## 1. 需要你做的 3 个外部动作

我不能替你注册/授权账号，但仓库这边已经配置好。你只需要：

1. 打开 https://signpath.org/apply
2. 用 GitHub 登录并提交仓库：
   https://github.com/ChenWenhui816/Personal_Game_Studio_UE
3. 审核通过后安装 SignPath GitHub App，允许访问该仓库。

## 2. 申请时可直接填写

Code signing policy URL（可直接填）：
https://github.com/ChenWenhui816/Personal_Game_Studio_UE/blob/main/CODE_SIGNING.md


| 字段 | 建议填写 |
|---|---|
| Project / repository | https://github.com/ChenWenhui816/Personal_Game_Studio_UE |
| License | MIT |
| Project type | Desktop application / game development tool |
| Description | A local-first one-person UE5 game studio console: project stages, gates, agent handoff and document editing. |
| Release | https://github.com/ChenWenhui816/Personal_Game_Studio_UE/releases |
| Build system | GitHub Actions |
| Signing policy | release-signing |
| Artifact configs | app, installer |

申请说明可写：

---
Personal_Game_Studio_UE is an MIT-licensed, actively maintained local-first
game studio console. It ships a Windows PyInstaller app plus an Inno Setup
installer. All release builds run on GitHub-hosted runners. We want to sign
both the main executable and the installer so users do not get Unknown
Publisher warnings. The certificate will be used only for official releases
from this repository.
---

## 3. 审核通过后创建

在 SignPath 控制台创建：

- Organization：Personal Game Studio
- Project slug：personal-game-studio-ue
- Signing policy slug：release-signing
- Artifact configuration slug：app
  - 粘贴 .signpath/artifact-configurations/app.xml
- Artifact configuration slug：installer
  - 粘贴 .signpath/artifact-configurations/installer.xml

## 4. GitHub 设置

Repository -> Settings -> Secrets and variables -> Actions：

Variables：

- SIGNPATH_ORGANIZATION_ID
- SIGNPATH_PROJECT_SLUG = personal-game-studio-ue
- SIGNPATH_SIGNING_POLICY_SLUG = release-signing

Secret：

- SIGNPATH_API_TOKEN（SignPath 控制台创建 API token）

## 5. 发布

打 tag 后：

- 如果 SIGNPATH_PROJECT_SLUG 没配置：走原来的未签名 build-desktop；
- 如果配置了：走 .github/workflows/signpath-windows.yml，先签 exe，再用签好的 exe 打 Inno Setup，再签 setup；
- SignPath 每次发布需要维护者人工批准（Foundation 规则）；
- 最终 release 会包含已签名 exe 和 setup。

## 6. 当前已有文件

- .github/workflows/signpath-windows.yml
- .signpath/artifact-configurations/app.xml
- .signpath/artifact-configurations/installer.xml

## 7. 重要限制

- 签名证书属于 SignPath Foundation，不是个人；
- 每次 release 需要人工批准；
- SmartScreen 信誉仍需下载量积累，但不再是未知发布者；
- 申请审核需要时间，通常不是当天；
- SignPath 可能关注项目的公开使用/维护声誉；新仓库没有 star/用户时可能被要求补充材料或被拒；
- 若被拒：自签名仅本机可用，公共免费路径改为 Microsoft Store MSIX（商店重签）；
- 不想上架 Microsoft Store 的情况下，SignPath 是免费公共可信签名的主要路径。
