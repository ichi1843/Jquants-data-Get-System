import os
import time
import datetime
import requests
import pandas as pd
import boto3
from io import BytesIO

# --- 設定 ---
API_KEY = os.environ["JQUANTS_API_KEY"]
R2_ACCOUNT_ID = os.environ["R2_ACCOUNT_ID"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET_NAME = os.environ["R2_BUCKET_NAME"]
R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
BASE_URL = "https://api.jquants.com/v2"

DATASETS = {
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
            response = requests.get(url, headers=headers, params=curr_params)
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

def save_to_r2(df, dataset_name, target_date):
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
    s3_client = boto3.client('s3', endpoint_url=R2_ENDPOINT_URL, aws_access_key_id=R2_ACCESS_KEY_ID, aws_secret_access_key=R2_SECRET_ACCESS_KEY)
    year, month = target_date[:4], target_date[4:6]
    file_key = f"raw/{dataset_name}/{year}/{month}/{dataset_name}_{target_date}.parquet"
    s3_client.upload_fileobj(buffer, R2_BUCKET_NAME, file_key)
    print(f"Successfully uploaded: {file_key}")

def main():
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now_jst = datetime.datetime.now(jst)
    manual_date = os.environ.get("TARGET_DATE_INPUT", "").strip()
    if manual_date:
        target_date = manual_date
    else:
        weekday = now_jst.weekday()
        if weekday == 5: target_date_obj = now_jst - datetime.timedelta(days=1)
        elif weekday == 6: target_date_obj = now_jst - datetime.timedelta(days=2)
        else: target_date_obj = now_jst
        target_date = target_date_obj.strftime('%Y%m%d')

    for folder_name, endpoint in DATASETS.items():
        data = get_jquants_data(endpoint, target_date)
        if data:
            save_to_r2(pd.DataFrame(data), folder_name, target_date)

if __name__ == "__main__":
    main()
