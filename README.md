# J-Quants Data Collection System

J-Quants API v2 から日本株市場データを自動収集し、Cloudflare R2 ストレージに Parquet 形式で保存するためのシステムです。
GitHub Actions を利用して、日次データの取得、過去データのバックフィル、欠損データの整合性チェックを自動化しています。

## 🚀 特徴

*   **完全自動化**: GitHub Actions により、毎日決まった時間（JST 19:30）にデータを収集。
*   **低コスト・高効率**: データは軽量な Parquet 形式で圧縮され、Cloudflare R2（S3互換）に保存されます。
*   **バックフィル機能**: 指定した年月のデータをまとめて取得可能。
*   **整合性チェック**: 週間スケジュールで過去データの欠損をチェックし、自動リカバリを試みます。

## 📊 収集データ (Datasets)

以下のエンドポイントに対応しています。

*   `equities_master`: 銘柄マスター
*   `daily_quotes`: 株価四本値 (日足)
*   `fins_summary`: 財務情報
*   `earnings_calendar`: 決算発表予定
*   `indices_topix`: TOPIX (日足)
*   `margin_interest`: 信用取引残高
*   `margin_alert`: 信用取引残高 (日証金)
*   `short_ratio`: 空売り比率
*   `short_sale_report`: 空売り集計
*   `investor_types`: 投資部門別売買状況
*   `options_225`: 日経225オプション (日足)

## 🛠️ セットアップ

### 1. 前提条件
*   **J-Quants API アカウント**: 有効なリフレッシュトークンが必要です。
*   **Cloudflare R2**: バケットを作成し、API クレデンシャルを発行してください。

### 2. GitHub Secrets の設定
リポジトリの `Settings` > `Secrets and variables` > `Actions` に以下のシークレットを設定してください。

| Secret Name | 説明 |
| :--- | :--- |
| `JQUANTS_API_KEY` | J-Quants API のリフレッシュトークン |
| `R2_ACCOUNT_ID` | Cloudflare のアカウント ID |
| `R2_ACCESS_KEY_ID` | R2 の Access Key ID |
| `R2_SECRET_ACCESS_KEY` | R2 の Secret Access Key |
| `R2_BUCKET_NAME` | 保存先のバケット名 |

## 🔄 ワークフローの使い方

### 1. Daily J-Quants Data Collection (`daily_stock_data.yml`)
*   **自動実行**: 毎日 **19:30 JST** (10:30 UTC) に実行されます。当日（土日の場合は直前の金曜日）のデータを取得します。
*   **手動実行**: `Workflow dispatch` から日付 (`YYYYMMDD`) を指定して特定日のデータを再取得できます。

### 2. Monthly Backfill Collection (`backfill_data.yml`)
*   **手動実行**: `Actions` タブからこのワークフローを選択し、対象月 (`YYYYMM`) を入力して実行します。
*   **例**: `202411` と入力すると、2024年11月の全営業日のデータを取得します。

### 3. Weekly Data Integrity Check (`integrity_check.yml`)
*   **自動実行**: 毎週 **日曜日 00:00 JST** (土曜 15:00 UTC) に実行されます。
*   **機能**: 直近10日間のデータをスキャンし、保存されていないデータがあれば自動的に再取得を試みます。

## 📂 保存ディレクトリ構成

R2 バケット内には以下の構造で保存されます。

```text
raw/
 ├── daily_quotes/
 │    └── 2025/
 │         └── 02/
 │              └── daily_quotes_20250211.parquet
 ├── fins_summary/
 │    └── ...
 └── ...
