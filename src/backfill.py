import os
import time
import datetime
import calendar
import requests
import pandas as pd
import boto3
from io import BytesIO
from botocore.exceptions import ClientError

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

s3_client = boto3.client('s3', endpoint_url=R2_ENDPOINT_URL, aws_access_key_id=R2_ACCESS_KEY_ID, aws_secret_access_key=R2_SECRET_ACCESS_KEY)

def check_exists(file_key):
    try:
        s3_client.head_object(Bucket=R2_BUCKET_NAME, Key=file_key)
        return True
    except ClientError: return False

def main():
    target_month_str = os.environ.get("TARGET_MONTH", "").strip()
    year, month = int(target_month_str[:4]), int(target_month_str[4:6])
    _, last_day = calendar.monthrange(year, month)

    for day in range(1, last_day + 1):
        target_date = f"{year}{month:02d}{day:02d}"
        for name, endpoint in DATASETS.items():
            file_key = f"raw/{name}/{target_date[:4]}/{target_date[4:6]}/{name}_{target_date}.parquet"
            if check_exists(file_key): continue
            
            # 取得ロジック（簡略化）
            headers = {"x-api-key": API_KEY}
            params = {"date": target_date} if endpoint != "/equities/master" else {}
            res = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params=params)
            if res.status_code == 200:
                data = res.json().get("data", [])
                if data:
                    # 保存ロジックはmain.pyと同一にする必要があるため、実際には共通化するかコピーする
                    # ここでは概念のみ。実際には整合性のためmain.pyのsave_to_r2と同じ処理を入れる
                    print(f"Fetched and saving: {file_key}")
