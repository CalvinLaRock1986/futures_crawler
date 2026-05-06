# futures-crawler 部署与执行文档

本文档用于将 `futures-crawler` 从 Git 部署到云服务器，并稳定执行（支持飞书推送）。

## 1. 环境要求

- Linux 云服务器（Ubuntu/CentOS 均可）
- Python >= 3.10
- Git
- 可访问目标 API 与飞书开放平台

## 2. 首次部署（从 Git 拉取）

```bash
# 1) 安装基础软件（Ubuntu 示例）
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip

# 2) 拉取代码
cd /opt
sudo git clone <你的仓库地址> futures_crawler
sudo chown -R $USER:$USER /opt/futures_crawler
cd /opt/futures_crawler

# 3) 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 4) 安装依赖
pip install -U pip
pip install pyyaml chinese-calendar
```

## 3. 配置文件与密钥

### 3.1 业务配置

- 复制并编辑配置（建议生产使用独立配置文件）：

```bash
cp config.yaml config.prod.yaml
```

按实际业务修改 `config.prod.yaml` 中的 API 地址、参数、输出路径等。

### 3.2 飞书凭证（推荐用 env 文件）

```bash
cp feishu.env.example feishu.env
```

编辑 `feishu.env`，填入：

```bash
FEISHU_APP_ID='cli_a93a9df49f389cca' 
FEISHU_APP_SECRET='NuLt0B6eSSdc9lT8utAaXcqdrtsndfVs' 
FEISHU_CHAT_ID='oc_d812bf1521bb103e62419ac091458d86' 
```

> 安全要求：
>
> - `feishu.env` 不要提交到 Git。
> - 若凭证泄露，立刻在飞书后台轮换 App Secret。

## 4. 手工执行

### 4.1 使用脚本（推荐）

```bash
cd /opt/futures_crawler
./scripts/run_with_feishu.sh
```

默认读取：

- `config.prod.yaml`
- `feishu.env`

如需显式指定配置：

```bash
cd /opt/futures_crawler
CONFIG=config.prod.yaml ./scripts/run_with_feishu.sh
```

### 4.2 直接命令执行（带飞书参数）

```bash
cd /opt/futures_crawler && /opt/futures_crawler/.venv/bin/python -m futures_crawler.cli run --config /opt/futures_crawler/config.prod.yaml --feishu-app-id "cli_a93a9df49f389cca" --feishu-app-secret "NuLt0B6eSSdc9lT8utAaXcqdrtsndfVs" --feishu-chat-id "oc_d812bf1521bb103e62419ac091458d86"
```

### 4.3 仅工作日执行

```bash
cd /opt/futures_crawler && /opt/futures_crawler/.venv/bin/python -m futures_crawler.cli run-workday --config /opt/futures_crawler/config.prod.yaml --feishu-app-id "cli_xxx" --feishu-app-secret "xxx" --feishu-chat-id "oc_xxx"
```

## 5. 定时任务（cron）

编辑 crontab：

```bash
crontab -e
```

示例：每天 09:05 执行（程序内会在节假日/周末自动跳过）：

```cron
5 9 * * * cd /opt/futures_crawler && /opt/futures_crawler/.venv/bin/bash -lc 'set -a; . /opt/futures_crawler/feishu.env; set +a; exec /opt/futures_crawler/scripts/run_with_feishu.sh' >> /opt/futures_crawler/cron.log 2>&1
```

查看任务与日志：

```bash
crontab -l
tail -n 100 /opt/futures_crawler/cron.log
```

## 6. 服务器更新代码（Git 已有新提交后）

```bash
ssh <user>@<server-ip>
cd /opt/futures_crawler

git fetch origin
git checkout main
git pull --ff-only origin main

source .venv/bin/activate
pip install -U pyyaml chinese-calendar
```

更新后建议手工跑一次：

```bash
cd /opt/futures_crawler
./scripts/run_with_feishu.sh
```

## 7. 常见问题排查

### 7.1 能抓到数据但没有推送飞书

通常是以下原因之一：

- 未传入 `FEISHU_APP_ID/FEISHU_APP_SECRET/FEISHU_CHAT_ID`
- cron 环境未加载 `feishu.env`
- 飞书密钥过期或错误

排查命令（增加日志）：

```bash
cd /opt/futures_crawler
VERBOSE=1 ./scripts/run_with_feishu.sh
```

### 7.2 Python 版本不符

确认版本：

```bash
python3 --version
```

需 >= 3.10。

### 7.3 依赖缺失

重新安装：

```bash
source /opt/futures_crawler/.venv/bin/activate
pip install -U pyyaml chinese-calendar
```

## 8. 运维建议

- 使用最小权限账号运行任务，避免 root 长期执行。
- `feishu.env` 权限建议设置为仅当前用户可读：

```bash
chmod 600 /opt/futures_crawler/feishu.env
```

- 每次更新后先手工运行一遍，再观察下一次 cron 日志。

