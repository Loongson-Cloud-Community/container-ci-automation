# debian

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/debian（参考）；实际 rootfs 来自 snapshot.debian.org |
| 分支 | master |
| 上次同步 commit | 不适用（不使用上游 Dockerfile，本地用 debuerreotype 自建 rootfs） |
| 上游渲染方式 | 无——rootfs 由 debuerreotype 容器构建，Dockerfile 为本地自创 |

## 映射表（输入产物来源 → 本地用途）

| 输入产物 | 获取方式 | 本地用途 |
|----------|----------|----------|
| debuerreotype rootfs（loong64, suite=unstable） | update.sh 用 debuerreotype/debuerreotype 容器构建，输出 rootfs.tar.xz + 元数据到 template/out/ | apply-templates.sh 复制到 dockerfiles/{version}/{variant}/ 供 buildx ADD |

版本号为 Debian 快照时间戳（如 `20250521T073957Z`），来自 snapshot.debian.org。

## 改动清单

- 模板: Dockerfile-standard.template / Dockerfile-slim.template 为本地自创（FROM scratch + ADD rootfs.tar.xz），非上游派生
- 逻辑: update.sh 用 debuerreotype 构建 rootfs（docker run --privileged），suite=unstable、arch=loong64
- 逻辑: modify-rootfs-url.sh 修改 rootfs 内 apt 源地址（指向快照源）
- 逻辑: DEBIAN_VERSION=14 / DEBIAN_VERSION_NAME=forky 定义在 update.sh 顶部，VERSION_NAMES 映射表备用（13=trixie 等）

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {DEBIAN_VERSION} | update.sh | 主版本号（如 14） |
| {DEBIAN_VERSION_NAME} | update.sh（VERSION_NAMES 映射） | 发行版代号（如 forky） |
| {SUITE} | update.sh | 固定 unstable |
| {TIME_VERSION} | update.sh | 从版本号（时间戳）提取的日期部分 |

## 上游同步清单

1. 检查 snapshot.debian.org 是否有新快照（get_versions.sh 自动取当月最新）
2. 需要切换 Debian 版本时，改 update.sh 顶部 DEBIAN_VERSION 并核对 VERSION_NAMES
3. rootfs 源地址有变时，改 modify-rootfs-url.sh

## LoongArch64 约束

- Debian 仅支持 forky（不支持 trixie/bookworm），切换版本前先确认 loong64 可用性

## 已知问题

- 无未解决问题
