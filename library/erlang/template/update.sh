#!/usr/bin/env bash
# library/erlang/template/update.sh
# 接收版本号，下载上游 Dockerfile，生成 dockerfiles/
set -Eeuo pipefail

cd "$(dirname "$(readlink -f "$BASH_SOURCE")")"

VERSION="$1"

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 28.5.0.6"
    exit 1
fi

# 提取主版本号
MAJOR="${VERSION%%.*}"

# Debian 版本映射（覆盖上游默认值）
case "$MAJOR" in
    24|25) DEBIAN_VERSION="bullseye" ;;
    26|27) DEBIAN_VERSION="bookworm" ;;
    28|29) DEBIAN_VERSION="forky" ;;
    *) echo "ERROR: 不支持的主版本号: $MAJOR"; exit 1 ;;
esac

# 上游仓库
UPSTREAM_REPO="erlang/docker-erlang-otp"
UPSTREAM_BASE="https://raw.githubusercontent.com/${UPSTREAM_REPO}/master"

# 变体 → 上游路径映射
declare -A VARIANT_PATHS=(
    ["debian"]="${MAJOR}/Dockerfile"
    ["debian-slim"]="${MAJOR}/slim/Dockerfile"
    ["alpine"]="${MAJOR}/alpine/Dockerfile"
)

# 下载目录
DOCKERFILES_DIR="../dockerfiles/${VERSION}"

echo "下载上游 Dockerfiles: erlang OTP ${MAJOR}.x (请求版本 ${VERSION})" >&2

for variant in debian debian-slim alpine; do
    upstream_path="${VARIANT_PATHS[$variant]}"
    url="${UPSTREAM_BASE}/${upstream_path}"
    out_dir="${DOCKERFILES_DIR}/${variant}"
    out_file="${out_dir}/Dockerfile"

    mkdir -p "$out_dir"

    echo "  下载 ${variant} ← ${url}" >&2
    if ! curl -fSL --retry 3 --retry-delay 2 -o "$out_file" "$url" 2>/dev/null; then
        echo "ERROR: 下载失败: ${url}" >&2
        exit 1
    fi

    # 验证下载的文件是有效 Dockerfile
    if ! head -1 "$out_file" | grep -q '^FROM'; then
        echo "ERROR: 下载的文件不是有效 Dockerfile: ${out_file}" >&2
        exit 1
    fi

    # debian 变体：替换基础镜像版本（保留 -slim 后缀）
    if [[ "$variant" != "alpine" ]]; then
        sed -i -E "s/^(FROM (buildpack-deps|debian):)(trixie|bookworm|bullseye)(-slim)?/\1${DEBIAN_VERSION}\4/" "$out_file"
    fi

    echo "  ✓ ${variant} → ${out_file}" >&2
done

echo "✓ 所有变体 Dockerfile 已下载" >&2
