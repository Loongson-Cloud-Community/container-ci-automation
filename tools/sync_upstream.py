#!/usr/bin/env python3
"""tools/sync_upstream.py — 同步项目上游变更并刷新 AGENTS.md 的上次同步 commit

职责分工（脚本做机械活 + 把关，AI Agent 做模板合并）:
  脚本: 解析 AGENTS.md → 取上游 HEAD → compare 基线 diff → 1:1 拷贝自动同步
        → 调用 Agent 合并拆分/重写类模板 → 校验 → 写回 commit
  Agent: 仅处理「需人工合并」项（上游补丁 → 本地占位符模板的适配合并）

用法:
  python3 tools/sync_upstream.py library/ruby                # 完整同步（默认 hermes agent）
  python3 tools/sync_upstream.py library/ruby --dry-run      # 仅报告，不改任何文件
  python3 tools/sync_upstream.py library/ruby --agent none   # 不调用 Agent，只报告待合并项
  python3 tools/sync_upstream.py library/ruby --init         # 记录当前上游 HEAD 为初始基线

写回规则:
  校验全部通过才刷新「上次同步 commit」；有任何待合并/校验失败，基线不动，
  下次重跑还能拿到同一份 diff。

退出码: 0 成功/无更新; 1 校验失败或 Agent 失败; 2 用法/基线问题
"""

import argparse
import base64
import json
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 可扩展的 Agent 后端：命令模板。{prompt} 为提示词，工作目录固定为仓库根。
AGENT_BACKENDS = {
    "hermes": ["hermes", "-z", "{prompt}", "--in", str(ROOT), "--yolo"],
}

RELATION_INFO_SKIP = ("运行时依赖",)  # 映射表中标注这类关系的行不参与同步


# ── 日志 ────────────────────────────────────────────────────────────

def info(msg):
    print(f"[sync] {msg}", flush=True)


def warn(msg):
    print(f"[sync][WARN] {msg}", file=sys.stderr, flush=True)


# ── AGENTS.md 解析 ──────────────────────────────────────────────────

@dataclass
class Mapping:
    upstream: str      # 上游路径（可能含 {MAJOR} 等占位符）
    local: str         # 本地路径
    relation: str      # 1:1 拷贝 / 拆分 / 重写 / 本地新增 / 上游已废弃 / ...


@dataclass
class ProjectMeta:
    project: str
    agents_md: Path
    owner_repo: str | None    # "owner/repo"；非 GitHub 上游为 None
    branch: str
    baseline: str | None      # 上次同步 commit；未记录/不适用为 None
    baseline_note: str        # 原始单元格文本（用于识别"不适用"）
    mappings: list = field(default_factory=list)


def parse_table_cell(line, idx):
    """从 markdown 表格行取第 idx 个单元格（0-based），取不到返回 None"""
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells[idx] if len(cells) > idx else None


def parse_agents_md(project_dir: Path) -> ProjectMeta:
    agents_md = project_dir / "AGENTS.md"
    if not agents_md.exists():
        warn(f"{agents_md} 不存在")
        sys.exit(2)
    text = agents_md.read_text()

    owner_repo = branch = None
    baseline = None
    baseline_note = ""
    mappings = []
    section = None
    prev_upstream = ""

    for line in text.splitlines():
        h = re.match(r"^##\s+(\S+)", line)
        if h:
            section = h.group(1)
            continue

        if section == "上游信息" and line.strip().startswith("|"):
            key = parse_table_cell(line, 0) or ""
            val = parse_table_cell(line, 1) or ""
            if key in ("字段", "------") or set(key) <= {"-", ":"}:
                continue
            if "仓库" in key:
                m = re.search(r"github\.com/([^/\s]+/[^/\s.]+)", val)
                if m:
                    owner_repo = m.group(1).rstrip("/")
            elif "分支" in key:
                branch = val
            elif "commit" in key:
                baseline_note = val
                m = re.search(r"\b([0-9a-f]{7,40})\b", val)
                if m:
                    baseline = m.group(1)

        elif section == "映射表" and line.strip().startswith("|"):
            up, local, rel = (parse_table_cell(line, i) or "" for i in range(3))
            if not up or set(up) <= {"-", ":"} or up in ("上游路径",):
                continue
            if up == "同上":
                up = prev_upstream
            else:
                prev_upstream = up
            if local and rel:
                mappings.append(Mapping(up, local, rel))

    return ProjectMeta(
        project=project_dir.name,
        agents_md=agents_md,
        owner_repo=owner_repo,
        branch=branch or "master",
        baseline=baseline,
        baseline_note=baseline_note,
        mappings=mappings,
    )


