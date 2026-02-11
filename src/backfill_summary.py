import os, duckdb, datetime

def backfill_summary_month():
    target_month = os.environ.get("TARGET_MONTH", "").strip()
    if not target_month or len(target_month) != 6:
        print("❌ TARGET_MONTH (YYYYMM) を指定してください。")
        return

    year, month = target_month[:4], target_month[4:6]
    print(f"🚀 {year}/{month} のバックフィル調理を開始します...")

    R2_ACC = os.environ["R2_ACCOUNT_ID"]
    R2_KEY = os.environ["R2_ACCESS_KEY_ID"]
    R2_SEC = os.environ["R2_SECRET_ACCESS_KEY"]
    BUCKET = os.environ["R2_BUCKET_NAME"]
    DOMAIN = f"{R2_ACC}.r2.cloudflarestorage.com"

    con = duckdb.connect(database=':memory:')
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"""
        SET s3_endpoint='{DOMAIN}';
        SET s3_access_key_id='{R2_KEY}';
        SET s3_secret_access_key='{R2_SEC}';
        SET s3_url_style='path';
        SET s3_use_ssl=true;
    """)

    quotes_glob = f"s3://{BUCKET}/raw/daily_quotes/{year}/{month}/*.parquet"
    try:
        files_df = con.sql(f"SELECT file FROM glob('{quotes_glob}')").df()
        dates = sorted(files_df['file'].str.extract(r'daily_quotes_(\d{8})')[0].unique().tolist())
    except Exception as e:
        print(f"⚠️ 指定月のデータが見つかりません: {e}")
        return

    for d_str in dates:
        print(f"  🍳 調理中: {d_str} ... ", end="", flush=True)
        fmt_date = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]}"
        
        # 出力先を Sum_data に変更
        output_key = f"Sum_data/daily_summary/{year}/{month}/summary_{d_str}.parquet"

        query = f"""
        COPY (
            WITH RawQuotes AS (
                SELECT CAST(Date AS DATE) as Date, Code, C, Vo, H, L
                FROM read_parquet('s3://{BUCKET}/raw/daily_quotes/**/*.parquet')
                WHERE CAST(Date AS DATE) <= '{fmt_date}'
                  AND CAST(Date AS DATE) >= CAST('{fmt_date}' AS DATE) - INTERVAL 60 DAY
            ),
            TechnicalStats AS (
                SELECT 
                    Date, Code, C, Vo,
                    AVG(C) OVER (PARTITION BY Code ORDER BY Date ROWS 24 PRECEDING) as MA25,
                    STDDEV_POP(C) OVER (PARTITION BY Code ORDER BY Date ROWS 24 PRECEDING) as STD25,
                    AVG(Vo) OVER (PARTITION BY Code ORDER BY Date ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING) as AvgVo5,
                    MAX(C) OVER (PARTITION BY Code ORDER BY Date ROWS 60 PRECEDING) as HighMax
                FROM RawQuotes
            ),
            LatestFins AS (
                SELECT Code, ShOutFY, Sales, FSales, OP, FEPS, BPS, FDivAnn
                FROM read_parquet('s3://{BUCKET}/raw/fins_summary/**/*.parquet')
                WHERE DiscDate <= '{fmt_date}'
                QUALIFY ROW_NUMBER() OVER (PARTITION BY Code ORDER BY DiscDate DESC) = 1
            ),
            LatestMaster AS (
                SELECT Code, CoName, S33Nm, MktNm, TU  -- TU (TradingUnit) に修正
                FROM read_parquet('s3://{BUCKET}/raw/equities_master/**/*.parquet')
                WHERE Date <= '{fmt_date}'
                QUALIFY ROW_NUMBER() OVER (PARTITION BY Code ORDER BY Date DESC) = 1
            )
            SELECT 
                t.Date, t.Code, m.CoName, m.S33Nm, m.MktNm, t.C as Price,
                (t.C * CAST(NULLIF(m.TU, '') AS INTEGER)) as MinPurchasePrice, -- TU に修正
                (t.C * CAST(NULLIF(f.ShOutFY, '') AS DOUBLE)) as MarketCap,
                ROUND((t.C - t.MA25) / NULLIF(t.MA25, 0) * 100, 2) as MA25Diff,
                ROUND((t.C - t.MA25) / NULLIF(t.STD25, 0), 2) as BB_SigmaScore,
                ROUND((t.STD25 * 4) / NULLIF(t.MA25, 0), 3) as BB_Width,
                ROUND(t.Vo / NULLIF(t.AvgVo5, 0), 2) as VolumeRatio,
                ROUND(t.C / NULLIF(t.HighMax, 0), 3) as HighNearRatio,
                ROUND(t.C / NULLIF(CAST(NULLIF(f.FEPS, '') AS DOUBLE), 0), 2) as PER,
                ROUND(t.C / NULLIF(CAST(NULLIF(f.BPS, '') AS DOUBLE), 0), 2) as PBR,
                ROUND(((CAST(NULLIF(f.FSales, '') AS DOUBLE) / NULLIF(CAST(NULLIF(f.Sales, '') AS DOUBLE), 0)) - 1) * 100, 2) as SalesGrowth,
                ROUND((CAST(NULLIF(f.OP, '') AS DOUBLE) / NULLIF(CAST(NULLIF(f.Sales, '') AS DOUBLE), 0)) * 100, 2) as OPMargin,
                ROUND(CAST(NULLIF(f.FDivAnn, '') AS DOUBLE) / NULLIF(t.C, 0) * 100, 2) as Yield
            FROM TechnicalStats t
            LEFT JOIN LatestMaster m ON t.Code = m.Code
            LEFT JOIN LatestFins f ON t.Code = f.Code
            WHERE t.Date = '{fmt_date}'
        ) TO 's3://{BUCKET}/{output_key}' (FORMAT PARQUET);
        """
        try:
            con.execute(query)
            print("✨ Done")
        except Exception as e:
            print(f"❌ Failed: {e}")

if __name__ == "__main__":
    backfill_summary_month()
