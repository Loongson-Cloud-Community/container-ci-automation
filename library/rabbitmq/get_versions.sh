#!/bin/bash
# library/rabbitmq/get_versions.sh
# 输出活跃版本线的最新 patch 版本号（每行一个，完整版本如 4.4.0）
set -eo pipefail

# 跟踪的版本线（次版本号，空格分隔；按需扩展，如 "4.3 4.4"）
# 注意：启用多版本线时 latest / {major_version} 标签会互相覆盖，需评估 config.yml tags
MINOR_LINES="4.4"

RABBITMQ_SERVER_REPO='https://github.com/rabbitmq/rabbitmq-server.git'

for line in $MINOR_LINES; do
    # 该版本线的全部 tag（排除 rc/beta/milestone），新版本在前
    candidates=$(git ls-remote --tags "$RABBITMQ_SERVER_REPO" \
        "refs/tags/v${line}" "refs/tags/v${line}.*" \
        | cut -d'/' -f3 | cut -d'^' -f1 \
        | grep -E "^v${line//./\\.}\.[0-9]+$" \
        | sed 's/^v//' \
        | sort -uVr)

    # 取第一个 release 资产真实存在的版本（tag 可能先于资产上传）
    for v in $candidates; do
        if wget --spider -q "https://github.com/rabbitmq/rabbitmq-server/releases/download/v${v}/rabbitmq-server-generic-unix-latest-toolchain-${v}.tar.xz" 2>/dev/null; then
            echo "$v"
            break
        fi
    done
done
