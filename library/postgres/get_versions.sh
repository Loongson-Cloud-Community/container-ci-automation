#!/bin/bash
# library/postgres/get_versions.sh
# 输出可构建的版本线最新 GA 版本（每行一个，升序，如 14.24 / 18.6）
#   版本线 = 上游 docker-library/postgres versions.json 的 key（上游当前支持的主版本）
#   版本号 = apt.postgresql.org forky-pgdg(binary-loong64) 中该线最新的 GA 包
# 自动排除：预发布（apt 版本串含 "~"，如 19~rc1）、上游已删除的版本线、
#           forky 仓库尚无 GA 包的版本线（等仓库跟上后再构建）
set -eo pipefail

PGDG_SUITE="forky-pgdg"
PACKAGES_URL="http://apt.postgresql.org/pub/repos/apt/dists/$PGDG_SUITE/main/binary-loong64/Packages.bz2"
UPSTREAM_VERSIONS_URL="https://raw.githubusercontent.com/docker-library/postgres/master/versions.json"

# 上游支持的版本线（数字升序 → 最新主版本最后构建，latest 标签落在最新线上）
upstream_lines="$(curl -fsSL "$UPSTREAM_VERSIONS_URL" | jq -r 'keys[]' | sort -n)"

# forky-pgdg 各线最新的 GA 包版本（排除预发布）
apt_versions="$(
    curl -fsSL "$PACKAGES_URL" | bunzip2 \
        | awk -F ': ' '
            $1 == "Package" && $2 ~ /^postgresql-[0-9]+$/ { pkg = $2 }
            $1 == "Version" && pkg != "" && $2 !~ /~/ { print pkg, $2; pkg = "" }
        ' \
        | sort -k1,1 -k2,2V \
        | awk '{ last[$1] = $2 } END { for (p in last) print p, last[p] }'
)"

for line in $upstream_lines; do
    apt_ver="$(awk -v p="postgresql-$line" '$1 == p { print $2 }' <<<"$apt_versions")"
    if [[ -n "$apt_ver" ]]; then
        echo "${apt_ver%%-*}"   # 18.6-1.pgdg14+2 → 18.6
    fi
done
