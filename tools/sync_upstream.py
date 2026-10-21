#!/usr/bin/env python3
"""tools/sync_upstream.py — 基于「本地当前文件 vs 上游最新文件」的 AI 同步

设计（状态比对，不依赖 git 历史 diff）:
  脚本: 解析 AGENTS.md（上游仓库/分支 + 映射表）→ 取上游 HEAD
        → 与「上次成功检查的 HEAD」比较做跳过缓存
        → 按映射表取上游最新文件与本地逐文件比对：
             一致的跳过；不一致/取不到/含占位符的打包成任务交 AI
  AI:   自行 diff 本地与上游最新文件，判断是否需要合并（改动清单随任务提供）
  把关: 快照越界校验 / bash -n / 模板无 registry 前缀 / build.py --dry-run
        全部通过才记录 HEAD —— 它只是下次的跳过缓存，不参与正确性判断

用法:
  python3 tools/sync_upstream.py library/ruby              # 同步（默认 hermes agent）
  python3 tools/sync_upstream.py library/ruby --dry-run    # 仅报告差异，不调 Agent
  python3 tools/sync_upstream.py library/ruby --agent none # 仅列待比对项

退出码: 0 成功/无更新; 1 校验失败或 Agent 失败; 2 用法问题
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

RELATION_INFO_SKIP = ("运行时依赖",)   # 映射表标注这类关系的行不参与比对
NO_UPSTREAM = ("—", "", "-")           # 本地新增行，无上游文件可比


# ── 日志 ────────────────────────────────────────────────────────────

def info(msg):
    print(f"[sync] {msg}", flush=True)


def warn(msg):
    print(f"[sync][WARN] {msg}", file=sys.stderr, flush=True)


# ── AGENTS.md 解析 ──────────────────────────────────────────────────

@dataclass
class Mapping:
    upstream: str      # 上游路径（可能含 {MAJOR} 等占位符或 "a / b / c" 多文件）
    local: str         # 本地路径
    relation: str      # 1:1 拷贝 / 拆分 / 重写 / 本地新增 / 上游已废弃 / ...


@dataclass
class ProjectMeta:
    project: str
    agents_md: Path
    owner_repo: str | None    # "owner/repo"；非 GitHub 上游为 None
    branch: str
    last_checked: str | None  # 上次成功检查的上游 HEAD（纯跳过缓存）；未记录为 None
    note: str                 # 该字段原始文本（用于识别"不适用"）
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
    last_checked = None
    note = ""
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
                note = val
                m = re.search(r"\b([0-9a-f]{7,40})\b", val)
                if m:
                    last_checked = m.group(1)

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
        last_checked=last_checked,
        note=note,
        mappings=mappings,
    )


def record_head(meta: ProjectMeta, commit: str):
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
    info(f"已记录上次检查的上游 HEAD: {short}")


def extract_section(text: str, name: str) -> str:
    m = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(0).strip() if m else ""


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
    return gh([f"repos/{meta.owner_repo}/branches/{meta.branch}"], jq=".commit.sha").strip()


def fetch_upstream_file(meta: ProjectMeta, path: str, ref: str) -> bytes | None:
    """取上游某 ref 下的文件内容；不存在/失败返回 None"""
    try:
        b64 = gh([f"repos/{meta.owner_repo}/contents/{path}?ref={ref}"], jq=".content").strip()
        if not b64 or b64 == "null":
            return None
        return base64.b64decode(b64)
    except RuntimeError:
        return None


# ── 映射比对 ────────────────────────────────────────────────────────

def upstream_names(upstream: str) -> list[str]:
    """映射表上游单元格可能是 \"a / b / c\" 多文件 → 拆成列表"""
    if " / " in upstream:
        return [s.strip() for s in upstream.split(" / ")]
    return [upstream]


def resolve_local(m: Mapping) -> str | None:
    """本地落点；返回 None 表示构建时自动获取或无本地文件（不参与比对）"""
    local = m.local.split("（")[0].strip()
    if local.startswith("dockerfiles/") or local in NO_UPSTREAM:
        return None
    if "同名" in local or " " in local:
        # 多文件同行（如 php 的 docker-php-* 脚本）→ 按上游 basename 落到 template/
        return f"template/{m.upstream.split('/')[-1]}"
    return local


@dataclass
class Candidate:
    upstream: str       # 映射表原样（展示用）
    local: str          # 映射表本地列原文（展示用）
    relation: str
    files: list         # [(name, local_rel, upstream_bytes|None, note)]


