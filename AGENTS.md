# Container CI Automation

## 项目用途

适用于 LoongArch64 架构的多项目容器镜像构建流水线

## 文件地图

| 文件 | 功能 | 性质 |
|------|------|------|
| `AGENTS.md`（本文件） | 文档路由 + 场景指引 + 修改权限契约 | 入口 |
| `docs/01-project-structure.md` | 仓库结构、config schema、build.py 接口、数据流、关键约束 | 规范（描述现状） |
| `docs/02-maintenance-log.md` | 已修复问题与根因，累积经验；只追加 | 日志（发生过什么） |
| `{org}/{project}/AGENTS.md` | 该项目与上游的派生关系（映射表、改动清单、变量表） | 项目级上下文 |
| `config.yml` / `{组织}/{项目}/config.yml` | 全局 registry / 项目声明式配置 | 配置 |

## 调用方式

```bash
python3 tools/build.py library/ruby              # 构建（不推送、不记录）
python3 tools/build.py --test library/ruby 4.0.6 # 测试构建单版本（不推送）
python3 tools/build.py --dry-run library/ruby    # 仅打印命令
python3 tools/build.py --versions library/ruby   # 仅输出版本号
python3 tools/build.py --push library/ruby       # 构建 + 推送 + 记录版本
```

## 修改权限矩阵

| 文件 | 何时允许改 | 修改方式 |
|------|-----------|---------|
| 本文件 | 新增/删除文档、工具或调用方式变化 | 一次性改 |
| docs/01 | 仓库结构 / config schema / build.py 接口实际变化 | 随代码同步改 |
| docs/02 | 任何修复、踩坑、经验 | 只追加，永不改写/删除历史条目 |
| `{org}/{proj}/AGENTS.md` | 该项目代码与上游关系变化（映射、改动、同步 commit、未解决问题增减） | 随项目代码同步改；禁止写全局信息（命令/registry/平台） |
| `config.yml` / `{org}/{proj}/config.yml` | 构建需要 | 按需改；影响面大时在 03 记一条 |
