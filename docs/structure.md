# 分割案（拡張性重視・1ファイル1責務）

> 目的: `main.py` 1枚構成から脱却し、
> - 取得元の差し替え（Serper / RSS / Notion / 他）
> - 出力先の差し替え（Email / Notion / Slack / 保存）
> - ターゲット/プロンプトの外部管理（YAML / Notion DB）
> を容易にする。

## 1. 目標ディレクトリ構成（案）
.
├─ main.py # エントリーポイント（最小）
├─ config/
│ ├─ targets.yml # 監視対象・検索クエリ
│ ├─ prompts.yml # GPT要約のプロンプト
│ ├─ settings.yml # 接続先や実行モードなどの設定
│ └─ scoring.yml # 記事の軽重判定ルール（調整可能）
├─ src/
│ ├─ config/
│ │ ├─ env.py # 環境変数の読み込み
│ │ └─ settings.py # settings.yml の読み込み
│ ├─ domain/
│ │ ├─ models.py # Article/Target などのドメインモデル
│ │ └─ time.py # 日付・タイムゾーン関連ユーティリティ
│ ├─ usecases/
│ │ ├─ collect_articles.py # 記事収集フロー（取得・フィルタ・整形）
│ │ ├─ score_articles.py # 記事の軽重スコアリング
│ │ ├─ summarize.py # GPT要約フロー
│ │ ├─ build_report.py # HTMLレポート組み立て
│ │ └─ dispatch.py # 通知/ログ出力のオーケストレーション
│ ├─ ports/
│ │ ├─ targets.py # TargetRepository 抽象
│ │ ├─ articles.py # ArticleSource 抽象
│ │ ├─ scorer.py # ArticleScorer 抽象
│ │ ├─ summarizer.py # Summarizer 抽象
│ │ ├─ notifier.py # Notifier 抽象
│ │ └─ log_sink.py # LogSink 抽象
│ ├─ adapters/
│ │ ├─ targets_yaml.py # YAMLからTargetを読む
│ │ ├─ targets_notion.py # Notion DBからTargetを読む（将来）
│ │ ├─ serper_source.py # Serper 検索
│ │ ├─ google_alert_source.py # Google Alert RSS取得
│ │ ├─ article_parser.py # 本文抽出/分類/日付正規化
│ │ ├─ rule_based_scorer.py # ルールベース軽重判定（scoring.yml）
│ │ ├─ openai_summarizer.py # OpenAI GPT要約
│ │ ├─ email_notifier.py # Gmail送信
│ │ ├─ notion_log_sink.py # Notionへログ保存（将来）
│ │ └─ yahoo_finance.py # 株価/為替取得
│ └─ utils/
│ └─ http.py # HTTP共通処理（ヘッダー/リトライ等）
└─ docs/
└─ structure.md # このファイル


## 2. 主要責務の分割方針

| 現在の責務 | 新規ファイル | 補足 |
| --- | --- | --- |
| 環境変数読み込み | `src/config/env.py` | APIキー・メール設定など |
| ターゲット管理 | `src/adapters/targets_yaml.py` / `src/adapters/targets_notion.py` | YAML/Notion切替可能に |
| Serper検索 | `src/adapters/serper_source.py` | ArticleSource 実装 |
| Google Alert RSS | `src/adapters/google_alert_source.py` | ArticleSource 実装 |
| 本文抽出・日付・分類 | `src/adapters/article_parser.py` | parserは1責務に寄せる |
| 記事の軽重判定 | `src/adapters/rule_based_scorer.py` | scoring.yml を参照して重み付け |
| GPT要約 | `src/adapters/openai_summarizer.py` | Summarizer 実装 |
| HTML組み立て | `src/usecases/build_report.py` | 文面設計とロジックを分離 |
| 送信 | `src/adapters/email_notifier.py` | Notifier 実装 |
| Notionログ | `src/adapters/notion_log_sink.py` | LogSink 実装（将来） |
| 株価/為替 | `src/adapters/yahoo_finance.py` | 外部API依存を分離 |

## 3. 軽重判定の扱い（将来調整可能）

- `config/scoring.yml` にルールを集約し、非コードで調整可能にする
- `rule_based_scorer.py` は `ArticleScorer` 実装として、
  - キーワード
  - 企業名/テーマ
  - 記事分類（BUSINESS / GREEN / STOCK / OTHER）
  - ソース信頼度
  - 発表元（IR/政府/業界団体など）
  などの要素を重みづけ評価できるようにする

### scoring.yml の例（イメージ）
weights:
base: 1.0
business: 2.0
green: 1.5
stock: 0.5
official_source: 2.0
low_trust_source: 0.5

keywords:
high_impact:
- "capacity"
- "investment"
- "設備投資"
- "新工場"
low_impact:
- "event"
- "award"

source_trust:
match: "reuters.com"
weight: 2.0

match: "prtimes.jp"
weight: 0.5


- ルール変更は `scoring.yml` の差し替えで可能にする
- 将来的に Notion DB に `scoring` テーブルを持たせ、
  `targets` と同様にアダプタ差し替えで設定源を切替可能にする

## 4. main.py の最小化イメージ

- 実行順序だけを定義し、依存は `settings.yml` で切り替え
- 例: `TargetRepository=YAML` / `LogSink=Notion` など

main.py
-> settings を読む
-> TargetRepository を選ぶ
-> ArticleSource を束ねて記事取得
-> ArticleScorer で軽重を付与
-> Summarizer で要約
-> build_report でHTML化
-> Notifier で送信
-> LogSink でログ保存


## 5. すぐできる最初の分割（MVP）

1. `targets.yml` / `prompts.yml` / `scoring.yml` を追加（コードから外す）
2. `serper_source.py` / `google_alert_source.py` / `openai_summarizer.py` を分離
3. `rule_based_scorer.py` を追加して軽重判定を差し替え可能にする
4. `main.py` を「配線・実行」のみに縮小

この3〜4段階まで進めれば、Notion連携は **アダプタ追加だけ** で差し替え可能になります。


