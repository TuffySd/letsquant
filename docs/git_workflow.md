# Git Workflow

## 账号信息

GitHub 账号邮箱：

- `shendan_sd@126.com`

不要在项目文件、文档、提交历史或配置中保存 GitHub 密码、Personal Access Token、SSH 私钥或其他凭据。

如果密码已经在聊天、日志或文档中暴露，应立即在 GitHub 修改密码，并检查账号安全设置。

## 当前仓库状态

当前运行环境将标准 `.git` 路径挂载为只读空目录，因此本项目使用 `.git-local/` 作为本地 Git 元数据目录。

在当前环境执行 Git 命令时使用：

```bash
git --git-dir=.git-local --work-tree=. status
git --git-dir=.git-local --work-tree=. log --oneline --decorate --graph --all
```

也可以使用项目内包装脚本：

```bash
scripts/git-local status
scripts/git-local log --oneline --decorate --graph --all
```

如果后续环境允许使用标准 `.git`，可以迁移为普通 Git 仓库。

## 本地配置

本项目本地 Git 配置：

```bash
git --git-dir=.git-local --work-tree=. config user.email shendan_sd@126.com
git --git-dir=.git-local --work-tree=. config user.name shendan_sd
```

## 分支策略

默认长期分支：

- `main`：稳定主线，只保留已经验证通过的里程碑。

里程碑分支命名：

- `milestone/<date>-<topic>`
- 示例：`milestone/2026-05-26-foundation`
- 示例：`milestone/2026-06-01-tushare-data-sync`

每个里程碑完成时：

1. 运行测试和关键命令。
2. 更新 `project_state.md`。
3. 在当前里程碑分支提交。
4. 合并回 `main`。
5. 如已配置远程仓库，则推送分支和 `main`。

## 远程仓库

不要使用账号密码配置 HTTPS 远程。推荐二选一：

### SSH

```bash
git --git-dir=.git-local --work-tree=. remote add origin git@github.com:<github-user>/<repo>.git
git --git-dir=.git-local --work-tree=. push -u origin main
```

### GitHub CLI

```bash
gh auth login
gh repo create letsquant --private --source=. --remote=origin
git --git-dir=.git-local --work-tree=. push -u origin main
```

如果使用 Personal Access Token，只能放在系统 credential manager、环境变量或交互式凭据管理中，不写入项目文件。

## 提交要求

每次提交前至少执行：

```bash
make test
make compile
```

涉及回测、策略、信号输出时还应执行：

```bash
make backtest
make signal
```

提交信息格式建议：

```text
<type>: <short summary>
```

常用类型：

- `init`
- `data`
- `strategy`
- `backtest`
- `signal`
- `docs`
- `test`
- `chore`
