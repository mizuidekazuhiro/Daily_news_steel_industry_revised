# Daily News Steel Industry (Revised)

鉄鋼業界のニュースを収集・要約し、日次レポートとして配信するためのバッチプロジェクトです。
Serper検索とGoogle Alert RSSで記事を集め、本文抽出・分類・スコアリング・タグ付けを行い、GPT要約と株価情報を組み合わせたHTMLを生成してメール送信します。
また、Notion連携が有効な場合は記事と日次サマリをNotionデータベースへ保存します。 【F:main.py†L4-L156】【F:src/adapters/serper_source.py†L1-L27】【F:src/adapters/google_alert_source.py†L1-L76】【F:src/adapters/openai_summarizer.py†L1-L105】【F:src/adapters/yahoo_finance.py†L1-L244】【F:src/adapters/notion_exporter.py†L1-L154】

## 全体像（処理フロー）

1. 設定・プロンプト・ターゲットを読み込む
2. Serperでニュース検索 → 本文抽出 → 記事分類・時刻正規化
3. 企業向けターゲットはGoogle Alert RSSで補完し、重複除外
4. スコアリングとタグ付けを実施し、優先度順に並び替え
5. GPTでラベル単位の要約を生成し、朝一サマリを生成
6. 株価・為替セクションを追加してHTML化
7. メール送信、必要に応じてNotionへ記事・サマリを書き込み

上記の一連の処理は `main.py` がオーケストレーションしています。 【F:main.py†L4-L156】

## ディレクトリ構成

```
.
├─ main.py
├─ config/
│  ├─ targets.yml      # 監視対象（企業/テーマ）と検索クエリ
│  ├─ prompts.yml      # GPT要約用のプロンプト
│  ├─ settings.yml     # 取得範囲や最大件数などの実行設定
│  ├─ scoring.yml      # スコアリングルール
│  └─ tagging.yml      # 国・セクターのタグルール
├─ src/
│  ├─ adapters/        # 外部サービスとのI/O（検索、RSS、OpenAI、Notion、株価など）
│  ├─ config/          # 環境変数・YAML読み込み
│  ├─ domain/          # 日付処理などドメインロジック
│  └─ usecases/        # スコア/タグ付けなどのユースケース
└─ docs/               # 補足ドキュメント
```

## 主要モジュールの役割

- `main.py`
  - 実行フローをまとめるエントリーポイントです。設定読込、検索・要約・配信・Notion連携までを統括します。 【F:main.py†L4-L156】
- `src/adapters/serper_source.py`
  - Serper APIでニュース検索を実行します。 【F:src/adapters/serper_source.py†L1-L27】
- `src/adapters/google_alert_source.py`
  - Google Alert RSSから記事を取得し、本文抽出・分類・重複除外を行います。 【F:src/adapters/google_alert_source.py†L1-L98】
- `src/adapters/article_parser.py`
  - Web記事本文の抽出、公開日時の推定、記事タイプ分類を行います。 【F:src/adapters/article_parser.py†L1-L50】
- `src/adapters/openai_summarizer.py`
  - GPT要約（ラベル単位）と朝一サマリを生成します。 【F:src/adapters/openai_summarizer.py†L1-L105】
- `src/adapters/yahoo_finance.py`
  - 株価・時価総額・為替を取得し、HTMLセクションを生成します。 【F:src/adapters/yahoo_finance.py†L1-L244】
- `src/adapters/notion_exporter.py`
  - Notion DBへ記事と日次サマリを保存します。 【F:src/adapters/notion_exporter.py†L1-L154】
- `src/usecases/score_articles.py`
  - ルールベースのスコアリングを適用し、重要度ラベルを付与します。 【F:src/usecases/score_articles.py†L1-L13】【F:src/adapters/rule_based_scorer.py†L1-L64】
- `src/usecases/tag_articles.py`
  - ルールに基づき国・セクターのタグを付与します。 【F:src/usecases/tag_articles.py†L1-L29】

## 設定ファイル

