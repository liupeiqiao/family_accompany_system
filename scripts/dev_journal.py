from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable


RunGit = Callable[[list[str]], str]

CURRENT_TEMPLATE = """# 当前开发记录备注

## 本次目标


## AI 协作摘要


## 关键决策

"""


@dataclass(frozen=True)
class JournalResult:
    wrote_entry: bool
    journal_path: Path | None


@dataclass(frozen=True)
class ConversationMessage:
    timestamp: datetime
    role: str
    text: str


@dataclass(frozen=True)
class ConversationSummary:
    goal: str
    ai_summary: str
    decisions: str


def run_git_command(repo_root: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def find_repo_root(start: Path | None = None) -> Path:
    cwd = start or Path.cwd()
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return Path(completed.stdout.strip())


def generate_journal(
    repo_root: Path,
    run_git: RunGit | None = None,
    now: datetime | None = None,
    session_roots: Iterable[Path] | None = None,
) -> JournalResult:
    repo_root = Path(repo_root)
    git = run_git or (lambda args: run_git_command(repo_root, args))
    current_time = now or datetime.now()

    staged_files = _split_lines(git(["diff", "--cached", "--name-only"]))
    if not staged_files:
        return JournalResult(wrote_entry=False, journal_path=None)

    journal_dir = repo_root / "docs" / "dev-journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    current_notes_path = journal_dir / "current.md"
    if not current_notes_path.exists():
        current_notes_path.write_text(CURRENT_TEMPLATE, encoding="utf-8")

    branch = git(["branch", "--show-current"]).strip() or "unknown"
    diff_stat = git(["diff", "--cached", "--stat"]).strip()
    manual_notes = current_notes_path.read_text(encoding="utf-8").strip()
    conversation_summary = _build_conversation_summary(
        messages=_collect_recent_conversation_messages(
            repo_root=repo_root,
            since=_last_commit_time(git),
            session_roots=session_roots,
        ),
        fallback_notes=manual_notes,
    )

    journal_path = journal_dir / f"{current_time:%Y-%m-%d}.md"
    entry = _build_entry(
        current_time=current_time,
        branch=branch,
        staged_files=staged_files,
        diff_stat=diff_stat,
        conversation_summary=conversation_summary,
    )
    _append_entry(journal_path, entry)
    return JournalResult(wrote_entry=True, journal_path=journal_path)


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _build_entry(
    current_time: datetime,
    branch: str,
    staged_files: Iterable[str],
    diff_stat: str,
    conversation_summary: ConversationSummary | None,
) -> str:
    files = "\n".join(f"- `{path}`" for path in staged_files)
    stat_block = diff_stat or "无 diff 统计信息。"
    sections = [
        f"## {current_time:%Y-%m-%d %H:%M:%S}",
        "",
        "### 基本信息",
        "",
        f"- 分支：`{branch}`",
        "",
        "### Staged 文件",
        "",
        files,
        "",
        "### Diff 摘要",
        "",
        "```text",
        stat_block,
        "```",
    ]
    if conversation_summary is not None:
        sections.extend([
            "",
            "### 当前开发记录备注",
            "",
            "#### 本次目标",
            "",
            conversation_summary.goal,
            "",
            "#### AI 协作摘要",
            "",
            conversation_summary.ai_summary,
            "",
            "#### 关键决策",
            "",
            conversation_summary.decisions,
        ])
    sections.extend(["", "---", ""])
    return "\n".join(sections)


def _last_commit_time(git: RunGit) -> datetime | None:
    try:
        value = git(["log", "-1", "--format=%cI"]).strip()
    except Exception:
        return None
    if not value:
        return None
    return _parse_timestamp(value)


def _collect_recent_conversation_messages(
    repo_root: Path,
    since: datetime | None,
    session_roots: Iterable[Path] | None = None,
) -> list[ConversationMessage]:
    if since is None:
        return []

    repo_root_text = _normalize_path(repo_root)
    messages: list[ConversationMessage] = []
    for session_root in session_roots or _default_session_roots():
        root = Path(session_root)
        if not root.exists():
            continue
        for path in root.rglob("*.jsonl"):
            try:
                if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) <= since:
                    continue
            except OSError:
                continue
            session_cwd: str | None = None
            session_matches = False
            for raw_line in _read_jsonl_lines(path):
                if raw_line.get("type") == "session_meta":
                    session_cwd = raw_line.get("payload", {}).get("cwd")
                    session_matches = _normalize_path(session_cwd) == repo_root_text
                    continue
                if not session_matches:
                    continue
                timestamp = _parse_timestamp(str(raw_line.get("timestamp", "")))
                if timestamp is None or timestamp <= since:
                    continue
                message = _message_from_record(timestamp, raw_line)
                if message is not None:
                    messages.append(message)
    return sorted(messages, key=lambda message: message.timestamp)


