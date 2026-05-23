# 开发记录 Pre-Commit 工作流设计

## 目标

创建一个第一版工作流，在每次本地 Git commit 前记录 Codex/AI 辅助开发过程。这个工作流需要帮助总结本次改了什么、为什么改、做过哪些验证，并把记录保存在仓库中，后续正常 push 到 GitHub 时一起上传。

这一版只记录开发协作过程，不记录产品运行时的用户对话。

## 推荐方案

使用仓库管理的 Git `pre-commit` hook 加一个 Python 脚本。

- `scripts/dev_journal.py` 生成或更新当天的开发记录文件。
- `.githooks/pre-commit` 在每次 commit 前运行脚本。
- `docs/dev-journal/YYYY-MM-DD.md` 保存生成的开发记录。
- `docs/dev-journal/current.md` 作为可选的手动备注文件，用户可以在 commit 前写入本次目标、AI 协作摘要和验证说明。

这个方案保持工作流本地化、透明且可版本控制。它避免依赖 Codex 私有对话存储格式，因为那些格式可能变化，也不保证长期稳定。

工作流需要支持不同分支和不同 Git worktree。脚本应始终以当前命令所在的 worktree 仓库根目录为准写入记录，并在记录中标明当前分支。每个 worktree 需要各自执行一次 hook 启用命令。

## 用户流程

1. 开发过程中，可以按需编辑 `docs/dev-journal/current.md`。
2. 像平常一样 stage 代码变更。
3. 执行 `git commit -m "message"`。
4. `pre-commit` hook 自动运行 `python scripts/dev_journal.py`。
5. 脚本向 `docs/dev-journal/YYYY-MM-DD.md` 写入一条带日期的记录。
6. hook 自动 stage 生成的当天开发记录文件，让它进入同一个 commit。
7. 正常执行 `git push` 后，代码变更和开发记录会一起上传到 GitHub。

## 记录内容

每条生成的记录应包含：

- 时间戳和当前分支。
- 已 staged 的文件列表。
- 来自 `git diff --cached --stat` 的 staged diff 摘要。
- 来自 `docs/dev-journal/current.md` 的可选手动备注。
- 如果手动备注中填写了验证说明，则一并记录验证情况。

第一版不尝试保存完整原始聊天记录，而是捕获简洁、可读的开发过程摘要。

## 文件职责

### `scripts/dev_journal.py`

职责：

- 检测仓库根目录。
- 读取 staged 变更。
- 如果没有 staged 变更，则跳过记录生成。
- 读取 `docs/dev-journal/current.md` 中的可选备注。
- 向 `docs/dev-journal/YYYY-MM-DD.md` 追加一条新记录。
- 如果开发记录目录或备注模板文件不存在，则自动创建。
- 对非关键的可选文件缺失保持容错，避免无意义地中断 commit。

脚本只使用 Python 标准库。

### `.githooks/pre-commit`

职责：

- 运行 Python 开发记录脚本。
- stage 生成的开发记录文件。
- 只有在脚本本身异常失败时才阻止 commit。

hook 应保持简短，便于检查。

### `docs/dev-journal/current.md`

职责：

- 为用户或 AI 助手提供一个稳定位置，用于写入当前开发目标和摘要。
- 保持可手动编辑。
- 使用简单模板，包含目标、AI 协作、关键决策和验证情况等部分。

## 错误处理

- 如果没有 staged 文件，脚本成功退出，不写入开发记录。
- 如果可选备注为空，生成的记录仍包含从 Git 获取的变更信息。
- 如果 Git 命令失败，脚本以非零状态退出，让 hook 阻止 commit 并显示错误。
- 如果没有通过 `core.hooksPath` 安装 hook，工作流不会自动运行；设置说明需要清楚写明这一点。

## 设置

在 README 中加入设置说明：

```powershell
git config core.hooksPath .githooks
```

设置后，本地 commit 会运行仓库管理的 hook。

如果使用多个 Git worktree，需要进入每个 worktree 的项目根目录分别执行一次上面的命令。不同分支的记录会写入各自 worktree 中的 `docs/dev-journal/`，并在记录中显示当前分支名。

## 测试

验证应覆盖：

- 在没有 staged 变更时运行脚本。
- 在存在 staged 变更时运行脚本。
- 确认当天开发记录文件会被创建。
- 确认 hook 能 stage 生成的开发记录文件。
- 确认脚本只使用 Python 标准库。

如果后续工作流变复杂，可以再补自动化测试。第一版可以先通过一次临时 staged 变更进行手动验证。

## 暂不包含

- 自动提取完整 Codex 聊天记录。
- GitHub Actions 自动化。
- push 时汇总。
- 产品运行时聊天日志。
- 外部服务或数据库。