def write_baseline(meta: ProjectMeta, commit: str):
    """只改 AGENTS.md「上次同步 commit」一行，其他内容不动"""
    text = meta.agents_md.read_text()
    short = commit[:12]
    new_text, n = re.subn(
        r"^\|\s*上次同步 commit\s*\|.*$",
        f"| 上次同步 commit | {short} |",
        text,
        count=1,
        flags=re.M,
    )
    if n != 1:
        warn("未能在 AGENTS.md 中定位「上次同步 commit」行")
        sys.exit(1)
    meta.agents_md.write_text(new_text)
    info(f"已写回上次同步 commit: {short}")


# ── GitHub 访问 ──────────────────────────────────────────────────────

def gh(args, jq=None):
    cmd = ["gh", "api"] + args
    if jq:
        cmd += ["--jq", jq]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api 失败: {' '.join(args)}\n{r.stderr.strip()}")
    return r.stdout


def upstream_head(meta: ProjectMeta) -> str:
    return gh([f"repos/{meta.owner_repo}/branches/{meta.branch}", "--jq", ".commit.sha"]).strip()


def compare_files(meta: ProjectMeta, base: str, head: str) -> list:
    data = json.loads(gh([f"repos/{meta.owner_repo}/compare/{base}...{head}"]))
    files = data.get("files") or []
    if data.get("total_commits", 0) >= 250 or len(files) >= 300:
        warn("上游变更规模接近 compare API 上限（300 文件），结果可能不完整")
    return files


def fetch_upstream_file(meta: ProjectMeta, path: str, ref: str) -> bytes | None:
    """取上游某 ref 下的文件内容；不存在返回 None"""
    try:
        b64 = gh([f"repos/{meta.owner_repo}/contents/{path}", f"ref={ref}", "--jq", ".content"]).strip()
        if not b64 or b64 == "null":
            return None
        return base64.b64decode(b64)
    except RuntimeError:
        return None


# ── 映射匹配 ────────────────────────────────────────────────────────

def upstream_regex(upstream: str) -> re.Pattern:
    """含 {MAJOR} 等占位符的上游路径 → 通配正则"""
    pat = re.escape(upstream)
    pat = re.sub(r"\\\{[A-Za-z_]+\\\}", "[^/]+", pat)
    return re.compile(f"^{pat}$")


def match_mapping(meta: ProjectMeta, changed_path: str) -> Mapping | None:
    exact = [m for m in meta.mappings if m.upstream == changed_path]
    if exact:
        return exact[0]
    for m in meta.mappings:
        if "{" in m.upstream and upstream_regex(m.upstream).match(changed_path):
            return m
    return None


def resolve_local(m: Mapping) -> str | None:
    """1:1 拷贝行的本地落点；返回 None 表示构建时自动获取，无需同步"""
    local = m.local.split("（")[0].strip()
    if local.startswith("dockerfiles/") or local == "—":
        return None
    if "同名" in local or " " in local:
        # 多文件同行（如 php 的 docker-php-* 脚本）→ 按上游 basename 落到 template/
        return f"template/{m.upstream.split('/')[-1]}"
    return local


# ── Agent 调用 ──────────────────────────────────────────────────────