def _default_session_roots() -> list[Path]:
    codex_home = Path.home() / ".codex"
    return [codex_home / "sessions", codex_home / "archived_sessions"]


def _read_jsonl_lines(path: Path) -> Iterable[dict]:
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    yield value
    except OSError:
        return


def _message_from_record(timestamp: datetime, record: dict) -> ConversationMessage | None:
    record_type = record.get("type")
    payload = record.get("payload", {})
    if record_type == "response_item" and payload.get("type") == "message":
        role = str(payload.get("role", ""))
        if role not in {"user", "assistant"}:
            return None
        text = _content_text(payload.get("content", []))
    elif record_type == "event_msg":
        event_type = payload.get("type")
        if event_type == "user_message":
            role = "user"
        elif event_type == "agent_message":
            role = "assistant"
        else:
            return None
        text = str(payload.get("message", ""))
    else:
        return None

    text = _clean_text(text)
    if not text:
        return None
    return ConversationMessage(timestamp=timestamp, role=role, text=text)


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def _build_conversation_summary(
    messages: list[ConversationMessage],
    fallback_notes: str,
) -> ConversationSummary | None:
    user_messages = [
        message.text
        for message in messages
        if message.role == "user" and not _is_short_approval(message.text)
    ]
    assistant_messages = [message.text for message in messages if message.role == "assistant"]
    if not user_messages and not assistant_messages:
        fallback = _strip_template_headings(fallback_notes)
        if not fallback:
            return None
        return ConversationSummary(
            goal=_shorten(fallback),
            ai_summary="无可用的最新对话记录，保留 current.md 中的备注内容。",
            decisions="未从最新对话中识别到明确决策。",
        )

    goal = _shorten(user_messages[-1] if user_messages else "根据最新对话继续完善开发记录。")
    ai_summary = _shorten(
        assistant_messages[-1] if assistant_messages else "根据用户最新要求调整开发记录生成逻辑。"
    )
    decision_candidates = [
        text for text in user_messages if any(keyword in text for keyword in ("需要", "不需要", "不要", "优先", "决定", "改为"))
    ]
    decisions = _shorten(
        "；".join(decision_candidates[-2:]) if decision_candidates else "按最新用户要求生成简短开发记录总结。"
    )
    return ConversationSummary(goal=goal, ai_summary=ai_summary, decisions=decisions)


def _strip_template_headings(text: str) -> str:
    ignored = {"# 当前开发记录备注", "## 本次目标", "## AI 协作摘要", "## 关键决策", "## 验证情况"}
    lines = [line for line in text.splitlines() if line.strip() not in ignored]
    return "\n".join(lines).strip()


def _is_short_approval(text: str) -> bool:
    normalized = " ".join(line.strip() for line in text.splitlines() if line.strip())
    return normalized in {"批准了", "批准", "同意", "可以", "好的", "好", "ok", "OK"}


def _shorten(text: str, limit: int = 120) -> str:
    normalized = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1]}…"


def _clean_text(text: str) -> str:
    if text.lstrip().startswith("# AGENTS.md instructions") or "<environment_context>" in text:
        return ""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def _normalize_path(path: object) -> str:
    if path is None:
        return ""
    return str(path).replace("/", "\\").rstrip("\\").casefold()


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _append_entry(journal_path: Path, entry: str) -> None:
    if not journal_path.exists():
        journal_path.write_text(f"# {journal_path.stem} 开发记录\n\n", encoding="utf-8")
    with journal_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(entry)


def main() -> int:
    repo_root = find_repo_root()
    result = generate_journal(repo_root)
    if result.wrote_entry and result.journal_path is not None:
        print(f"开发记录已更新：{result.journal_path.relative_to(repo_root)}")
    else:
        print("没有 staged 变更，跳过开发记录生成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
