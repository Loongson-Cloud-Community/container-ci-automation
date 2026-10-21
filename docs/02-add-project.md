# 02 — 新增项目流程（AI Agent 操作手册）

> 只回答「怎么做」。仓库结构与约束见 `01-project-structure.md`，踩坑记录见 `03-ai-maintenance-log.md`。
> 遇到构建报错先查 03，不要重复踩同一个坑。

## 前置输入

- 上游仓库地址（GitHub 或其他）
- 目标 org/name（一般为 `library/{name}`）
- 上游支持的变体（debian / debian-slim / alpine / 其他）

## 步骤总览

```
1 分析上游 → 2 建目录+config.yml → 3 提取变量+拆分模板 → 4 update.sh
→ 5 apply-templates.sh → 6 版本来源 → 7 验证 → 8 workflow → 9 AGENTS.md → 10 首次推送
```

## 步骤 1：分析上游

1. 阅读上游 README 和目录结构，找到模板文件与渲染脚本。
2. 阅读上游 `versions.sh` / `update.sh` / `apply-templates.sh`，理解版本获取与渲染逻辑。
3. 实际运行上游脚本，拿到最终生成的 Dockerfile——这是提取变量的基准。
4. 判断上游形态，选择本地方案：
   - jinja / jq-template.awk 混合模板 → 拆分为每变体一个独立模板（步骤 3）
   - 每版本目录的成品 Dockerfile（如 erlang）→ 直接下载 + sed 替换基础镜像版本，apply-templates.sh 置空
   - 无 Dockerfile 只有产物（如 alpine minirootfs）→ FROM scratch + ADD 产物

## 步骤 2：建目录与 config.yml

```
library/{name}/
├── config.yml
├── get_versions.sh          （type=script 时）
├── processed_versions.txt   （空文件即可）
└── template/
```

config.yml 骨架（字段含义见 01）：

```yaml
project:
  org: library
  name: {name}

version_source:
  type: script                # 或 github_releases + repository + tag_regex
  script: get_versions.sh

variants:
  - name: "debian"
    template: "Dockerfile-debian.template"
    tags:
      - "{version}"
      - "{minor_version}"
      - "latest"              # latest 只给 debian（或唯一变体）
  - name: "alpine"
    template: "Dockerfile-alpine.template"
    tags:
      - "{version}-alpine"
      - "{minor_version}-alpine"
```

注意：模板文件名必须与 `template` 字段逐字对应（如 `Dockerfile-alpine.template`）。

## 步骤 3：提取变量与拆分模板

1. 对比上游最终 Dockerfile，找出随版本变化的值，替换为 `{VAR}` 占位符。
   常见：`{VERSION}`、`{SHA256}`、`{URL_xxx}`、`{ALPINE_VERSION}`、`{DEBIAN_VERSION}`、`{GPG_KEYS}`。
2. 上游混合模板拆分原则：
   - 每个模板文件只含一个变体的完整内容
   - 移除所有 jinja / awk 条件逻辑（需要条件的整块内容由 update.sh 预计算为 `{BLOCK_*}`）
   - 保留完整 Dockerfile 语法，使用统一占位符
3. FROM 保持与上游一致，不加 registry 前缀。
4. 模板中不得出现基础镜像版本数字（`3.24`、`forky` 只能以 `{ALPINE_VERSION}`/`{DEBIAN_VERSION}` 出现）。

## 步骤 4：写 update.sh

1. 接收参数 `$1` = 版本号；脚本开头 `cd "$(dirname "$(readlink -f "$BASH_SOURCE")")"`。
2. 集中定义基础镜像版本（禁止单独 `.version` 文件）：

   ```bash
   ALPINE_VERSION="3.24"
   DEBIAN_VERSION="forky"
   ```

3. 从上游 API / 下载站获取该版本元数据（checksum、GPG key、下载 URL 等）。
4. 生成 `versions.json`，key 为版本号，value 只含模板渲染所需字段（精简原则）。

## 步骤 5：写 apply-templates.sh

1. 接收参数 `$1` = 版本号；脚本开头同样 cd 到自身目录。
2. 用 `jq` 从 versions.json 提取变量，用 `sed` 渲染模板中所有 `{VAR}` 占位符。
3. 输出到 `dockerfiles/{version}/{variant}/Dockerfile`，需要的辅助文件（entrypoint 脚本、rootfs 等）一并复制到同目录。
4. 变体遍历以 config.yml 的 `variants[].name` 为准，目录名逐字一致。
5. 工具选择：sed 做简单替换，jq 做 JSON 提取，尽量不用 Python；新建 .sh 必须 `chmod +x`。

## 步骤 6：版本来源

- `type: github_releases`：config.yml 写 repository + tag_regex，无需脚本。
- `type: script`：写 `get_versions.sh`，stdout 输出版本号每行一个（可多行，build.py 逐个处理）。

## 步骤 7：验证

按顺序执行，全部通过才算完成：

