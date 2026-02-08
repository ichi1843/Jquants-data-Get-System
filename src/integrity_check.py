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
    try:
        s3_client.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        return True
    except ClientError:
        return False

def main():
    jst = datetime.timezone(datetime.timedelta(hours=9))
    today = datetime.datetime.now(jst).date()
    lookback = int(os.environ.get("LOOKBACK_DAYS", 10))
    
    print(f"--- Integrity Check Starting (Lookback: {lookback} days) ---")
    for i in range(lookback, 0, -1):
        date_obj = today - datetime.timedelta(days=i)
        if date_obj.weekday() >= 5: continue # 土日はスキップ
        
        date = date_obj.strftime("%Y%m%d")
        print(f"Checking Date: {date}")
        for name, endpoint in DATASETS.items():
            key = f"raw/{name}/{date[:4]}/{date[4:6]}/{name}_{date}.parquet"
            if check_exists(key):
                continue
                
            print(f"  [Recovering] {name}...")
            headers = {"x-api-key": API_KEY}
            try:
                res = requests.get(f"{BASE_URL}{endpoint}", headers=headers, params={"date": date}, timeout=30)
                if res.status_code == 200:
                    data = res.json().get("data", [])
                    if data:
                        df = pd.DataFrame(data)
                        # 型変換（念のため）
                        num_cols = ['O','H','L','C','Vo','Va','AdjO','AdjH','AdjL','AdjC','AdjVo','AdjFactor','NetSales','OperatingProfit','OrdinaryProfit','NetIncome','EarningsPerShare','ShortVolume','LongVolume','ShortOut','LongOut','ShrtOutRatio','ShortRatio','Position','Ratio','ForeignBuying','ForeignSelling','IndividualBuying','IndividualSelling','StrikePrice','ImpliedVolatility','OpenInterest']
                        for c in df.columns:
                            if c in num_cols: df[c] = pd.to_numeric(df[c], errors='coerce')
                            elif df[c].dtype == 'object': df[c] = df[c].astype(str).replace('None', '')
                        
                        buf = BytesIO()
                        df.to_parquet(buf, index=False, compression='snappy')
                        buf.seek(0)
                        s3_client.upload_fileobj(buf, R2_BUCKET_NAME, key)
                        print(f"    -> Successfully recovered.")
            except Exception:
                continue

if __name__ == "__main__":
    main()
