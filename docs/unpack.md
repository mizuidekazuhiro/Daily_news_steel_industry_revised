# Codespaceでの展開手順（.git なし zip）

## 前提
- ここで配布しているzipは `.git` を含みません。
- 展開後は、そのまま新しいGitHubリポジトリに配置できる構成です。

## 手順
1. Codespaceでターミナルを開く
2. zipファイルを作業ディレクトリに置く（例: `output_no_git.zip`）
3. 展開先のディレクトリを作成する
4. zipを展開する
5. 展開結果を確認する

## 具体例
```bash
# 1) 展開先フォルダを作成
mkdir -p my-project

# 2) zipを展開
unzip output_no_git.zip -d my-project

# 3) 展開結果を確認
ls -la my-project
