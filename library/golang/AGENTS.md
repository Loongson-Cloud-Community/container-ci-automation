# golang

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/golang |
| 分支 | master |
| 上次同步 commit | 未记录（历史迁移未保存，下次同步时补记） |
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
- 架构: 只保留本地构建需要的架构变量（含 {URL_LOONG64}/{SHA256_LOONG64}）
- 基础镜像: 版本值集中在 update.sh；FROM 保持上游通用形式
- 目录名: 变体目录统一为 debian（曾不一致导致 build.py 找不到 Dockerfile，见 docs/03）

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {URL_AMD64} {URL_ARMHF} {URL_ARM64} {URL_I386} {URL_LOONG64} 等 | update.sh | 各架构 go 源码包下载 URL |
| {SHA256_AMD64} {SHA256_ARMHF} {SHA256_ARM64} {SHA256_I386} {SHA256_LOONG64} 等 | update.sh | 对应校验和 |
| {DEBIAN_VARIANT} | update.sh | debian 变体系列名（如 scm） |
| {ALPINE_VERSION} | update.sh | Alpine 版本 |

架构名映射（API 名 → 模板占位符 → 系统名）：amd64→x86_64，armv6l→armhf/armv7，arm64→aarch64，386→i386/x86，loong64→loongarch64。

## 上游同步清单

1. 上游新增架构时，模板加 case 分支 + update.sh 加对应变量
2. 上游新增变体（新 Alpine 版本）时，更新 update.sh 的 alpine 版本列表
3. Go 新大版本核对 go.dev API 路径未变

## 已知问题

- 无未解决问题
