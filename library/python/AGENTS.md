# python

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/python |
| 分支 | master |
| 上次同步 commit | 未记录（历史迁移未保存，下次同步时补记） |
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

- 模板: 上游条件逻辑（GPG 验证、setuptools、zstd、frame pointers 等）改为 apply-templates.sh 预生成 {BLOCK_*} 文本块注入模板
- 基础镜像: debian=forky、alpine=3.24，值集中在 update.sh；FROM 保持上游通用形式
- 版本差异: 3.10/3.11 需 GPG 验证 + setuptools；3.12 仅 GPG 验证；3.13+ 无 GPG 验证（PEP 761）
- 编译选项: alpine 禁用 --enable-optimizations + -DTHREAD_STACK_SIZE=0x100000；非 alpine 启用 --enable-optimizations + -fno-omit-frame-pointer

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {PYTHON_SHA256}（经 {BLOCK_ENV_SHA256}） | update.sh | 源码 tarball 校验和 |
| {GPG_KEY} | update.sh | GPG 公钥 ID（仅 3.10-3.12） |
| {V_SETUPTOOLS} | update.sh | setuptools 版本（仅 3.10/3.11） |
| {BLOCK_GPG_VERIFY} {BLOCK_GPG_DOWNLOAD} {BLOCK_SETUPTOOLS} {BLOCK_ENV_*} {BLOCK_DEBIAN_*} {BLOCK_ALPINE_BUILD_DEPS} {BLOCK_FRAME_PTRS} {BLOCK_MAKE_FLAGS} | apply-templates.sh | 预计算条件块（按版本/变体注入或置空） |
| {DEBIAN_VERSION} / {ALPINE_VERSION} | update.sh | 基础镜像版本 |

## 上游同步清单

1. 上游 Dockerfile-linux.template 有新条件逻辑时，在 apply-templates.sh 预计算新 {BLOCK_*}
2. 新 GPG key 或 setuptools 变更时，更新 update.sh 中按大版本的映射
3. 新大版本默认按 3.13+ 模式处理（无 GPG 验证），确认上游无变化

## 已知问题

- 无未解决问题
