# erlang

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/erlang/docker-erlang-otp |
| 分支 | master |
| 上次同步 commit | 未记录（历史迁移未保存，下次同步时补记） |
| 上游渲染方式 | 上游本身就是每主版本一套成品 Dockerfile（无模板渲染） |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| {MAJOR}/Dockerfile | dockerfiles/{version}/debian/Dockerfile | 1:1 拷贝 + sed 替换基础镜像（update.sh 运行时下载） |
| {MAJOR}/slim/Dockerfile | dockerfiles/{version}/debian-slim/Dockerfile | 1:1 拷贝 + sed 替换 |
| {MAJOR}/alpine/Dockerfile | dockerfiles/{version}/alpine/Dockerfile | 1:1 拷贝（alpine 不替换） |
| generate-stackbrew-library.sh | — | 上游已废弃（本地不迁移） |
| — | template/update.sh | 本地新增（下载 + sed 替换逻辑） |
| — | template/apply-templates.sh | 本地新增（空操作占位） |

注意：本地无 template/Dockerfile-*.template 模板文件，config.yml 中的 template 字段名仅为占位（apply 为空操作，build.py 不校验）。

## 改动清单

- 渲染: 弃用模板方案（4445a21），改为 update.sh 直接下载上游 Dockerfile
- 基础镜像: 按主版本 sed 替换 FROM 行的 debian 版本（保留 -slim 后缀）：24-25 → bullseye，26-27 → bookworm，28-29 → forky
- 下载校验: 下载后 head -1 验证文件以 FROM 开头，防止 404 页被当 Dockerfile 构建
- 版本范围: get_versions.sh 当前仅跟踪主版本 29（24-28 已注释，见脚本内 MAJOR_VERSIONS）

## 变量表

无本地模板占位符（Dockerfile 为上游成品，变量都是上游 Dockerfile 内部的 ARG/ENV）。

## 上游同步清单

1. 上游新增主版本目录时，在 update.sh 的 DEBIAN_VERSION case 与 VARIANT_PATHS 中补充
2. 上游改用其他基础镜像名时，核对 sed 替换正则 `^(FROM (buildpack-deps|debian):)...` 是否仍匹配
3. 需恢复多主版本跟踪时，改 get_versions.sh 的 MAJOR_VERSIONS

## 已知问题

- 无未解决问题
