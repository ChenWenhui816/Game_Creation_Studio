---
name: game-creation-studio
description: Production controller for a solo UE5 studio (bilingual entry, local visual console, 8 pipelines). Covers concept, standards, script/narrative, whitebox/tech, art/video, music/audio, content production, release/publishing. Use it for UE 5.8 development, AI art/video/audio pipelines, MCP tool bus, dual keyboard+gamepad input, screenshots, testing/packaging and Steam/console release.
---

# UE5 Solo 3D Level-Based Game · Production Controller

> This is the routing layer. **Determine the project's current stage first, then load only the matching references file.** Do not read every document at once.
> All workflow commands: `python <skill>/scripts/gamecheck.py <subcommand> --root <project root>`.
> Visual console: `python scripts/gameconsole.py serve` (see `docs/控制台使用指南.md`).
> Desktop app: `python scripts/console_app.py` (build in `docs/桌面版.md`).
> Studio CLI: `python scripts/studio.py doctor|explain|next` (see `docs/管线/README.md`).
> MCP tool bus: `python scripts/mcp_gateway.py` (see `mcp/README.md`).

## Start here: do these three things first

1. **Confirm the project root**: only a directory with `gamecheck.json` and `docs/` is a project. If it is missing, run `gamecheck.py init` first.
2. **Run the full check once**:
   ```bash
   python <skill>/scripts/gamecheck.py check all --root .
   ```
3. **Locate the stage from the result**: the first failing check is the thing to do now.

If the user only says "I want to make a game" and there is no project yet, start at P0, load `references/01-立项.md`, and run the concept interview. Do not open the engine.

## Iron rules (eight)

1. **The standard book is the only truth.** When code, assets or levels conflict with `docs/01`–`docs/03`, change the implementation, not the book. Changing the book requires a change order.
2. **The user makes three kinds of decisions only**: D1 requirements (what to build, what to cut), D2 assets (pick A/B/C), D3 acceptance (does it enter the game). You decide everything else and record the reasoning in the delivery note.
3. **Never hand-edit the editor, never make the user read code.** Prove results with screenshots, recordings or command output.
4. **Any "improvement" that deviates from the standard** stops first: record it in the "Deviations" section of the delivery note and wait for confirmation.
5. **Numbers live in one place only**: `docs/06_数值表.csv`. Documents and code reference it, never copy it.
6. **A gate only turns green by fixing content** — never by deleting checks, loosening tolerances or skipping sections.
7. **One commit and one runnable build per day.** No rollback point means no batch operation.
8. **Change orders and the asset manifest reconcile both ways.** A change order carries a `CO-001` id and its affected asset ids; the manifest's `source`/`note` cites the same id; `change check` must pass.

## Stage routing table

|Pipeline|Load|Run first|One-line test|
|---|---|---|---|
|P0 Concept|`docs/管线/00_立项/README.md`|`studio explain 00`|No concept doc|
|P1 Standards|`docs/管线/01_标准/README.md`|`gate spec`|G1 not passed|
|P2 Script|`docs/管线/02_剧本/README.md`|`gate script`|SC/SH/LINE ids incomplete|
|P3 Whitebox & tech|`docs/管线/03_概念与美术/README.md`|`gate whitebox`|Cannot run/jump or blind test failed|
|P4 Art & video|`docs/管线/04_测试与技术/README.md`|`gate art`|Manifest/PV doc not passed|
|P5 Music & audio|`docs/管线/05_音乐与音频/README.md`|`gate audio`|MUS/SFX/VO or integration missing|
|P6 Content|`docs/管线/06_内容生产与视频/README.md`|`gate content`|No full playthrough|
|P7 Release|`docs/管线/07_上线与发行/README.md`|`gate release`|Release/store checklist not green|
|Assets / daily screenshots|`docs/管线/04_测试与技术/README.md`|`asset_registry.py scan` / `daily_gallery.py`|Manual import or guessing|
|MCP / tool adoption|`mcp/README.md`|`mcp_gateway.py doctor`|No health/permissions|
|First time / explaining the workflow|`references/00-总览与协作.md`|—|—|

## Standard loop for every task

```
1. Read the standard → find the standard-book section and acceptance criteria for this task; if there is none, stop and write the standard first
2. Post a plan     → one-sentence goal + files to change + acceptance method + expected evidence
3. Execute         → touch only planned files; record deviations instead of deciding them yourself
4. Self-test       → run commands/tests, keep the output
5. Produce evidence → screenshot / recording / command output (at least one)
6. Delivery note   → docs/07_交付单/<id>.md with goal / changes / evidence / known issues / open decisions (≤3)
7. Wait for sign-off → the user signs or lists changes; do not start the next task before sign-off
```

## Gate commands

