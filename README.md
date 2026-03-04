# 📦 J-Quants Data Collection System

J-Quants API v2 から日本株市場データを自動収集し、Cloudflare R2 ストレージに Parquet 形式で保存するためのデータレイク構築システムです。

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Storage](https://img.shields.io/badge/Storage-Cloudflare%20R2-orange)
![Platform](https://img.shields.io/badge/Platform-GitHub%20Actions-black)
![Format](https://img.shields.io/badge/Format-Parquet-green)

GitHub Actions を利用して、日次データの取得、過去データのバックフィル、欠損データの整合性チェックを完全に自動化しています。

## 🚀 特徴

- **完全自動化**: GitHub Actions により、毎日決まった時間（JST 19:30）にデータを自動収集。
- **低コスト・高効率**: データは軽量な **Parquet形式** で圧縮。Cloudflare R2（S3互換）に保存することで、ストレージ費用を抑えつつ高速なデータアクセスを実現。
- **堅牢な運用**: 
  - **バックフィル**: 過去の特定年月データを一括取得可能。
  - **整合性チェック**: 毎週日曜日に過去10日間のデータをスキャンし、欠損があれば自動リカバリ。

## 📊 収集データ (Datasets)

J-Quants API v2 の以下の主要エンドポイントを網羅しています。

| カテゴリ | データセット名 | 内容 |
| :--- | :--- | :--- |
| **基本情報** | `equities_master` | 銘柄マスター |
| **株価** | `daily_quotes` | 株価四本値 (日足) |
| **財務/決算** | `fins_summary`, `earnings_calendar` | 財務情報、決算発表予定 |
| **指数** | `indices_topix` | TOPIX (日足) |
| **信用/空売り** | `margin_*`, `short_*` | 信用取引残高、空売り比率 |
| **その他** | `investor_types`, `options_225` | 投資部門別売買、日経225オプション |

## 🛠️ セットアップ

### 1. 前提条件
- **J-Quants API アカウント**: 有効なリフレッシュトークンが必要です。
- **Cloudflare R2**: バケットを作成し、API クレデンシャル（S3互換）を発行してください。

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

### 1. 日次収集 (`daily_stock_data.yml`)
- **自動実行**: 毎日 **19:30 JST** に実行。
- **手動実行**: `Actions` タブより、日付 (`YYYYMMDD`) を指定して再取得が可能。

### 2. バックフィル実行 (`backfill_data.yml`)
- **用途**: 過去データの蓄積。
- **方法**: `Actions` タブから対象月 (`YYYYMM`) を入力して実行。

### 3. 整合性チェック (`integrity_check.yml`)
- **自動実行**: 毎週 **日曜日 00:00 JST**。
- **機能**: 直近10日間の欠損を検知し、自動で再取得を試みます。

## 📂 保存ディレクトリ構成

Cloudflare R2 内には、DuckDBなどで扱いやすいパーティション構造で保存されます。

```text
raw/
 ├── daily_quotes/
 │    └── 2025/
 │         └── 02/
 │              └── daily_quotes_20250211.parquet
 ├── fins_summary/
 │    └── ...
 └── ...
