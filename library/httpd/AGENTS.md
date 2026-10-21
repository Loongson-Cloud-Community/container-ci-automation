# httpd

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/httpd |
| 分支 | master |
| 上次同步 commit | c5248004fec9 |
| 上游渲染方式 | update.sh 直接 sed 改成品 Dockerfile 中的版本号 |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| 2.4/Dockerfile | template/Dockerfile-debian.template | 拆分/重写（版本号改为 {VAR} 占位符） |
| 2.4/alpine/Dockerfile | template/Dockerfile-alpine.template | 拆分/重写 |
| update.sh | template/update.sh | 重写（wget 取 sha256 + 补丁列表） |
| httpd-foreground | template/httpd-foreground | 1:1 拷贝 |
| — | template/apply-templates.sh | 本地新增（jq 提取 + sed 渲染） |

## 改动清单

- 模板: 上游成品 Dockerfile 中的硬编码值替换为占位符，模板内容独立于版本
- 基础镜像: debian=debian:{DEBIAN_VERSION}-slim、alpine=alpine:{ALPINE_VERSION}，值集中在 update.sh
- 补丁: {PATCHES} 由 update.sh 从 Apache `patches/apply_to_{VERSION}/` 目录检测生成

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {SHA256} | update.sh | `httpd-$VERSION.tar.bz2.sha256` |
| {PATCHES} | update.sh | 该版本适用的补丁文件列表（可为空） |
| {DEBIAN_VERSION} / {ALPINE_VERSION} | update.sh | 基础镜像版本 |

## 上游同步清单

1. 对比上游 `2.4/Dockerfile` 与本地 Dockerfile-debian.template
2. 对比上游 `2.4/alpine/Dockerfile` 与本地 Dockerfile-alpine.template
3. 合并上游变更时保留 {VAR} 占位符；新增环境变量需同步加到 update.sh 与 apply-templates.sh

## 已知问题

- 无未解决问题
