#!/bin/bash
# library/debian/template/update.sh
# 接收版本号，构建 rootfs，生成 versions.json
set -eo pipefail

cd "$(dirname "$(readlink -f "$BASH_SOURCE")")"

VERSION="$1"

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 20250521T073957Z"
    exit 1
fi

# 验证版本格式
if [[ ! "$VERSION" =~ ^[0-9]{8}T[0-9]{6}Z$ ]]; then
    echo "ERROR: Invalid version format: $VERSION"
    echo "Expected format: 20250501T015255Z"
    exit 1
fi

# ===== 变体版本集中管理 =====
DEBIAN_VERSION="14"
DEBIAN_VERSION_NAME="forky"
SUITE="unstable"
ARCH="loong64"

# 版本名映射（备用）
declare -A VERSION_NAMES=(
    ["14"]="forky"
    ["13"]="trixie"
    ["12"]="bookworm"
    ["11"]="bullseye"
    ["10"]="buster"
)
DEBIAN_VERSION_NAME="${VERSION_NAMES[$DEBIAN_VERSION]}"

echo "Building rootfs for Debian $DEBIAN_VERSION ($DEBIAN_VERSION_NAME)"

# 创建输出目录
mkdir -p out

# 转换时间格式
format_time() {
    echo "$1" | sed -E 's/([0-9]{4})([0-9]{2})([0-9]{2})T([0-9]{2})([0-9]{2})([0-9]{2})/\1-\2-\3T\4:\5:\6/'
}

# 构建 rootfs
formatted=$(format_time "$VERSION")
timestamp=$(date -d "$formatted" +%s)

echo "Building rootfs with debuerreotype..."

# 上游 debuerreotype/debuerreotype 官方镜像只发布 linux/amd64，
# loong64 上 docker pull 报 "no matching manifest for linux/loong64"（run 42407710865）。
# 本机没有该镜像（或架构不符）时，从上游源码用 debian:forky（loong64）构建同名本地镜像。
DEBUERREOTYPE_IMAGE='debuerreotype/debuerreotype:latest'
image_arch="$(docker image inspect --format '{{.Architecture}}' "$DEBUERREOTYPE_IMAGE" 2>/dev/null || true)"
if [ "$image_arch" != "$ARCH" ]; then
    echo "Local $DEBUERREOTYPE_IMAGE unavailable (arch=${image_arch:-none}), building it from source..."
    build_dir="$(mktemp -d)"
    git clone --depth 1 https://github.com/debuerreotype/debuerreotype.git "$build_dir/src"

    # 构建上下文只放运行 examples/debian.sh 需要的内容
    ctx="$build_dir/ctx"
    mkdir -p "$ctx"
    cp -a "$build_dir/src/scripts" "$build_dir/src/examples" "$build_dir/src/VERSION" "$ctx/"

    cat > "$ctx/Dockerfile" <<EOF
FROM debian:$DEBIAN_VERSION_NAME
RUN set -eux; \\
    apt-get update; \\
    apt-get install -y --no-install-recommends \\
        debootstrap \\
        wget ca-certificates \\
        xz-utils \\
        gnupg dirmngr \\
        gpgv \\
    ; \\
    rm -rf /var/lib/apt/lists/*
ENV WGETRC /.wgetrc
RUN echo 'hsts=0' >> "\$WGETRC"
ENV DEBUERREOTYPE_DIRECTORY /opt/debuerreotype
COPY . \$DEBUERREOTYPE_DIRECTORY
RUN set -eux; \\
    cd "\$DEBUERREOTYPE_DIRECTORY/scripts"; \\
    for f in debuerreotype-*; do \\
        ln -svL "\$PWD/\$f" "/usr/local/bin/\$f"; \\
    done
WORKDIR /tmp
EOF

    docker buildx build --platform "linux/$ARCH" --load -t "$DEBUERREOTYPE_IMAGE" "$ctx"
    rm -rf "$build_dir"
fi

docker run --privileged -v "$(pwd)/out":/v -w /v \
    -e https_proxy="$https_proxy" \
    -e http_proxy="$http_proxy" \
    "$DEBUERREOTYPE_IMAGE" \
    /opt/debuerreotype/examples/debian.sh --arch "$ARCH" . "$SUITE" "@$timestamp"

echo "Rootfs built successfully"

# 生成 versions.json
if [[ -f versions.json ]]; then
    json=$(< versions.json)
else
    json='{}'
fi

json=$(echo "$json" | jq -c \
    --arg v "$VERSION" \
    --arg debian_ver "$DEBIAN_VERSION" \
    --arg debian_name "$DEBIAN_VERSION_NAME" \
    --arg suite "$SUITE" \
    --arg arch "$ARCH" \
    '.[$v] = {
        version: $v,
        debian_version: $debian_ver,
        debian_version_name: $debian_name,
        suite: $suite,
        arch: $arch
    }')

echo "$json" | jq -S . > versions.json

echo "Version info saved to versions.json"
