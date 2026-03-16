import os, time, datetime, calendar, requests, boto3
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
    "equities_master":   "/equities/master",
    "daily_quotes":      "/equities/bars/daily",
    "fins_summary":      "/fins/summary",
    "earnings_calendar": "/equities/earnings-calendar",
    "indices_topix":     "/indices/bars/daily/topix",
    "indices_daily":     "/indices/bars/daily",
    "margin_interest":   "/markets/margin-interest",
    "margin_alert":      "/markets/margin-alert",
    "short_ratio":       "/markets/short-ratio",
    "short_sale_report": "/markets/short-sale-report",
    "investor_types":    "/equities/investor-types",
    "options_225":       "/derivatives/bars/daily/options/225",
}

NUM_COLS = [
    'O','H','L','C','Vo','Va','AdjO','AdjH','AdjL','AdjC','AdjVo','AdjFactor',
    'NetSales','OperatingProfit','OrdinaryProfit','NetIncome','EarningsPerShare',
    'ShortVolume','LongVolume','ShortOut','LongOut','ShrtOutRatio','ShortRatio',
    'Position','Ratio','ForeignBuying','ForeignSelling','IndividualBuying',
    'IndividualSelling','StrikePrice','ImpliedVolatility','OpenInterest'
]

s3_client = boto3.client(
    's3',
    endpoint_url=R2_ENDPOINT_URL,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY
)

def check_exists(key):
    try:
        s3_client.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        return True
    except ClientError:
        return False

def get_data(endpoint, target_date):
    url = f"{BASE_URL}{endpoint}"
    headers = {"x-api-key": API_KEY}
    params = {"date": target_date} if endpoint != "/equities/master" else {}
    all_data = []
    pagination_key = None

    while True:
        p = params.copy()
        if pagination_key:
            p["pagination_key"] = pagination_key
        try:
            res = requests.get(url, headers=headers, params=p, timeout=30)
            if res.status_code == 429:
                print(f"  Rate limit. Waiting 10s...")
                time.sleep(10)
                continue
            if res.status_code != 200:
                return None
            data = res.json()
            all_data.extend(data.get("data", []))
            pagination_key = data.get("pagination_key")
            if not pagination_key:
                break
            time.sleep(1)
        except Exception:
            return None

    return all_data

def get_calendar_data(from_date, to_date):
    """取引カレンダーは月単位でまとめて取得"""
    url = f"{BASE_URL}/markets/calendar"
    headers = {"x-api-key": API_KEY}
    params = {"from": from_date, "to": to_date}
    all_data = []
    pagination_key = None

    while True:
        p = params.copy()
        if pagination_key:
            p["pagination_key"] = pagination_key
        try:
            res = requests.get(url, headers=headers, params=p, timeout=30)
            if res.status_code == 429:
                print(f"  Rate limit. Waiting 10s...")
                time.sleep(10)
                continue
            if res.status_code != 200:
                return None
            data = res.json()
            all_data.extend(data.get("data", []))
            pagination_key = data.get("pagination_key")
            if not pagination_key:
                break
            time.sleep(1)
        except Exception:
            return None

    return all_data

def save_r2(df, name, date):
    if df.empty:
        return
    for c in df.columns:
        if c in NUM_COLS:
            df[c] = pd.to_numeric(df[c], errors='coerce')
        elif df[c].dtype == 'object':
            df[c] = df[c].astype(str).replace('None', '')

    buf = BytesIO()
    df.to_parquet(buf, index=False, compression='snappy')
    buf.seek(0)

    key = f"raw/{name}/{date[:4]}/{date[4:6]}/{name}_{date}.parquet"
    s3_client.upload_fileobj(buf, R2_BUCKET_NAME, key)
    print(f"  [Saved] {key}")

def main():
    target_month = os.environ.get("TARGET_MONTH", "").strip()
    if not target_month or len(target_month) != 6:
        print("ERROR: TARGET_MONTH must be set in YYYYMM format (e.g. 202401)")
        return

    year = int(target_month[:4])
    month = int(target_month[4:6])
    _, last_day = calendar.monthrange(year, month)
    from_date = f"{year}{month:02d}01"
    to_date   = f"{year}{month:02d}{last_day:02d}"

    print(f"--- Starting Backfill for {target_month} ---")

    # ─── 取引カレンダーは月単位で1回まとめて取得 ───────────────
    cal_key = f"raw/market_calendar/{year}/{month:02d}/market_calendar_{from_date}.parquet"
    if check_exists(cal_key):
        print(f"  [Skip] market_calendar {target_month} already exists")
    else:
        print(f"  Fetching market_calendar {from_date} - {to_date} ...")
        cal_data = get_calendar_data(from_date, to_date)
        if cal_data:
            save_r2(pd.DataFrame(cal_data), "market_calendar", from_date)
        else:
            print(f"  No data for market_calendar {target_month}")
    time.sleep(1)

    # ─── 通常データセットを日次で取得 ──────────────────────────
    for day in range(1, last_day + 1):
        date = f"{year}{month:02d}{day:02d}"
        print(f"\nProcessing Day: {date}")

        for name, endpoint in DATASETS.items():
            key = f"raw/{name}/{date[:4]}/{date[4:6]}/{name}_{date}.parquet"
            if check_exists(key):
                print(f"  [Skip] {name} already exists")
                continue

            data = get_data(endpoint, date)
            if data:
                save_r2(pd.DataFrame(data), name, date)
            else:
                print(f"  No data for {name} on {date}")

            wait = 2 if name == "indices_daily" else 0.5
            time.sleep(wait)

if __name__ == "__main__":
    main()
