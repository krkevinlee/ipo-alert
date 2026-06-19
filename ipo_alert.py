import requests, os
from datetime import datetime, timedelta

DART_KEY = os.environ["DART_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg}, timeout=10)

end = datetime.today()
start = end - timedelta(days=30)

r = requests.get("https://opendart.fss.or.kr/api/list.json", params={
    "crtfc_key": DART_KEY,
    "pblntf_ty": "C",
    "pblntf_detail_ty": "C001",
    "bgn_de": start.strftime("%Y%m%d"),
    "end_de": end.strftime("%Y%m%d"),
    "page_count": 20,
}, timeout=10)

items = r.json().get("list", [])
lines = [f"C001 전체 목록 (최근30일 {len(items)}건)", ""]
for i in items[:15]:
    lines.append(f"{i['corp_name']} | {i['report_nm']}")

send("\n".join(lines))
