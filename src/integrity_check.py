import os, time, datetime, requests, boto3
import pandas as pd
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
    "equities_master": "/equities/master", "daily_quotes": "/equities/bars/daily",
    "fins_summary": "/fins/summary", "earnings_calendar": "/equities/earnings-calendar",
    "indices_topix": "/indices/bars/daily/topix", "margin_interest": "/markets/margin-interest",
    "margin_alert": "/markets/margin-alert", "short_ratio": "/markets/short-ratio",
    "short_sale_report": "/markets/short-sale-report", "investor_types": "/equities/investor-types",
    "options_225": "/derivatives/bars/daily/options/225"
}

s3_client = boto3.client('s3', endpoint_url=R2_ENDPOINT_URL, aws_access_key_id=R2_ACCESS_KEY_ID, aws_secret_access_key=R2_SECRET_ACCESS_KEY)

def check_exists(key):
    try: s3_client.head_object(Bucket=R2_BUCKET_NAME, Key=key); return True
    except ClientError: return False

def main():
    jst = datetime.timezone(datetime.timedelta(hours=9))
    today = datetime.datetime.now(jst).date()
    print("--- Integrity Check Starting ---")
    for i in range(10, 0, -1):
        date_obj = today - datetime.timedelta(days=i)
        if date_obj.weekday() >= 5: continue
        date = date_obj.strftime("%Y%m%d")
        for name, endpoint in DATASETS.items():
            key = f"raw/{name}/{date[:4]}/{date[4:6]}/{name}_{date}.parquet"
            if not check_exists(key):
                print(f"Recovering {name} for {date}")
                headers = {"x-api-key": API_KEY}
                res = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params={"date": date})
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    if data:
                        df = pd.DataFrame(data)
                        buf = BytesIO()
                        df.to_parquet(buf, index=False)
                        buf.seek(0)
                        s3_client.upload_fileobj(buf, R2_BUCKET_NAME, key)

if __name__ == "__main__": main()
