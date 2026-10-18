# GitHub 命令手册

仓库地址：`https://github.com/CalvinLaRock1986/futures_crawler.git`

本文只放 **新项目上传、日常代码更新、云服务器部署** 需要的命令。飞书密钥请写在服务器本地的 `feishu.env`，不要提交到 GitHub。

---

## 1. 新项目上传到 GitHub

在 GitHub 网页先建空仓库（不要勾选自动生成 README），然后在本地项目目录执行：

```bash
cd /path/to/futures_crawler

git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/CalvinLaRock1986/futures_crawler.git
git push -u origin main
```

如果本地已经是 git 仓库，只差绑定 GitHub：

```bash
cd /path/to/futures_crawler
git remote -v
git remote add origin https://github.com/CalvinLaRock1986/futures_crawler.git
# 若 origin 已存在但地址不对：
# git remote set-url origin https://github.com/CalvinLaRock1986/futures_crawler.git
git push -u origin main
```

不要提交这些文件（已在 `.gitignore`）：

- `feishu.env`
- `.venv/`
- `__pycache__/`、`*.pyc`
- `cron.log`

---

## 2. 日常代码更新（本机 -> GitHub）

```bash
cd /path/to/futures_crawler

git status
git add README.md docs/GITHUB.md config.yaml futures_crawler/*.py scripts/run_with_feishu.sh tests/test_crawler_engine.py
# 只 add 源码和文档，不要 add __pycache__、feishu.env、运行产物 CSV

git commit -m "说明本次改了什么"
git push origin main
```

查看远端是否已收到：

```bash
git fetch origin
git status
git log -1 --oneline
```

若 `git pull` 被 `__pycache__` 挡住（本机或服务器都可能遇到）：

```bash
git checkout -- futures_crawler/__pycache__/
# 或：git restore futures_crawler/__pycache__/
git pull --ff-only origin main
```

彻底不再跟踪这些 `.pyc`（做一次即可）：

```bash
git rm -r --cached futures_crawler/__pycache__ tests/__pycache__
git commit -m "stop tracking __pycache__"
git push origin main
```

---

## 3. 从 GitHub 部署到云服务器（首次）

```bash
# Ubuntu 示例
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip

cd /opt
sudo git clone https://github.com/CalvinLaRock1986/futures_crawler.git futures_crawler
sudo chown -R "$USER:$USER" /opt/futures_crawler
cd /opt/futures_crawler

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pyyaml chinese-calendar

cp config.yaml config.prod.yaml
cp feishu.env.example feishu.env
chmod 600 feishu.env
# 编辑 config.prod.yaml 和 feishu.env（密钥只放服务器，不要 git add）
```

手工跑一次（推荐脚本，会读取 `feishu.env`）：

```bash
cd /opt/futures_crawler
CONFIG=config.prod.yaml ./scripts/run_with_feishu.sh
```

或直接带飞书参数：

```bash
cd /opt/futures_crawler
/opt/futures_crawler/.venv/bin/python -m futures_crawler.cli run \
  --config /opt/futures_crawler/config.prod.yaml \
  --feishu-app-id "cli_xxx" \
  --feishu-app-secret "xxx" \
  --feishu-chat-id "oc_xxx"
```

每天 17:35 定时（crontab）：

```cron
35 17 * * * cd /opt/futures_crawler && /bin/bash -lc 'set -a; . /opt/futures_crawler/feishu.env; set +a; CONFIG=config.prod.yaml exec /opt/futures_crawler/scripts/run_with_feishu.sh' >> /opt/futures_crawler/cron.log 2>&1
```

```bash
crontab -e
crontab -l
tail -n 100 /opt/futures_crawler/cron.log
```

---

## 4. 服务器从 GitHub 更新代码（已部署过）

本机先 `git push origin main`，再到服务器：

```bash
ssh <user>@<server-ip>
cd /opt/futures_crawler

git checkout -- futures_crawler/__pycache__/
git fetch origin
git checkout main
git pull --ff-only origin main

source .venv/bin/activate
pip install -U pyyaml chinese-calendar

CONFIG=config.prod.yaml ./scripts/run_with_feishu.sh
```

一条命令版：

```bash
cd /opt/futures_crawler && git checkout -- futures_crawler/__pycache__/ && git pull --ff-only origin main && source .venv/bin/activate && pip install -U pyyaml chinese-calendar
```

私有仓库用 HTTPS 时，clone/pull 需要 GitHub 账号 + Personal Access Token（密码处填 token，不是登录密码）。

---

## 5. 常用对照

| 场景 | 在哪执行 | 命令 |
|------|----------|------|
| 第一次上传 | 本机 | `git remote add origin ...` + `git push -u origin main` |
| 改完代码 | 本机 | `git add` → `git commit` → `git push origin main` |
| 第一次上云 | 服务器 | `git clone` → 建 `.venv` → 配 `feishu.env` → 跑脚本 |
| 以后更新云端 | 服务器 | `git pull --ff-only origin main` 再试跑 |

更细的运行说明见 `docs/deploy-and-run.md`。
