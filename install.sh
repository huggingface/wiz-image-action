#!/usr/bin/env bash
# Downloads the Wiz CLI to a fixed path under RUNNER_TEMP. Both actions in this repository
# call this script, so whichever runs second reuses the binary. The runner empties
# RUNNER_TEMP between jobs, so this is one download per job.
#
# There is no version argument because Wiz serves no versioned download path: every
# /v1/wizcli/<version>/ URL answers 403, so `latest` is the only reference that exists.
set -euo pipefail

dir="${RUNNER_TEMP}/wiz-image-action"
cli="${dir}/wizcli"

if [ -x "$cli" ]; then
  echo "The Wiz CLI is already installed at ${cli}."
  exit 0
fi

os=$(uname -s | tr '[:upper:]' '[:lower:]')
case "$(uname -m)" in
  x86_64 | amd64) arch=amd64 ;;
  aarch64 | arm64) arch=arm64 ;;
  *)
    echo "::error title=Wiz CLI::The architecture $(uname -m) is not supported."
    exit 1
    ;;
esac

mkdir -p "$dir"
# The binary is around 270 MiB, so resume rather than start again after a drop.
curl -sSfL --retry 3 --retry-all-errors -C - -o "$cli" \
  "https://downloads.wiz.io/v1/wizcli/latest/wizcli-${os}-${arch}"
chmod +x "$cli"
