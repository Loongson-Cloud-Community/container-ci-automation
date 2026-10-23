# redis

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/redis/docker-library-redis |
| 分支 | release/8.10 |
| 上次同步 commit | cba49c32a61bd316b0708fbf1909278d4a233be6 |
| 上游渲染方式 | 成品 Dockerfile（release/* 分支按版本线直接维护 debian/、alpine/ 目录；8.x 起不再用 jq-template.awk，`.redis.version.json` 由发布自动化维护） |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| debian/Dockerfile | template/Dockerfile-debian.template | 重写（版本/URL/SHA/基础镜像改占位符） |
| alpine/Dockerfile | template/Dockerfile-alpine.template | 重写（同上） |
| debian/docker-entrypoint.sh | template/docker-entrypoint-debian.sh | 1:1 拷贝 |
| alpine/docker-entrypoint.sh | template/docker-entrypoint-alpine.sh | 1:1 拷贝 |
| .redis.version.json | template/update.sh | 重写（本地下载 release 资产计算 sha256，不依赖 GitHub API） |
| versions.sh / apply-templates.sh / Dockerfile.j2 / bin/ / legacy-templating-scripts/ | — | 上游发布自动化与 8.x 前旧模板遗迹，与本地构建链路无关，不映射 |
| master 分支（6.2/7.0/7.2/7.4 旧式 jq-template.awk + gosu） | — | 上游旧线，本地不迁移（gosu 无 loong64 二进制） |

## 改动清单

- 模板: 上游成品 Dockerfile 中硬编码的 REDIS_VERSION/下载 URL/SHA/基础镜像版本替换为占位符；FROM 保持上游通用形式，不加 registry 前缀
- 基础镜像: debian=trixie → forky、alpine=3.23 → 3.24，值集中在 template/update.sh
- 版本来源: 上游按 release/* 分支固定版本线 → 本地 get_versions.sh 从 redis-hashes 取各线最新稳定版（排除 -rc）
- 下载资产: 上游 .redis.version.json 的 redis-full.tar.gz（GitHub release 资产，含 modules 子模块）；本地 update.sh 按固定 URL 模式下载计算 sha256，不走 GitHub API（匿名限流 60 次/小时，共享出口 IP 易耗尽）
- 架构: 无需改动——loong64 自动落入上游 `BUILD_WITH_MODULES=no` 分支（与 i386/riscv64/s390x 同路径，不构建 Rust modules）；gosu 在 8.x 已被 setpriv（发行版自带包）替代，无预编译二进制依赖

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {REDIS_DOWNLOAD_URL} | update.sh | GitHub release 资产 redis-full.tar.gz 下载链接 |
| {REDIS_DOWNLOAD_SHA} | update.sh | 该资产 sha256（本地下载计算） |
| {DEBIAN_VERSION} / {ALPINE_VERSION} | update.sh | 基础镜像版本 |

## 上游同步清单

1. 新版本线（8.11、8.12 …）由 get_versions.sh 的下限语义（MIN_LINE，当前 8.10）自动纳入，无需改脚本；但纳入新线后需对比上游 `release/<新线>` 分支 Dockerfile 与本地模板的差异（新线可能新增依赖或逻辑，模板是按 release/8.10 写的）
2. 当前跟随 release/8.10 分支 HEAD（含 zstd 复制压缩支持，比 v8.10.2 tag 新）；若改为跟随 tag 需同步调整
3. 上游 Dockerfile 新增构建依赖/条件逻辑时合并进模板；BUILD_WITH_MODULES 的架构 case 若新增 loong64 需重新评估 modules 构建（Rust 工具链 + clang21）
4. entrypoint 两份分别独立维护（debian 用 /usr/bin/setpriv、alpine 用 /bin/setpriv），同步时需分别对比
5. 下限 MIN_LINE 不可调到 8.0 以下（6.2/7.x 为旧式 gosu 模板，不可用本模板构建）；若需构建 8.0/8.2 等旧线，先确认上游对应 release/* 分支与本地模板兼容再下调

## LoongArch64 约束

- Redis modules（RedisJSON/RediSearch/TimeSeries 等，Rust+clang21 构建）在 loong64 上不可用，上游架构 case 自动禁用；镜像为纯 redis-server（BUILD_TLS=yes 保留）
- master 分支旧线（6.2/7.x）依赖 gosu 预编译二进制（无 loong64），如需该版本线需先解决 gosu 替代方案

## 已知问题

- Alpine 变体本机构建被代理阻断（`wget: error getting response`，本机环境问题，见 docs/03 通用经验）；实际构建验证待 CI runner。模板渲染结果已与上游 release/8.10 分支成品逐行比对一致
