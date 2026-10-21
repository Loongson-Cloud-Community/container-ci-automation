# 03 — AI 维护记录（追加式日志）

> 记录「遇到过什么问题 → 根因 → 怎么修 → 适用范围 → commit」。
> 结构定义见 `01-project-structure.md`，操作流程见 `02-add-project.md`。

## 写入约定

- **何时写**：修复构建错误、上游变更适配踩坑、迁移/重构中定位到根因的问题。
- **只追加**：已有条目永不改写、永不删除；写错就再加一条更正。
- **归属规则**：
  - 已解决的问题 → 只写这里；对应项目 AGENTS.md 的「已知问题」节删除该条。
  - 未解决且影响该项目构建的问题 → 留在项目 AGENTS.md 的「已知问题」节；解决后迁到这里。
  - 跨项目通用结论 → 只写这里（`通用经验` 节），项目 AGENTS.md 不重复。
- **禁止**：为"记录"而修改 `01`/`02`——文档不是修复对象。

## 条目模板

```
### YYYY-MM-DD {项目或 ci} — 一句话现象
- 现象:
- 根因:
- 修复:
- 适用范围: （单项目 / 所有项目 / CI）
- commit: {hash}
```

## 通用经验

- **sed 渲染模板时占位符之间不能有交叉依赖**：如上游 `from` 变量既要用于 FROM 行又要用于 `is_alpine` 判断，直接替换会破坏条件逻辑；应保留原值或在 update.sh 预计算整块（`2363ef7`）。
- **apply-templates.sh 内部操作的相对路径**：gawk/jq 访问模板文件前必须先 `cd` 到 template 目录，否则从 build.py 调用（cwd=template）与手动调用（cwd=仓库根）行为不一致（`d9dd59a`）。
- **jq 字符串拼接易漏引号**：构造 versions.json 提取命令时注意闭合，否则脚本运行到一半才报错（`79ca4ad`）。
- **上游 jinja/awk 混合模板必须拆成每变体一个独立模板**，拆分时先跑通上游原始脚本拿到最终 Dockerfile，再逐行对照提取变量（流程见 02）。
- **模板 FROM 保持上游通用形式**，registry 前缀只在推送时由 build.py 拼接；历史上曾在模板内写死前缀，已统一回归（`313637c`）。
- **变体目录名与 config.yml `variants[].name` 必须逐字一致**，否则 build.py 找不到 Dockerfile 静默跳过（`5f78920`）。

## 条目

### 2026-09-21 ci — 定时流水线在 Actions 列表中难以辨识
- 现象: 多个项目定时流水线混在一起，无法快速定位。
- 根因: workflow name 未按项目分组。
- 修复: 定时流水线统一加 `Build/` 前缀（先用 `Build:` 后改 `/`，因 Actions 分组特性）。
- 适用范围: CI
- commit: `9d17102`, `0ab22c6`

### 2026-09-21 library/alpine — minirootfs 下载 404
- 现象: update.sh 下载 minirootfs 返回 404。
- 根因: Alpine 下载站目录段用的是 minor 版本（`v3.24/`），脚本曾用 full version / `latest-stable` 拼 URL，连续修正 4 次才对。
- 修复: URL 路径用 minor version：`https://cz.alpinelinux.org/alpine/v{minor}/releases/loongarch64/alpine-minirootfs-{version}-loongarch64.tar.gz`。
- 适用范围: library/alpine
- commit: `c70f0e0`, `dc6aeec`, `1ee7b60`, `ea02825`

### 2026-09-21 library/erlang — 模板渲染方案废弃
- 现象: 按模板流程维护 erlang 成本高（上游 6 个主版本各自独立 Dockerfile，差异大）。
- 根因: 上游本身就是"每版本一目录"的成品 Dockerfile，本地再模板化是重复劳动。
- 修复: 改为 update.sh 直接下载上游 Dockerfile + sed 替换基础镜像版本（24-25 bullseye / 26-27 bookworm / 28-29 forky）；apply-templates.sh 为空操作。
- 适用范围: library/erlang
- commit: `4445a21`

### 2026-08-06 library/debian — apply-templates.sh jq 语法错误
- 现象: 脚本执行中途报 jq 解析错误。
- 根因: 构造的 jq 字符串缺少闭合引号。
- 修复: 补全引号。
- 适用范围: library/debian
- commit: `79ca4ad`

### 2026-08-05 全局 — 模板 FROM 写死 registry 前缀
- 现象: 模板内 FROM 带 `lcr.loongnix.cn/` 前缀，与上游 diff 噪音大，换 registry 需改所有模板。
- 根因: 早期把 registry 硬编码进模板。
- 修复: registry 提取到根 config.yml；模板 FROM 回归上游通用形式，推送时由 build.py 拼前缀。
- 适用范围: 所有项目
- commit: `313637c`

