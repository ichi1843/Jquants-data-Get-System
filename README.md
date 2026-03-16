# 📦 J-Quants Data Collection System

J-Quants API v2 から日本株市場データを自動収集し、Cloudflare R2 ストレージに Parquet 形式で保存するためのデータレイク構築システムです。

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Storage](https://img.shields.io/badge/Storage-Cloudflare%20R2-orange)
![Platform](https://img.shields.io/badge/Platform-GitHub%20Actions-black)
![Format](https://img.shields.io/badge/Format-Parquet-green)

GitHub Actions を利用して、日次データの取得・サマリー生成、過去データのバックフィル、欠損データの整合性チェックを完全に自動化しています。

---

## 🚀 特徴

- **完全自動化**: GitHub Actions により、毎日 JST 19:30 にデータ取得とサマリー生成を自動実行。
- **低コスト・高効率**: データは軽量な **Parquet形式** で圧縮。Cloudflare R2（S3互換）に保存することで、ストレージ費用を抑えつつ高速なデータアクセスを実現。
- **堅牢な運用**:
  - **バックフィル**: 過去の特定年月データを一括取得可能。
  - **整合性チェック**: 毎週日曜日に過去10日間のデータをスキャンし、欠損があれば自動リカバリ。

---

## 📊 収集データ (Datasets)

J-Quants API v2 Standard プランの全対応エンドポイントを網羅しています。

| カテゴリ | データセット名 | エンドポイント | 内容 |
| :--- | :--- | :--- | :--- |
| **基本情報** | `equities_master` | `/equities/master` | 銘柄マスター |
| **株価** | `daily_quotes` | `/equities/bars/daily` | 株価四本値（日足） |
| **財務/決算** | `fins_summary` | `/fins/summary` | 財務情報サマリー |
| **財務/決算** | `earnings_calendar` | `/equities/earnings-calendar` | 決算発表予定日 |
| **指数** | `indices_topix` | `/indices/bars/daily/topix` | TOPIX（日足） |
| **指数** | `indices_daily` | `/indices/bars/daily` | 業種別33指数・TOPIX-17等 |
| **信用取引** | `margin_interest` | `/markets/margin-interest` | 信用取引週末残高 |
| **信用取引** | `margin_alert` | `/markets/margin-alert` | 日々公表信用取引残高 |
| **空売り** | `short_ratio` | `/markets/short-ratio` | 業種別空売り比率 |
| **空売り** | `short_sale_report` | `/markets/short-sale-report` | 空売り残高報告 |
| **投資家動向** | `investor_types` | `/equities/investor-types` | 投資部門別売買状況 |
| **デリバティブ** | `options_225` | `/derivatives/bars/daily/options/225` | 日経225オプション四本値 |
| **カレンダー** | `market_calendar` | `/markets/calendar` | 取引カレンダー（営業日判定） |

---

## 📈 サマリーデータ (Sum_data)

収集した raw データを DuckDB で集計・加工したサマリーを `Sum_data/daily_summary/` に保存します。

| カラム名 | 内容 |
| :--- | :--- |
| `Price` | 終値 |
| `MinPurchasePrice` | 最低購入金額（100株固定） |
| `MarketCap` | 時価総額（発行済株式数 - 自己株式数 × 株価） |
| `MA25Diff` | 25日移動平均乖離率 |
| `BB_SigmaScore` | ボリンジャーバンド σスコア |
| `BB_Width` | ボリンジャーバンド幅 |
| `VolumeRatio` | 出来高比率（5日平均比） |
| `HighNearRatio` | 60日高値近接率 |
| `PER` | 株価収益率 |
| `PBR` | 株価純資産倍率 |
| `SalesGrowth` | 売上高成長率（予想） |
| `OPMargin` | 営業利益率 |
| `Yield` | 配当利回り |

---

## 🛠️ セットアップ

### 1. 前提条件

- **J-Quants API アカウント**: Standardプラン以上が必要です。
- **Cloudflare R2**: バケットを作成し、API クレデンシャル（S3互換）を発行してください。

### 2. GitHub Secrets の設定

リポジトリの `Settings` > `Secrets and variables` > `Actions` に以下のシークレットを設定してください。

| Secret Name | 説明 |
| :--- | :--- |
| `JQUANTS_API_KEY` | J-Quants API キー |
| `R2_ACCOUNT_ID` | Cloudflare のアカウント ID |
| `R2_ACCESS_KEY_ID` | R2 の Access Key ID |
| `R2_SECRET_ACCESS_KEY` | R2 の Secret Access Key |
| `R2_BUCKET_NAME` | 保存先のバケット名 |

---

## 🔄 ワークフローの使い方

### 1. 日次収集 (`daily_stock_data.yml`)

- **自動実行**: 毎日 **19:30 JST** に自動実行。
- **処理内容**: Step1でデータ取得（`main.py`）、Step2でサマリー生成（`make_summary.py`）を順次実行。
- **手動実行**: `Actions` タブより、日付（`YYYYMMDD`）を指定して特定日の再取得が可能。

### 2. データバックフィル (`backfill_data.yml`)

- **用途**: 過去データの遡及取得。
- **方法**: `Actions` タブから対象年月（`YYYYMM`）を入力して実行。
- **既存ファイルはスキップ**: 取得済みのファイルは上書きされません。

### 3. サマリーバックフィル (`backfill_summary.yml`)

- **用途**: 過去サマリーの遡及生成。
- **方法**: `Actions` タブから対象年月（`YYYYMM`）を入力して実行。
- **注意**: データバックフィル完了後に実行してください。

### 4. 整合性チェック (`integrity_check.yml`)

- **自動実行**: 毎週 **日曜日 00:00 JST**。
- **機能**: 直近10日間の欠損を検知し、自動で再取得を試みます。
- **手動実行**: `lookback_days` を指定して任意の期間をチェック可能。

---

## 📂 保存ディレクトリ構成

```text
raw/
 ├── daily_quotes/          # 株価四本値（日足）
 │    └── 2025/03/
 │         └── daily_quotes_20250301.parquet
 ├── equities_master/       # 銘柄マスター
 ├── fins_summary/          # 財務情報
 ├── earnings_calendar/     # 決算発表予定日
 ├── indices_topix/         # TOPIX
 ├── indices_daily/         # 業種別33指数・TOPIX-17等
 ├── margin_interest/       # 信用取引週末残高
 ├── margin_alert/          # 日々公表信用取引残高
 ├── short_ratio/           # 業種別空売り比率
 ├── short_sale_report/     # 空売り残高報告
 ├── investor_types/        # 投資部門別売買状況
 ├── options_225/           # 日経225オプション四本値
 └── market_calendar/       # 取引カレンダー（月単位）
      └── 2025/03/
           └── market_calendar_20250301.parquet

Sum_data/
 └── daily_summary/         # 日次サマリー（DuckDB加工済み）
      └── 2025/03/
           └── summary_20250301.parquet
```

---

## 📝 備考

- `market_calendar` は月単位で1ファイルに保存されます（他のデータは日次）。
- 時価総額は `発行済株式数（ShOutFY）- 自己株式数（TrShFY）× 株価` で計算しています。
- 最低購入金額は売買単位がAPIで取得できないため、100株固定で計算しています。
- Standardプランのレートリミットは120リクエスト/分です。