def collect_candidates(meta: ProjectMeta, head: str) -> tuple[list, int]:
    """按映射表比对上游最新文件与本地；返回 (待比对项, 已一致行数)"""
    candidates, in_sync = [], 0
    for m in meta.mappings:
        if m.relation in RELATION_INFO_SKIP or m.upstream in NO_UPSTREAM:
            continue
        local = resolve_local(m)
        if local is None:
            continue  # 构建时自动获取（dockerfiles/ 等）

        names = upstream_names(m.upstream)
        files, mismatched = [], []
        for name in names:
            local_rel = local if len(names) == 1 else f"template/{Path(name).name}"
            if "{" in name:
                mismatched.append((name, local_rel, None, "上游路径含占位符，请自行 gh api 获取（ref=HEAD）"))
                continue
            up_bytes = fetch_upstream_file(meta, name, head)
            if up_bytes is None:
                mismatched.append((name, local_rel, None, "上游取不到该文件（404/改名？），请核实映射表"))
                continue
            local_path = ROOT / f"library/{meta.project}" / local_rel
            if local_path.exists() and local_path.read_bytes() == up_bytes:
                files.append((name, local_rel, up_bytes, "已一致"))
                continue
            note = "本地文件不存在" if not local_path.exists() else "与上游最新版不一致"
            mismatched.append((name, local_rel, up_bytes, note))

        if mismatched:
            candidates.append(Candidate(m.upstream, m.local, m.relation, mismatched))
        else:
            in_sync += 1
    return candidates, in_sync


# ── Agent 调用 ──────────────────────────────────────────────────────

TASK_RULES = """\
## 硬性规则

1. 只允许修改 `library/@PROJECT@/**`（template/、config.yml、AGENTS.md）；仓库其他文件一律不动
2. 不执行 git commit / push
3. 模板合并规则（同 docs/02）：
   - 保留本地 {VAR} 占位符，上游新硬编码值改为占位符并加到 update.sh / versions.json 链路
   - FROM 保持上游通用形式，不加 registry 前缀
   - 基础镜像版本值只在 update.sh 定义，模板中以 {DEBIAN_VERSION}/{ALPINE_VERSION} 出现
   - 基础镜像版本是 loong64 平台硬约束：Debian 一律 forky，不随上游 variants 变化（docs/01 约束 7）；Alpine 版本如需变更先在摘要中提出等待确认，不得径直改
   - 保留全部 loong64 适配（pcre-jit、fiber、libucontext、unofficial-builds 等）
4. 新建/修改的 .sh 保持可执行权限；改完对每个改动的 .sh 跑 `bash -n`
5. AGENTS.md 可能受文件保护无法直接写入：如需更新映射表/改动清单，把**完整的新版 AGENTS.md** 写到任务目录下的 `AGENTS_md_update.md`（由脚本在校验通过后应用）；「上次同步 commit」行保持原值不动（由脚本写回）
6. 完成后输出变更摘要（每个文件改了什么、为什么）
"""

JUDGE_GUIDE = """\
## 判断方法

对每个「待比对文件」自行 diff「本地当前版」与「上游最新版」，自行判断是否需要落到本地：

- 上游改动与本地无关、或本地已用其他方式实现 → 不改文件，在摘要中说明理由即可
- 需要合并 → 按下方规则修改本地文件
- 关系为「1:1 拷贝」且本地无特殊适配 → 可直接以上游最新版覆盖本地
- 怀疑上游新增了映射表未覆盖的模板文件时，可用 `gh api repos/@REPO@/contents/` 列上游目录核对（可选）
"""


def build_task_file(meta: ProjectMeta, head: str, candidates: list, out_dir: Path) -> Path:
    agents_text = meta.agents_md.read_text()
    lines = [
        f"# 上游同步任务: library/{meta.project}",
        "",
        f"- 上游: https://github.com/{meta.owner_repo}（分支 {meta.branch}，HEAD {head[:12]}）",
        f"- 项目目录: library/{meta.project}",
        "",
        "## 本地改动清单（AGENTS.md，改本地前必读）",
        "",
        extract_section(agents_text, "改动清单") or "（无）",
        "",
        "## 待比对文件",
        "",
    ]
    for i, c in enumerate(candidates):
        lines.append(f"### {c.upstream} → {c.local}（{c.relation}）")
        lines.append("")
        for j, (name, local_rel, up_bytes, note) in enumerate(c.files):
            if up_bytes is not None:
                up_path = out_dir / f"upstream-{i}-{j}-{Path(name).name}"
                up_path.write_bytes(up_bytes)
                lines.append(f"- `{name}` → `{local_rel}`（{note}）：上游最新版 `{up_path}`，本地 `library/{meta.project}/{local_rel}`")
            else:
                lines.append(f"- `{name}` → `{local_rel}`（{note}）")
        lines.append("")
    lines += [
        JUDGE_GUIDE.replace("@REPO@", meta.owner_repo or ""),
        "## 规则",
        "",
        TASK_RULES.replace("@PROJECT@", meta.project),
    ]
    task_file = out_dir / "TASK.md"
    task_file.write_text("\n".join(lines))
    return task_file


