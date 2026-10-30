#!/usr/bin/env bash
# library/postgres/template/update.sh
# 接收完整版本号（如 18.6）：
#   1. 从 apt.postgresql.org 的 forky-pgdg 仓库取该版本的 apt 包版本与官方架构列表
#   2. 从 ftp.postgresql.org 取源码 tarball 的 sha256（alpine 变体源码编译用）
#   3. 合并写入 versions.json
set -Eeuo pipefail
cd "$(dirname "$(readlink -f "$BASH_SOURCE")")"

VERSION="$1"

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 18.6"
    exit 1
fi

if [[ -f versions.json ]] && [[ -s versions.json ]]; then
    json=$(< versions.json)
else
    json='{}'
fi

# 变体版本（集中管理；loong64 平台硬约束，见 docs/01 关键约束 6/7）
debian_version="forky"   # Debian 统一 forky；apt.postgresql.org 对应仓库为 forky-pgdg
alpine_version="3.24"    # 只跟上游最新 alpine
gosu_version="1.20"      # 上游 1.19 无 loong64 资产；1.20 起官方提供（签名密钥不变）
llvm_version="18"        # 上游 alpine 模板写死 21；loongarch64 仓库最高只有 llvm18/clang18

MAJOR="${VERSION%%.*}"
PGDG_SUITE="$debian_version-pgdg"
packages_url="http://apt.postgresql.org/pub/repos/apt/dists/$PGDG_SUITE/main/binary-loong64/Packages.bz2"
release_url="http://apt.postgresql.org/pub/repos/apt/dists/$PGDG_SUITE/Release"

# === 该版本的 apt 包版本（如 18.6-1.pgdg14+2） ===
apt_version="$(
    curl -fsSL "$packages_url" | bunzip2 \
        | awk -F ': ' -v pkg="postgresql-$MAJOR" -v ver="$VERSION" '
            $1 == "Package" { p = $2 }
            $1 == "Version" && p == pkg && index($2, ver "-") == 1 { print $2 }
        ' | sort -V | tail -1
)"
if [[ -z "$apt_version" ]]; then
    echo "error: $PGDG_SUITE (binary-loong64) 中没有 postgresql-$MAJOR=$VERSION" >&2
    exit 1
fi

# === 仓库官方构建的架构列表（Dockerfile case 判断用） ===
# 先取回再解析：awk 里直接 exit 会提前关管道，curl 报 23 + pipefail 让脚本失败
release="$(curl -fsSL "$release_url")"
arches="$(gawk -F ':[[:space:]]+' '$1 == "Architectures" { print $2; exit }' <<<"$release")"
if [[ -z "$arches" ]]; then
    echo "error: 无法获取 $PGDG_SUITE 的 Architectures" >&2
    exit 1
fi

# === 源码 tarball 校验和（alpine 变体源码编译用） ===
sha256="$(
    curl -fsSL "https://ftp.postgresql.org/pub/source/v${VERSION}/postgresql-${VERSION}.tar.bz2.sha256" \
        | cut -d' ' -f1
)"
if ! [[ "$sha256" =~ ^[0-9a-f]{64}$ ]]; then
    echo "error: 获取 postgresql-$VERSION 的 sha256 失败" >&2
    exit 1
fi

echo "  apt_version: $apt_version" >&2
echo "  arches: $arches" >&2
echo "  sha256: $sha256" >&2

# === 构建版本数据 ===
new_data=$(
    jq -n \
        --arg version "$VERSION" \
        --argjson major "$MAJOR" \
        --arg apt_version "$apt_version" \
        --arg arches "$arches" \
        --arg sha256 "$sha256" \
        --arg debian_version "$debian_version" \
        --arg alpine_version "$alpine_version" \
        --arg gosu_version "$gosu_version" \
        --arg llvm_version "$llvm_version" \
        '{
            version: $version,
            major: $major,
            apt_version: $apt_version,
            arches: ($arches | split(" ")),
            sha256: $sha256,
            debian_version: $debian_version,
            alpine_version: $alpine_version,
            gosu_version: $gosu_version,
            llvm_version: $llvm_version
        }'
)

json=$(echo "$json" | jq -c --argjson d "$new_data" '.[$d.version] = $d')
echo "$json" | jq -S . > versions.json

echo "Version info saved to versions.json" >&2
