#!/usr/bin/env bash
# library/rabbitmq/template/update.sh
# 接收完整版本号（如 4.4.0），确定该版本线所需的 OTP / OpenSSL 版本与校验和，生成 versions.json
# 注: 校验和均从 GitHub release 资产下载小文件（SHA256.txt / .sha256）获取，
#     不依赖 GitHub API（匿名限流 60 次/小时，共享出口 IP 容易耗尽）。
set -Eeuo pipefail
cd "$(dirname "$(readlink -f "$BASH_SOURCE")")"

VERSION="$1"

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 4.4.0"
    exit 1
fi

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: Invalid version format: $VERSION (expected X.Y.Z)"
    exit 1
fi

# 该版本线（X.Y）所需的 OTP 主版本
# 来源: https://www.rabbitmq.com/which-erlang.html（"Maximum supported Erlang/OTP"），与上游 versions.sh 的 otpMajors 对齐
case "${VERSION%.*}" in
    4.0|4.1|4.2|4.3) OTP_MAJOR=27 ;;
    4.4) OTP_MAJOR=29 ;;
    *)
        echo "ERROR: 未知版本线 ${VERSION%.*}，请在 update.sh 的 case 中补充其 OTP 主版本"
        exit 1
        ;;
esac

# OpenSSL 主版本（当前所有 4.x 线均为 3.5，与上游 versions.sh 的 opensslMajors 对齐）
OPENSSL_MAJOR="3.5"

# 变体基础镜像版本（集中管理；Debian 统一 forky 为 loong64 平台硬约束，不随上游 ubuntu 版本变化）
debian_version="forky"
alpine_version="3.24"

# === OTP: 取该主版本下最新且 release 资产可用的版本 ===
otpVersion=
otpSha256=
while read -r possibleVersion; do
    [[ -n "$possibleVersion" ]] || continue
    if otpSha256=$(wget -qO- "https://github.com/erlang/otp/releases/download/OTP-${possibleVersion}/SHA256.txt" \
        | awk -v v="$possibleVersion" '$2 == "otp_src_" v ".tar.gz" { print $1 }') && [[ -n "$otpSha256" ]]; then
        otpVersion="$possibleVersion"
        break
    fi
done < <(git ls-remote --tags https://github.com/erlang/otp.git "refs/tags/OTP-${OTP_MAJOR}.*" \
    | cut -d'/' -f3- | cut -d'^' -f1 | cut -d- -f2- \
    | sort -urV)

if [[ -z "$otpVersion" ]]; then
    echo "ERROR: 无法确定 OTP ${OTP_MAJOR} 的版本（网络或上游资产问题）"
    exit 1
fi

# === OpenSSL: 取该主版本下最新正式版（排除 alpha/beta） ===
opensslVersion=
opensslSha256=
while read -r possibleVersion; do
    [[ -n "$possibleVersion" ]] || continue
    if opensslSha256=$(wget -qO- "https://github.com/openssl/openssl/releases/download/openssl-${possibleVersion}/openssl-${possibleVersion}.tar.gz.sha256") && [[ -n "$opensslSha256" ]]; then
        opensslVersion="$possibleVersion"
        break
    fi
done < <(git ls-remote --tags https://github.com/openssl/openssl.git "refs/tags/openssl-${OPENSSL_MAJOR}.*" \
    | cut -d'/' -f3- | cut -d'^' -f1 | cut -d- -f2- \
    | grep -vE -- '-[A-Za-z]+' \
    | sort -urV)

if [[ -z "$opensslVersion" ]]; then
    echo "ERROR: 无法确定 OpenSSL ${OPENSSL_MAJOR} 的版本（网络或上游资产问题）"
    exit 1
fi

# OpenSSL 3.0.5 的 sha256 文件以单个空格开头；3.1.8+ / 3.3.3+ 现在包含文件名
opensslSha256="${opensslSha256# }"
opensslSha256="${opensslSha256%% *}"

