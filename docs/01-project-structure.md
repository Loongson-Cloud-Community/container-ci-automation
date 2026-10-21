# 01 — 项目结构（静态参考）

> 只描述「仓库现在长什么样、每个部分干什么、约束是什么」。
> 操作流程见 `02-add-project.md`，历史问题与修复经验见 `03-ai-maintenance-log.md`。

## 仓库目录树

```
config.yml                          ← 全局配置（仅 registry）
AGENTS.md                           ← 仓库入口：文档路由 + 修改权限
docs/
├── 01-project-structure.md         ← 本文件
├── 02-add-project.md               ← 新增项目流程 + 项目 AGENTS.md 模板规范
└── 03-ai-maintenance-log.md        ← AI 维护记录（追加式）

tools/
├── build.py                        ← 统一构建入口（所有项目共用）
└── pull_request.py                 ← PR 变更目录解析（CI 用）

library/{project}/
├── AGENTS.md                       ← 项目级 AI 上下文（格式规范见 02）
├── config.yml                      ← 项目声明式配置
├── get_versions.sh                 ← 自定义版本脚本（type=script 时）
├── processed_versions.txt          ← 已构建版本跟踪（唯一被提交的生成物）
├── template/
│   ├── update.sh                   ← 取版本元数据 → 生成 versions.json
│   ├── apply-templates.sh          ← 渲染模板 → 生成 dockerfiles/
│   ├── Dockerfile-{variant}.template
│   └── {辅助文件}                   ← 如 docker-php-*、*.S、httpd-foreground
└── dockerfiles/                    ← 生成的构建目录（被 .gitignore 排除，不提交）

.github/workflows/
├── library-{project}.yml           ← 每个项目一个薄封装（定时 + 手动触发）
├── build.yml                       ← 可复用：仅构建（PR 验证用）
├── build-push.yml                  ← 可复用：构建 + 推送 + 提交版本跟踪
└── pull-request.yml                ← PR / merge-push 动态调度
```

## 文件职责

| 文件 | 性质 | 职责 |
|------|------|------|
| `config.yml` | 配置 | 全局 registry（如 `lcr.loongnix.cn`），推送时拼在镜像名前 |
| `tools/build.py` | 工具 | 版本获取 → 去重 → update.sh → apply-templates.sh → buildx 构建 → 推送 → 版本记录 |
| `tools/pull_request.py` | 工具 | 由 PR 变更文件推导受影响项目目录，写入 CI 的 `dynamic_ci_name` |
| `library/{p}/config.yml` | 配置 | 项目标识、版本来源、变体与 tag 声明 |
| `library/{p}/get_versions.sh` | 脚本 | 输出版本号，每行一个；仅 `version_source.type=script` 时被调用 |
| `library/{p}/processed_versions.txt` | 数据 | 已推送版本号，每行一个；build.py 据此跳过重复构建 |
| `library/{p}/template/update.sh` | 脚本 | `$1`=版本号；拉取该版本元数据（checksum、GPG key、基础镜像版本等）写入 `template/versions.json` |
| `library/{p}/template/apply-templates.sh` | 脚本 | `$1`=版本号；读 versions.json，渲染模板，输出 `dockerfiles/{version}/{variant}/`（Dockerfile + 构建所需辅助文件） |
| `library/{p}/template/Dockerfile-*.template` | 模板 | 每个变体一个；FROM 不带 registry 前缀（例外见下「FROM 前缀的历史变化」） |
| `library/{p}/dockerfiles/` | 生成物 | 构建上下文；由 `.gitignore` 的 `**/dockerfiles/` 排除，不进 git |
| `library/{p}/AGENTS.md` | 文档 | 该项目与上游的派生关系（映射表、改动清单、变量表），格式规范见 02 |
| `.github/workflows/library-{p}.yml` | CI | cron 定时 + workflow_dispatch，调用 build-push.yml |

## config.yml schema

### 全局（`config.yml`）

```yaml
registry: "lcr.loongnix.cn"   # 推送目标；构建本地 tag 不带此前缀
```

### 项目（`library/{p}/config.yml`）

```yaml
project:
  org: library                    # 必填
  name: ruby                      # 必填；org/name 唯一标识项目

version_source:                   # 必填
  type: github_releases           # github_releases | script
  repository: "ruby/ruby"         # type=github_releases 时必填
  tag_regex: "^v([0-9]+\\.[0-9]+\\.[0-9]+)$"  # 可选：从 tag 提取版本号
  script: get_versions.sh         # type=script 时必填

variants:                         # 必填，至少一个
  - name: "debian"                # 必填且唯一；对应 dockerfiles/{version}/{name}/ 目录名
    template: "Dockerfile-debian.template"   # 必填；须存在于 template/ 目录
    tags:                         # 必填，至少一个
      - "{version}"
      - "latest"
```

### 约束规则

| 规则 | 说明 |
|------|------|
| `variants[].name` | 唯一，且是 `dockerfiles/{version}/` 下的目录名 |
| `variants[].template` | 文件必须在 `template/` 下存在（erlang 例外：apply 为空操作，不校验模板） |
| `variants[].tags` | 只允许 `{version}` `{major_version}` `{minor_version}` 三个变量占位符 |
| 变体命名 | 不含基础镜像版本（用 `debian`/`alpine`，不用 `forky`/`alpine3.24`） |

