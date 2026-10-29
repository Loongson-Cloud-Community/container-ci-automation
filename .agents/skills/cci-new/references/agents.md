# 项目 AGENTS.md 模板规范

## 位置与目的

`{org}/{project}/AGENTS.md`。核心目的：让 AI Agent 不看上游仓库也能回答「本地这份代码是怎么从上游变来的」。

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
# {org}/{project}

## 上游信息

| 字段 | 值 |
|------|-----|
| 仓库 | https://github.com/docker-library/{project} |
| 分支 | master |
| 上次同步 commit | {hash}（上次成功检查的上游 HEAD，同步脚本维护） |
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

- {未解决且影响构建的问题}
```

## 填写规则

1. **禁止写入全局信息**：构建命令、registry、平台、Dry run 用法等一律不写（根 AGENTS.md 与 01 已覆盖），项目 AGENTS.md 只写「与上游的差异」
2. **禁止写入通用变量**：`{VERSION}`/`{MAJOR_VERSION}`/`{VARIANT}` 等通用占位符不必入变量表；只列项目自定义的
3. **上游类型非 Dockerfile 派生**（如 alpine 的产物打包）：映射表改写为「输入产物来源 → 本地用途」，上游渲染方式写「无」
4. **成品 Dockerfile 直下型**：映射表按变体列出上游路径，关系写「1:1 拷贝 + sed 替换基础镜像」
5. **上次同步 commit**：记录「该模板基线」
6. **已知问题只留未解决项**；修复后删除该条，结论写入 

## 合规检查清单

- [ ] 上游信息：必填；「上次同步 commit」必填
- [ ] 映射表、改动清单、变量表三节齐全
- [ ] 无构建命令 / registry / 平台等全局信息
- [ ] 无 `{VERSION}` 等通用变量条目
- [ ] 已知问题节只含未解决项（或整节省略）
- [ ] 与 config.yml / template/ 实际文件一致（映射表里的本地路径都存在）
