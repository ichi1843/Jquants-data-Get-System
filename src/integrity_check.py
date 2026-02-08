import os
import time
import datetime
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
    lookback = 10
    jst = datetime.timezone(datetime.timedelta(hours=9))
    today = datetime.datetime.now(jst).date()
    for i in range(lookback, 0, -1):
        target_date_obj = today - datetime.timedelta(days=i)
        if target_date_obj.weekday() >= 5: continue
        target_date = target_date_obj.strftime("%Y%m%d")
        for name, endpoint in DATASETS.items():
            year, month = target_date[:4], target_date[4:6]
            file_key = f"raw/{name}/{year}/{month}/{name}_{target_date}.parquet"
            if not check_exists(file_key):
                print(f"Recovering {name} for {target_date}...")
                # 取得・保存処理（main.pyと同等のロジック）