TASK_RULES = """\
## 硬性规则

1. 只允许修改 `library/@PROJECT@/**`（template/、config.yml、AGENTS.md）；仓库其他文件一律不动
2. 不执行 git commit / push
3. 模板合并规则（同 docs/02）：
   - 保留本地 {VAR} 占位符，上游新硬编码值改为占位符并加到 update.sh / versions.json 链路
   - FROM 保持上游通用形式，不加 registry 前缀
   - 基础镜像版本值只在 update.sh 定义，模板中以 {DEBIAN_VERSION}/{ALPINE_VERSION} 出现
   - 保留全部 loong64 适配（pcre-jit、fiber、libucontext、unofficial-builds 等）
4. 新建/修改的 .sh 保持可执行权限；改完对每个改动的 .sh 跑 `bash -n`
5. AGENTS.md 可能受文件保护无法直接写入：如需更新映射表/改动清单，把**完整的新版 AGENTS.md** 写到任务目录下的 `AGENTS_md_update.md`（由脚本在校验通过后应用）；「上次同步 commit」行保持原值不动（由脚本写回）
6. 完成后输出变更摘要（每个文件改了什么、为什么）
"""


def build_task_file(meta: ProjectMeta, head: str, tasks: list, out_dir: Path) -> Path:
    lines = [
        f"# 上游同步任务: library/{meta.project}",
        "",
        f"- 上游: https://github.com/{meta.owner_repo}（分支 {meta.branch}）",
        f"- 目标 commit: {head}",
        f"- 项目目录: library/{meta.project}",
        "",
        "## 待合并文件",
        "",
    ]
    for t in tasks:
        lines.append(f"### {t['upstream']} → {t['local']}（{t['relation']}）")
        lines.append("")
        if t["patch"]:
            patch_path = out_dir / f"{abs(hash(t['upstream'])) % 10**8}.patch"
            patch_path.write_text(t["patch"])
            lines.append(f"上游补丁见 `{patch_path}`（基线→目标的 diff）")
        else:
            lines.append("补丁过大或为二进制，无内嵌 diff；请用以下命令自行获取完整文件对比：")
            lines.append(f"```\ngh api repos/{meta.owner_repo}/contents/{t['upstream']}?ref={head} --jq .content | base64 -d\n```")
        lines.append("")
    lines += ["## 规则", "", TASK_RULES.replace("@PROJECT@", meta.project)]
    task_file = out_dir / "TASK.md"
    task_file.write_text("\n".join(lines))
    return task_file


def run_agent(agent: str, task_file: Path, log_file: Path) -> bool:
    prompt = (
        f"读取 {task_file} 并严格按其要求执行上游同步合并任务。"
        f"先读仓库根 AGENTS.md 了解文档结构，再读 docs/02 了解模板规范，然后动手。"
    )
    cmd = [c.format(prompt=prompt) for c in AGENT_BACKENDS[agent]]
    info(f"调用 Agent [{agent}]: {shlex.join(cmd[:3])}…（日志: {log_file}）")
    with open(log_file, "w") as logf:
        try:
            r = subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT, timeout=3600)
        except subprocess.TimeoutExpired:
            warn("Agent 执行超时（3600s）")
            return False
        except FileNotFoundError:
            warn(f"Agent 命令不存在: {cmd[0]}")
            return False
    if r.returncode != 0:
        warn(f"Agent 退出码 {r.returncode}，日志: {log_file}")
        return False
    return True


# ── 校验 ────────────────────────────────────────────────────────────

def git_snapshot() -> dict:
    """工作区快照：变更文件（相对 HEAD）+ 未跟踪文件 → 内容 hash"""
    import hashlib
    r = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    snap = {}
    for line in r.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ")[-1]
        fp = ROOT / path
        if fp.is_file():
            snap[path] = hashlib.sha256(fp.read_bytes()).hexdigest()
        else:
            snap[path] = ""
    return snap


