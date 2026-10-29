# rabbitmq

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/rabbitmq |
| 分支 | master |
| 上次同步 commit | 0b2a146a189d6d604a77e5a474e3f12f46abdbe4 |
| 上游渲染方式 | jq-template.awk（三个模板：ubuntu / alpine / management，management 依赖前两者产物作 FROM 基础） |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| Dockerfile-ubuntu.template | template/Dockerfile-debian.template | 拆分/重写（ubuntu → debian forky，见改动清单） |
| Dockerfile-alpine.template | template/Dockerfile-alpine.template | 拆分/重写 |
| Dockerfile-management.template | template/Dockerfile-management.template | 拆分/重写（management 为独立变体，FROM 本地基础镜像；rabbitmqadmin 改用 loong64 构建） |
| 同上 | template/Dockerfile-alpine-management.template | 拆分（alpine 侧 management，同上） |
| versions.sh | template/update.sh | 重写（bash + git ls-remote + wget，不走 GitHub API；rabbitmqadmin 取自 loongarch64-releases） |
| apply-templates.sh | template/apply-templates.sh | 重写（jq 提取 + sed 渲染） |
| docker-entrypoint.sh | template/docker-entrypoint.sh | 1:1 拷贝（alpine 渲染时 sed gosu→su-exec，沿用上游逻辑） |
| conf.d/*.conf | template/conf.d/*.conf | 1:1 拷贝 |
| generate-stackbrew-library.sh | — | 官方镜像库元数据生成，本地不迁移 |

## 改动清单

- 基础镜像: 上游 ubuntu 24.04/26.04 → debian forky（LoongArch64 硬约束，值集中在 template/update.sh）；alpine 上游 3.23 → 3.24（对齐本仓库统一版本，值集中在 template/update.sh）
- 模板: jq-template 的 `{{ }}` 条件块全部展开为占位符（{VERSION}/{OTP_VERSION}/{OTP_SOURCE_SHA256}/{OPENSSL_VERSION}/{OPENSSL_SOURCE_SHA256}/{DEBIAN_VERSION}/{ALPINE_VERSION}/{RABBITMQADMIN_URL}/{RABBITMQADMIN_SHA256}）；上游预计算的 OpenSSL PGP key 列表（jq 内联）直接内联进模板
- 架构: opensslMachine case 新增 `loong64 → linux64-loongarch64`（OpenSSL 3.2+ 官方 target，两变体模板均加）；Erlang JIT case 保持上游原样，loong64 自动落入无 JIT 分支
- 依赖: debian 变体 libncurses5-dev → libncurses-dev（forky 已移除 ncurses5 兼容包；两者都提供 Erlang 需要的头文件）
- 依赖: debian 变体最终镜像显式安装 libatomic1——loong64 的 beam.smp 运行时链接 libatomic（构建阶段由 build-essential 连带安装所以 erlang-builder 无感，最终镜像是干净 debian:forky 需显式装；上游 amd64/arm64 不链接故无此需求）；必须装在最终阶段第一个 RUN 的 erl 冒烟测试之前（见 docs/02 2026-10-28 条目）。alpine 变体无需处理——scanelf runDeps 自动扫描出 so:libatomic.so.1
- 依赖: rabbitmqadmin 官方预编译二进制无 loong64 构建（仅 x86_64/aarch64），改用 https://github.com/loongarch64-releases/rabbitmqadmin-ng 的 loong64 构建——debian/management 变体用 gnu（glibc 动态链接），alpine-management 变体用 musl（静态链接）；update.sh 每次取该仓库 releases/latest，下载资产本地计算 sha256
- 变体: management 拆为独立变体（management / alpine-management），FROM 指向本地构建的 `library/rabbitmq:{VERSION}`[-alpine]，需排在基础变体之后构建（config.yml 顺序保证）
- 版本来源: 上游 versions.sh 按 4.0–4.4 五个版本线各自维护映射表；本地 get_versions.sh 默认仅跟踪最新版本线（MINOR_LINES="4.4"），OTP/OpenSSL 主版本映射保留在 update.sh 的 case 中

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {OTP_VERSION} | update.sh | 该版本线所需 OTP 主版本下最新的 release 版本号 |
| {OTP_SOURCE_SHA256} | update.sh | OTP 源码 tarball 校验和（GitHub release 资产 SHA256.txt） |
| {OPENSSL_VERSION} | update.sh | OpenSSL 主版本下最新的正式版本号 |
| {OPENSSL_SOURCE_SHA256} | update.sh | OpenSSL 源码 tarball 校验和（release 资产 .sha256） |
| {RABBITMQADMIN_URL} | update.sh | loongarch64-releases rabbitmqadmin-ng loong64 资产 URL（gnu 或 musl，按变体） |
| {RABBITMQADMIN_SHA256} | update.sh | 对应资产 sha256（本地下载计算） |
| {DEBIAN_VERSION} / {ALPINE_VERSION} | update.sh | 基础镜像版本 |

## 上游同步清单

1. 上游 versions.sh 的 otpMajors / opensslMajors 变更时，同步 update.sh 顶部的 case 映射（新版本线出现时同时改 get_versions.sh 的 MINOR_LINES）
2. OpenSSL 签名 key 变更时（上游注释标记 as of 日期），同步两个基础变体模板内联的 OPENSSL_PGP_KEY_IDS
3. rabbitmqadmin 版本跟随 loongarch64-releases/rabbitmqadmin-ng 的 releases/latest（update.sh 自动取最新）；该仓库落后于官方 rabbitmqadmin-ng 时（如官方 2.35.0 vs loong64 2.32.0），功能差异无需处理，等待其跟进即可
4. 确认上游是否已给 Erlang JIT case 增加 loong64（当前仅 amd64/arm64；若增加则同步模板）

## LoongArch64 约束

- OpenSSL 必须走 `linux64-loongarch64` target，上游 case 无此项，本地已补
- rabbitmqadmin 官方无 loong64 预编译二进制，改用 loongarch64-releases 的 loong64 构建（见改动清单）
- Erlang JIT 不支持 loong64（上游 OTP 限制），构建自动落入解释器模式
- Debian 基础镜像固定 forky（全局硬约束），不随上游 ubuntu 版本变化；management 变体的 apt-get dist-clean 在 forky 可用（已验证）

## 已知问题

- 无未解决问题（模板渲染结果已与上游 4.4 线成品 Dockerfile 逐段比对；完整构建验证待 CI runner——本机无代理环境下 OpenSSL/Erlang 源码编译预计耗时较长）
