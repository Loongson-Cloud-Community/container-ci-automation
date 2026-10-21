# rust

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/rust |
| 分支 | master |
| 上次同步 commit | 未记录（历史迁移未保存，下次同步时补记） |
| 上游渲染方式 | jq-template.awk（Dockerfile-linux.template，多架构 case） |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| Dockerfile-linux.template | template/Dockerfile-debian.template | 拆分（rustup-init 多架构 case 展开为 {SHA256_*} 占位符） |
| 同上 | template/Dockerfile-debian-slim.template | 拆分 |
| 同上 | template/Dockerfile-alpine.template | 拆分（musl 架构，独立 SHA256 变量） |
| versions.sh | template/update.sh | 重写（bash + wget，取 rustup 版本与各架构 SHA256） |
| apply-templates.sh | template/apply-templates.sh | 重写（jq 提取 + sed 渲染） |

## 改动清单

- 模板: 上游 rustup-init 架构 case 展开为每架构 {SHA256_*} 占位符，含 loong64（glibc）与 loongarch64-musl（alpine）
- 基础镜像: debian=forky、alpine=3.24，值集中在 update.sh 顶部；FROM 保持上游通用形式
- 版本: rustup 版本从 static.rust-lang.org/rustup/release-stable.toml 实时获取
- 变体: config.yml 只含 debian / debian-slim / alpine 三个

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {RUSTUP_VERSION} | update.sh | rustup 版本号 |
| {SHA256_AMD64} {SHA256_ARM64} {SHA256_ARMHF} {SHA256_I386} {SHA256_RISCV64} {SHA256_S390X} {SHA256_PPC64EL} {SHA256_LOONG64} | update.sh | glibc 系 rustup-init 校验和 |
| {SHA256_AARCH64_MUSL} {SHA256_LOONGARCH64_MUSL} {SHA256_PPC64LE_MUSL} {SHA256_X86_64_MUSL} | update.sh | musl 系（alpine 变体）校验和 |
| {DEBIAN_VERSION} / {ALPINE_VERSION} | update.sh | 基础镜像版本 |

## 上游同步清单

1. 上游新增架构时，模板加 case 分支 + update.sh 加 SHA256 变量
2. 上游 Rust 大版本发布后，get_versions.sh 从 channel-rust-stable.toml 自动取新版
3. 检查 static.rust-lang.org 的 rustup archive 路径格式未变

## 已知问题

- 无未解决问题
