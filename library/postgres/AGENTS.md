# library/postgres

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/postgres |
| 分支 | master |
| 上次同步 commit | `dfc76bb299b057785026eb2eea39556b6fe52983`（2026-10-15，模板基线；同步脚本后续自动维护） |
| 上游渲染方式 | jq-template.awk（`Dockerfile-{debian,alpine}.template` + `versions.sh` 按 suite 展开） |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| Dockerfile-debian.template | template/Dockerfile-debian.template | 拆分（`{{ if }}` 条件块改为 `{BLOCK_*}` 占位符） |
| Dockerfile-alpine.template | template/Dockerfile-alpine.template | 拆分（同上） |
| versions.sh | template/update.sh | 重写（单 suite forky-pgdg；bash + jq + gawk，取 apt 包版本 / 仓库架构 / 源码 sha256） |
| apply-templates.sh | template/apply-templates.sh | 重写（jq 提取 + sed 占位符 + awk 注入 `{BLOCK_*}`） |
| versions.json | template/versions.json | 生成物，精简为本地渲染所需字段（gitignored，不提交） |
| docker-entrypoint.sh | template/docker-entrypoint.sh | 1:1 拷贝 |
| docker-ensure-initdb.sh | template/docker-ensure-initdb.sh | 1:1 拷贝 |
| update.sh | — | 上游仅串联 versions.sh + apply-templates.sh；本地由 build.py 依次调用两个脚本，不映射 |
| generate-stackbrew-library.sh / AUTHORS / LICENSE / README.md | — | 上游官方镜像发布与仓库文件，与本地构建无关，不映射 |

## 改动清单

- 基础镜像: debian trixie/bookworm → `forky`（约束 7；apt.postgresql.org 对应 `forky-pgdg`，该 suite 含 loong64）、alpine 3.23/3.24 → 仅 `3.24`（约束 6）；值集中在 template/update.sh
- 变体: 上游按 suite 展开 4 个目录（trixie/bookworm/alpine3.24/alpine3.23）→ 本地只有 `debian` + `alpine` 两个变体
- 条件逻辑: 上游 10 处 `{{ if }}` 全部改为 `{BLOCK_*}` 占位符，由 apply-templates.sh 按主版本预计算（14 与 18 两个端点的渲染结果已与上游 `./apply-templates.sh` 产物逐行比对）
- gosu: `1.19` → `1.20`（1.19 的 release 资产无 loong64；1.20 起官方提供，签名密钥不变）
- llvm: alpine 模板写死的 `21` → `{LLVM_VERSION}`，本地取 `18`（loongarch64 的 Alpine 3.24 仓库最高只有 llvm18/clang18）
- postgres 仓库密钥: 上游 `gpg --keyserver keyserver.ubuntu.com --recv-keys`（hkp 11371）在构建网络不可达（代理只放行常见 HTTPS 站点）→ 改为 HTTPS 直下 `https://www.postgresql.org/media/keys/ACCC4CF8.asc` + `gpg --list-keys <完整指纹>` 校验（等价于上游 `--recv-keys <完整指纹>` 的指纹校验）；该步骤按 gosu 步骤的写法临时安装 ca-certificates/wget 后 `apt-mark`/`purge --auto-remove` 还原
- apt 安装: 服务端之外**同时钉住** `postgresql-client-$PG_MAJOR=$PG_VERSION`——Debian sid（forky 未发布时与 sid 同套）自带同主版本 postgresql 且版本更高，客户端不钉会让 apt3 解析死锁（`postgresql-… Depends postgresql-client-… (= pgdg 版本)` 选不中）
- jit 条件: `apt-get install -s "…-jit"` → `"…-jit=$PG_VERSION"`（探测要装的那个版本，避免 Debian 侧同名包让探测误判成功后钉版本安装失败）；loong64 当前两侧都无 jit 包，条件为假、跳过安装
- 版本来源: 上游 versions.sh 双 suite 交叉校验 → 本地 get_versions.sh = 上游 versions.json 的版本线 ∩ forky-pgdg(binary-loong64) 的 GA 包（自动排除 `19~rc1` 等预发布与上游已删版本线）
- tag: `latest` 只给 debian；`{major_version}`（`18.6` → `18`）依赖 build.py 两段式版本解析（见 docs/02）

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {PG_MAJOR} | update.sh | 主版本（如 `18`），上游 `env.version` |
| {PG_APT_VERSION} | update.sh | debian 变体的 apt 包版本（如 `18.6-1.pgdg14+2`），仅 debian 模板 |
| {PG_ARCHES} | update.sh | forky-pgdg 官方架构列表，渲染成 `amd64 \| arm64 \| …` 供 Dockerfile case 判断 |
| {PG_SHA256} | update.sh | 源码 tarball sha256（alpine 变体源码编译校验） |
| {DEBIAN_VERSION} / {ALPINE_VERSION} | update.sh | 基础镜像版本（`forky` / `3.24`），同时用于 `FROM` 与 `…-pgdg` suite 名 |
| {GOSU_VERSION} | update.sh | gosu 版本（`1.20`） |
| {LLVM_VERSION} | update.sh | llvm/clang 大版本（`18`，loongarch64 仓库上限） |
| {BLOCK_JIT} / {BLOCK_PGDATA} / {BLOCK_SU_EXEC} / {BLOCK_ZSTD_DEV} / {BLOCK_CURL_URING_DEV} / {BLOCK_THREAD_SAFETY} / {BLOCK_GNU_LD} / {BLOCK_CONFIGURE_CURL_URING} / {BLOCK_WITH_ZSTD} | apply-templates.sh | 主版本条件块（18+ jit、18+ PGDATA、14-16 su-exec、15+ zstd、18+ libcurl/liburing、≤16 thread-safety、≤15 gnu-ld） |

