import os, time, datetime, requests, boto3
import pandas as pd
from io import BytesIO

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

def get_data(endpoint, target_date):
    url = f"{BASE_URL}{endpoint}"
    headers = {"x-api-key": API_KEY}
    params = {"date": target_date} if endpoint != "/equities/master" else {}
    all_data = []
    pagination_key = None
    while True:
        p = params.copy()
        if pagination_key: p["pagination_key"] = pagination_key
        res = requests.get(url, headers=headers, params=p)
        if res.status_code == 429:
            time.sleep(10); continue
        res.raise_for_status()
        data = res.json()
        all_data.extend(data.get("data", []))
        pagination_key = data.get("pagination_key")
        if not pagination_key: break
        time.sleep(1)
    return all_data

def save_r2(df, name, date):
    if df.empty: return
    num_cols = ['O','H','L','C','Vo','Va','AdjO','AdjH','AdjL','AdjC','AdjVo','AdjFactor','NetSales','OperatingProfit','OrdinaryProfit','NetIncome','EarningsPerShare','ShortVolume','LongVolume','ShortOut','LongOut','ShrtOutRatio','ShortRatio','Position','Ratio','ForeignBuying','ForeignSelling','IndividualBuying','IndividualSelling','StrikePrice','ImpliedVolatility','OpenInterest']
    for c in df.columns:
        if c in num_cols: df[c] = pd.to_numeric(df[c], errors='coerce')
        elif df[c].dtype == 'object': df[c] = df[c].astype(str).replace('None', '')
    buf = BytesIO()
    df.to_parquet(buf, index=False, compression='snappy')
    buf.seek(0)
    s3 = boto3.client('s3', endpoint_url=R2_ENDPOINT_URL, aws_access_key_id=R2_ACCESS_KEY_ID, aws_secret_access_key=R2_SECRET_ACCESS_KEY)
    key = f"raw/{name}/{date[:4]}/{date[4:6]}/{name}_{date}.parquet"
    s3.upload_fileobj(buf, R2_BUCKET_NAME, key)
    print(f"Saved: {key}")

def main():
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)
    date = os.environ.get("TARGET_DATE_INPUT", "").strip() or ((now - datetime.timedelta(days=1 if now.weekday()==5 else 2 if now.weekday()==6 else 0)).strftime('%Y%m%d'))
    print(f"Target: {date}")
    for n, e in DATASETS.items():
        d = get_data(e, date)
        if d: save_r2(pd.DataFrame(d), n, date)

if __name__ == "__main__": main()