- `config/targets.yml`: 企業名/テーマと検索クエリ、Google Alert RSSの対応付け。 【F:config/targets.yml†L1-L105】
- `config/prompts.yml`: GPT要約プロンプト（ラベル要約・朝一サマリ）。 【F:config/prompts.yml†L1-L88】
- `config/settings.yml`: 取得対象時間や最大件数など。 【F:config/settings.yml†L1-L6】
- `config/scoring.yml`: スコアリング重みとキーワード。 【F:config/scoring.yml†L1-L19】
- `config/tagging.yml`: 国・セクターのタグ辞書。 【F:config/tagging.yml†L1-L24】

## 環境変数

`src/config/env.py` にまとめられています。 【F:src/config/env.py†L1-L15】

- `SERPER_API_KEY` / `OPENAI_API_KEY`
- `GMAIL_USER` / `GMAIL_PASS` / `EMAIL_TO`
- `NOTION_TOKEN` / `NOTION_ARTICLES_DB_ID` / `NOTION_DAILY_DB_ID` / `NOTION_TARGETS_DB_ID`

## 実行手順（例）

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SERPER_API_KEY=...
export OPENAI_API_KEY=...
export GMAIL_USER=...
export GMAIL_PASS=...
export EMAIL_TO=...

python main.py
```

> 注: メール送信の具体実装は `src/adapters/email_notifier.py` の `send_mail` に依存します。実運用ではここにSMTP送信処理を実装してください。 【F:main.py†L6-L14】

## 今後拡張するには（どこに何をどう追加するか）

### 1) 監視対象・検索クエリを追加したい
- `config/targets.yml` にラベルとクエリを追記します。
- Google Alert RSSで補完したい場合は `google_alert_rss` にRSS URLを追加します。 【F:config/targets.yml†L1-L105】

### 2) 重要度の判定ルールを調整したい
- `config/scoring.yml` の重みやキーワードを更新します。
- ロジック自体を変える場合は `src/adapters/rule_based_scorer.py` を拡張します。 【F:config/scoring.yml†L1-L19】【F:src/adapters/rule_based_scorer.py†L1-L64】

### 3) タグ（国・セクター）を追加したい
- `config/tagging.yml` にキーワードを追加します。
- 新しい分類軸を増やしたい場合は `src/usecases/tag_articles.py` に新規フィールドを追加します。 【F:config/tagging.yml†L1-L24】【F:src/usecases/tag_articles.py†L1-L29】

### 4) 新しい記事取得ソースを追加したい
- `src/adapters/` に新しいソースアダプタを追加します（例: RSS、社内DBなど）。
- `main.py` の取得ループでそのアダプタを呼び出し、記事配列に統合します。 【F:main.py†L39-L114】

### 5) 要約ロジックやモデルを変えたい
- `config/prompts.yml` を編集してプロンプトを調整します。
- モデルやAPI構成を変える場合は `src/adapters/openai_summarizer.py` を修正します。 【F:config/prompts.yml†L1-L88】【F:src/adapters/openai_summarizer.py†L1-L105】

### 6) 出力先を増やしたい（Slack/Teams/ファイルなど）
- 既存の通知処理は `send_mail` を呼ぶ構造です。新しい出力先を追加する場合は `src/adapters/` にNotifierを実装し、`main.py` の送信箇所を分岐させるのが最短です。 【F:main.py†L6-L14】【F:main.py†L129-L137】

### 7) Notion連携を拡張したい
- 記事保存は `src/adapters/notion_exporter.py` が担っています。保存項目の追加・変換ロジックの変更はここを修正します。 【F:src/adapters/notion_exporter.py†L1-L154】
- 監視対象をNotionで管理したい場合は `NOTION_TARGETS_DB_ID` を設定すると、`config/targets.yml` に追記する形で取り込まれます。 【F:src/adapters/targets_yaml.py†L1-L35】【F:src/config/env.py†L1-L15】

## 補足ドキュメント

- `docs/structure.md`: さらなる分割・拡張を見据えた構成案。 【F:docs/structure.md†L1-L117】
- `docs/unpack.md`: zip配布時の展開手順。 【F:docs/unpack.md†L1-L25】
