# golang

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/golang |
| 分支 | master |
| 上次同步 commit | 41d9b4da7032 |
| 上游渲染方式 | jq-template.awk（Dockerfile-linux.template，含多架构 case 语句） |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| Dockerfile-linux.template | template/Dockerfile-debian.template | 拆分（case 展开为 {URL_*}/{SHA256_*} 占位符） |
| 同上 | template/Dockerfile-alpine.template | 拆分（架构名不同，见下表） |
| versions.sh | template/update.sh | 重写（wget + jq，取 go.dev 全架构下载信息） |
| apply-templates.sh | template/apply-templates.sh | 重写（jq 提取 + sed 渲染） |

## 改动清单

- 模板: 上游多架构 case 语句展开为每架构一对 {URL_xxx}/{SHA256_xxx} 占位符
- 架构: 只保留本地构建需要的架构变量（含 {URL_LOONG64}/{SHA256_LOONG64}）；上游新增的 armel 未纳入
- 基础镜像: 版本值集中在 update.sh（debian=forky、alpine=3.24）；Debian 固定 forky 是 loong64 平台约束（docs/01 约束 7），不随上游 variants 变化；FROM 保持上游通用形式
- GOARM 块: 上游 arm32v7 复用 armv6 二进制时向 go.env 写 GOARM=7（docker-library/golang#494）；本地按变体展开为 'armhf'（debian 模板）/'armv7'（alpine 模板），GOARM 值 '7' 硬编码（上游对该块恒为 7）
- COPY: 上游 `COPY --from=build --link` 可复现性优化已同步（build.py 走 buildx/BuildKit，支持 --link）
- debian 依赖: arm64 构建时安装 binutils-gold（docker-library/golang#570，trixie 起 binutils 移除 gold）
- 目录名: 变体目录统一为 debian（曾不一致导致 build.py 找不到 Dockerfile，见 docs/03）

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {URL_AMD64} {URL_ARMHF} {URL_ARM64} {URL_I386} {URL_LOONG64} 等 | update.sh | 各架构 go 源码包下载 URL |
| {SHA256_AMD64} {SHA256_ARMHF} {SHA256_ARM64} {SHA256_I386} {SHA256_LOONG64} 等 | update.sh | 对应校验和 |
| {DEBIAN_VARIANT} | update.sh | debian 版本代号（如 forky） |
| {ALPINE_VERSION} | update.sh | Alpine 版本 |

架构名映射（API 名 → 模板占位符 → 系统名）：amd64→x86_64，armv6l→armhf/armv7，arm64→aarch64，386→i386/x86，loong64→loongarch64。

## 上游同步清单

1. 上游新增/删除架构时，模板加 case 分支 + update.sh 加对应变量（armel 未纳入：本地只保留所需架构）
2. 上游 versions.sh 的 variants 列表（Debian/Alpine 版本）变化时，核对 update.sh 的 alpine_version；debian_version 须保持 forky（loong64 约束），不得照抄上游
3. Go 新大版本核对 go.dev API 路径未变
4. 上游 arm32v7 不再复用 armv6 二进制（.arches["arm32v7"].url 不含 armv6）时，删除两个模板中的 GOARM/go.env 块
5. 上游 Dockerfile-linux.template 的构建流程（多阶段、COPY、SOURCE_DATE_EPOCH 等）变化时，需同步落到两个拆分模板

## 已知问题

- 无未解决问题