```bash
# 1. 语法检查
bash -n library/{name}/template/*.sh library/{name}/get_versions.sh

# 2. 版本获取
python3 tools/build.py --versions library/{name}

# 3. 渲染检查（不真构建）
python3 tools/build.py --dry-run library/{name}

# 4. 实际构建单版本（不推送）
python3 tools/build.py --test library/{name} {version}

# 5. 对比生成的 Dockerfile 与上游最终 Dockerfile，确认功能逻辑一致
```

## 步骤 8：workflow

`.github/workflows/library-{name}.yml`，参考现有项目：

```yaml
name: "Build/library/{name}"

on:
  schedule:
    - cron: '0 16 * * *'      # 北京时间 00:00
  workflow_dispatch:
    inputs:
      version:
        description: '指定版本号（留空=自动检测）'
        required: false
        type: string

jobs:
  build:
    uses: ./.github/workflows/build-push.yml
    with:
      project: library/{name}
      version: ${{ inputs.version || '' }}
```

## 步骤 9：写项目 AGENTS.md（模板规范见下）

## 步骤 10：首次推送

```bash
python3 tools/build.py --push library/{name}
```

推送成功后 build.py 自动记录 processed_versions.txt；确认 CI 提交了版本跟踪。

---

# 项目 AGENTS.md 模板规范

## 位置与目的

`library/{project}/AGENTS.md`。核心目的：让 AI Agent 不看上游仓库也能回答「本地这份代码是怎么从上游变来的」。

## 节定义

| 节 | 必填 | 内容 |
|------|------|------|
| 上游信息 | 必填 | 上游仓库地址 + 上次同步的上游 commit 号（+ 分支） |
| 映射表 | 必填 | 上游文件 → 本地文件的逐条对应关系 |
| 改动清单 | 必填 | 本地相对上游改了什么、改在哪个文件 |
| 变量表 | 必填 | 模板自定义占位符及其来源 |
| 上游同步清单 | 可省 | 同步该项目上游时必查的点；无特殊点写「无」或省略 |
| LoongArch64 约束 | 可省 | 仅该项目相关的平台约束 / 已禁用变体及原因；无则省略 |
| 已知问题 | 可省 | 仅未解决且影响构建的问题；已解决的写 03 后从此删除 |

## 模板骨架

```markdown
# {project}

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/{project} |
| 分支 | master |
| 上次同步 commit | {hash} |
| 上游渲染方式 | jq-template.awk / 成品 Dockerfile / 无（产物打包） |

## 映射表

| 上游路径 | 本地路径 | 关系 |
|----------|----------|------|
| Dockerfile-linux.template | template/Dockerfile-debian.template | 拆分 |
| 同上 | template/Dockerfile-alpine.template | 拆分 |
| versions.sh | template/update.sh | 重写（bash + jq + sed） |
| apply-templates.sh | template/apply-templates.sh | 重写（jq 提取 + sed 渲染） |
| — | template/Dockerfile-xxx.template | 本地新增 |

关系取值：1:1 拷贝 / 拆分 / 重写 / 本地新增 / 上游已废弃

## 改动清单

- 基础镜像: debian → forky，alpine → 3.24（值集中在 template/update.sh）
- 模板: FROM 保持上游通用形式，不加 registry 前缀
- 架构: {新增/删除的架构处理，改在哪个文件}
- 依赖: {增删的包及原因}
- 逻辑删除: {删掉的上游逻辑及原因}

## 变量表

| 占位符 | 来源 | 说明 |
|--------|------|------|
| {VERSION} | update.sh | 完整版本号 |
| {CUSTOM_X} | update.sh | {含义} |

## 上游同步清单

1. {必查点，如：检查 rust.json 架构映射是否新增}
2. {必查点}

## LoongArch64 约束

- {仅该项目的约束}

## 已知问题

- {未解决且影响构建的问题；解决后删除并记入 docs/03}
```

## 填写规则

1. **禁止写入全局信息**：构建命令、registry、平台、Dry run 用法等一律不写（根 AGENTS.md 与 01 已覆盖），项目 AGENTS.md 只写「与上游的差异」。
2. **禁止写入通用变量**：`{VERSION}`/`{MAJOR_VERSION}`/`{VARIANT}` 等通用占位符不必入变量表；只列项目自定义的。
3. **上游类型非 Dockerfile 派生**（如 alpine 的产物打包）：映射表改写为「输入产物来源 → 本地用途」，上游渲染方式写「无」。
4. **成品 Dockerfile 直下型**（如 erlang）：映射表按变体列出上游路径，关系写「1:1 拷贝 + sed 替换基础镜像」。
5. **上次同步 commit**：每次同步上游后必须更新为同步时的上游 commit hash。
6. **已知问题只留未解决项**；修复后删除该条，结论写入 `docs/03-ai-maintenance-log.md`。

## 合规检查清单

- [ ] 上游信息：仓库地址、上次同步 commit 都有值
- [ ] 映射表、改动清单、变量表三节齐全
- [ ] 无构建命令 / registry / 平台等全局信息
- [ ] 无 `{VERSION}` 等通用变量条目
- [ ] 已知问题节只含未解决项（或整节省略）
- [ ] 与 config.yml / template/ 实际文件一致（映射表里的本地路径都存在）
