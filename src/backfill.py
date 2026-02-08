import os
import time
import datetime
import calendar
import requests
import pandas as pd
import boto3
from io import BytesIO
from botocore.exceptions import ClientError

# --- 設定 ---
API_KEY = os.environ["JQUANTS_API_KEY"]
R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET_NAME = os.environ["R2_BUCKET_NAME"]
R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
BASE_URL = "https://api.jquants.com/v2"

# 取得対象（メインのmain.pyと完全に一致させています）
ALL_DATASETS = {
    "equities_master": "/equities/master",
    "daily_quotes": "/equities/bars/daily",
    "fins_summary": "/fins/summary",
    "earnings_calendar": "/equities/earnings-calendar",
    "indices_topix": "/indices/bars/daily/topix",
    "margin_interest": "/markets/margin-interest",
    "margin_alert": "/markets/margin-alert",
    "short_ratio": "/markets/short-ratio",
    "short_sale_report": "/markets/short-sale-report",
    "investor_types": "/equities/investor-types",
    "options_225": "/derivatives/bars/daily/options/225"
}

s3_client = boto3.client(
    's3',
    endpoint_url=R2_ENDPOINT_URL,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY
)

def check_exists(file_key):
    try:
        s3_client.head_object(Bucket=R2_BUCKET_NAME, Key=file_key)
        return True
    except ClientError:
        return False

def get_jquants_data(endpoint, target_date):
    url = f"{BASE_URL}{endpoint}"
    headers = {"x-api-key": API_KEY}
    params = {"date": target_date} if endpoint != "/equities/master" else {}
    
    all_data = []
    pagination_key = None
    while True:
        curr_params = params.copy()
        if pagination_key: curr_params["pagination_key"] = pagination_key
        try:
            response = requests.get(url, headers=headers, params=curr_params, timeout=30)
            if response.status_code == 429:
                time.sleep(10)
                continue
            response.raise_for_status()
            result = response.json()
            all_data.extend(result.get("data", []))
            pagination_key = result.get("pagination_key")
            if not pagination_key: break
            time.sleep(1)
        except Exception as e:
            print(f"Error fetching {endpoint}: {e}")
            return None
    return all_data

def save_to_r2(data, dataset_name, target_date, file_key):
    df = pd.DataFrame(data)
    if df.empty: return

    numeric_cols = [
        'O', 'H', 'L', 'C', 'Vo', 'Va', 'AdjO', 'AdjH', 'AdjL', 'AdjC', 'AdjVo', 'AdjFactor',
        'NetSales', 'OperatingProfit', 'OrdinaryProfit', 'NetIncome', 'EarningsPerShare',
        'ShortVolume', 'LongVolume', 'ShortOut', 'LongOut', 'ShrtOutRatio', 'ShortRatio', 
        'Position', 'Ratio', 'ForeignBuying', 'ForeignSelling', 'IndividualBuying', 'IndividualSelling',
        'StrikePrice', 'ImpliedVolatility', 'OpenInterest'
    ]
    for col in df.columns:
        if col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        elif df[col].dtype == 'object':
            df[col] = df[col].astype(str).replace('None', '')

    buffer = BytesIO()
    df.to_parquet(buffer, index=False, compression='snappy', engine='pyarrow')
    buffer.seek(0)
    s3_client.upload_fileobj(buffer, R2_BUCKET_NAME, file_key)
    print(f"  -> Uploaded: {file_key}")

def main():
    target_month_str = os.environ.get("TARGET_MONTH", "").strip()
    dataset_choice = os.environ.get("DATASET_CHOICE", "all").strip()
    
    if not target_month_str or len(target_month_str) != 6:
        print("Invalid TARGET_MONTH. Use YYYYMM format.")
        return

    year, month = int(target_month_str[:4]), int(target_month_str[4:6])
    _, last_day = calendar.monthrange(year, month)

    # フィルタリング
    if dataset_choice == "all":
        target_datasets = ALL_DATASETS
    else:
        if dataset_choice in ALL_DATASETS:
            target_datasets = {dataset_choice: ALL_DATASETS[dataset_choice]}
        else:
            print(f"Unknown dataset: {dataset_choice}")
            return

    print(f"Starting Backfill: {target_month_str} | Mode: {dataset_choice}")

    for day in range(1, last_day + 1):
        target_date = f"{year}{month:02d}{day:02d}"
        print(f"\n--- Day: {target_date} ---")
        
        for name, endpoint in target_datasets.items():
            file_key = f"raw/{name}/{year}/{month:02d}/{name}_{target_date}.parquet"
            
            # 存在チェック
            if check_exists(file_key):
                print(f"  [{name}] Skip: Already exists.")
                continue

            # 取得
            data = get_jquants_data(endpoint, target_date)
            if data:
                save_to_r2(data, name, target_date, file_key)
                time.sleep(1)
            else:
                print(f"  [{name}] No data (Holiday or N/A)")

    print("\n--- Backfill Process Completed ---")

if __name__ == "__main__":
    main()
