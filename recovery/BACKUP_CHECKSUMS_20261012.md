# Backup checksum manifest — 2026-10-12

**Repository:** `Asanda021/StructuralPro-Recovery`
**Source snapshot commit:** `19e63bc05d11fc34d85d464ee02c90414e2ca296`

The following two backups were independently checksum-verified and are stored in the owner's ChatGPT Library folder `/StructuralPro_Recovery_Backup_20261012`:

| Artifact | SHA-256 |
|---|---|
| `StructuralPro_Complete_Recovery_Backup_20261012.zip` | `3341438dca1aaa5c45bacb6157faa014c89990a8d0d344c9af85568bc3d1b45e` |
| `StructuralPro_Recovery_Git_20261012.bundle` | `d5d3eb97d9e89b5094763b942bff0a7c2f071db916237e6aedfc3117e1ec32b9` |
| `StructuralPro_GitHubReady_20261012.zip` | `b47abbc26b3f3e356cf0c8e449eef87dfd6dcfd54abb4932c43781710472be79` |

**Verification:** ZIP CRC passed; git bundle verified and fetched into a fresh temporary Git repository with 1,480 tracked files.

**Important:** Git bundle contains a self-contained *local* source recovery history (HEAD `0db9e2d7dff9fe7179008826fab2e646d34ec9e3`), not the lost original repository's Git history and not a mirror of remote source snapshot commit. The content is provisional; complete PR #481 recovery and Windows UI/report tests remain unverified.

**Safety:** 193 legacy workflows are quarantined at `recovery/disabled_workflows`, and no active GitHub Actions workflows should be present. Do not activate release pipelines without owner authorization.
