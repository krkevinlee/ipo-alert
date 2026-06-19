import requests, os, re
from datetime import datetime, timedelta

DART_KEY = os.environ["DART_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post("https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg}, timeout=10)

end = datetime.today()
start = end - timedelta(days=30)
report = ["🔍 DART API 파라미터 테스트", ""]

# 테스트 1: pblntf_detail_ty=D001만 (pblntf_ty 없이)
r = requests.get("https://opendart.fss.or.kr/api/list.json", params={
    "crtfc_key": DART_KEY,
    "pblntf_detail_ty": "D001",
    "bgn_de": start.strftime("%Y%m%d"),
    "end_de": end.strftime("%Y%m%d"),
    "page_count": 5,
}, timeout=10)
data = r.json()
report.append("[D001 단독] 총: " + str(data.get("total_count", 0)) + "건")
for i in (data.get("list") or [])[:3]:
    report.append("  " + i["corp_name"] + " | " + i["report_nm"][:20])

report.append("")

# 테스트 2: pblntf_ty=D + pblntf_detail_ty=D001
r2 = requests.get("https://opendart.fss.or.kr/api/list.json", params={
    "crtfc_key": DART_KEY,
    "pblntf_ty": "D",
    "pblntf_detail_ty": "D001",
    "bgn_de": start.strftime("%Y%m%d"),
    "end_de": end.strftime("%Y%m%d"),
    "page_count": 5,
}, timeout=10)
data2 = r2.json()
report.append("[pblntf_ty=D + D001] 총: " + str(data2.get("total_count", 0)) + "건")
for i in (data2.get("list") or [])[:3]:
    report.append("  " + i["corp_name"] + " | " + i["report_nm"][:20])

report.append("")

# 테스트 3: report_nm에 증권신고서 키워드 검색
r3 = requests.get("https://opendart.fss.or.kr/api/list.json", params={
    "crtfc_key": DART_KEY,
    "pblntf_ty": "D",
    "bgn_de": start.strftime("%Y%m%d"),
    "end_de": end.strftime("%Y%m%d"),
    "page_count": 100,
}, timeout=10)
data3 = r3.json()
all_items = data3.get("list") or []
ipo_items = [i for i in all_items if "증권신고서" in i.get("report_nm", "") and "지분" in i.get("report_nm", "")]
report.append("[pblntf_ty=D 전체] 총: " + str(data3.get("total_count", 0)) + "건")
report.append("  → 증권신고서(지분) 포함: " + str(len(ipo_items)) + "건")
for i in ipo_items[:5]:
    report.append("  " + i["corp_name"] + " | " + i["report_nm"][:25] + " | " + i.get("pblntf_detail_ty",""))

send("\n".join(report))
print("\n".join(report))
