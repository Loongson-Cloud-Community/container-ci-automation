# library/erlang — AI Agent 上下文

## 项目信息

- **上游仓库**: https://github.com/erlang/docker-erlang-otp.git
- **迁移范围**: 主版本 24-29（共 6 个大版本）
- **变体**: debian（默认）、debian-slim、alpine
- **构建方式**: 从源码编译 OTP，附带 rebar 和 rebar3

## 上游结构

```
docker-erlang-otp/
├── {MAJOR_VERSION}/           # 24/, 25/, ..., 29/
│   ├── Dockerfile             # 默认变体（buildpack-deps）
│   ├── slim/Dockerfile        # slim 变体（debian）
│   └── alpine/Dockerfile      # alpine 变体
└── generate-stackbrew-library.sh
```

## 版本差异

| 主版本 | 基础镜像 | OTP 下载 URL | REBAR3 |
|--------|----------|--------------|--------|
| 24-25 | bullseye | archive/ | 3.23-3.24 |
| 26 | bookworm | archive/ | 3.26 |
| 27-29 | bookworm/trixie | releases/download/ | 3.27 |

## 构建流程

Dockerfile 直接从上游下载，无需模板渲染：

```
get_versions.sh → 获取最新 OTP 版本
update.sh       → 下载上游 Dockerfile 到 dockerfiles/{version}/{variant}/
apply-templates.sh → 空操作（Dockerfile 已就绪）
build.py        → docker build
```

## 模板变量（上游 Dockerfile 内部使用）

| 变量 | 说明 | 示例 |
|------|------|------|
| OTP_VERSION | OTP 版本号 | 28.5.0.6 |
| REBAR3_VERSION | rebar3 版本号 | 3.27.0 |
| OTP_DOWNLOAD_URL | OTP 源码下载 URL | https://github.com/... |
| OTP_DOWNLOAD_SHA256 | OTP 源码 SHA256 | 49d7a75... |
| REBAR3_DOWNLOAD_SHA256 | rebar3 SHA256 | 985cae6... |
| runtimeDeps | 运行时依赖 | libodbc2 libsctp1 ... |
| buildDeps | 构建依赖 | unixodbc-dev libsctp-dev |

## 本地调整

- FROM 行不需要添加 registry 前缀（Docker 系统配置默认仓库）
- 只支持构建上游最新版本（按大版本匹配）

## 构建命令

```bash
# 测试单个版本
python3 tools/build.py --test library/erlang 28.5.0.6

# 生产构建
python3 tools/build.py library/erlang
```