def _agent_db():
    """hermes 会话库（只读）；失败返回 None（实时日志降级为心跳）"""
    import sqlite3
    db = Path.home() / ".hermes/state.db"
    if not db.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
        con.row_factory = sqlite3.Row
        return con
    except Exception:
        return None


def _one_line(s: str, n: int = 160) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n] + "…"


def _fmt_agent_msg(row) -> str | None:
    """把 messages 表的一行转成一行可读活动日志；无需展示返回 None"""
    try:
        role = row["role"]
        if role == "assistant":
            tc = row["tool_calls"] or ""
            if tc:
                calls = json.loads(tc)
                parts = []
                for c in calls[:3]:
                    fn = c.get("function", {})
                    args = _one_line(fn.get("arguments", ""), 70)
                    parts.append(f"{fn.get('name', '?')}({args})")
                return f"调用 {', '.join(parts)}"
            content = (row["content"] or "").strip()
            return f"说: {_one_line(content)}" if content else None
        if role == "tool":
            name = row["tool_name"] or "tool"
            content = (row["content"] or "").strip()
            extra = ""
            try:
                data = json.loads(content)
                if isinstance(data, dict) and data.get("exit_code") not in (None, 0):
                    extra = f" exit={data['exit_code']}"
            except Exception:
                pass
            return f"{name} 完成{extra}"
    except Exception:
        return None
    return None


def _tail_agent_messages(con, session_id: str, last_id: int) -> tuple[list, int]:
    """取该会话 last_id 之后的新消息，返回 (展示行, 新 last_id)"""
    rows = con.execute(
        "SELECT id, role, content, tool_name, tool_calls FROM messages "
        "WHERE session_id = ? AND id > ? ORDER BY id LIMIT 30",
        (session_id, last_id),
    ).fetchall()
    lines = [s for s in (_fmt_agent_msg(r) for r in rows) if s]
    new_last = rows[-1]["id"] if rows else last_id
    return lines, new_last


