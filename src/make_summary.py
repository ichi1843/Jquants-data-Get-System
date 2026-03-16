import os, duckdb, datetime

def cook_daily_summary():
    jst = datetime.timezone(datetime.timedelta(hours=9))
    target_date = os.environ.get("TARGET_DATE_INPUT")
    if not target_date:
        target_date = datetime.datetime.now(jst).strftime('%Y%m%d')

    print(f"🍳 本日の調理開始: {target_date}")

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

    output_key = f"Sum_data/daily_summary/{target_date[:4]}/{target_date[4:6]}/summary_{target_date}.parquet"

    query = f"""
    COPY (
        WITH RawQuotes AS (
            SELECT CAST(Date AS DATE) as Date, Code, C, Vo, H, L
            FROM read_parquet('s3://{BUCKET}/raw/daily_quotes/**/*.parquet')
            WHERE CAST(Date AS DATE) >= (CURRENT_DATE - INTERVAL 60 DAY)
        ),
        TechnicalStats AS (
            SELECT
                Date, Code, C, Vo,
                AVG(C)        OVER (PARTITION BY Code ORDER BY Date ROWS 24 PRECEDING) as MA25,
                STDDEV_POP(C) OVER (PARTITION BY Code ORDER BY Date ROWS 24 PRECEDING) as STD25,
                AVG(Vo)       OVER (PARTITION BY Code ORDER BY Date ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING) as AvgVo5,
                MAX(C)        OVER (PARTITION BY Code ORDER BY Date ROWS 60 PRECEDING) as HighMax
            FROM RawQuotes
        ),
        LatestFins AS (
            -- 直近決算の財務データを1件だけ取得
            SELECT Code, ShOutFY, TrShFY, Sales, FSales, OP, FEPS, BPS, FDivAnn
            FROM read_parquet('s3://{BUCKET}/raw/fins_summary/**/*.parquet')
            QUALIFY ROW_NUMBER() OVER (PARTITION BY Code ORDER BY DiscDate DESC) = 1
        ),
        LatestMaster AS (
            SELECT Code, CoName, S33Nm, MktNm
            FROM read_parquet('s3://{BUCKET}/raw/equities_master/**/*.parquet')
            QUALIFY ROW_NUMBER() OVER (PARTITION BY Code ORDER BY Date DESC) = 1
        )
        SELECT
            t.Date,
            t.Code,
            m.CoName,
            m.S33Nm,
            m.MktNm,
            t.C                                                                 as Price,

            -- 最低購入金額: 売買単位がAPIで取得できないため100株固定
            (t.C * 100)                                                         as MinPurchasePrice,

            -- 時価総額: 発行済株式数 - 自己株式数（流通株式数ベース）
            ROUND(
                t.C * (
                    CAST(NULLIF(f.ShOutFY, '') AS DOUBLE)
                    - COALESCE(CAST(NULLIF(f.TrShFY, '') AS DOUBLE), 0)
                ),
            0)                                                                  as MarketCap,

            ROUND((t.C - t.MA25) / NULLIF(t.MA25, 0) * 100, 2)                as MA25Diff,
            ROUND((t.C - t.MA25) / NULLIF(t.STD25, 0), 2)                     as BB_SigmaScore,
            ROUND((t.STD25 * 4) / NULLIF(t.MA25, 0), 3)                       as BB_Width,
            ROUND(t.Vo / NULLIF(t.AvgVo5, 0), 2)                              as VolumeRatio,
            ROUND(t.C / NULLIF(t.HighMax, 0), 3)                              as HighNearRatio,
            ROUND(t.C / NULLIF(CAST(NULLIF(f.FEPS,   '') AS DOUBLE), 0), 2)   as PER,
            ROUND(t.C / NULLIF(CAST(NULLIF(f.BPS,    '') AS DOUBLE), 0), 2)   as PBR,
            ROUND(((CAST(NULLIF(f.FSales, '') AS DOUBLE)
                   / NULLIF(CAST(NULLIF(f.Sales, '') AS DOUBLE), 0)) - 1) * 100, 2) as SalesGrowth,
            ROUND((CAST(NULLIF(f.OP,     '') AS DOUBLE)
                   / NULLIF(CAST(NULLIF(f.Sales, '') AS DOUBLE), 0)) * 100, 2) as OPMargin,
            ROUND(CAST(NULLIF(f.FDivAnn, '') AS DOUBLE)
                   / NULLIF(t.C, 0) * 100, 2)                                  as Yield
        FROM TechnicalStats t
        LEFT JOIN LatestMaster m ON t.Code = m.Code
        LEFT JOIN LatestFins   f ON t.Code = f.Code
        WHERE REPLACE(CAST(t.Date AS STRING), '-', '') = '{target_date}'
          AND t.C IS NOT NULL
    ) TO 's3://{BUCKET}/{output_key}' (FORMAT PARQUET);
    """

    try:
        con.execute(query)
        print(f"✨ 本日のSummary保存完了: {output_key}")
    except Exception as e:
        print(f"❌ 調理エラー: {e}")

if __name__ == "__main__":
    cook_daily_summary()
