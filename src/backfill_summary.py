import os, duckdb, datetime

def backfill_summary_month():
    target_month = os.environ.get("TARGET_MONTH", "").strip()
    if not target_month or len(target_month) != 6:
        print("❌ TARGET_MONTH (YYYYMM) を正しく指定してください。")
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
        output_key = f"Sum_data/daily_summary/{year}/{month}/summary_{d_str}.parquet"
        output_path = f"s3://{BUCKET}/{output_key}"

        query = f"""
        COPY (
            WITH RawQuotes AS (
                SELECT CAST(Date AS DATE) as Date, Code, C, Vo, H, L
                FROM read_parquet('s3://{BUCKET}/raw/daily_quotes/**/*.parquet')
                WHERE CAST(Date AS DATE) <= '{fmt_date}'
                  AND CAST(Date AS DATE) >= CAST('{fmt_date}' AS DATE) - INTERVAL 60 DAY
            ),
            TechnicalStats AS (
