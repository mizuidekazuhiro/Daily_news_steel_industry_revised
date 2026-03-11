# 現在の構成（Notion単一情報源）

このプロジェクトは、Targets/Rules を Notion DB で一元管理する構成です。
ローカル YAML（`config/targets.yml` / `config/scoring.yml`）への依存はありません。

## ディレクトリ概要

.
├─ main.py # 実行オーケストレーション
├─ config/
│ ├─ prompts.yml # GPT要約のプロンプト
│ ├─ settings.yml # 実行上限など
│ ├─ tagging.yml # タグ補助ルール
│ └─ notion.yml # Notionプロパティ設定
├─ src/
│ ├─ adapters/
│ │ ├─ notion_targets.py # Targets DB読み込み
│ │ ├─ notion_rules.py # Rules DB読み込み
│ │ ├─ notion_exporter.py # Articles/Daily Summary 反映
│ │ ├─ serper_source.py # Serper検索
│ │ ├─ google_alert_source.py # Google Alert RSS取得
│ │ ├─ article_parser.py # 本文抽出/分類/公開日時
│ │ ├─ openai_summarizer.py # GPT要約
│ │ ├─ email_notifier.py # メール送信
│ │ └─ yahoo_finance.py # 株価/為替情報
│ ├─ usecases/
│ │ ├─ score_articles.py # Rules DBベースの重要度算出
│ │ ├─ tag_articles.py # Rules DB優先のタグ付与
│ │ └─ target_coverage.py # Targets読込結果の集計
│ ├─ domain/
│ │ ├─ rule_engine.py # Rules評価エンジン
│ │ └─ time_utils.py # 時刻処理
│ └─ config/
│   ├─ env.py # 環境変数
│   ├─ notion.py # notion.ymlローダ
│   ├─ prompts.py # prompts.ymlローダ
│   └─ settings.py # settings.ymlローダ
└─ docs/
  └─ structure.md

## 実行時の前提

起動時に以下が未設定ならエラーで停止します（Notion専用運用）。

- `NOTION_TOKEN`
- `NOTION_TARGETS_DB_ID`
- `NOTION_RULES_DB_ID`
- `NOTION_ARTICLES_DB_ID`
- `NOTION_DAILY_DB_ID`

## 重要度ルール

- 重要度は Rules DB の `RuleType=importance` のみを使って算出します。
- importance ルールが0件の場合は `score=0` / `importance=Low` を設定して安全に継続します。