def verify(meta: ProjectMeta, before: dict) -> list[str]:
    """校验本次同步引入的变化（与 before 快照对比）；返回错误列表，空 = 通过"""
    errors = []
    prefix = f"library/{meta.project}/"
    now = git_snapshot()

    # 只看本次同步新产生或新修改的文件
    new_changes = [f for f, h in now.items() if before.get(f) != h]

    for f in new_changes:
        if not f.startswith(prefix):
            errors.append(f"越界修改: {f}（只允许 {prefix}**）")

    for f in new_changes:
        if f.startswith(prefix) and f.endswith(".sh"):
            r = subprocess.run(["bash", "-n", str(ROOT / f)], capture_output=True, text=True)
            if r.returncode != 0:
                errors.append(f"bash -n 失败: {f}\n{r.stderr.strip()}")

    # registry 前缀回归检查（模板 FROM 不得写死 registry）
    registry = ""
    gcfg = ROOT / "config.yml"
    if gcfg.exists():
        m = re.search(r'^registry:\s*"?([^"\n]+)"?', gcfg.read_text(), re.M)
        registry = m.group(1).strip() if m else ""
    tmpl_dir = ROOT / prefix / "template"
    if registry and tmpl_dir.is_dir():
        for t in tmpl_dir.glob("Dockerfile-*.template"):
            if registry in t.read_text():
                errors.append(f"模板写死了 registry 前缀: {t.relative_to(ROOT)}")

    r = subprocess.run(
        [sys.executable, str(ROOT / "tools/build.py"), "--dry-run", prefix.rstrip("/")],
        cwd=ROOT, capture_output=True, text=True,
    )
    if r.returncode != 0:
        errors.append(f"build.py --dry-run 失败:\n{(r.stderr or r.stdout).strip()}")
    return errors