### tag 变量渲染（build.py 负责）

| 变量 | 含义 | 示例（`3.24.1`） |
|------|------|------|
| `{version}` | 完整版本号 | `3.24.1` |
| `{major_version}` | 主版本号 | `3` |
| `{minor_version}` | 次版本号 | `3.24` |

仅语义版本 `a.b.c` 会拆出 major/minor；其他格式（如 debian 的时间戳版本 `20250521T073957Z`）三个变量都等于原串。

### 模板占位符（apply-templates.sh 负责，与 tag 变量无关）

| 占位符 | 含义 |
|------|------|
| `{VERSION}` | 完整版本号 |
| `{DEBIAN_VERSION}` / `{ALPINE_VERSION}` | 基础镜像版本（值在 update.sh 里定义） |
| `{SHA256_*}` / `{URL_*}` / `{GPG_KEYS}` 等 | 项目自定义，由 update.sh 写入 versions.json |
| `{BLOCK_*}` | 预计算的整块文本（python/ruby），由 update.sh 生成、apply 时注入 |

## build.py 外部接口（不可随意变更）

```
python3 tools/build.py <project_dir> [version] [选项]

位置参数:
  project_dir        项目目录（如 library/ruby）
  version            可选；指定版本号（--test 常配合使用）

选项:
  --test, -t         测试模式：强制构建、不推送、不记录版本
  --dry-run, -n      仅打印命令，不执行
  --versions, -V     仅获取并输出版本号（stdout，每行一个），不做其他事
  --push             构建后 tag + push 到 registry；仅此模式会更新 processed_versions.txt
```

### 数据流

```
build.py library/ruby
  ├─ get_versions.sh → 版本列表（每行一个）
  ├─ 已在 processed_versions.txt ？→ 是则跳过（--test 除外）
  ├─ template/update.sh {version}       → template/versions.json
  ├─ template/apply-templates.sh {version} → dockerfiles/{version}/{variant}/Dockerfile
  ├─ docker buildx build --platform linux/{arch} --load -t org/name:{tag} {build_dir}
  │     平台由宿主机 platform.machine() 自动映射（loongarch64 → loong64）
  ├─ (--push) docker tag org/name:{tag} → registry/org/name:{tag} && docker push
  └─ (--push 且非 --test/--dry-run) 追加 version 到 processed_versions.txt
```

## 关键约束

1. **构建 tag 与推送 tag 分离**：本地构建用 `org/name:tag`，推送时才拼 registry 前缀。
2. **FROM 不带 registry 前缀**：模板 FROM 与上游一致，基础镜像来源由宿主机 Docker 配置解析。（历史例外：php 模板曾在模板内加前缀，后随全局 registry 重构统一回归，见 `313637c`。以当前模板实际内容为准。）
3. **processed_versions.txt 是唯一被提交的生成物**；dockerfiles/、versions.json、out/ 均被根 `.gitignore` 排除。
4. **版本记录仅在真正推送时发生**：`--push` 且非 `--test`、非 `--dry-run` 才写 processed_versions.txt。
5. **并发冲突在 CI 层解决**：build-push.yml 推送失败时 `git pull --rebase` 重试（1 次）。
6. **单基础镜像版本**：上游若支持多个 alpine/debian 版本，本地只构建最新一个，版本值留在 update.sh。
7. **Debian 统一 forky**（LoongArch64 约束，不支持 trixie/bookworm；erlang 按主版本例外保留上游映射）。

## CI 结构

| workflow | 触发 | 行为 |
|------|------|------|
| `library-{p}.yml` | cron 定时 + workflow_dispatch（可传 version） | 调 `build-push.yml`，构建 + 推送 + 提交版本跟踪 |
| `build.yml` | 被 pull-request.yml 调用 | 仅构建（PR 验证） |
| `build-push.yml` | 被 library-*.yml / pull-request.yml 调用 | 构建 + 推送；提交 `processed_versions.txt`（`chore({project}): 更新版本跟踪`），push 冲突自动 rebase 重试 |
| `pull-request.yml` | PR、merge 到 main | `pull_request.py ci-name` 算出首个变更目录 → 动态选择构建目标 |

`pull_request.py` 忽略前缀：`.github/`、`docs/`、`tools/` —— 只改文档/工具不会触发镜像构建。

## 特殊项目形态（模板规范内的既有例外）

| 项目 | 形态 | 说明 |
|------|------|------|
| alpine | 产物打包 | 无上游 Dockerfile；FROM scratch + ADD minirootfs |
| debian | rootfs 构建 | 用 debuerreotype 构建 rootfs，版本号为快照时间戳 |
| erlang | 上游直下 | update.sh 直接下载上游 Dockerfile + sed 替换基础镜像版本；apply-templates.sh 为空操作 |
| php | 多辅助文件 | 7 个变体模板 + docker-php-* 脚本 + loongarch64 fiber 汇编文件 |
