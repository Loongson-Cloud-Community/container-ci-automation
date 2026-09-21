#!/usr/bin/env bash
# library/erlang/template/apply-templates.sh
# 空操作：Dockerfile 由 update.sh 直接从上游下载，无需模板渲染
set -Eeuo pipefail

echo "✓ apply-templates.sh: 无需操作（Dockerfile 已由 update.sh 下载）" >&2
