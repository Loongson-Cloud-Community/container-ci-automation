# Container CI Automation — AGENTS.md

## 项目用途

将 container-ci 中 70+ 个项目的镜像构建从「每项目手写脚本」转为「声明式配置 + 统一工具」：项目只需 `config.yml` + `template/`，构建、推送、版本跟踪由 `tools/build.py` 统一完成。目标平台 linux/loong64，推送至 `lcr.loongnix.cn`。

## 文件地图

| 文件 | 功能 | 性质 |
|------|------|------|
| `AGENTS.md`（本文件） | 文档路由 + 场景指引 + 修改权限契约 | 入口 |
| `docs/01-project-structure.md` | 仓库结构、config schema、build.py 接口、数据流、关键约束 | 规范（描述现状） |
| `docs/02-add-project.md` | 新增项目 10 步流程 + 项目级 AGENTS.md 模板规范 | 操作手册（怎么做） |
| `docs/03-ai-maintenance-log.md` | 已修复问题与根因，累积经验；只追加 | 日志（发生过什么） |
| `library/{项目}/AGENTS.md` | 该项目与上游的派生关系（映射表、改动清单、变量表） | 项目级上下文 |
| `config.yml` / `library/{项目}/config.yml` | 全局 registry / 项目声明式配置 | 配置 |

## 调用方式

```bash
python3 tools/build.py library/ruby              # 构建（不推送、不记录）
python3 tools/build.py --test library/ruby 4.0.6 # 测试构建单版本（不推送）
python3 tools/build.py --dry-run library/ruby    # 仅打印命令
python3 tools/build.py --versions library/ruby   # 仅输出版本号
python3 tools/build.py --push library/ruby       # 构建 + 推送 + 记录版本
```

完整参数与数据流见 docs/01。

## 场景路由：什么时候用什么、改什么

| 场景 | 先读 | 允许改 |
|------|------|--------|
| 理解仓库结构 / 配置字段含义 / build.py 行为 | docs/01 | 不改（结构变了才改 01） |
| 新增一个项目 | docs/02 | 新建 `library/新项目/**`；流程本身有变才改 02 |
| 构建失败排查修复 | 该项目 AGENTS.md + docs/03 | 改该项目 `template/`、`config.yml`；结论追加进 03 |
| 同步该项目上游更新 | 该项目 AGENTS.md（映射表 + 同步清单） | 改模板 + 更新该 AGENTS.md 的映射/同步 commit |
| 发现跨项目通用新约束 | docs/03 | 写 03 的「通用经验」；结构/流程真变了才改 01/02 |
| 修复构建错误时想"记一笔" | — | 只写 03；禁止为记录而改 01/02/本文件 |

## 修改权限矩阵

| 文件 | 何时允许改 | 修改方式 |
|------|-----------|---------|
| 本文件 | 新增/删除文档、工具或调用方式变化 | 一次性改 |
| docs/01 | 仓库结构 / config schema / build.py 接口实际变化 | 随代码同步改 |
| docs/02 | 新增项目流程或项目 AGENTS.md 模板规范变化 | 随流程同步改 |
| docs/03 | 任何修复、踩坑、经验 | 只追加，永不改写/删除历史条目 |
| `library/{p}/AGENTS.md` | 该项目代码与上游关系变化（映射、改动、同步 commit、未解决问题增减） | 随项目代码同步改；禁止写全局信息（命令/registry/平台） |
| `config.yml` / `library/{p}/config.yml` | 构建需要 | 按需改；影响面大时在 03 记一条 |

## 项目 AGENTS.md 必备内容（规范正文在 docs/02）

上游信息（仓库 + 上次同步 commit）、映射表、改动清单、变量表四项必填；上游同步清单 / LoongArch64 约束 / 已知问题可省略。已解决问题从项目 AGENTS.md 删除并记入 docs/03。
