#!/usr/bin/env bash
# library/postgres/template/apply-templates.sh
# 接收版本号，读取 versions.json：
#   1. 按主版本预计算 {BLOCK_*} 条件块（上游 jq-template 的 if 分支）
#   2. sed 替换普通占位符，awk 注入块内容（独占一行的 {BLOCK_*} → 块文件内容）
#   3. 输出 dockerfiles/{version}/{debian,alpine}/ 并复制 entrypoint 脚本
set -Eeuo pipefail

VERSION="$1"

if [[ -z "$VERSION" ]]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 18.6"
    exit 1
fi
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$BASH_SOURCE")")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKERFILES_DIR="$PROJECT_DIR/dockerfiles"
BLOCKS_DIR="$(mktemp -d)"
trap 'rm -rf "$BLOCKS_DIR"' EXIT

if [[ ! -f "$SCRIPT_DIR/versions.json" ]]; then
    echo "ERROR: versions.json not found. Run update.sh first."
    exit 1
fi

entry="$(jq -r --arg v "$VERSION" '.[$v] // empty' "$SCRIPT_DIR/versions.json")"
if [[ -z "$entry" ]]; then
    echo "ERROR: Version $VERSION not found in versions.json"
    exit 1
fi

V_VERSION="$(jq -r '.version' <<<"$entry")"
V_MAJOR="$(jq -r '.major' <<<"$entry")"
V_APT_VERSION="$(jq -r '.apt_version' <<<"$entry")"
V_ARCHES="$(jq -r '.arches | join(" | ")' <<<"$entry")"
V_SHA256="$(jq -r '.sha256' <<<"$entry")"
V_DEBIAN="$(jq -r '.debian_version' <<<"$entry")"
V_ALPINE="$(jq -r '.alpine_version' <<<"$entry")"
V_GOSU="$(jq -r '.gosu_version' <<<"$entry")"
V_LLVM="$(jq -r '.llvm_version' <<<"$entry")"

echo "Generating Dockerfiles for postgres $V_VERSION (PG_MAJOR=$V_MAJOR)" >&2

# === 初始化所有块为空（条件不命中的块渲染为空，占位符行整行移除） ===
for b in BLOCK_JIT BLOCK_PGDATA BLOCK_SU_EXEC BLOCK_ZSTD_DEV BLOCK_CURL_URING_DEV \
         BLOCK_THREAD_SAFETY BLOCK_GNU_LD BLOCK_CONFIGURE_CURL_URING BLOCK_WITH_ZSTD; do
    : > "$BLOCKS_DIR/$b.txt"
done

# === 按主版本预计算条件块（对应上游 Dockerfile-*.template 的 {{ if }} 分支） ===

# debian: 18+ 的 JIT 独立包（仅在架构有包时安装）
if (( V_MAJOR >= 18 )); then
    cat > "$BLOCKS_DIR/BLOCK_JIT.txt" << 'EOF'
# https://github.com/docker-library/postgres/pull/1344#issuecomment-2936578203 (JIT is a separate package in 18+, but only supported for a subset of architectures)
	if apt-get install -s "postgresql-$PG_MAJOR-jit=$PG_VERSION" > /dev/null 2>&1; then \
		apt-get install -y --no-install-recommends "postgresql-$PG_MAJOR-jit=$PG_VERSION"; \
	fi; \
EOF
fi

# 两变体共用: 18+ 的 PGDATA 目录结构变化
if (( V_MAJOR >= 18 )); then
    cat > "$BLOCKS_DIR/BLOCK_PGDATA.txt" << EOF
#
# NOTE: in 18+, PGDATA has changed to match the pg_ctlcluster standard directory structure, and the VOLUME has moved from /var/lib/postgresql/data to /var/lib/postgresql
#
ENV PGDATA /var/lib/postgresql/$V_MAJOR/docker
VOLUME /var/lib/postgresql
# ("/var/lib/postgresql" is already pre-created with suitably usable permissions above)
EOF
else
    cat > "$BLOCKS_DIR/BLOCK_PGDATA.txt" << 'EOF'
ENV PGDATA /var/lib/postgresql/data
# this 1777 will be replaced by 0700 at runtime (allows semi-arbitrary "--user" values)
RUN install --verbose --directory --owner postgres --group postgres --mode 1777 "$PGDATA"
VOLUME /var/lib/postgresql/data
EOF
fi

# alpine: 14-16 的 su-exec 向后兼容（17+ 移除）
if (( V_MAJOR >= 14 && V_MAJOR <= 16 )); then
    cat > "$BLOCKS_DIR/BLOCK_SU_EXEC.txt" << 'EOF'