# === rabbitmqadmin: loong64 构建取自 loongarch64-releases/rabbitmqadmin-ng ===
# 官方 rabbitmqadmin-ng 无 loong64 资产（仅 x86_64/aarch64）；该镜像仓库提供
# loongarch64 gnu（debian 变体用）与 musl（alpine 变体用）构建。
# sha256 由本地下载计算，不依赖 GitHub API（同 library/redis 的做法）。
RABBITMQADMIN_REPO='https://github.com/loongarch64-releases/rabbitmqadmin-ng'

rabbitmqadminTag=$(wget -S --spider "$RABBITMQADMIN_REPO/releases/latest" 2>&1 \
    | grep -oE 'tag/v[0-9.]+' | head -1 | cut -d/ -f2)

if [[ -z "$rabbitmqadminTag" ]]; then
    echo "ERROR: 无法确定 rabbitmqadmin-ng 的最新 release（$RABBITMQADMIN_REPO/releases/latest）"
    exit 1
fi
rabbitmqadminVersion="${rabbitmqadminTag#v}"

adminGnuUrl="$RABBITMQADMIN_REPO/releases/download/$rabbitmqadminTag/rabbitmqadmin-$rabbitmqadminVersion-loongarch64-unknown-linux-gnu"
adminMuslUrl="$RABBITMQADMIN_REPO/releases/download/$rabbitmqadminTag/rabbitmqadmin-$rabbitmqadminVersion-loongarch64-unknown-linux-musl"

TMP_ADMIN=$(mktemp)
trap 'rm -f "$TMP_ADMIN"' EXIT

if ! wget -qO "$TMP_ADMIN" "$adminGnuUrl"; then
    echo "ERROR: rabbitmqadmin gnu 资产不存在或下载失败: $adminGnuUrl"
    exit 1
fi
adminGnuSha256=$(sha256sum "$TMP_ADMIN" | cut -d' ' -f1)

if ! wget -qO "$TMP_ADMIN" "$adminMuslUrl"; then
    echo "ERROR: rabbitmqadmin musl 资产不存在或下载失败: $adminMuslUrl"
    exit 1
fi
adminMuslSha256=$(sha256sum "$TMP_ADMIN" | cut -d' ' -f1)

echo "$VERSION: otp $otpVersion, openssl $opensslVersion, rabbitmqadmin $rabbitmqadminVersion, debian $debian_version, alpine $alpine_version" >&2

# === 构建版本数据 ===
if [[ -f versions.json ]] && [[ -s versions.json ]]; then
    json=$(< versions.json)
else
    json='{}'
fi

new_data=$(
    jq -n \
        --arg version "$VERSION" \
        --arg otp_version "$otpVersion" \
        --arg otp_sha256 "$otpSha256" \
        --arg openssl_version "$opensslVersion" \
        --arg openssl_sha256 "$opensslSha256" \
        --arg rabbitmqadmin_version "$rabbitmqadminVersion" \
        --arg rabbitmqadmin_gnu_url "$adminGnuUrl" \
        --arg rabbitmqadmin_gnu_sha256 "$adminGnuSha256" \
        --arg rabbitmqadmin_musl_url "$adminMuslUrl" \
        --arg rabbitmqadmin_musl_sha256 "$adminMuslSha256" \
        --arg debian_version "$debian_version" \
        --arg alpine_version "$alpine_version" \
        '{
            version: $version,
            otp_version: $otp_version,
            otp_sha256: $otp_sha256,
            openssl_version: $openssl_version,
            openssl_sha256: $openssl_sha256,
            rabbitmqadmin: {
                version: $rabbitmqadmin_version,
                gnu: { url: $rabbitmqadmin_gnu_url, sha256: $rabbitmqadmin_gnu_sha256 },
                musl: { url: $rabbitmqadmin_musl_url, sha256: $rabbitmqadmin_musl_sha256 }
            },
            debian_version: $debian_version,
            alpine_version: $alpine_version
        }'
)

json=$(echo "$json" | jq -c --argjson d "$new_data" '.[$d.version] = $d')
echo "$json" | jq -S . > versions.json

echo "Version info saved to versions.json" >&2
