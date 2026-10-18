# futures-crawler

Config-driven API crawler framework (Python, stdlib-only).

GitHub 上传、更新、部署命令见 [docs/GITHUB.md](docs/GITHUB.md)。

## Quick start

1. Edit `config.yaml` with your API endpoints and JSON paths.
2. Run:

```bash
/opt/anaconda3/envs/future/bin/python -m futures_crawler.cli run --config config.yaml --output output.csv
```

## Push generated file to Feishu bot (App mode)

Run crawler and push the generated CSV to a Feishu chat as a file message:

```bash
/opt/anaconda3/envs/future/bin/python -m futures_crawler.cli run \
  --config config.yaml \
  --feishu-app-id "cli_xxx" \
  --feishu-app-secret "xxx" \
  --feishu-chat-id "oc_xxx"
```

You can also set env vars instead of CLI args:

- `FEISHU_APP_ID`
- `FEISHU_APP_SECRET`
- `FEISHU_CHAT_ID`

## Run only on China workdays

Install holiday calendar dependency:

```bash
/opt/anaconda3/envs/future/bin/pip install chinese-calendar
```

Then use:

```bash
/opt/anaconda3/envs/future/bin/python -m futures_crawler.cli run-workday --config config.yaml
```

If today is weekend or China public holiday, it will skip automatically.

Example crontab (run every day 09:05, execute only on China workdays):

```bash
5 9 * * * /opt/anaconda3/envs/future/bin/python -m futures_crawler.cli run-workday --config /Users/yinyin/futures_crawler/config.yaml
```

## Offline smoke test

Before wiring real APIs, you can run a fully offline end-to-end demo:

```bash
/opt/anaconda3/envs/future/bin/python -m futures_crawler.cli run-mock --output mock_output.csv
```

## Config

See `config.yaml` for the required structure.

## Split CSV (long vs short)

When `output.split_only` is **false** (default in tests), the crawler writes one combined CSV and then also writes `{stem}_多单.csv` and `{stem}_空单.csv`.

When `output.split_only` is **true** (see `config.yaml`), the crawler **does not** write the combined file — only:

- `{stem}_多单.csv` — 交易日期, 合约, 品种, 会员简称, 多单持仓, 多单增减, 多单持仓均价
- `{stem}_空单.csv` — 交易日期, 合约, 品种, 会员简称, 空单持仓, 空单增减, 空单持仓均价

Example stem from `期货数据_{当前日期}.csv`: `期货数据_2026-04-30_多单.csv` and `期货数据_2026-04-30_空单.csv`.

With Feishu env vars set, **`split_only: true` uploads both split files** to the chat (two messages).

