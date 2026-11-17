# Code signing policy

Free code signing provided by [SignPath.io](https://signpath.io), certificate by [SignPath Foundation](https://signpath.org/).

## Scope

This policy applies to Windows release artifacts of Game_Creation_Studio:

- Game_Creation_Studio.exe
- Game_Creation_Studio-<version>-setup.exe

## Roles

| Role | Person / account |
|---|---|
| Authors | ChenWenhui816 |
| Reviewers | ChenWenhui816 |
| Approvers | ChenWenhui816 |

Every SignPath signing request requires a manual approval by the Approver.

## Build origin

- Builds run on GitHub-hosted runners via GitHub Actions.
- Source: https://github.com/ChenWenhui816/Game_Creation_Studio
- SignPath GitHub App is restricted to this repository.
- The signing request is created from the artifact uploaded by the same workflow run.

## Privacy

Release build artifacts are uploaded to SignPath for signing. No end-user personal data is included.
Project source and release notes are public under the MIT license.

## Contact

GitHub: https://github.com/ChenWenhui816
