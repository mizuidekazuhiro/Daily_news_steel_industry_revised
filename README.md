# Daily News Steel Industry (Revised)

鉄鋼業界のニュースを収集・要約し、日次レポートとして配信するバッチプロジェクトです。
Serper検索とGoogle Alert RSSで記事を集め、本文抽出・分類・スコアリング・タグ付けを行い、GPT要約と株価情報を組み合わせたHTMLを生成してメール送信します。
Notion連携が有効な場合は、記事ログ・日次サマリ・検索条件・タグ/重要度ルールをNotion中心で運用できます。

## 全体像（処理フロー）

```
[起動]
  ↓
設定/プロンプト読み込み
  ↓
Notion Targets/Rules 読み込み → 設定に合成
  ↓
Serper検索 + Google Alert RSS補完
  ↓
本文スクレイピング & 公開日時抽出
  ↓
タグ付与（Notion Rules優先）
  ↓
重要度スコア算出（Notion Rules優先）
  ↓
GPT要約（ラベル別）+ 朝一サマリ生成
  ↓
Notion ArticlesへUpsert（本文は [AUTO] ブロックに保存）
  ↓
Daily Summaryを作成しArticlesとRelation
  ↓
メール送信
```

## Notion DB 構成（4つ）

### 1) Articles DB（記事ログ）
| プロパティ | 種別 | 役割 |
| --- | --- | --- |
| Name | title | 記事タイトル |
| URL | url | 記事URL |
| Source | rich_text | ドメイン等の出典 |
| Label | select | 監視ラベル |
| Type | select | 記事タイプ |
| Country | multi_select | 国タグ |
| Sector | multi_select | 分野タグ |
| PrimaryCountry | select (任意) | 主国タグ |
| Importance | select (High/Medium/Low) | 重要度 |
| ImportanceScore | number | 重要度スコア |
| ImportanceReasons | rich_text | 重要度理由内訳 |
| PublishedAt | date | 公開日時 |
| PublishedSource | select (meta/jsonld/serper/unknown) | 公開日時ソース |
| ArticleId | rich_text | sha256(normalized_url) |
| NormalizedURL | url or rich_text | 正規化URL |
| BodyHash | rich_text | 本文ハッシュ |
| BodyPreview | rich_text | 本文プレビュー |

本文全文はページ本文に保存されます（[AUTO] 見出し配下のみ自動更新）。

### 2) Daily Summary DB（日次ログ）
| プロパティ | 種別 | 役割 |
| --- | --- | --- |
| Name | title | 日次タイトル |
| RunId | rich_text | 実行ID |
| RunDate | date | 実行日 |
| MorningSummary | rich_text | 朝一サマリ |
| Articles | relation | Articles DBとのRelation |
| RunStats | rich_text | 取得件数/失敗数など |

### 3) Targets DB（検索条件管理）
| プロパティ | 種別 | 役割 |
| --- | --- | --- |
| Enabled | checkbox | 有効/無効 |
| Label | title | 監視ラベル |
| Kind | select (serper / rss) | 種別 |
| Query | rich_text | Serper検索ワード |
| RSS | url | RSS URL |
| Enterprise | checkbox | 企業補完対象 |

### 4) Rules DB（タグ/重要度ルール管理）
| プロパティ | 種別 | 役割 |
| --- | --- | --- |
| Enabled | checkbox | 有効/無効 |
| RuleType | select (country / sector / importance) | ルール種別 |
| TagName | title | タグ名 |
| Keywords | rich_text | キーワード（カンマ区切り） |
| NegativeKeywords | rich_text | 除外キーワード |
| MatchField | select (title / body / both) | 判定対象 |
| Weight | number | 重要度加点 |
| Priority | number | 国優先度（主国判定） |
| Notes | rich_text | 運用メモ |

## Notion Integration 作成・DB共有手順

1. Notionで「Settings → Integrations → Develop your own integrations」を開く
2. Tokenを作成（Internal Integration）
3. Articles/Daily/Targets/Rules の各DBページで「Share」→ Integrationを招待
4. `.env` もしくは環境変数に `NOTION_TOKEN` と各DB IDを設定

## 環境変数一覧

### 必須
- `SERPER_API_KEY`
- `OPENAI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_ARTICLES_DB_ID`
- `NOTION_DAILY_DB_ID`
- `NOTION_TARGETS_DB_ID`
- `NOTION_RULES_DB_ID`

### メール送信を使う場合
- `GMAIL_USER`
- `GMAIL_PASS`
- `EMAIL_TO`

### GitHub Actions 例
```yaml
env:
  SERPER_API_KEY: ${{ secrets.SERPER_API_KEY }}
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
  NOTION_ARTICLES_DB_ID: ${{ secrets.NOTION_ARTICLES_DB_ID }}
  NOTION_DAILY_DB_ID: ${{ secrets.NOTION_DAILY_DB_ID }}
  NOTION_TARGETS_DB_ID: ${{ secrets.NOTION_TARGETS_DB_ID }}
  NOTION_RULES_DB_ID: ${{ secrets.NOTION_RULES_DB_ID }}
  GMAIL_USER: ${{ secrets.GMAIL_USER }}
  GMAIL_PASS: ${{ secrets.GMAIL_PASS }}
  EMAIL_TO: ${{ secrets.EMAIL_TO }}
```

## Notionでの運用方法

### 検索条件を追加/無効化したい
- Targets DBに新規行を追加し、`Enabled` をON
- Serper用なら `Kind=serper` と `Query` を入力
- RSS用なら `Kind=rss` と `RSS` を入力
- Enterprise補完対象は `Enterprise` をON

### タグ/重要度ルールを追加/無効化したい
- Rules DBに新規行を追加し、`Enabled` をON
- 国タグ: `RuleType=country`、`TagName` を国名に
- 分野タグ: `RuleType=sector`、`TagName` を分野名に
- 重要度: `RuleType=importance` と `Weight` を設定

## トラブルシュート

- **Serperのクレジット不足**: Serperダッシュボードで残量確認。`SERPER_CREDIT_ERROR` が出たらクエリ数を削減。
- **Notion rate limit**: 数分待って再実行。指数バックオフで再試行します。
- **本文が長すぎる**: ブロック分割は約1800文字ごとに行います（Notion制限対策）。
- **Notion権限エラー**: Integrationが各DBに共有されているか確認。
- **本文更新されない**: `BodyHash` が変わらない場合は [AUTO] セクションを更新しません。

## 運用Tips

- **Priorityの使い方**: countryルールで最も高いPriorityが主国になります。
- **NegativeKeywords**: 誤爆しやすい単語（例: football, chess）を入れて精度を上げる。
- **Enterprise補完**: Serperで拾い切れない企業名をRSSで補完する用途に便利。
- **コスト削減**: Rulesを絞って重要度が低い記事を除外すると、GPT要約のトークン消費が抑えられます。

## 実行手順（例）

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export SERPER_API_KEY=...
export OPENAI_API_KEY=...
export NOTION_TOKEN=...
export NOTION_ARTICLES_DB_ID=...
export NOTION_DAILY_DB_ID=...
export NOTION_TARGETS_DB_ID=...
export NOTION_RULES_DB_ID=...

python main.py
```

## 設定ファイル

- `config/targets.yml`: Serper/Google Alertのデフォルト検索条件（Notion未設定時のフォールバック）
- `config/tagging.yml`: タグ辞書のフォールバック
- `config/scoring.yml`: 重要度閾値/重みのフォールバック
- `config/notion.yml`: Notionプロパティ名/タイプ、[AUTO]見出し名
