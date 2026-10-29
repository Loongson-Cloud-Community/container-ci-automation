#!/usr/bin/env bash
# library/rabbitmq/template/apply-templates.sh
# 接收版本号，读取 versions.json，使用 sed 渲染 4 个变体模板并复制 entrypoint / conf.d
set -Eeuo pipefail

VERSION="$1"

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 4.4.0"
    exit 1
fi
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$BASH_SOURCE")")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKERFILES_DIR="$PROJECT_DIR/dockerfiles"

if [[ ! -f "$SCRIPT_DIR/versions.json" ]]; then
    echo "ERROR: versions.json not found. Run update.sh first."
    exit 1
fi

# 从 versions.json 提取变量
V_VERSION=$(jq -r --arg v "$VERSION" '.[$v].version // empty' "$SCRIPT_DIR/versions.json")
V_OTP_VERSION=$(jq -r --arg v "$VERSION" '.[$v].otp_version // empty' "$SCRIPT_DIR/versions.json")
V_OTP_SHA256=$(jq -r --arg v "$VERSION" '.[$v].otp_sha256 // empty' "$SCRIPT_DIR/versions.json")
V_OPENSSL_VERSION=$(jq -r --arg v "$VERSION" '.[$v].openssl_version // empty' "$SCRIPT_DIR/versions.json")
V_OPENSSL_SHA256=$(jq -r --arg v "$VERSION" '.[$v].openssl_sha256 // empty' "$SCRIPT_DIR/versions.json")
V_DEBIAN=$(jq -r --arg v "$VERSION" '.[$v].debian_version // empty' "$SCRIPT_DIR/versions.json")
V_ALPINE=$(jq -r --arg v "$VERSION" '.[$v].alpine_version // empty' "$SCRIPT_DIR/versions.json")
# rabbitmqadmin（loongarch64-releases 构建）：gnu 配 debian 变体，musl 配 alpine 变体
V_ADMIN_GNU_URL=$(jq -r --arg v "$VERSION" '.[$v].rabbitmqadmin.gnu.url // empty' "$SCRIPT_DIR/versions.json")
V_ADMIN_GNU_SHA=$(jq -r --arg v "$VERSION" '.[$v].rabbitmqadmin.gnu.sha256 // empty' "$SCRIPT_DIR/versions.json")
V_ADMIN_MUSL_URL=$(jq -r --arg v "$VERSION" '.[$v].rabbitmqadmin.musl.url // empty' "$SCRIPT_DIR/versions.json")
V_ADMIN_MUSL_SHA=$(jq -r --arg v "$VERSION" '.[$v].rabbitmqadmin.musl.sha256 // empty' "$SCRIPT_DIR/versions.json")

if [[ -z "$V_VERSION" ]]; then
    echo "ERROR: Version $VERSION not found in versions.json"
    exit 1
fi

echo "Generating Dockerfiles for rabbitmq $V_VERSION"
echo "  OTP: $V_OTP_VERSION  OpenSSL: $V_OPENSSL_VERSION"
echo "  Debian: $V_DEBIAN  Alpine: $V_ALPINE"

# 渲染后校验：不允许残留任何本项目已知占位符
KNOWN_PLACEHOLDERS='{VERSION}|{OTP_VERSION}|{OTP_SOURCE_SHA256}|{OPENSSL_VERSION}|{OPENSSL_SOURCE_SHA256}|{DEBIAN_VERSION}|{ALPINE_VERSION}|{RABBITMQADMIN_URL}|{RABBITMQADMIN_SHA256}'

render() {
    # render <template> <variant-dir> [admin_url] [admin_sha256]
    local template="$1" variant="$2" admin_url="${3:-}" admin_sha="${4:-}"
    local out_dir="$DOCKERFILES_DIR/$VERSION/$variant"
    mkdir -p "$out_dir"
    sed \
        -e "s/{VERSION}/$V_VERSION/g" \
        -e "s/{OTP_VERSION}/$V_OTP_VERSION/g" \
        -e "s/{OTP_SOURCE_SHA256}/$V_OTP_SHA256/g" \
        -e "s/{OPENSSL_VERSION}/$V_OPENSSL_VERSION/g" \
        -e "s/{OPENSSL_SOURCE_SHA256}/$V_OPENSSL_SHA256/g" \
        -e "s|{RABBITMQADMIN_URL}|$admin_url|g" \
        -e "s/{RABBITMQADMIN_SHA256}/$admin_sha/g" \
        -e "s/{DEBIAN_VERSION}/$V_DEBIAN/g" \
        -e "s/{ALPINE_VERSION}/$V_ALPINE/g" \
        "$SCRIPT_DIR/$template" > "$out_dir/Dockerfile"
    if grep -qE "$KNOWN_PLACEHOLDERS" "$out_dir/Dockerfile"; then
        echo "ERROR: $out_dir/Dockerfile 有未替换的占位符:"
        grep -nE "$KNOWN_PLACEHOLDERS" "$out_dir/Dockerfile"
        exit 1
    fi
    echo "  dockerfiles/$VERSION/$variant/Dockerfile"
}

# Debian 变体
render Dockerfile-debian.template debian
cp "$SCRIPT_DIR/docker-entrypoint.sh" "$DOCKERFILES_DIR/$VERSION/debian/docker-entrypoint.sh"
cp "$SCRIPT_DIR"/conf.d/*.conf "$DOCKERFILES_DIR/$VERSION/debian/"

# Debian management 变体（FROM 本地 debian 变体镜像，无需 entrypoint/conf 副本；rabbitmqadmin 用 gnu 构建）
render Dockerfile-management.template management "$V_ADMIN_GNU_URL" "$V_ADMIN_GNU_SHA"

# Alpine 变体
render Dockerfile-alpine.template alpine
# 上游 apply-templates.sh 对 alpine 的 entrypoint 做 gosu → su-exec 替换
sed -e 's/gosu/su-exec/g' "$SCRIPT_DIR/docker-entrypoint.sh" > "$DOCKERFILES_DIR/$VERSION/alpine/docker-entrypoint.sh"
cp "$SCRIPT_DIR"/conf.d/*.conf "$DOCKERFILES_DIR/$VERSION/alpine/"

# Alpine management 变体（FROM 本地 alpine 变体镜像；rabbitmqadmin 用 musl 静态构建）
render Dockerfile-alpine-management.template alpine-management "$V_ADMIN_MUSL_URL" "$V_ADMIN_MUSL_SHA"

echo "Done."
