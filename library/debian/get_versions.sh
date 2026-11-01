#!/bin/bash
# library/debian/get_versions.sh
# 输出最新版本号（1 行）
set -eo pipefail

DEBIAN_MIRROR='https://snapshot.debian.org/archive/debian'

# 当月初时当月可能尚无任何快照（列表为空导致 grep 无匹配、脚本非零退出），
# 因此从当月起向前回退最多 4 个月查找。
cur_year=$((10#$(date +%Y)))
cur_month=$((10#$(date +%m)))

version=''
for back in 0 1 2 3; do
    year=$cur_year
    month=$((cur_month - back))
    while [ "$month" -le 0 ]; do
        month=$((month + 12))
        year=$((year - 1))
    done
    month_str=$(printf '%02d' "$month")

    version=$(wget -qO- "$DEBIAN_MIRROR?year=$year&month=$month_str" \
        | grep -oE 'href="[0-9]{8}T[0-9]{6}Z/"' \
        | tail -1 \
        | cut -d '"' -f 2 | cut -d '/' -f 1) || true

    if [ -n "$version" ]; then
        break
    fi
done

if [ -z "$version" ]; then
    echo "get_versions.sh: 未在最近 4 个月的快照列表中找到版本" >&2
    exit 1
fi

echo "$version"
