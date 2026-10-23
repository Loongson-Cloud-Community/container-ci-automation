#!/bin/bash
# library/redis/get_versions.sh
# 输出所有活跃版本线的最新稳定版本号（每行一个）
# 版本清单来自 redis-hashes（上游 versions.sh 同源）
set -eo pipefail

# 构建下限版本线（含）：自动跟随所有 >= 此线的新版本线（8.11、8.12、9.x …），
# 上游发新线时无需改本脚本；如需构建更旧的线（8.0/8.2 …）在此下调。
# 注意: 8.0 以下（6.2/7.x）是上游旧式模板（依赖 gosu 预编译二进制，无 loong64），
#       不可用本模板构建，勿将下限调到 8.0 以下。
MIN_LINE="8.10"

wget -qO- 'https://github.com/redis/redis-hashes/raw/master/README' \
    | grep -oE '^hash redis-[0-9][0-9.]*\.tar\.gz sha256 [0-9a-f]{64}' \
    | awk '{print $2}' \
    | sed -E 's/^redis-//; s/\.tar\.gz$//' \
    | sort -V \
    | awk -v min="$MIN_LINE" '
BEGIN {
    split(min, m, ".")
    min_major = m[1] + 0
    min_minor = m[2] + 0
}
{
    split($0, v, ".")
    line = v[1] "." v[2]
    major = v[1] + 0
    minor = v[2] + 0
    if (major > min_major || (major == min_major && minor >= min_minor)) {
        latest[line] = $0
    }
}
END {
    for (line in latest) print latest[line]
}' \
    | sort -V
