import requests
import json
import os
import re
from datetime import datetime, timedelta

DART_KEY = os.environ["DART_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SEEN_FILE = "seen.json"

IPO_EXCLUDE = ["유상증자", "전환사채", "신주인수권", "교환사채", "합병"]
IPO_INCLUDE = ["증권신고서", "공모"]


def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def send_telegram(msg):
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)


# ── DART 공시 목록 조회 ────────────────────────────────
def get_dart_list(detail_ty):
    end = datetime.today()
    start = end - timedelta(days=3)
    r = requests.get(
        "https://opendart.fss.or.kr/api/list.json",
        params={
            "crtfc_key": DART_KEY,
            "pblntf_ty": "D",
            "pblntf_detail_ty": detail_ty,
            "bgn_de": start.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "page_count": 40,
        },
        timeout=10
    )
    items = r.json().get("list", [])
    return [i for i in items
            if not any(x in i["report_nm"] for x in IPO_EXCLUDE)
            and any(x in i["report_nm"] for x in IPO_INCLUDE)]


# ── DART 기업 기본정보 조회 ────────────────────────────
def get_corp_info(corp_code):
    try:
        r = requests.get(
            "https://opendart.fss.or.kr/api/company.json",
            params={"crtfc_key": DART_KEY, "corp_code": corp_code},
            timeout=8
        )
        return r.json()
    except Exception:
        return {}


# ── DART 공시 원문에서 공모가/주관사 파싱 ──────────────
def get_offering_details(rcept_no):
    """공시 원문 index에서 주요 문서 URL 찾아 공모가·주관사 파싱"""
    details = {"price_range": "", "underwriter": "", "total_amount": "", "shares": ""}
    try:
        r = requests.get(
            "https://opendart.fss.or.kr/api/index.json",
            params={"crtfc_key": DART_KEY, "rcept_no": rcept_no},
            timeout=8
        )
        data = r.json()
        docs = data.get("list", [])
        # 투자설명서 또는 증권신고서 본문 찾기
        target_doc = None
        for doc in docs:
            if any(x in doc.get("dc_nm", "") for x in ["증권신고서", "투자설명서", "요약정보"]):
                target_doc = doc
                break
        if not target_doc:
            return details

        # 문서 원문 가져오기
        doc_url = "https://dart.fss.or.kr" + target_doc.get("dc_url", "")
        r2 = requests.get(doc_url, timeout=10)
        text = r2.text

        # 공모가 범위 파싱
        price_patterns = [
            r'희망\s*공모가[^0-9]*([0-9,]+)\s*원?\s*[~～\-]\s*([0-9,]+)\s*원',
            r'공모\s*희망가격[^0-9]*([0-9,]+)\s*[~～\-]\s*([0-9,]+)',
            r'확정\s*공모가[^0-9]*([0-9,]+)\s*원',
        ]
        for pat in price_patterns:
            m = re.search(pat, text)
            if m:
                if len(m.groups()) == 2:
                    details["price_range"] = m.group(1) + "원 ~ " + m.group(2) + "원"
                else:
                    details["price_range"] = m.group(1) + "원 (확정)"
                break

        # 총 공모금액
        amt_m = re.search(r'총\s*공모금액[^0-9]*([0-9,]+)\s*억?\s*원', text)
        if amt_m:
            details["total_amount"] = amt_m.group(1) + "억원"

        # 공모주식수
        shares_m = re.search(r'공모\s*주식수[^0-9]*([0-9,]+)\s*주', text)
        if shares_m:
            details["shares"] = shares_m.group(1) + "주"

        # 대표주관사
        uw_patterns = [
            r'대표\s*주관\s*회사[^가-힣]*([가-힣A-Za-z\s()（）]+(?:증권|투자|금융))',
            r'주관\s*회사[^가-힣]*([가-힣A-Za-z\s()（）]+(?:증권|투자|금융))',
        ]
        for pat in uw_patterns:
            m = re.search(pat, text)
            if m:
                details["underwriter"] = m.group(1).strip()[:30]
                break

    except Exception as e:
        print("공시 원문 파싱 오류:", e)

    return details


