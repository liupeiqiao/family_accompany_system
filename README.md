# family_accompany_system

## 开发记录工作流

本项目提供一个本地 Git `pre-commit` 工作流，用于在每次 commit 前自动生成开发记录。记录文件会保存在 `docs/dev-journal/YYYY-MM-DD-HHMM.md`，并随同代码一起提交，后续执行 `git push` 时会一起上传到 GitHub。

### 首次启用

在当前工作树的项目根目录执行：

```powershell
git config core.hooksPath .githooks
```

如果你使用多个分支或多个 Git worktree，每个 worktree 都需要在对应目录下执行一次上面的命令。脚本会按当前 worktree 的仓库根目录写入记录，并在记录中标明当前分支。

### 日常使用

开发过程中正常执行：

```powershell
git add .
git commit -m "本次修改说明"
git push
```

执行 `git commit` 时，hook 会自动运行 `python scripts/dev_journal.py`，生成或更新本次提交对应的分钟级开发记录，并把开发记录加入同一个 commit。

生成的记录会读取当前工作树自上次提交以来的最新 Codex 对话，并自动生成“当前开发记录备注”“本次目标”“AI 协作摘要”和“关键决策”区块。如果没有可用对话记录，会回退使用 `docs/dev-journal/current.md` 中的备注内容。
