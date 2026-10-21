# ruby

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/ruby |
| 分支 | master |
| 上次同步 commit | cb7ae85544be |
| 上游渲染方式 | jq-template.awk（gawk），模板含复杂条件逻辑 |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| Dockerfile.template | template/Dockerfile-debian.template | 拆分 |
| 同上 | template/Dockerfile-debian-slim.template | 拆分 |
| 同上 | template/Dockerfile-alpine.template | 拆分 |
| versions.sh | template/update.sh | 重写（bash + wget + python3/yaml） |
| apply-templates.sh | template/apply-templates.sh | 重写（jq 提取 + sed/awk 渲染） |
| rust.json | template/update.sh 内嵌处理 | 重写（loong64 不在其中，case 为空） |

> 上游根目录的 `update.sh`（仅串联 versions.sh + apply-templates.sh）、`rust.sh`（生成 rust.json 的维护脚本）、`generate-stackbrew-library.sh`、`README.md`、`versions.json` 及 `3.3/3.4/4.0/4.1-rc/` 成品目录：均为上游仓库维护脚本与生成物，与本地构建链路无关，不映射（2026-10 目录核对结论）。

## 改动清单

- 模板: 上游单模板按变体拆为 3 个独立模板，移除 awk 条件逻辑，条件块由 apply-templates.sh 预计算
- 基础镜像: 值集中在 template/update.sh（debian=forky，alpine=3.24）；FROM 保持上游通用形式
- 架构: loong64 不在上游 rust.json 中 → rustArch 为空，YJIT/ZJIT 不启用
- 逻辑保留: Alpine thread-stack-fix 补丁（仅 alpine 变体）
- 安全加固: 三个模板 configure 前加 `export LDFLAGS='-Wl,-z,relro -Wl,-z,now'`（full RELRO，上游 docker-library/ruby#529，本次同步合入）

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {RUBY_DOWNLOAD_URL} | update.sh | 源码 tar.xz 下载链接 |
| {RUBY_DOWNLOAD_SHA256} | update.sh | tar.xz 校验和 |
| {POST} | update.sh | 发布博文路径 |
| {RUST_VERSION} | update.sh | rustup 相关 Rust 版本 |
| {RUSTUP_CASES} / {RUSTUP_CASES_ALPINE} | apply-templates.sh | 预计算的架构 case 块 |
| {BLOCK_ZJIT} | apply-templates.sh | 4.0+ 的 ZJIT 编译块（3.x 为空） |
| {DEBIAN_VERSION} / {ALPINE_VERSION} | update.sh | 基础镜像版本 |

## 上游同步清单

1. 上游 Dockerfile.template 有新条件逻辑时，在 apply-templates.sh 预计算新块
2. rust.json 有新增架构时，检查 rustArch case 是否需要补 loong64（当前决定不启用）
3. 新大版本行为：3.x 仅 YJIT，4.0+ 为 YJIT + ZJIT，同步时核对
4. 上游根目录新增文件时核对是否属于构建链路（维护脚本/生成物不映射，见映射表备注）

## 已知问题

- 无未解决问题（构建正常）