# ── KIND 예비심사 크롤링 ───────────────────────────────
def get_kind_prelim():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    try:
        session.get(
            "https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain",
            timeout=10
        )
    except Exception:
        pass

    end = datetime.today()
    start = end - timedelta(days=7)
    try:
        r = session.post(
            "https://kind.krx.co.kr/listinvstg/listinvstgcom.do",
            data={
                "method": "searchListInvstgCorpSub",
                "currentPageSize": "20",
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
        if r.status_code != 200:
            print("KIND 응답 오류:", r.status_code)
            return []
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.DOTALL)
        items = []
        for row in rows:
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
            if len(cols) >= 4 and cols[0] and re.search(r'\d{4}', cols[2] if len(cols) > 2 else ''):
                result = cols[4] if len(cols) > 4 else "청구서 접수"
                items.append({
                    "name": cols[0],
                    "listing_type": cols[1] if len(cols) > 1 else "",
                    "date": cols[2] if len(cols) > 2 else "",
                    "result_date": cols[3] if len(cols) > 3 else "",
                    "result": result,
                    "underwriter": cols[5] if len(cols) > 5 else "",
                    "id": "kind_" + cols[0] + "_" + (cols[2] if len(cols) > 2 else ""),
                })
        return items
    except Exception as e:
        print("KIND 크롤링 오류:", e)
        return []


# ── 메시지 포맷 ────────────────────────────────────────
def fmt_dart_msg(item, is_amendment=False):
    corp_info = get_corp_info(item.get("corp_code", ""))
    details = get_offering_details(item["rcept_no"])

    tag = "🔄 [DART] 증권신고서 <b>정정</b>" if is_amendment else "📋 [DART] <b>새 IPO 증권신고서</b>"
    link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + item["rcept_no"]

    lines = [tag, ""]
    lines.append("🏢 기업명: " + item["corp_name"])

    # 기업 기본정보
    if corp_info.get("induty_code"):
        lines.append("🏭 업종: " + corp_info.get("induty_code", ""))
    if corp_info.get("est_dt"):
        lines.append("📆 설립일: " + corp_info.get("est_dt", ""))
    if corp_info.get("hm_url"):
        lines.append("🌐 홈페이지: " + corp_info.get("hm_url", ""))

    lines.append("")
    lines.append("📄 공시명: " + item["report_nm"])
    lines.append("📅 접수일: " + item["rcept_dt"])

    # 공모 상세
    if details["price_range"]:
        lines.append("💰 공모가 범위: " + details["price_range"])
    if details["total_amount"]:
        lines.append("💵 총 공모금액: " + details["total_amount"])
    if details["shares"]:
        lines.append("📊 공모주식수: " + details["shares"])
    if details["underwriter"]:
        lines.append("🏦 대표주관사: " + details["underwriter"])

    lines.append("")
    lines.append("🔗 <a href=\"" + link + "\">공시 원문 보기</a>")
    return "\n".join(lines)


def fmt_kind_msg(item):
    emoji = "✅" if "승인" in item["result"] else "⚠️" if any(x in item["result"] for x in ["철회", "미승인"]) else "📨"
    link = "https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain"

    lines = [emoji + " [KIND] 예비심사 <b>" + item["result"] + "</b>", ""]
    lines.append("🏢 기업명: " + item["name"])
    lines.append("📋 상장유형: " + item["listing_type"])
    lines.append("📅 청구일: " + item["date"])
    if item["result_date"]:
        lines.append("📅 결과확정일: " + item["result_date"])
    if item["underwriter"]:
        lines.append("🏦 상장주선인: " + item["underwriter"])
    lines.append("")
    lines.append("🔗 <a href=\"" + link + "\">KIND 예비심사 현황</a>")
    return "\n".join(lines)


# ── 메인 ──────────────────────────────────────────────
def main():
    seen = load_seen()
    has_new = False

    # 1. DART 증권신고서 (신규 D001)
    for item in get_dart_list("D001"):
        if item["rcept_no"] not in seen:
            send_telegram(fmt_dart_msg(item, is_amendment=False))
            seen.add(item["rcept_no"])
            print("DART 신규:", item["corp_name"])
            has_new = True

    # 2. DART 증권신고서 정정 (D003)
    for item in get_dart_list("D003"):
        if item["rcept_no"] not in seen:
            send_telegram(fmt_dart_msg(item, is_amendment=True))
            seen.add(item["rcept_no"])
            print("DART 정정:", item["corp_name"])
            has_new = True

    # 3. KIND 예비심사
    for item in get_kind_prelim():
        if item["id"] not in seen:
            send_telegram(fmt_kind_msg(item))
            seen.add(item["id"])
            print("KIND:", item["name"], item["result"])
            has_new = True

    if not has_new:
        print("새 공시/예비심사 없음")

    save_seen(seen)


if __name__ == "__main__":
    main()
