# 开发记录 Pre-Commit 工作流实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个在本地 Git commit 前自动生成开发记录的第一版工作流。

**Architecture:** 用 `scripts/dev_journal.py` 负责读取当前 worktree 的 staged Git 信息并追加每日 Markdown 记录；用 `.githooks/pre-commit` 在 commit 前调用脚本并 stage 生成记录；用 `docs/dev-journal/current.md` 提供手动填写目标、AI 协作摘要和验证说明的入口。

**Tech Stack:** Python 标准库、pytest、Git hooks、Markdown。

---

## 文件结构

- Create: `scripts/dev_journal.py`，标准库 Python 脚本，提供 Git 命令封装、模板创建、开发记录生成和命令行入口。
- Create: `tests/test_dev_journal.py`，覆盖无 staged 变更跳过、创建模板、生成记录内容、追加每日记录等行为。
- Create: `.githooks/pre-commit`，运行开发记录脚本并 stage 生成文件。
- Create: `docs/dev-journal/current.md`，手动备注模板。
- Modify: `README.md`，说明 hook 安装、多个分支/worktree 的启用方式和使用命令。

### Task 1: 开发记录脚本测试

**Files:**
- Create: `tests/test_dev_journal.py`

- [ ] **Step 1: 写失败测试**

创建测试覆盖：

```python
from pathlib import Path

from scripts import dev_journal


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
    assert (tmp_path / "docs" / "dev-journal" / "current.md").exists()
    content = result.journal_path.read_text(encoding="utf-8")
    assert "## 2026-05-22 21:30:00" in content
    assert "- 分支：`main`" in content
    assert "- `app.py`" in content
    assert "app.py | 2 +-" in content


def test_generate_journal_includes_manual_notes(tmp_path):
    notes_path = tmp_path / "docs" / "dev-journal" / "current.md"
    notes_path.parent.mkdir(parents=True)
    notes_path.write_text("## 本次目标\n实现开发记录\n", encoding="utf-8")

    result = dev_journal.generate_journal(
        repo_root=tmp_path,
        run_git=FakeGit({
            ("diff", "--cached", "--name-only"): "scripts/dev_journal.py\n",
            ("branch", "--show-current"): "feature/dev-journal\n",
            ("diff", "--cached", "--stat"): " scripts/dev_journal.py | 20 ++++++++++++++++++++\n",
        }),
        now=dev_journal.datetime(2026, 5, 22, 22, 0, 0),
    )

    content = result.journal_path.read_text(encoding="utf-8")
    assert "## 手动备注" in content
    assert "实现开发记录" in content
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_dev_journal.py -v`

Expected: FAIL，失败原因是还没有 `scripts.dev_journal` 模块。

### Task 2: 实现开发记录脚本

**Files:**
- Create: `scripts/dev_journal.py`
- Create: `scripts/__init__.py`

- [ ] **Step 1: 写最小实现**

实现 `generate_journal()`、`JournalResult`、Git 命令封装和命令行入口。

- [ ] **Step 2: 运行测试确认通过**

Run: `pytest tests/test_dev_journal.py -v`

Expected: PASS。

### Task 3: Hook、模板和文档

**Files:**
- Create: `.githooks/pre-commit`
- Create: `docs/dev-journal/current.md`
- Modify: `README.md`

- [ ] **Step 1: 添加 hook**

`.githooks/pre-commit` 运行 `python scripts/dev_journal.py`，然后 stage `docs/dev-journal/*.md`。

- [ ] **Step 2: 添加手动备注模板**

`docs/dev-journal/current.md` 包含本次目标、AI 协作摘要、关键决策、验证情况四个部分。

- [ ] **Step 3: 更新 README**

说明启用 hook 的命令：

```powershell
git config core.hooksPath .githooks
```

并说明日常使用顺序：

```powershell
git add .
git commit -m "本次修改说明"
git push
```

说明多个 Git worktree 需要分别在各自目录执行 `git config core.hooksPath .githooks`，脚本会按当前 worktree 写入开发记录，并记录当前分支。

### Task 4: 验证

**Files:**
- Test: `tests/test_dev_journal.py`

- [ ] **Step 1: 运行新增测试**

Run: `pytest tests/test_dev_journal.py -v`

Expected: PASS。

- [ ] **Step 2: 运行全量测试**

Run: `pytest -q`

Expected: PASS。

- [ ] **Step 3: 检查 Git 状态**

Run: `git status --short`

Expected: 只看到本功能相关新增/修改，以及已有的未关联工作区变更。