## 上游同步清单

1. 上游 versions.json 版本线增减（19 转 GA、14 EOL 下线）由 get_versions.sh 自动跟随；新增主版本后必须比对上游新模板的条件分支，必要时在 apply-templates.sh 补 `{BLOCK_*}`（块名要同时加进初始化列表）
2. 上游 Dockerfile-*.template 有改动时：重新拆分模板 → 渲染 → 与上游 `./apply-templates.sh` 产物逐行 diff（本地已知差异见「改动清单」，diff 只应出现这些项）
3. 上游 gosu 版本 bump → update.sh 的 `gosu_version`（若上游升到 ≥1.20 可评估回归上游值）
4. 上游 `llvmver`（当前 21）变更 → 本地固定 `18` 不跟随；loongarch64 仓库提供更高版本后再评估
5. Debian 换代（forky 发布、约束 7 变化）→ update.sh 的 `debian_version` + apt suite 名 + 「Debian sid 自带同主版本 postgresql」的前提要重新确认
6. 上游新增 suite/变体（bookworm、alpine3.23 等）本地不跟随（约束 6/7）

## LoongArch64 约束

- gosu 必须 ≥1.20（1.19 及以前的 release 无 loong64 资产，下载 404）
- alpine 变体的 llvm/clang 只能用 loongarch64 仓库存在的版本（当前最高 18；上游模板写死 21）
- Debian 走 forky-pgdg 的 loong64 二进制包（`Architectures` 含 loong64，命中 Dockerfile 官方架构分支，不走源码编译回退）
- `postgresql-18-jit` 在 forky-pgdg 与 Debian sid 的 loong64 上都不存在，jit 条件为假（镜像不含 JIT）
- `alpine:3.24` / `debian:forky-slim` 的上游 manifest 不含 loong64，本地经镜像拉取（`apk --print-arch` 为 `loongarch64`，`dpkg --print-architecture` 为 `loong64`，两者命名不同）

## 已知问题

- alpine 变体本机构建被代理阻断（docs/02 通用经验：容器内 busybox wget 不走本机代理）；apk 依赖已确认可装、`dpkg --print-architecture` 已实测得到 `gosu-loong64`、渲染已与上游逐行比对一致，实际构建待 CI runner
