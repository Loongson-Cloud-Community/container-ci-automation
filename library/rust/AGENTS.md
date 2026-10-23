# rust

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/rust-lang/docker-rust |
| 分支 | master |
| 上次同步 commit | b98c33260d01 |
| 上游渲染方式 | x.py（Python）+ versions.toml，`%%VAR%%` 占位符，每变体一个模板 |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| Dockerfile-debian.template | template/Dockerfile-debian.template | 重写（%%VAR%% → {VAR}，多架构 case 展开为占位符） |
| Dockerfile-slim.template | template/Dockerfile-debian-slim.template | 重写 |
| Dockerfile-alpine.template | template/Dockerfile-alpine.template | 重写 |
| versions.toml | template/update.sh | 重写（上游仅 rust/rustup 版本；本地另取各架构 rustup-init SHA256） |
| x.py | template/apply-templates.sh | 重写（jq 提取 + sed 渲染） |

## 改动清单

- 占位符: 上游 `%%TAG%%`/`%%RUST-VERSION-ARG%%`/`%%ARCH-CASE%%`/`%%RUSTUP-VERSION%%` → 本地 `{VAR}`；架构 case 在 update.sh 展开为 `{SHA256_*}` 变量；`%%RUST-VERSION-ARG%%`（nightly 专用 ARG 行）随「仅 stable」渠道整行省略
- 基础镜像: debian=forky、alpine=3.24，值集中在 update.sh 顶部；FROM 保持上游通用形式（上游 debian 变体为 bookworm/trixie，本地固定 forky，不随上游 variants 变化）
- 版本来源: 上游 versions.toml（x.py 自更新）→ 本地 get_versions.sh 从 static.rust-lang.org 的 channel-rust-stable.toml 取最新 stable；rustup 版本从 release-stable.toml 实时取
- 架构: 本地含 loong64 支持（{SHA256_LOONG64} glibc、{SHA256_LOONGARCH64_MUSL} alpine），其余架构 case 与上游 x.py 保持一致
- 渠道: 上游有 stable/nightly 两渠道，本地仅构建 stable

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {RUSTUP_VERSION} | update.sh | rustup 版本号 |
| {SHA256_AMD64} {SHA256_ARM64} {SHA256_ARMHF} {SHA256_I386} {SHA256_RISCV64} {SHA256_S390X} {SHA256_PPC64EL} {SHA256_LOONG64} | update.sh | glibc 系 rustup-init 校验和 |
| {SHA256_AARCH64_MUSL} {SHA256_RISCV64_MUSL} {SHA256_PPC64LE_MUSL} {SHA256_X86_64_MUSL} {SHA256_LOONGARCH64_MUSL} | update.sh | musl 系（alpine 变体）校验和；{SHA256_LOONGARCH64_MUSL} 为本地新增 loong64 架构 |
| {DEBIAN_VERSION} / {ALPINE_VERSION} | update.sh | 基础镜像版本 |

## 上游同步清单

1. 上游新增/调整架构时，模板加对应 {SHA256_*} 占位符 + update.sh 加取值逻辑
2. 上游 %%VAR%% 集合变化时，apply-templates.sh 的 sed 集合需同步增删
3. rust 新 stable 由 get_versions.sh 自动跟随；rustup 大版本升级后核对 static.rust-lang.org 的 archive 路径格式未变
4. 上游 debian/alpine 基础镜像版本与变体列表变化时：debian 固定 forky 不随动，alpine 需先确认再改 update.sh 的集中定义

## 已知问题

- 无未解决问题
