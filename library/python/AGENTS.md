# python

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/python |
| 分支 | master |
| 上次同步 commit | ce73ea7cebf0 |
| 上游渲染方式 | jq-template.awk（Dockerfile-linux.template，含复杂条件逻辑） |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| Dockerfile-linux.template | template/Dockerfile-debian.template | 拆分 |
| 同上 | template/Dockerfile-debian-slim.template | 拆分 |
| 同上 | template/Dockerfile-alpine.template | 拆分 |
| Dockerfile-windows.template | — | 上游已废弃（本地不迁移） |
| versions.sh | template/update.sh | 重写（bash + jq，从 python.org/SBOM 取 checksum） |
| apply-templates.sh | template/apply-templates.sh | 重写（jq 提取 + sed/awk 渲染，含 {BLOCK_*} 块注入） |

## 改动清单

- 模板: 上游条件逻辑（GPG 验证、setuptools、zstd、frame pointers 等）改为 apply-templates.sh 预生成 {BLOCK_*} 文本块注入模板；新块名必须同时加进 apply-templates.sh 的块初始化列表
- 基础镜像: debian=forky、alpine=3.24，值集中在 update.sh；FROM 保持上游通用形式
- 版本差异: GPG 验证覆盖 3.10-3.13（3.14+ 无，PEP 761）；setuptools 仅 3.10/3.11（上游 109436bfb 后仅剩 3.11）
- 编译选项: alpine 禁用 --enable-optimizations + -DTHREAD_STACK_SIZE=0x100000；非 alpine 启用 --enable-optimizations + -fno-omit-frame-pointer
- 构建依赖: 按上游 688a0b86b 给 alpine / debian-slim 补 g++（修复扩展构建）；按上游 ce73ea7ce 预置 3.15+ 的 mpdecimal-dev / libmpdec-dev（本地未启用 3.15；bookworm 专属 --without-system-libmpdec 不适用，Debian 固定 forky 走安装 libmpdec-dev 分支）
- 版本集: 上游 109436bfb 因 EOL 删除 3.10，本地 get_versions.sh 仍构建 3.10.21，LANG/setuptools/GPG 按上游删除前的规则保留；是否下线待确认
- apt 清理: 上游 trixie+ 用 apt-get dist-clean（bookworm 用 rm -rf），本地统一 rm -rf /var/lib/apt/lists/*

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {PYTHON_SHA256}（经 {BLOCK_ENV_SHA256}） | update.sh | 源码 tarball 校验和 |
| {GPG_KEY} | update.sh | GPG 公钥 ID（仅 3.10-3.13） |
| {V_SETUPTOOLS} | update.sh | setuptools 版本（仅 3.10/3.11） |
| {BLOCK_GPG_VERIFY} {BLOCK_GPG_DOWNLOAD} {BLOCK_SETUPTOOLS} {BLOCK_ENV_*} {BLOCK_DEBIAN_*} {BLOCK_ALPINE_BUILD_DEPS} {BLOCK_FRAME_PTRS} {BLOCK_MAKE_FLAGS} | apply-templates.sh | 预计算条件块（按版本/变体注入或置空） |
| {DEBIAN_VERSION} / {ALPINE_VERSION} | update.sh | 基础镜像版本 |

## 上游同步清单

1. 上游 Dockerfile-linux.template 有新条件逻辑时，在 apply-templates.sh 预计算新 {BLOCK_*}，并把块名加进初始化列表（否则占位符残留校验失败）
2. 新 GPG key 或 setuptools 变更时，更新 update.sh 中按大版本的映射（当前 GPG: 3.10-3.13；setuptools: 3.10/3.11）
3. 上游增删大版本时同步 get_versions.sh 的 MAJOR_VERSIONS（上游已删 3.10 但本地仍构建；3.15 已发布，mpdec 逻辑已预置）
4. 上游 alpine 大版本变更时先在同步摘要中提出确认，再改 update.sh 的 alpine_versions；Debian 固定 forky 不随上游 variants 变化

## 已知问题

- 无未解决问题
