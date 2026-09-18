#!/usr/bin/env python3
"""tools/pull_request.py — PR 相关操作

输出约定：
- 日志（提示/状态）走 stderr，格式 `[pull-request] 文件名:行号 消息`（见 log()）
- 数据走 stdout（changed-files 每行一个目录，如 `library/alpine`）；命令只在 -n/--dry-run 下打印（见 print_command()）
- ci-name 的结果同时追加写入 $GITHUB_OUTPUT 的 dynamic_ci_name（GitHub Actions 步骤输出）
"""

import logging
import os
import shlex
import subprocess
import sys

import click

# 日志格式：[pull-request] 文件名:行号 消息（行号 = log() 的调用点，见 log 的 stacklevel）
LOG_FORMAT = "[pull-request] %(filename)s:%(lineno)d %(message)s"


def _build_logger():
    logger = logging.getLogger("pull-request")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # 不向 root 传播，避免重复输出/被 basicConfig 干扰
    return logger


logger = _build_logger()


def log(msg):
    """把日志打到 stderr，格式 `[pull-request] 文件名:行号 消息`。

    用标准 logging 库实现；stacklevel=2 让记录的位置是 log() 的**调用点**，
    而不是 log() 内部那行 logger.info。
    """
    logger.info(msg, stacklevel=2)


# 与镜像构建无关的变更前缀：这些目录的改动不触发镜像构建
IGNORE_PREFIXES = (".github/", "docs/", "tools/")

# 配置全局变量：默认目标仓库，ChangedFiles 构造时可不传 repository
REPOSITORY = "Loongson-Cloud-Community/container-ci-automation"

# GitHub Actions 输出文件的环境变量名（CI 里由 runner 注入）
GITHUB_OUTPUT_ENV = "GITHUB_OUTPUT"


class ChangedFiles:
    def __init__(self, pull_request_id, repository=None):
        self.pull_request_id = pull_request_id
        self.repository = repository or REPOSITORY

    def command(self):
        """构造实际执行的 gh 命令（唯一来源，打印与执行共用，避免两处漂移）"""
        return [
            "gh", "api",
            f"repos/{self.repository}/pulls/{self.pull_request_id}/files",
            "--paginate", "--jq", ".[].filename",
        ]

    def print_command(self):
        """打印实际执行的命令（命令走 stdout，与走 stderr 的日志分流）"""
        print(shlex.join(self.command()))

    def get_changed_files(self):
        """获取该 PR 的文件变动列表（文件名）"""
        log(f"获取 PR 文件变动: {self.repository}#{self.pull_request_id}")
        r = subprocess.run(
            self.command(),
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            log(f"gh api 调用失败: {r.stderr.strip()}")
            raise RuntimeError(f"获取 PR {self.pull_request_id} 文件变动失败: {r.stderr.strip()}")
        files = [name for name in r.stdout.splitlines() if name]
        # 过滤无关前缀
        kept = [name for name in files if not name.startswith(IGNORE_PREFIXES)]
        if len(kept) != len(files):
            log(f"过滤无关变更 {len(files) - len(kept)} 个（前缀 {' '.join(IGNORE_PREFIXES)}）")
        # 只取前两层目录（library/alpine/template/update.sh → library/alpine），按首次出现顺序去重
        dirs = list(dict.fromkeys("/".join(name.split("/")[:2]) for name in kept))
        log(f"文件变动 {len(kept)} 个 → 目录 {len(dirs)} 个")
        return dirs


class CiName:
    """取 PR 的首个变更目录，转成 workflow 名写入 $GITHUB_OUTPUT（library/alpine → library::alpine）"""

    OUTPUT_KEY = "dynamic_ci_name"

    def __init__(self, pull_request_id, repository=None):
        self.pull_request_id = pull_request_id
        self.repository = repository or REPOSITORY
        self.changed_files = ChangedFiles(self.pull_request_id, self.repository)

    def print_command(self):
        """打印实际执行的命令（命令走 stdout，与走 stderr 的日志分流）"""
        self.changed_files.print_command()

    def name(self):
        """第一个变更目录 → workflow 名（'library/alpine' → 'library::alpine'）"""
        dirs = self.changed_files.get_changed_files()
        if not dirs:
            raise RuntimeError(f"PR {self.pull_request_id} 无有效变更目录，无法确定 {self.OUTPUT_KEY}")
        return dirs[0].replace("/", "::")

    def write_output(self, name):
        """把 {OUTPUT_KEY}={name} 追加写入 $GITHUB_OUTPUT 指向的文件"""
        path = os.environ.get(GITHUB_OUTPUT_ENV)
        if not path:
            raise RuntimeError(f"环境变量 {GITHUB_OUTPUT_ENV} 未设置，无法写入 {self.OUTPUT_KEY}")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{self.OUTPUT_KEY}={name}\n")
        log(f"已写入 {path}：{self.OUTPUT_KEY}={name}")


# ── CLI ────────────────────────────────────────────────────────────

@click.group()
def cli():
    """PR 相关操作"""


# 注意：click 命令函数名一律 <name>_cmd，避免与模块级 helper 重名
# （重名会静默替换 helper，既有调用点全部失效）
@cli.command("changed-files")
@click.argument("repository", metavar="OWNER/REPO")
@click.argument("pull_request_id", type=int)
@click.option("-n", "--dry-run", is_flag=True, help="仅打印命令，不执行")
def changed_files_cmd(repository, pull_request_id, dry_run):
    """打印 PR 变更涉及的目录（每行一个，如 library/alpine）"""
    cf = ChangedFiles(pull_request_id, repository)
    if dry_run:
        log("dry-run：仅打印命令，未执行")
        cf.print_command()
        return
    try:
        files = cf.get_changed_files()
    except RuntimeError as e:
        raise click.ClickException(str(e))
    for name in files:
        click.echo(name)


@cli.command("ci-name")
@click.argument("pull_request_id", type=int)
@click.option("-r", "--repository", default=None, metavar="OWNER/REPO",
              help="默认取全局 REPOSITORY")
@click.option("-n", "--dry-run", is_flag=True, help="仅打印命令，不执行")
def ci_name_cmd(pull_request_id, repository, dry_run):
    """取 PR 首个变更目录写入 $GITHUB_OUTPUT 的 dynamic_ci_name（library/alpine → library::alpine）"""
    cn = CiName(pull_request_id, repository)
    if dry_run:
        log("dry-run：仅打印命令，未执行")
        cn.print_command()
        return
    try:
        name = cn.name()
        cn.write_output(name)
    except RuntimeError as e:
        raise click.ClickException(str(e))
    click.echo(name)


if __name__ == "__main__":
    cli()
