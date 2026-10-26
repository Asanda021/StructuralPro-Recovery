# Deprecated: the four-tier model downloader is forbidden for unified StructuralPro.
# Keep this compatibility path explicitly fail-closed; never download weights or
# mislabel their copyright licenses. Use an independently reviewed, verified
# staging directory and build_windows_edition.ps1 -Edition unified instead.
param([string]$Payload,[string]$Edition)
throw "Legacy AI model auto-download/tier bundling is disabled. Supply approved local assets to the unified Windows preflight."
