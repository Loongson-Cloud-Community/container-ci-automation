# php

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/php |
| 分支 | master |
| 上次同步 commit | 未记录（历史迁移未保存，下次同步时补记） |
| 上游渲染方式 | jq-template.awk（Dockerfile-linux.template，`{{ }}` 语法 + is_alpine/variant 条件） |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| Dockerfile-linux.template | template/Dockerfile-debian-cli.template | 拆分（7 模板之一） |
| 同上 | template/Dockerfile-debian-apache.template | 拆分 |
| 同上 | template/Dockerfile-debian-fpm.template | 拆分 |
| 同上 | template/Dockerfile-debian-zts.template | 拆分 |
| 同上 | template/Dockerfile-alpine-cli.template | 拆分 |
| 同上 | template/Dockerfile-alpine-fpm.template | 拆分 |
| 同上 | template/Dockerfile-alpine-zts.template | 拆分 |
| versions.sh | template/update.sh | 重写（bash + jq，从 php.net API 取版本与 checksum） |
| apply-templates.sh | template/apply-templates.sh | 重写（jq 提取 + sed 渲染 + 辅助文件复制） |
| docker-php-source / docker-php-ext-install / docker-php-ext-configure / docker-php-ext-enable / docker-php-entrypoint | template/ 下同名文件 | 1:1 拷贝（随 Dockerfile 打包进镜像） |
| apache2-foreground | template/apache2-foreground | 1:1 拷贝（仅 apache 变体） |
| — | template/jump_loongarch64_sysv_elf_gas.S、make_loongarch64_sysv_elf_gas.S | 本地新增（loong64 fiber 汇编） |

## 改动清单

- 模板: 上游单模板拆为 7 个独立完整模板（suite × variant），删除 blocks/ 目录
- 变体: 上游 `{suite}/{variant}` 简化为 debian(+apache/fpm/zts) 与 alpine(+fpm/zts)；基础镜像 debian=forky、alpine=3.24
- 架构: 禁用 pcre JIT（loongarch64 不支持，按 gnuArch 判断，改在各模板 configure 段）
- 架构: PHP 8.2 fiber 支持——apply-templates.sh 把两个 .S 汇编文件 COPY 进 /usr/src/php/Zend/asm/（COPY 必须在 RUN 块之前的顶层位置）
- 架构: Alpine loong64 安装 libucontext-dev（musl 无 swapcontext）并设置 LIBS
- JSON key: versions.json 以 major.minor 为 key（apply 中 RC_VERSION=${VERSION%.*}）

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {PHP_VERSION} | update.sh | 完整版本号 |
| {PHP_URL} / {PHP_ASC_URL} / {PHP_SHA256} | update.sh | 源码包与签名下载信息 |
| {GPG_KEYS} | update.sh | 该大版本的 GPG 公钥列表（按 major.minor 查） |
| {ALPINE_VERSION} | update.sh | Alpine 版本 |

## 上游同步清单

1. 新 PHP 大版本：确认 php.net API 中的 GPG_KEYS 映射已加到 update.sh
2. 8.2 的 fiber 汇编补丁与 libucontext 处理在 8.2 EOL 后可移除（apply-templates.sh 中有按版本判断）
3. 新变体（如新 SAPI）需同时加 config.yml + 模板 + apply 逻辑

## 已知问题

- 无未解决问题（8.2 fiber/libucontext 补丁属已适配项，非阻塞）
