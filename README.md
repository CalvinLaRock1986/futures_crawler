# futures-crawler

Config-driven API crawler framework (Python, stdlib-only).

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

