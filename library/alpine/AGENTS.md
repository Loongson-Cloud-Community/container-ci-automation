# alpine

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://gitlab.alpinelinux.org/alpine/aports（发行版源码）；下载站 cz.alpinelinux.org |
| 分支 | latest-stable |
| 上次同步 commit | 不适用（无 Dockerfile 派生，直接下载官方 minirootfs 产物） |
| 上游渲染方式 | 无——本地模板是自创的打包脚本，非上游 Dockerfile 派生 |

## 映射表（输入产物来源 → 本地用途）

| 输入产物 | 获取方式 | 本地用途 |
|----------|----------|----------|
| alpine-minirootfs-{version}-loongarch64.tar.gz | update.sh 从 cz.alpinelinux.org 下载 | template/apply-templates.sh 复制到 dockerfiles/{version}/alpine/ 供 buildx ADD |

下载 URL 结构：`https://cz.alpinelinux.org/alpine/v{minor}/releases/loongarch64/alpine-minirootfs-{version}-loongarch64.tar.gz`
（目录段必须用 minor 版本 `v3.24`，用 full version 或 latest-stable 会 404——见 docs/03）

## 改动清单

- 模板: Dockerfile-alpine.template 为本地自创（FROM scratch + ADD rootfs.tar.gz），非上游派生
- 逻辑: update.sh 校验版本格式 a.b.c、按 minor 拼 URL 下载 rootfs 到 template/out/
- 逻辑: apply-templates.sh 渲染 {VERSION}/{MINOR_VERSION}/{MAJOR_VERSION} 并复制 rootfs 到构建目录

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {MINOR_VERSION} | apply-templates.sh（由 $1 截取） | 次版本号（如 3.24） |
| {MAJOR_VERSION} | apply-templates.sh（由 $1 截取） | 主版本号（如 3） |

## 已知问题

- minirootfs 下载速度慢，拖长 CI 耗时（未解决；可考虑缓存）