def run_agent(agent: str, task_file: Path, log_file: Path) -> bool:
    import time
    prompt = (
        f"读取 {task_file} 并严格按其要求执行上游同步任务。"
        f"先读仓库根 AGENTS.md 了解文档结构，再读 docs/01 的关键约束与 docs/02 的模板规范，然后动手。"
    )
    cmd = [c.format(prompt=prompt) for c in AGENT_BACKENDS[agent]]
    info(f"调用 Agent [{agent}]: {shlex.join(cmd[:3])}…")
    info(f"  预计 5~20 分钟；下方实时输出 Agent 活动，完整输出见 {log_file}")
    with open(log_file, "w") as logf:
        try:
            proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT)
        except FileNotFoundError:
            warn(f"Agent 命令不存在: {cmd[0]}")
            return False

        # 实时日志：只读尾随 hermes 会话库中本次嵌套会话的新消息；失败降级为心跳
        db_since = time.time() - 5
        session_id = last_id = None
        con = _agent_db()
        next_beat = 60
        start = time.monotonic()
        while proc.poll() is None:
            time.sleep(5)
            if con is not None:
                try:
                    if session_id is None:
                        row = con.execute(
                            "SELECT id FROM sessions WHERE started_at >= ? "
                            "ORDER BY started_at LIMIT 1",
                            (db_since,),
                        ).fetchone()
                        if row:
                            session_id = row["id"]
                            info(f"  [agent] 会话 {session_id}，实时日志已连接")
                            last_id = con.execute(
                                "SELECT coalesce(max(id), 0) AS m FROM messages "
                                "WHERE session_id = ?",
                                (session_id,),
                            ).fetchone()["m"]
                    elif last_id is not None:
                        lines, last_id = _tail_agent_messages(con, session_id, last_id)
                        for ln in lines:
                            info(f"  [agent] {ln}")
                except Exception:
                    con.close()
                    con = None
                    warn("  [agent] 实时日志断开（会话库不可读），降级为心跳")
            el = int(time.monotonic() - start)
            if el >= next_beat:
                info(f"  Agent 运行中… {el // 60} 分钟")
                next_beat += 60
            if el >= 3600:
                proc.kill()
                warn("Agent 执行超时（3600s），已终止")
                return False
        if con is not None:
            con.close()

    if proc.returncode != 0:
        warn(f"Agent 退出码 {proc.returncode}，日志: {log_file}")
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
    p = argparse.ArgumentParser(description="本地文件 vs 上游最新文件的 AI 同步，记录检查点到 AGENTS.md")
    p.add_argument("project_dir", help="项目目录（如 library/ruby）")
    p.add_argument("--dry-run", action="store_true", help="仅报告比对结果，不调用 Agent、不改文件")
    p.add_argument("--agent", default="hermes", choices=["hermes", "none"], help="合并用 Agent（默认 hermes）")
    args = p.parse_args()

    project_dir = (ROOT / args.project_dir).resolve()
    if not project_dir.is_dir():
        warn(f"项目目录不存在: {project_dir}")
        sys.exit(2)
    meta = parse_agents_md(project_dir)

    # 无 git 上游的项目（alpine/debian 等）
    if not meta.owner_repo or "不适用" in meta.note:
        info(f"library/{meta.project} 无 git 上游（或不适用），无需同步")
        sys.exit(0)

    try:
        head = upstream_head(meta)
    except RuntimeError as e:
        warn(str(e))
        sys.exit(1)
    info(f"上游 HEAD: {head[:12]}（{meta.owner_repo}@{meta.branch}）")

    # 跳过缓存：上次成功检查点 == 当前 HEAD → 上游没动过
    if meta.last_checked and (head.startswith(meta.last_checked) or meta.last_checked.startswith(head)):
        info("上游无更新（与上次检查点一致）")
        sys.exit(0)

    # 状态比对：上游最新 vs 本地当前
    candidates, in_sync = collect_candidates(meta, head)
    info(f"映射 {len(meta.mappings)} 行：已一致 {in_sync} | 待比对 {len(candidates)}")
    for c in candidates:
        for name, local_rel, _, note in c.files:
            if note != "已一致":
                info(f"    [比对] {name} → {local_rel}：{note}")

    if not candidates:
        if not args.dry_run:
            record_head(meta, head)
        info("所有映射文件与上游最新一致")
        sys.exit(0)

    if args.dry_run:
        info("[dry-run] 结束，未修改任何文件")
        sys.exit(0)

    if args.agent == "none":
        warn(f"--agent none：{len(candidates)} 项待比对，未记录 HEAD，可重跑或人工处理")
        sys.exit(0)

    # 拍快照 → 交给 AI 判断 → 校验 → 记录检查点
    before = git_snapshot()
    out_dir = Path(tempfile.mkdtemp(prefix=f"sync-{meta.project}-"))
    task_file = build_task_file(meta, head, candidates, out_dir)
    log_file = out_dir / "agent.log"
    agent_ok = run_agent(args.agent, task_file, log_file)
    if not agent_ok:
        warn(f"Agent 未完成。任务文件: {task_file}，日志: {log_file}")
        warn("未记录 HEAD；修复后重跑即可重新比对")
        sys.exit(1)

    errors = verify(meta, before)
    for e in errors:
        warn(f"校验失败: {e}")

    # Agent 因文件保护无法直接写 AGENTS.md 时，把更新写到任务目录由脚本应用
    agents_md_update = out_dir / "AGENTS_md_update.md"
    if not errors and agents_md_update.exists():
        meta.agents_md.write_text(agents_md_update.read_text())
        info("已应用 Agent 提交的 AGENTS.md 更新（AGENTS_md_update.md）")

    if errors:
        warn("同步校验未通过；未记录 HEAD，请检查工作区改动后重跑")
        sys.exit(1)

    record_head(meta, head)
    changed = [f for f, h in git_snapshot().items() if before.get(f) != h]
    info(f"同步完成。本次变更 {len(changed)} 个文件，建议检查后提交：")
    info(f"  git add {args.project_dir} && git commit -m 'sync({meta.project}): 同步上游 {head[:12]}'")


if __name__ == "__main__":
    main()
