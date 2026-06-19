import requests, os
from datetime import datetime, timedelta

DART_KEY = os.environ["DART_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg}, timeout=10)

# DART 공모기업 현황 API
end = datetime.today()
start = end - timedelta(days=30)

# 시도 1: ipoSttus (공모주 청약일정)
r1 = requests.get("https://opendart.fss.or.kr/api/ipoSttus.json", params={
    "crtfc_key": DART_KEY,
    "bgn_de": start.strftime("%Y%m%d"),
    "end_de": end.strftime("%Y%m%d"),
}, timeout=10)
print("ipoSttus:", r1.status_code, r1.text[:200])
send("ipoSttus 응답:\n" + str(r1.status_code) + "\n" + r1.text[:300])

# 시도 2: ipo_rpt (공모주 신고서)
r2 = requests.get("https://opendart.fss.or.kr/api/ipo_rpt.json", params={
    "crtfc_key": DART_KEY,
    "bgn_de": start.strftime("%Y%m%d"),
    "end_de": end.strftime("%Y%m%d"),
}, timeout=10)
send("ipo_rpt 응답:\n" + str(r2.status_code) + "\n" + r2.text[:300])