|Command|Purpose|When|
|---|---|---|
|`gameconsole.py serve`|Open the local visual console|Day one / daily|
|`gameconsole.py serve --project <path>`|Open an existing project|Existing project|
|`gamecheck.py init --dir . --name "Project"`|Scaffold the project|Day one|
|`gamecheck.py doc check --stage N`|Stage documents are complete|Before each stage|
|`gamecheck.py gate spec`|G1 standards frozen|Before work starts, and every Monday|
|`gamecheck.py gate script`|G2 script shootable|End of script/storyboard|
|`gamecheck.py gate whitebox`|G3 whitebox playable|End of whitebox|
|`gamecheck.py gate art`|G4 art/video/PV + manifest|Before asset batch/PV|
|`gamecheck.py gate audio`|G5 audio integrable|After VO/mix/integration|
|`gamecheck.py gate content`|G6 full playthrough|End of content production|
|`gamecheck.py gate release`|G7 release, including automated checks|Before shipping the Demo|
|`gamecheck.py numbers check`|Jump physics is self-consistent|Every numbers change|
|`gamecheck.py manifest check`|Manifest vs directories|Every day|
|`gamecheck.py change check`|Change orders vs the asset manifest, both ways|After every change|

**Read the exit code, not the log.** 0 = pass, 1 = fail, 2 = usage error.

### v0.2.0 additions

|Addition|How to use it|
|---|---|
|**Bilingual entry**|`README.en.md`, this file and `references/en/00-overview.md` are the English route. Detailed references and templates stay Chinese-first; translate the section you need on demand instead of inventing English equivalents|
|**UE Python asset import**|`scripts/ue_import_assets.py` imports a batch through the editor's Python API and sets materials, collision and LOD from `docs/05_资产清单.csv`; run it with `--help` for the options of the installed version|
|**Daily screenshot tour**|`scripts/daily_gallery.py` turns a folder of automated screenshots into one page; it is the artefact the user reviews on Friday (D3)|
|**Keyboard & mouse + gamepad**|Every action is bound on both devices with Enhanced Input, every menu is gamepad-navigable, UI prompts follow the last used device. Treat a missing gamepad path as a defect, not a polish item|
|**Change order ↔ asset manifest**|`change check` cross-checks change orders against the asset manifest both ways; a change that adds, removes or re-specifies assets must reconcile|
|**Automated release checks**|`gate release` proves what it can from files (store assets, localization, build) instead of trusting ticked boxes|
|**Multilingual store assets**|`templates/13_多语言商店素材清单.md` covers per-language capsule art, screenshots, trailer, subtitles and copy; `gate release` checks the files|

## Output discipline

Every task ends with a delivery note at `docs/07_交付单/<id>.md` with eight sections: Goal / Changes / Evidence / Self-test / Known issues / Deviations / Open decisions (≤3) / Next step. A delivery note without evidence counts as not done.

When accepting an asset or a system, use `docs/08_验收单/<name>.md` with four sections: Asset info / Spec check / In-game verification / Verdict. The verdict is either "Pass" or "Rejected", and a rejection must list the rejected items.

Any change to scope, numbers or style, or anything that costs more than one day of work, goes into a change order (`docs/09_变更单/<id>.md`) before it is executed.

## Prohibitions

- Turning a gate green by deleting checks, loosening tolerances or skipping sections
- Committing directly to `main`, deleting `art/Source/`, or upgrading the UE engine version
- Batch-generating more than 12 assets, or changing more than 3 systems at once, without confirmation
- Using "feels better", "more consistent" or "close enough" as an acceptance reason
- Changing requirements verbally in chat; every change goes into a change order
- Importing raw AI image-to-3D meshes into the game (retopology and re-UV are mandatory)
- Shipping a build whose gamepad path was never tested, or whose store assets exist in one language only

## File index

|File|Contents|
|---|---|
|`references/00-总览与协作.md`|Governance overview, three decision types, gates, weekly rhythm, cost model (8 pipelines in docs/管线)|
|`references/01-立项.md`|P0: from an idea to a one-page concept doc|
|`references/02-文档与标准.md`|P1: GDD / art bible / tech plan / numbers / change orders|
|`references/03-美术资产管线.md`|P3: concept → 3D → textures → rigging → UE import|
|`references/04-引擎实现.md`|P2–P4: project setup, whitebox, systems, levels, packaging|
|`references/05-打磨与Demo上线.md`|P5: polish, Steam/Epic, release checklist|
|`references/06-风险与反模式.md`|20 traps, the cut protocol, retrospectives|
|`references/en/00-overview.md`|English overview of the six stages, gates, pipelines and cost model|
|`templates/`|18 templates you can fill in directly|
|`scripts/gamecheck.py`|Gate validator (standard library, no dependencies)|
|`scripts/gameconsole.py`|Local visual console: wizard, stages, save/freeze/next, agent inbox|
|`scripts/console_app.py`|Windows desktop entry (pywebview / WebView2)|
|`scripts/version.py`|Single version source + GitHub update check|
|`build/desktop.spec`|PyInstaller build spec|
|`docs/桌面版.md`|Desktop build, distribution and update|
|`docs/安装包与签名.md`|Inno Setup installer and code signing|
|`build/installer.iss`|Inno Setup definition|
|`build/sign.ps1`|Optional code signing (skips without cert)|
|`console_web/`|Console frontend (no build step)|
|`docs/控制台使用指南.md`|Full console guide|
|`scripts/ue_import_assets.py`|UE editor Python: batch import with material / collision / LOD setup|
|`scripts/daily_gallery.py`|Daily screenshot tour builder|
|`docs/设计说明.md`|Why the workflow is designed this way|
|`docs/GitHub发布指南.md`|Release and iteration|

---

**Languages:** [English](SKILL.en.md) · [中文](SKILL.md)
