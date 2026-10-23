# node

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/nodejs/docker-node |
| 分支 | main |
| 上次同步 commit | 未记录（历史迁移未保存，下次同步时补记） |
| 上游渲染方式 | update.sh（gawk），动态生成架构 case 语句 |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| Dockerfile-debian.template | template/Dockerfile-debian.template | 拆分/重写 |
| Dockerfile-slim.template | template/Dockerfile-debian-slim.template | 拆分/重写 |
| Dockerfile-alpine.template | template/Dockerfile-alpine.template | 拆分/重写（变体已禁用） |
| update.sh | template/update.sh | 重写（bash + jq） |
| apply-templates.sh | template/apply-templates.sh | 重写（jq 提取 + sed/python 替换） |
| keys/node.keys | update.sh 运行时从上游仓库实时获取 | 运行时依赖 |
| docker-entrypoint.sh | template/docker-entrypoint.sh | 1:1 拷贝 |

## 改动清单

- 二进制来源: Debian 变体改用 unofficial-builds.nodejs.org 的 loong64 glibc 预编译二进制（官方 nodejs.org 无 loong64）
- 模板: 移除上游多架构 case，仅保留 loong64 路径；下载 URL 指向 unofficial-builds
- 基础镜像: 版本值集中在 template/update.sh；FROM 保持上游通用形式
- 变体: alpine 已从 config.yml 移除（见已知问题）

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {LOONG64_SHA256} | update.sh | unofficial-builds loong64 glibc 二进制校验和 |
| {NODE_KEYS} | update.sh | GPG 公钥列表（多行，来自上游 keys/node.keys） |
| {BUILD_DEPS} | apply-templates.sh | 预计算的构建依赖块（按变体不同） |
| {YARN_SECTION} | apply-templates.sh | 预计算的 Yarn 安装块（Node 26+ 已无） |
| {DEBIAN_VERSION} / {ALPINE_VERSION} | update.sh | 基础镜像版本 |

## 上游同步清单

1. 检查 GPG 公钥是否变更（update.sh 实时获取，一般自动跟随）
2. Node 26+ 移除 Yarn v1，上游若有 Yarn 相关变更需同步到 {YARN_SECTION}
3. 新大版本确认 unofficial-builds 是否已放出 loong64 二进制（可能滞后）

## 已知问题

- unofficial-builds.nodejs.org 的 loong64 二进制发布可能滞后于官方版本
- alpine 变体无法构建（loong64 无 musl 预编译二进制，源码编译失败，2026-08-04 起从 config.yml 移除，待排查）
