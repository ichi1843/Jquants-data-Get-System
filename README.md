📦 J-Quants Data Collection System
J-Quants API v2 から日本株市場データを自動収集し、Cloudflare R2 ストレージに Parquet 形式で保存するためのデータレイク構築システムです。
![Python](https://img.shields.io/badge/Python-3.10-blue)
![Storage](https://img.shields.io/badge/Storage-Cloudflare%20R2-orange)
![Platform](https://img.shields.io/badge/Platform-GitHub%20Actions-black)
![Format](https://img.shields.io/badge/Format-Parquet-green)
![Plan](https://img.shields.io/badge/J--Quants-Standard-green)
GitHub Actions を利用して、日次データの取得、過去データのバックフィル、欠損データの整合性チェックを完全に自動化しています。
---
🚀 特徴
完全自動化: GitHub Actions により、毎日 JST 19:30 にデータを自動収集。
低コスト・高効率: データは軽量な Parquet形式 で圧縮。Cloudflare R2（S3互換）に保存することで、ストレージ費用を抑えつつ高速なデータアクセスを実現。
堅牢な運用:
バックフィル: 過去の特定年月データを一括取得可能。
整合性チェック: 毎週日曜日に過去10日間のデータをスキャンし、欠損があれば自動リカバリ。
---
📊 収集データ一覧
J-Quants API v2 エンドポイントと R2 保存先フォルダの対応表です。
カテゴリ	J-Quants エンドポイント	R2 フォルダ名	内容	取得粒度	Standardプラン
基本情報	`/equities/master`	`raw/equities_master/`	銘柄マスター	日次	10年前まで
株価	`/equities/bars/daily`	`raw/daily_quotes/`	株価四本値（日足）	日次	10年前まで
財務/決算	`/fins/summary`	`raw/fins_summary/`	財務情報サマリー	日次	10年前まで
財務/決算	`/equities/earnings-calendar`	`raw/earnings_calendar/`	決算発表予定日	日次	全プラン
指数	`/indices/bars/daily/topix`	`raw/indices_topix/`	TOPIX（日足）	日次	10年前まで
指数	`/indices/bars/daily`	`raw/indices_daily/`	業種別33指数・TOPIX-17等	日次	10年前まで
信用取引	`/markets/margin-interest`	`raw/margin_interest/`	信用取引週末残高	週次	10年前まで
信用取引	`/markets/margin-alert`	`raw/margin_alert/`	日々公表信用取引残高	日次	10年前まで
空売り	`/markets/short-ratio`	`raw/short_ratio/`	業種別空売り比率	日次	10年前まで
空売り	`/markets/short-sale-report`	`raw/short_sale_report/`	空売り残高報告	日次	10年前まで
投資家動向	`/equities/investor-types`	`raw/investor_types/`	投資部門別売買状況	週次	10年前まで
デリバティブ	`/derivatives/bars/daily/options/225`	`raw/options_225/`	日経225オプション四本値	日次	10年前まで
カレンダー	`/markets/calendar`	`raw/market_calendar/`	取引カレンダー（営業日判定）	月次※	10年前まで
> ※ `market_calendar` のみ月単位で1ファイルに保存されます（他のデータは日次）。
---
🛠️ セットアップ
1. 前提条件
J-Quants API アカウント: Standardプラン以上が必要です。
Cloudflare R2: バケットを作成し、API クレデンシャル（S3互換）を発行してください。
2. GitHub Secrets の設定
リポジトリの `Settings` > `Secrets and variables` > `Actions` に以下のシークレットを設定してください。
Secret Name	説明
`JQUANTS_API_KEY`	J-Quants API キー
`R2_ACCOUNT_ID`	Cloudflare のアカウント ID
`R2_ACCESS_KEY_ID`	R2 の Access Key ID
`R2_SECRET_ACCESS_KEY`	R2 の Secret Access Key
`R2_BUCKET_NAME`	保存先のバケット名
---
🔄 ワークフローの使い方
1. 日次収集 (`daily_stock_data.yml`)
自動実行: 毎日 19:30 JST に自動実行。
手動実行: `Actions` タブより、日付（`YYYYMMDD`）を指定して特定日の再取得が可能。
2. バックフィル (`backfill_data.yml`)
用途: 過去データの遡及取得。
方法: `Actions` タブから対象年月（`YYYYMM`）を入力して実行。
既存ファイルはスキップ: 取得済みのファイルは上書きされません。
3. 整合性チェック (`integrity_check.yml`)
自動実行: 毎週 日曜日 00:00 JST。
機能: 直近10日間の欠損を検知し、自動で再取得を試みます。
手動実行: `lookback_days` を指定して任意の期間をチェック可能。
---
📂 R2 保存ディレクトリ構成
```text
s3://バケット名/
└── raw/
     ├── equities_master/       # 銘柄マスター
     │    └── 2025/03/
     │         └── equities_master_20250301.parquet
     ├── daily_quotes/          # 株価四本値（日足）
     │    └── 2025/03/
     │         └── daily_quotes_20250301.parquet
     ├── fins_summary/          # 財務情報サマリー
     ├── earnings_calendar/     # 決算発表予定日
     ├── indices_topix/         # TOPIX
     ├── indices_daily/         # 業種別33指数・TOPIX-17等
     ├── margin_interest/       # 信用取引週末残高
     ├── margin_alert/          # 日々公表信用取引残高
     ├── short_ratio/           # 業種別空売り比率
     ├── short_sale_report/     # 空売り残高報告
     ├── investor_types/        # 投資部門別売買状況
     ├── options_225/           # 日経225オプション四本値
     └── market_calendar/       # 取引カレンダー（月単位1ファイル）
          └── 2025/03/
               └── market_calendar_20250301.parquet
```
---
📝 備考
Standardプランのレートリミットは 120リクエスト/分 です。
`indices_daily` はデータ量が多いため、バックフィル時は他より長めの待機時間（2秒）を設定しています。
`market_calendar` は月単位で1ファイルに保存されます（月初日付のファイル名）。
Standardプランの取得可能期間は 過去10年分 です（データ格納開始は2008年）。