# ── 主流程 ──────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="同步项目上游变更，刷新 AGENTS.md 上次同步 commit")
    p.add_argument("project_dir", help="项目目录（如 library/ruby）")
    p.add_argument("--dry-run", action="store_true", help="仅报告，不改文件、不调用 Agent")
    p.add_argument("--agent", default="hermes", choices=["hermes", "none"], help="合并用 Agent（默认 hermes）")
    p.add_argument("--init", action="store_true", help="记录当前上游 HEAD 为初始基线")
    args = p.parse_args()

    project_dir = (ROOT / args.project_dir).resolve()
    if not project_dir.is_dir():
        warn(f"项目目录不存在: {project_dir}")
        sys.exit(2)
    meta = parse_agents_md(project_dir)

    # 无 git 上游的项目（alpine/debian 等）
    if not meta.owner_repo or "不适用" in meta.baseline_note:
        info(f"library/{meta.project} 无 git 上游（或基线不适用），无需同步")
        sys.exit(0)

    try:
        head = upstream_head(meta)
    except RuntimeError as e:
        warn(str(e))
        sys.exit(1)
    info(f"上游 HEAD: {head[:12]}（{meta.owner_repo}@{meta.branch}）")

    # --init
    if args.init:
        if args.dry_run:
            info(f"[dry-run] 将记录基线 {head[:12]}")
            sys.exit(0)
        write_baseline(meta, head)
        info("初始化完成；后续运行将以该 commit 为基线做 diff")
        sys.exit(0)

    # 基线缺失
    if not meta.baseline:
        warn("AGENTS.md 中「上次同步 commit」未记录，无法 diff。请先运行：")
        warn(f"  python3 tools/sync_upstream.py {args.project_dir} --init")
        sys.exit(2)

    if head.startswith(meta.baseline) or meta.baseline.startswith(head):
        info("上游无更新")
        sys.exit(0)

    # 获取基线 diff
    try:
        files = compare_files(meta, meta.baseline, head)
    except RuntimeError as e:
        warn(str(e))
        sys.exit(1)
    info(f"基线 {meta.baseline[:12]} → HEAD：{len(files)} 个文件变更")

    # 分类
    auto_copy, agent_tasks, skipped, unmapped = [], [], [], []
    for f in files:
        path = f["filename"]
        if f.get("status") == "removed":
            skipped.append((path, "上游已删除（仅提示）"))
            continue
        m = match_mapping(meta, path)
        if m is None:
            unmapped.append(path)
            agent_tasks.append({"upstream": path, "local": "（未映射，判断是否需本地适配）",
                                "relation": "未映射", "patch": f.get("patch")})
            continue
        if m.relation in RELATION_INFO_SKIP or (m.relation == "1:1 拷贝" and resolve_local(m) is None):
            skipped.append((path, f"{m.relation}（构建时自动获取，无需同步）"))
            continue
        if m.relation == "1:1 拷贝":
            auto_copy.append((path, resolve_local(m), f.get("patch")))
        else:
            agent_tasks.append({"upstream": path, "local": resolve_local(m) or m.local,
                                "relation": m.relation, "patch": f.get("patch")})

    # 报告
    info(f"  1:1 自动拷贝: {len(auto_copy)} | Agent 合并: {len(agent_tasks)} | 跳过: {len(skipped)}")
    for up, local, _ in auto_copy:
        info(f"    [auto] {up} → {local}")
    for t in agent_tasks:
        info(f"    [agent] {t['upstream']} → {t['local']}（{t['relation']}）")
    for up, why in skipped:
        info(f"    [skip] {up}：{why}")

    if args.dry_run:
        info("[dry-run] 结束，未修改任何文件")
        sys.exit(0)

    # 拍快照：本次同步前的工作区状态（verify 只对比快照之后的变化）
    before = git_snapshot()

    # 1:1 自动拷贝（三层校验：基线版本与本地一致才覆盖）
    copy_ok, copy_conflict = [], []
    for up, local, _ in auto_copy:
        local_path = ROOT / f"library/{meta.project}" / local
        base_content = fetch_upstream_file(meta, up, meta.baseline)
        head_content = fetch_upstream_file(meta, up, head)
        if head_content is None:
            warn(f"  获取上游文件失败: {up}@{head[:12]}")
            copy_conflict.append(up)
            continue
        if local_path.exists() and base_content is not None:
            if local_path.read_bytes() != base_content:
                info(f"  [本地有改动] {up} → 转 Agent 合并")
                agent_tasks.append({"upstream": up, "local": local, "relation": "1:1 拷贝（本地已修改）",
                                    "patch": None})
                continue
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(head_content)
        copy_ok.append(up)
        info(f"  [auto] 已更新 {local}")

    # Agent 合并
    agent_ok = True
    out_dir = None
    if agent_tasks:
        if args.agent == "none":
            warn(f"--agent none：{len(agent_tasks)} 个文件待合并，基线不变，稍后可重跑或人工处理")
            sys.exit(0)
        out_dir = Path(tempfile.mkdtemp(prefix=f"sync-{meta.project}-"))
        task_file = build_task_file(meta, head, agent_tasks, out_dir)
        log_file = out_dir / "agent.log"
        agent_ok = run_agent(args.agent, task_file, log_file)
        if not agent_ok:
            warn(f"Agent 合并未完成。任务文件: {task_file}，日志: {log_file}")
            warn("基线不变，修复后重跑即可重新获得 diff")

    # 校验（只看快照之后的新变化）
    errors = verify(meta, before) if (copy_ok or agent_tasks) else []
    for e in errors:
        warn(f"校验失败: {e}")

    # Agent 因文件保护无法直接写 AGENTS.md 时，会把更新写到任务目录的 AGENTS_md_update.md
    agents_md_update = (out_dir / "AGENTS_md_update.md") if (out_dir and agent_tasks and not errors) else None
    if agents_md_update and agents_md_update.exists():
        meta.agents_md.write_text(agents_md_update.read_text())
        info("已应用 Agent 提交的 AGENTS.md 更新（AGENTS_md_update.md）")

    if errors or not agent_ok or copy_conflict:
        warn(f"同步未完全成功（auto={len(copy_ok)} 冲突={len(copy_conflict)} agent_ok={agent_ok}）")
        warn("基线不变；请检查工作区改动后重跑")
        sys.exit(1)

    # 全部成功 → 写回基线
    write_baseline(meta, head)
    changed = [f for f, h in git_snapshot().items() if before.get(f) != h]
    info(f"同步完成。本次变更 {len(changed)} 个文件，建议检查后提交：")
    info(f"  git add {args.project_dir} && git commit -m 'sync({meta.project}): 同步上游 {head[:12]}'")


if __name__ == "__main__":
    main()