RUN set -eux; ln -svf gosu /usr/local/bin/su-exec; su-exec nobody true # backwards compatibility (removed in PostgreSQL 17+)
EOF
fi

# alpine: 15+ 的 zstd 支持（构建依赖 + configure 选项）
if (( V_MAJOR >= 15 )); then
    cat > "$BLOCKS_DIR/BLOCK_ZSTD_DEV.txt" << 'EOF'
# https://www.postgresql.org/docs/15/release-15.html "--with-zstd to enable Zstandard builds"
		zstd-dev \
EOF
    cat > "$BLOCKS_DIR/BLOCK_WITH_ZSTD.txt" << 'EOF'
		--with-zstd \
EOF
fi

# alpine: 18+ 的 libcurl / liburing（构建依赖 + configure 选项）
if (( V_MAJOR >= 18 )); then
    cat > "$BLOCKS_DIR/BLOCK_CURL_URING_DEV.txt" << 'EOF'
# https://salsa.debian.org/postgresql/postgresql-common/-/commit/a31ce5b893c11e0f17a016e38c1882fbe1820081
# https://www.postgresql.org/docs/18/install-make.html#CONFIGURE-OPTION-WITH-LIBCURL
		curl-dev \
# https://salsa.debian.org/postgresql/postgresql-common/-/commit/89c384273f4c4092483598c292b1b1b188816cce
# https://www.postgresql.org/docs/18/install-make.html#CONFIGURE-OPTION-WITH-LIBURING
		liburing-dev \
EOF
    cat > "$BLOCKS_DIR/BLOCK_CONFIGURE_CURL_URING.txt" << 'EOF'
		--with-libcurl \
		--with-liburing \
EOF
fi

# alpine: 16 及以前的 --enable-thread-safety（17 起反转为需显式禁用）
if (( V_MAJOR <= 16 )); then
    cat > "$BLOCKS_DIR/BLOCK_THREAD_SAFETY.txt" << 'EOF'
		--enable-thread-safety \
EOF
fi

# alpine: 15 及以前的 --with-gnu-ld（16 起 configure 不再识别该选项）
if (( V_MAJOR <= 15 )); then
    cat > "$BLOCKS_DIR/BLOCK_GNU_LD.txt" << 'EOF'
		--with-gnu-ld \
EOF
fi

# === awk 块注入: 模板中独占一行的 {BLOCK_*} → 块文件内容（空块则整行移除） ===
replace_blocks() {
    awk -v bdir="$BLOCKS_DIR" '
    {
        line = $0
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", line)
        if (line ~ /^\{[A-Z0-9_]+\}$/) {
            name = line
            gsub(/[{}]/, "", name)
            fname = bdir "/" name ".txt"
            if (system("[ -f \"" fname "\" ]") == 0) {
                while ((getline content < fname) > 0) print content
                close(fname)
                next
            }
        }
        print
    }' "$1" > "$2"
}

# === 渲染单个变体 ===
render() {
    local template="$1" variant="$2"
    local out_dir="$DOCKERFILES_DIR/$VERSION/$variant"
    mkdir -p "$out_dir"

    sed \
        -e "s/{PG_MAJOR}/$V_MAJOR/g" \
        -e "s/{VERSION}/$V_VERSION/g" \
        -e "s/{PG_APT_VERSION}/$V_APT_VERSION/g" \
        -e "s/{DEBIAN_VERSION}/$V_DEBIAN/g" \
        -e "s/{ALPINE_VERSION}/$V_ALPINE/g" \
        -e "s/{PG_ARCHES}/$V_ARCHES/g" \
        -e "s/{PG_SHA256}/$V_SHA256/g" \
        -e "s/{GOSU_VERSION}/$V_GOSU/g" \
        -e "s/{LLVM_VERSION}/$V_LLVM/g" \
        "$SCRIPT_DIR/$template" > "$out_dir/Dockerfile.tmp"

    replace_blocks "$out_dir/Dockerfile.tmp" "$out_dir/Dockerfile"
    rm -f "$out_dir/Dockerfile.tmp"

    cp "$SCRIPT_DIR/docker-entrypoint.sh" "$SCRIPT_DIR/docker-ensure-initdb.sh" "$out_dir/"
    echo "  dockerfiles/$VERSION/$variant/Dockerfile" >&2
}

render Dockerfile-debian.template debian
render Dockerfile-alpine.template alpine

echo "Done." >&2
