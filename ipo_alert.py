import requests
import json
import os
from datetime import datetime, timedelta

DART_KEY = os.environ["DART_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SEEN_FILE = "seen.json"


def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def get_dart_reports():
    end = datetime.today()
    start = end - timedelta(days=3)
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": DART_KEY,
        "pblntf_ty": "D",
        "pblntf_detail_ty": "D001",
        "bgn_de": start.strftime("%Y%m%d"),
        "end_de": end.strftime("%Y%m%d"),
        "page_count": 40,
    }
    r = requests.get(url, params=params, timeout=10)
    return r.json().get("list", [])


def is_ipo(report_nm):
    exclude = ["유상증자", "전환사채", "신주인수권", "교환사채", "합병"]
    include = ["증권신고서", "공모"]
    if any(x in report_nm for x in exclude):
        return False
    return any(x in report_nm for x in include)


def send_telegram(msg):
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)


def main():
    reports = get_dart_reports()
    seen = load_seen()
    new_items = [r for r in reports if r["rcept_no"] not in seen and is_ipo(r["report_nm"])]

    if not new_items:
        print("새 IPO 공시 없음")
        return

    for r in new_items:
        link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + r["rcept_no"]
        msg = (
            "📋 <b>새 IPO 증권신고서</b>\n\n"
            "🏢 기업명: " + r["corp_name"] + "\n"
            "📄 공시명: " + r["report_nm"] + "\n"
            "📅 접수일: " + r["rcept_dt"] + "\n"
            "🔗 <a href=\"" + link + "\">공시 보러가기</a>"
        )
        send_telegram(msg)
        seen.add(r["rcept_no"])
        print("발송:", r["corp_name"])

    save_seen(seen)


if __name__ == "__main__":
    main()
