import importlib.util
import sys
from datetime import timezone
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "dev_journal.py"
SPEC = importlib.util.spec_from_file_location("dev_journal", MODULE_PATH)
dev_journal = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = dev_journal
SPEC.loader.exec_module(dev_journal)


class FakeGit:
    def __init__(self, outputs):
        self.outputs = outputs

    def __call__(self, args):
        key = tuple(args)
        if key not in self.outputs:
            raise AssertionError(f"unexpected git args: {args}")
        return self.outputs[key]


def test_generate_journal_skips_when_no_staged_changes(tmp_path):
    result = dev_journal.generate_journal(
        repo_root=tmp_path,
        run_git=FakeGit({
            ("diff", "--cached", "--name-only"): "",
        }),
    )

    assert result.wrote_entry is False
    assert result.journal_path is None


def test_generate_journal_creates_template_and_appends_entry(tmp_path):
    fake_git = FakeGit({
        ("diff", "--cached", "--name-only"): "app.py\nREADME.md\n",
        ("branch", "--show-current"): "main\n",
        ("diff", "--cached", "--stat"): " app.py | 2 +-\n README.md | 3 +++\n",
    })

    result = dev_journal.generate_journal(
        repo_root=tmp_path,
        run_git=fake_git,
        now=dev_journal.datetime(2026, 5, 22, 21, 30, 0),
    )

    assert result.wrote_entry is True
    assert result.journal_path == tmp_path / "docs" / "dev-journal" / "2026-05-22.md"
    current_template = (tmp_path / "docs" / "dev-journal" / "current.md").read_text(encoding="utf-8")
    assert "## 验证情况" not in current_template
    content = result.journal_path.read_text(encoding="utf-8")
    assert "## 2026-05-22 21:30:00" in content
    assert "- 分支：`main`" in content
    assert "- `app.py`" in content
    assert "app.py | 2 +-" in content


def test_generate_journal_summarizes_recent_workspace_conversation(tmp_path):
    session_root = tmp_path / "codex" / "sessions"
    session_path = session_root / "2026" / "05" / "23" / "rollout.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(
        "\n".join([
            '{"timestamp":"2026-05-22T15:00:00Z","type":"session_meta","payload":{"cwd":"' + str(tmp_path).replace("\\", "\\\\") + '"}}',
            '{"timestamp":"2026-05-22T15:01:00Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"之后生成的记录中不需要手动备注和验证情况这两行"}]}}',
            '{"timestamp":"2026-05-22T15:02:00Z","type":"event_msg","payload":{"type":"agent_message","message":"我会定位日志生成脚本并调整模板。"}}',
            '{"timestamp":"2026-05-22T15:03:00Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"当前开发记录备注、本次目标、AI 协作摘要、关键决策需要自动生成简短总结"}]}}',
        ]),
        encoding="utf-8",
    )

    result = dev_journal.generate_journal(
        repo_root=tmp_path,
        run_git=FakeGit({
            ("diff", "--cached", "--name-only"): "scripts/dev_journal.py\n",
            ("branch", "--show-current"): "feature/dev-journal\n",
            ("diff", "--cached", "--stat"): " scripts/dev_journal.py | 20 ++++++++++++++++++++\n",
            ("log", "-1", "--format=%cI"): "2026-05-22T22:00:00+08:00\n",
        }),
        now=dev_journal.datetime(2026, 5, 22, 22, 0, 0),
        session_roots=[session_root],
    )

    content = result.journal_path.read_text(encoding="utf-8")
    assert "## 手动备注" not in content
    assert "## 验证情况" not in content
    assert "### 当前开发记录备注" in content
    assert "#### 本次目标" in content
    assert "自动生成简短总结" in content
    assert "#### AI 协作摘要" in content
    assert "定位日志生成脚本" in content
    assert "#### 关键决策" in content
    assert "不需要手动备注和验证情况" in content


def test_find_recent_conversation_ignores_other_worktrees_and_old_messages(tmp_path):
    session_root = tmp_path / "sessions"
    session_path = session_root / "rollout.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(
        "\n".join([
            '{"timestamp":"2026-05-22T14:59:00Z","type":"session_meta","payload":{"cwd":"' + str(tmp_path).replace("\\", "\\\\") + '"}}',
            '{"timestamp":"2026-05-22T14:59:30Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"旧目标"}]}}',
            '{"timestamp":"2026-05-22T15:00:01Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"新目标"}]}}',
        ]),
        encoding="utf-8",
    )
    other_path = session_root / "other.jsonl"
    other_path.write_text(
        "\n".join([
            '{"timestamp":"2026-05-22T15:00:00Z","type":"session_meta","payload":{"cwd":"C:\\\\other"}}',
            '{"timestamp":"2026-05-22T15:01:00Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"其他工作树目标"}]}}',
        ]),
        encoding="utf-8",
    )

    messages = dev_journal._collect_recent_conversation_messages(
        repo_root=tmp_path,
        since=dev_journal.datetime(2026, 5, 22, 15, 0, tzinfo=timezone.utc),
        session_roots=[session_root],
    )

    assert [message.text for message in messages] == ["新目标"]


def test_find_recent_conversation_ignores_codex_context_messages(tmp_path):
    session_root = tmp_path / "sessions"
    session_path = session_root / "rollout.jsonl"
    session_path.parent.mkdir(parents=True)
    session_path.write_text(
        "\n".join([
            '{"timestamp":"2026-05-22T15:00:00Z","type":"session_meta","payload":{"cwd":"' + str(tmp_path).replace("\\", "\\\\") + '"}}',
            '{"timestamp":"2026-05-22T15:00:01Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"# AGENTS.md instructions for C:\\\\repo\\n- 安装依赖时优先使用 pnmp\\n<environment_context>...</environment_context>"}]}}',
            '{"timestamp":"2026-05-22T15:00:02Z","type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"生成自动摘要"}]}}',
        ]),
        encoding="utf-8",
    )

    messages = dev_journal._collect_recent_conversation_messages(
        repo_root=tmp_path,
        since=dev_journal.datetime(2026, 5, 22, 15, 0, tzinfo=timezone.utc),
        session_roots=[session_root],
    )

    assert [message.text for message in messages] == ["生成自动摘要"]


def test_build_conversation_summary_ignores_short_approval_as_goal():
    messages = [
        dev_journal.ConversationMessage(
            timestamp=dev_journal.datetime(2026, 5, 23, 9, 0, tzinfo=timezone.utc),
            role="user",
            text="提交当前工作树内容并与上两次提交合并，生成上述工作流总结文件",
        ),
        dev_journal.ConversationMessage(
            timestamp=dev_journal.datetime(2026, 5, 23, 9, 1, tzinfo=timezone.utc),
            role="user",
            text="批准了",
        ),
    ]

    summary = dev_journal._build_conversation_summary(messages, fallback_notes="")

    assert summary.goal == "提交当前工作树内容并与上两次提交合并，生成上述工作流总结文件"
