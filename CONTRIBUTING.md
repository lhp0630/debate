---
audience: llm-agent
purpose: 贡献工作流约束（分支、提交、PR）
scope: branching, commits, pull-request, docs-touch
priority: 执行任何 Git 写操作前 MUST 完整读取并遵守
reference: conventional-commits-1.0.0 + 本项目扩展
---



执行任何 Git 分支创建、提交、推送、PR 操作之前: 1. MUST 完整读取本文件。 2. MUST NOT 直接向 `main` 推送或提交。 3. MUST NOT 创建 commit, 除非用户在对话中明确要求（见项目 user rules）。 4. MUST NOT 执行 `git push --force` 到 `main`/`master`, 除非用户明确要求。 5. 变更范围不明确时: STOP, 向用户澄清, 对齐 rules.mdc 的计划确认门禁后再继续。



PRECONDITION:

- base_branch = `main`
- 本地 `main` 已与 upstream 同步

MUST:

- 从最新 `main` 切出功能分支
- 禁止直接向 `main` 提交

BRANCH_NAME_PATTERN:
  feat/   # 新功能
  fix/    # Bug 修复
  docs/   # 仅文档变更

PROCEDURE:

1. git checkout main
2. git pull upstream main
3. git checkout -b /

VALIDATION:

- slug: 小写, 连字符分隔, 无空格
- type: 必须为 [feat, fix, docs] 之一





TEMPLATE:

```text
<type>(<scope>): <subject>

<body>

<footer>
```

SUBJECT_RULES (MUST):

- 祈使语气, 标题行末尾不加句号
- 标题行不超过 50 字符
- 原子提交: 每次 commit 仅解决一个逻辑变更

BODY_RULES (SHOULD):

- 说明改了什么以及为什么改（不仅是如何改）
- 正文每行建议 72 字符内换行
- 标题与正文之间保留一个空行

FOOTER_RULES (MAY):

- 引用工单: `Closes #123`, `Refs #456`

BREAKING_CHANGE (MUST, 若适用):

- 在 type 后加 `!`: 如 `feat!:` 
- 或在页脚注明: `BREAKING CHANGE: <description>`

COMMIT_MESSAGE_DELIVERY:

- 通过 HEREDOC 传递 commit message, 避免 shell 转义问题:

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<body>

EOF
)"
```



{ "allowed_types": { "feat": { "含义": "新功能", "scope_required": false }, "fix": { "含义": "Bug 修复", "scope_required": false }, "docs": { "含义": "仅文档/注释", "scope_required": false }, "style": { "含义": "格式调整, 不改变逻辑", "scope_required": false }, "refactor": { "含义": "结构性重构, 行为不变", "scope_required": true }, "tweak": { "含义": "局部微调/重命名", "scope_required": true, "note": "非标准 Conventional Commits 扩展类型, 见 " }, "perf": { "含义": "性能优化", "scope_required": false }, "test": { "含义": "测试用例增删改", "scope_required": false }, "chore": { "含义": "构建工具/依赖/辅助脚本", "scope_required": false }, "ci": { "含义": "CI/CD 配置", "scope_required": false }, "revert": { "含义": "回滚先前 commit", "scope_required": false } }, "forbidden_types": ["wip", "tmp", "update", "misc", "fixed", "changes"] }

本项目扩展了 Conventional Commits, 新增 `tweak` 类型。 若启用 commitlint, MUST 在配置中显式注册该类型, 否则 `tweak` 提交会被拒绝。

参考配置 (commitlint.config.js):

```js
module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "type-enum": [2, "always", [
      "feat", "fix", "docs", "style", "refactor", "tweak", "perf", "test", "chore", "ci", "revert"
    ]],
    "scope-empty": [2, "never", ["refactor", "tweak"]],
  },
};
```

无 commitlint 时: agent MUST 在生成 commit message 前对照  自行校验。


feat(auth): 添加微信 Token 校验 fix(api): 处理超时时的空响应 docs(contributing): 重写面向模型的贡献规范 refactor(auth): 重写 Token 校验模块 tweak(auth): 优化冗余守卫变量命名 feat!: 移除旧版 session cookie 格式

BREAKING CHANGE: session cookie 现仅支持 JWT


fixed stuff update code feat: 重构微信登录的 Token 校验模块（标题过长/非祈使语气） refactor: 大范围结构调整（大型 refactor 缺少 scope） tweak: 小改动（tweak 类型 MUST 带 scope）

当 commit type = docs 时: - MAY 修改: README.md, CONTRIBUTING.md, docs/**, tasks/**, .cursor/rules/** - MUST NOT 在同一 commit 中混入代码逻辑变更 - SHOULD 若工作流文档变更, 同步更新 tasks/active_context.md



PRECONDITION:

- 功能分支已完成开发与 commit
- 用户明确要求创建 PR（或对话上下文已授权）

PROCEDURE (MUST 按序执行):

[Step 1] 并行收集状态:

```bash
git status
git diff
git branch -vv
git log --oneline -10
git diff <base-branch>...HEAD
```

[Step 2] 分析:

- 纳入 PR 的全部 commit（不仅是最近一次）
- 确认无 .env / credentials 等敏感文件

[Step 3] 推送（若未跟踪远程）:

```bash
git push -u origin HEAD
```

需要网络权限时 MUST 请求 `all` 或 `full_network`。

[Step 4] 创建 PR:

```bash
gh pr create --title "<简明标题>" --body "$(cat <<'EOF'
## Summary
- <变更要点 1>
- <变更要点 2>

## Test plan
- [ ] <验证项 1>
- [ ] <验证项 2>

EOF
)"
```

PR_TITLE_RULES (MUST):

- 聚焦 why, 1 行概括
- 与主要 commit type/scope 语义一致

PR_BODY_RULES (SHOULD):

- Summary: 1-3 条 bullet
- Test plan: checklist 格式

POSTCONDITION:

- MUST 将 PR URL 返回给用户
- MUST NOT 未经用户要求执行 push 到 remote



规则冲突或校验失败时: 1. HALT 当前 Git/PR 操作 2. 报告触犯的规则条目 3. 给出修正后的分支名或 commit message 草案 4. 等待用户确认后再重试

本文件与以下规则协同: - `.cursor/rules/rules.mdc` 第 9 条: 所有 Git 操作 MUST 遵守本文件 - 项目 user rules: committing-changes-with-git, creating-pull-requests - `.cursor/rules/plan.mdc`: 计划确认门禁优先于实施

