import os
import time
import datetime
import calendar
import requests
import pandas as pd
import boto3
from io import BytesIO
from botocore.exceptions import ClientError # 追加

# 設定（変更なし）
API_KEY = os.environ["JQUANTS_API_KEY"]
R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET_NAME = os.environ["R2_BUCKET_NAME"]
R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
BASE_URL = "https://api.jquants.com/v2"

# S3クライアントの初期化
s3_client = boto3.client(
    's3',
    endpoint_url=R2_ENDPOINT_URL,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY
)

def check_file_exists(file_key):
    """R2にファイルが既に存在するか確認する"""
    try:
        s3_client.head_object(Bucket=R2_BUCKET_NAME, Key=file_key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            return False
        raise e

def get_daily_quotes(target_date):
    # (変更なし)
    url = f"{BASE_URL}/equities/bars/daily"
    headers = {"x-api-key": API_KEY}
    params = {"date": target_date}
    all_data = []
    while True:
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 429:
                time.sleep(10)
                continue
            response.raise_for_status()
            result = response.json()
            all_data.extend(result.get("data", []))
            pagination_key = result.get("pagination_key")
            if pagination_key:
                params["pagination_key"] = pagination_key
                time.sleep(1)
            else:
                break
        except Exception:
            return None
    return all_data

def save_to_r2(df, target_date, file_key):
    # (引数にfile_keyを追加して効率化)
    numeric_cols = ['O', 'H', 'L', 'C', 'Vo', 'Va', 'AdjO', 'AdjH', 'AdjL', 'AdjC', 'AdjVo', 'AdjFactor']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    buffer = BytesIO()
    df.to_parquet(buffer, index=False, compression='snappy')
    buffer.seek(0)

    s3_client.upload_fileobj(buffer, R2_BUCKET_NAME, file_key)
    print(f"Successfully uploaded: {file_key}")

def main():
    target_month_str = os.environ.get("TARGET_MONTH", "").strip()
    if not target_month_str or len(target_month_str) != 6:
        print("Invalid TARGET_MONTH.")
        return

    year, month = int(target_month_str[:4]), int(target_month_str[4:6])
    _, last_day = calendar.monthrange(year, month)

    print(f"--- Starting Backfill for {target_month_str} ---")

    for day in range(1, last_day + 1):
        target_date = f"{year}{month:02d}{day:02d}"
        file_key = f"raw/daily_quotes/{year}/{month:02d}/daily_quotes_{target_date}.parquet"

        # 【ここが進化ポイント】存在チェック
        if check_file_exists(file_key):
            print(f"Skipping {target_date}: Already exists in R2.")
            continue # すでにある日は何もしないで次へ

        print(f"Processing: {target_date}...")
        data = get_daily_quotes(target_date)
        
        if data:
            df = pd.DataFrame(data)
            save_to_r2(df, target_date, file_key)
            time.sleep(1) # 負荷軽減
        else:
            print(f"No data for {target_date}. (Market holiday?)")

    print(f"--- Completed! ---")

if __name__ == "__main__":
    main()
