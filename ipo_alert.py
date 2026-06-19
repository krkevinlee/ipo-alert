import requests, os, re
from datetime import datetime, timedelta

DART_KEY = os.environ["DART_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg}, timeout=10)

end = datetime.today()
start = end - timedelta(days=30)

# pblntf_detail_ty 없이 pblntf_ty=D (발행공시 전체)로 조회
r = requests.get("https://opendart.fss.or.kr/api/list.json", params={
    "crtfc_key": DART_KEY,
    "pblntf_ty": "D",
    "bgn_de": start.strftime("%Y%m%d"),
    "end_de": end.strftime("%Y%m%d"),
    "page_count": 10,
}, timeout=10)

data = r.json()
lines = ["DART 발행공시 전체 샘플 (최근30일 10건)", f"총: {data.get('total_count',0)}건", ""]
for i in data.get("list", []):
    lines.append(f"[{i.get('pblntf_detail_ty','')}] {i['corp_name']} | {i['report_nm'][:30]}")

send("\n".join(lines))

# D001만 따로 조회
r2 = requests.get("https://opendart.fss.or.kr/api/list.json", params={
    "crtfc_key": DART_KEY,
    "pblntf_detail_ty": "D001",
    "bgn_de": start.strftime("%Y%m%d"),
    "end_de": end.strftime("%Y%m%d"),
    "page_count": 10,
}, timeout=10)
data2 = r2.json()
lines2 = [f"D001 단독 조회: {data2.get('total_count',0)}건", ""]
for i in data2.get("list", []):
    lines2.append(f"{i['corp_name']} | {i['report_nm'][:30]}")
send("\n".join(lines2))