### 2026-08-05 library/golang — build.py 找不到 Dockerfile
- 现象: 构建时提示 Dockerfile 不存在，跳过变体。
- 根因: apply-templates.sh 生成的变体目录名与 config.yml `variants[].name` 不一致。
- 修复: 目录名统一为 `debian`。
- 适用范围: library/golang（同类问题适用所有项目）
- commit: `5f78920`

### 2026-08-05 library/php — 7 变体模板重构
- 现象: 单模板 + blocks/ 目录维护 7 个变体困难。
- 根因: 上游 Dockerfile-linux.template 的条件逻辑被整体搬进本地 blocks/，sed 无法可靠渲染。
- 修复: 拆分为 7 个独立完整模板，删除 blocks/ 目录。
- 适用范围: library/php
- commit: `7c91ae7`

### 2026-08-04 library/php — loongarch64 fiber 支持缺失
- 现象: PHP 在 loong64 上编译/运行时 fiber 相关符号缺失。
- 根因: 上游 fiber 实现依赖 x86/AArch64 汇编，loong64 无对应文件。
- 修复: 预下载 `jump_loongarch64_sysv_elf_gas.S` / `make_loongarch64_sysv_elf_gas.S` 到 template/，apply 时 COPY 进构建目录（后续又修正为不依赖上游 patch 文件的方式）。
- 适用范围: library/php（PHP 8.2）
- commit: `ecc12fb`, `6c6b20b`

### 2026-08-04 library/php — Alpine loong64 swapcontext 链接错误
- 现象: Alpine 变体链接阶段报 swapcontext 未定义。
- 根因: musl 不提供 swapcontext，PHP fiber 依赖它。
- 修复: Alpine loong64 构建时安装 `libucontext-dev` 并设置 LIBS。
- 适用范围: library/php（Alpine 8.2/8.3）
- commit: `176fde0`

### 2026-08-04 library/php — loong64 不支持 pcre JIT
- 现象: PHP 在 loong64 上启用 pcre-jit 编译/运行失败。
- 根因: bundled pcre 的 JIT 不支持 loongarch64。
- 修复: 模板中按 `gnuArch` 判断，loongarch64 时加 `--without-pcre-jit`。
- 适用范围: library/php（所有变体）
- commit: `1f065a6`

### 2026-08-04 library/php — 上游 patch 文件依赖导致构建失败
- 现象: 依赖上游 patch 文件的方案在构建环境中失败。
- 根因: patch 文件未随构建上下文提供。
- 修复: 改为直接内联修改 + 汇编文件随 template 分发。
- 适用范围: library/php
- commit: `6c6b20b`

### 2026-08-04 通用 — apply-templates.sh 相对路径不一致
- 现象: 手动运行正常，被 build.py 调用时报文件找不到。
- 根因: 脚本未先 cd 到自身目录，依赖调用方 cwd。
- 修复: 脚本开头统一 `cd "$(dirname "$(readlink -f "$BASH_SOURCE")")"`。
- 适用范围: 所有项目的 template/*.sh
- commit: `d9dd59a`

### 2026-08-04 通用 — sed 替换破坏上游条件逻辑
- 现象: Alpine Dockerfile 渲染后 is_alpine 判断失效。
- 根因: `from` 变量被过早替换，模板条件分支读不到原始值。
- 修复: 保留原变量供条件判断，或在 update.sh 预计算整块文本（{BLOCK_*}）。
- 适用范围: 所有项目
- commit: `2363ef7`

### 2026-08-04 library/node — Alpine loong64 源码编译失败（未解决）
- 现象: Alpine 变体从源码编译 Node.js 失败。
- 根因: loong64 无 musl 预编译二进制（unofficial-builds 只有 glibc），源码编译待排查。
- 修复: 暂无；config.yml 中已移除 alpine 变体（当前仅 debian + debian-slim）。
- 适用范围: library/node
- commit: `bf3c455`（迁移时状态）

### 2026-08-03 library/alpine — 脚本执行权限缺失
- 现象: build.py 调用 update.sh 报 Permission denied。
- 根因: 新建 .sh 未 chmod +x。
- 修复: 补执行权限（build.py 对 get_versions.sh 有自动 chmod，template/ 下脚本需自行保证）。
- 适用范围: 所有新建脚本
- commit: `acfe73f`

### 2026-08-04 ci — pull-request.yml 使用不存在的 replace() 函数
- 现象: workflow 运行报表达式错误。
- 根因: GitHub Actions 表达式没有字符串替换函数。
- 修复: 在 shell 里做 `library::alpine` → `library/alpine` 的转换。
- 适用范围: CI
- commit: `386a672`
