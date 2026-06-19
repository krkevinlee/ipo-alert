import requests
import os
import re
from datetime import datetime, timedelta

DART_KEY = os.environ["DART_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post(
        "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg},
        timeout=10
    )

now = datetime.today().strftime("%Y-%m-%d %H:%M")
report = ["🔍 진단 리포트 " + now, ""]

# DART 테스트
try:
    end = datetime.today()
    start = end - timedelta(days=30)
    r = requests.get(
        "https://opendart.fss.or.kr/api/list.json",
        params={
            "crtfc_key": DART_KEY,
            "pblntf_ty": "D",
            "pblntf_detail_ty": "D001",
            "bgn_de": start.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "page_count": 10,
        },
        timeout=10
    )
    data = r.json()
    total = data.get("total_count", 0)
    items = data.get("list", [])
    report.append("DART 응답: " + str(r.status_code) + " / 총 " + str(total) + "건")
    for i in items[:5]:
        report.append("  - " + i["corp_name"] + " | " + i["report_nm"] + " | " + i["rcept_dt"])
except Exception as e:
    report.append("DART 오류: " + str(e))

report.append("")

# KIND 테스트
try:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    })
    session.get("https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain", timeout=10)
    end = datetime.today()
    start = end - timedelta(days=30)
    r = session.post(
        "https://kind.krx.co.kr/listinvstg/listinvstgcom.do",
        data={
            "method": "searchListInvstgCorpSub",
            "currentPageSize": "10",
            "pageIndex": "1",
            "orderMode": "0",
            "orderStat": "D",
            "marketType": "",
            "fromDate": start.strftime("%Y-%m-%d"),
            "toDate": end.strftime("%Y-%m-%d"),
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Origin": "https://kind.krx.co.kr",
            "Referer": "https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain",
        },
        timeout=10
    )
    report.append("KIND 응답: " + str(r.status_code) + " / 길이: " + str(len(r.text)))
    # 테이블 행 수 확인
    rows = re.findall(r"<tr[^>]*>.*?</tr>", r.text, re.DOTALL)
    report.append("KIND tr 행 수: " + str(len(rows)))
    report.append("KIND 본문 앞 200자: " + r.text[:200].replace("<", "&lt;"))
except Exception as e:
    report.append("KIND 오류: " + str(e))

send("\n".join(report))
print("\n".join(report))
