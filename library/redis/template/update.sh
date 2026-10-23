#!/usr/bin/env bash
# library/redis/template/update.sh
# 接收版本号，获取 redis-full.tar.gz 的 URL 与校验和，生成 versions.json
# 注: 8.x 起上游改用 GitHub release 资产 redis-full.tar.gz（含 modules 子模块），
#     不是 download.redis.io 的 redis-x.y.z.tar.gz（两者 sha256 不同）。
#     URL 模式取自上游 .redis.version.json；sha256 由本地下载计算——
#     不依赖 GitHub API（匿名限流 60 次/小时，共享出口 IP 容易耗尽）。
set -Eeuo pipefail
cd "$(dirname "$(readlink -f "$BASH_SOURCE")")"

VERSION="$1"

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 8.10.2"
    exit 1
fi

if [[ -f versions.json ]] && [[ -s versions.json ]]; then
    json=$(< versions.json)
else
    json='{}'
fi

# 变体版本（集中管理）
debian_version="forky"
alpine_version="3.24"

# === 获取下载 URL 与 SHA256 ===
URL="https://github.com/redis/redis/releases/download/${VERSION}/redis-full.tar.gz"

echo "Downloading $URL to compute sha256..." >&2
TMP_TAR=$(mktemp)
trap 'rm -f "$TMP_TAR"' EXIT
if ! wget -qO "$TMP_TAR" "$URL"; then
    echo "error: redis $VERSION 的 release 资产 redis-full.tar.gz 不存在（或下载失败）"
    exit 1
fi
SHA256=$(sha256sum "$TMP_TAR" | cut -d' ' -f1)

echo "URL: $URL" >&2
echo "SHA256: $SHA256" >&2

# === 构建版本数据 ===
new_data=$(
    jq -n \
        --arg version "$VERSION" \
        --arg url "$URL" \
        --arg sha256 "$SHA256" \
        --arg debian_version "$debian_version" \
        --arg alpine_version "$alpine_version" \
        '{
            version: $version,
            url: $url,
            sha256: $sha256,
            debian_version: $debian_version,
            alpine_version: $alpine_version
        }'
)

json=$(echo "$json" | jq -c --argjson d "$new_data" '.[$d.version] = $d')
echo "$json" | jq -S . > versions.json

echo "Version info saved to versions.json" >&2
