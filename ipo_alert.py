import requests
import json
import os
import re
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


# ── DART: 증권신고서(IPO) ──────────────────────────────
def get_dart_ipo():
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
    items = r.json().get("list", [])
    exclude = ["유상증자", "전환사채", "신주인수권", "교환사채", "합병"]
    include = ["증권신고서", "공모"]
    return [i for i in items
            if not any(x in i["report_nm"] for x in exclude)
            and any(x in i["report_nm"] for x in include)]


# ── KIND: 예비심사 크롤링 ──────────────────────────────
def get_kind_prelim():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://kind.krx.co.kr/",
    })
    # 세션 쿠키 먼저 받기
    try:
        session.get("https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain", timeout=10)
    except Exception:
        pass

    end = datetime.today()
    start = end - timedelta(days=7)
    payload = {
        "method": "searchListInvstgCorpSub",
        "currentPageSize": "15",
        "pageIndex": "1",
        "orderMode": "0",
        "orderStat": "D",
        "marketType": "",
        "fromDate": start.strftime("%Y-%m-%d"),
        "toDate": end.strftime("%Y-%m-%d"),
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Origin": "https://kind.krx.co.kr",
        "Referer": "https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain",
    }
    try:
        r = session.post(
            "https://kind.krx.co.kr/listinvstg/listinvstgcom.do",
            data=payload,
            headers=headers,
            timeout=10
        )
        if r.status_code != 200:
            print(f"KIND 응답 오류: {r.status_code}")
            return []
        # HTML 파싱으로 테이블 추출
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.DOTALL)
        items = []
        for row in rows:
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cols) >= 4:
                name = re.sub(r'<[^>]+>', '', cols[0]).strip()
                listing_type = re.sub(r'<[^>]+>', '', cols[1]).strip()
                date = re.sub(r'<[^>]+>', '', cols[2]).strip()
                result = re.sub(r'<[^>]+>', '', cols[4]).strip() if len(cols) > 4 else ""
                if name and date:
                    items.append({
                        "name": name,
                        "listing_type": listing_type,
                        "date": date,
                        "result": result or "청구서 접수",
                        "id": f"kind_{name}_{date}"
                    })
        return items
    except Exception as e:
        print(f"KIND 크롤링 오류: {e}")
        return []


# ── 텔레그램 발송 ──────────────────────────────────────
def send_telegram(msg):
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)


def main():
    seen = load_seen()
    has_new = False

    # 1. DART IPO 증권신고서
    dart_items = get_dart_ipo()
    new_dart = [i for i in dart_items if i["rcept_no"] not in seen]
    for item in new_dart:
        link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + item["rcept_no"]
        msg = (
            "📋 <b>[DART] 새 IPO 증권신고서</b>\n\n"
            "🏢 기업명: " + item["corp_name"] + "\n"
            "📄 공시명: " + item["report_nm"] + "\n"
            "📅 접수일: " + item["rcept_dt"] + "\n"
            "🔗 <a href=\"" + link + "\">공시 보러가기</a>"
        )
        send_telegram(msg)
        seen.add(item["rcept_no"])
        print("DART 발송:", item["corp_name"])
        has_new = True

    # 2. KIND 예비심사
    kind_items = get_kind_prelim()
    new_kind = [i for i in kind_items if i["id"] not in seen]
    for item in new_kind:
        emoji = "✅" if "승인" in item["result"] else "⚠️" if "철회" in item["result"] or "미승인" in item["result"] else "📨"
        msg = (
            emoji + " <b>[KIND] 예비심사 " + item["result"] + "</b>\n\n"
            "🏢 기업명: " + item["name"] + "\n"
            "📋 상장유형: " + item["listing_type"] + "\n"
            "📅 청구일: " + item["date"] + "\n"
            "🔗 <a href=\"https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain\">KIND 예비심사 현황</a>"
        )
        send_telegram(msg)
        seen.add(item["id"])
        print("KIND 발송:", item["name"], item["result"])
        has_new = True

    if not has_new:
        print("새 공시/예비심사 없음")

    save_seen(seen)


if __name__ == "__main__":
    main()
