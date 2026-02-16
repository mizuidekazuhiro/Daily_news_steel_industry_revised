# Daily News Steel Industry (Revised)

鉄鋼業界のニュースを収集・要約し、日次レポートとして配信するバッチプロジェクトです。
Serper検索とGoogle Alert RSSで記事を集め、本文抽出・分類・スコアリング・タグ付けを行い、GPT要約と株価情報を組み合わせたHTMLを生成してメール送信します。
Notion連携が有効な場合は、記事ログ・日次サマリ・検索条件・タグ/重要度ルールをNotion中心で運用できます。

## GPT投入件数のルール

- **ラベル別要約**: 1ラベルあたり最大 `max_articles_per_label` 件をGPTへ投入します（デフォルト 5 件）。
- **朝一サマリ**: 全ラベルからスコア上位を抽出したうえで `global_summary_top_n` 件をGPTへ投入します（未設定時は 7 件）。同一ラベルの分散上限は **企業=1件 / テーマ=2件** がデフォルトで、Notion Targets の `MaxPick` で上書き可能です。
- **要約対象の前提**:
  - **全体ニュース要約（朝一サマリ）** は importance > 0 かつ **株価系（STOCK）は除外** した記事のみが対象です。
  - **ラベル別要約** は importance による除外は行わず、株価系も含めて従来どおり上位件数を対象にします（importanceは順位づけに影響）。
- **変更方法**: 件数ルールを変更したい場合は `config/settings.yml`（`max_articles_per_label`）と `main.py` の `global_summary_top_n` 参照箇所を調整してください。

## 実行スケジュールと取得期間（JST基準）

- GitHub Actions の実行は `49 21 * * 0-4`（UTC）で、**JSTでは月〜金 06:49** に相当します。
- 曜日判定と取得期間の計算は **Asia/Tokyo (JST)** で行います（UTC曜日は使いません）。
- 取得期間は次の通りです。
  - **月曜実行（JST）**: 直近週末を拾うため、**金曜 00:00:00 〜 日曜 23:59:59（JST）** の3日分。
  - **それ以外（火〜金、関数上は日曜等も含む）**: 実行時刻から遡って **直近24時間**。

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
GPT要約（ラベル別）+ 朝一サマリ生成（同一Labelの分散上限あり）
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
| MaxPick | number (任意) | 朝一サマリの同一Label上限を上書き（未設定時は企業=1/テーマ=2） |

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
- 朝一サマリの分散上限を変えたい場合は `MaxPick` に数値を入力（未設定なら企業=1/テーマ=2）

### タグ/重要度ルールを追加/無効化したい
- Rules DBに新規行を追加し、`Enabled` をON
- 国タグ: `RuleType=country`、`TagName` を国名に
- 分野タグ: `RuleType=sector`、`TagName` を分野名に
- 重要度: `RuleType=importance` と `Weight` を設定

## 重要度判定ロジック（Notion優先）

- **Notion Rule DBに `RuleType=importance` が1件でも存在する場合**: 重要度は Notion ルールの Weight 合計で決定されます。
- **Notion Rule DBに `RuleType=importance` が存在しない場合のみ**: `config/scoring.yml` の従来スコアリング（RuleBasedScorer）で重要度を算出します。

## Notion Rule DB を“操作パネル”として使う運用方針

重要度と要約掲載/非掲載を **Notion Rule DB だけで運用**できるように、importance ルールを次の3種類に整理して管理します。

1. **Theme重要度（何の話か）**: 設備投資・脱炭素などテーマを表すルール
2. **Event重要度（出来事の強さ）**: 大型投資発表・規制変更などイベントを表すルール
3. **調整用ルール（ノイズ除去/抑制）**: 株価短期や一般市況など、要約から外したいノイズを抑制するルール

### 要約対象の定義

- **全体ニュース要約（朝一サマリ）**:
  - importance > 0 の記事のみが対象
  - **株価系（STOCK）は除外**
  - 重要度が高い順に **最大10件** を投入
- **ラベル別要約**:
  - importance による除外は行わず、株価系も含めて対象
  - 重要度は順位づけに反映（低めに抑えられる）
  - いずれも記事一覧の表示/Notion保存は従来どおり継続

### ルール記述の規約

- **TagNameは「理由文」**として書く（例: `脱炭素（水素関連）`, `設備投資・増設`, `株価・短期値動き`）
- **Weightは離散値のみ**で運用: `+5 / +3 / +1 / -2 / -5`（細かい数字は禁止）
- **調整用ルールは title マッチ推奨**（本文はノイズが多いため）
- **NegativeKeywords を活用**して誤抑制を防ぐ（例: `investment, capex, acquisition` など）

### ルール例（コピペ用）

**Theme例**
```
RuleType: importance
TagName: 脱炭素（水素関連）
Keywords: hydrogen, 脱炭素, 低炭素, green steel
MatchField: both
Weight: 3
```

```
RuleType: importance
TagName: 設備投資・増設
Keywords: investment, capex, 増設, 新工場, capacity
MatchField: both
Weight: 3
```

**Event例**
```
RuleType: importance
TagName: 大型投資発表
Keywords: investment, capex, 〇〇億, billion, 大型投資
MatchField: title
Weight: 5
```

```
RuleType: importance
TagName: 規制・政策変更
Keywords: regulation, policy, 規制, 政策, carbon tax, CBAM
MatchField: title
Weight: 3
```

```
RuleType: importance
TagName: 業績・決算
Keywords: earnings, results, 決算, 業績, guidance
MatchField: title
Weight: 3
```

**調整例**
```
RuleType: importance
TagName: 株価・短期値動き
Keywords: stock, share, 株価, target price, 52-week
MatchField: title
Weight: -5
```

```
RuleType: importance
TagName: 市況一般
Keywords: market sentiment, 市況, 需給, general market
MatchField: title
Weight: -3
```

### デバッグ方法

- **ImportanceReasons の見方**: `TagName(+Weight)` の形式で理由が残ります（例: `設備投資・増設(+3); 株価・短期値動き(-5)`）。
- **なぜ要約から消えたか**:
  - 全体ニュース要約は importance が **0以下** の記事は対象外です。
  - 株価系（STOCK）は全体ニュース要約から除外されます。
- **調整用ルールが効きすぎる場合の見直し**:
  - `MatchField` が `both` になっていないか（title推奨）
  - `Keywords` が広すぎないか
  - `NegativeKeywords` を追加できないか

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
