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
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    print("텔레그램 응답:", r.status_code, r.text[:100])


def get_dart_list(detail_ty):
    end = datetime.today()
    start = end - timedelta(days=7)
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
    data = r.json()
    print(f"DART {detail_ty} 응답 상태: {r.status_code}, 총 {data.get('total_count', 0)}건")
    items = data.get("list", [])
    filtered = [i for i in items
                if not any(x in i["report_nm"] for x in IPO_EXCLUDE)
                and any(x in i["report_nm"] for x in IPO_INCLUDE)]
    print(f"  필터 후 IPO 관련: {len(filtered)}건")
    for i in filtered:
        print(f"    - {i['corp_name']} | {i['report_nm']} | {i['rcept_no']}")
    return filtered


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


def get_offering_details(rcept_no):
    details = {"price_range": "", "underwriter": "", "total_amount": "", "shares": ""}
    try:
        r = requests.get(
            "https://opendart.fss.or.kr/api/index.json",
            params={"crtfc_key": DART_KEY, "rcept_no": rcept_no},
            timeout=8
        )
        docs = r.json().get("list", [])
        target_doc = None
        for doc in docs:
            if any(x in doc.get("dc_nm", "") for x in ["증권신고서", "투자설명서", "요약정보"]):
                target_doc = doc
                break
        if not target_doc:
            return details
        doc_url = "https://dart.fss.or.kr" + target_doc.get("dc_url", "")
        r2 = requests.get(doc_url, timeout=10)
        text = r2.text
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
        amt_m = re.search(r'총\s*공모금액[^0-9]*([0-9,]+)\s*억?\s*원', text)
        if amt_m:
            details["total_amount"] = amt_m.group(1) + "억원"
        shares_m = re.search(r'공모\s*주식수[^0-9]*([0-9,]+)\s*주', text)
        if shares_m:
            details["shares"] = shares_m.group(1) + "주"
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


def get_kind_prelim():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    try:
        session.get("https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain", timeout=10)
    except Exception as e:
        print("KIND 세션 오류:", e)

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
        print(f"KIND 응답: {r.status_code}, 길이: {len(r.text)}")
        if r.status_code != 200:
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
        print(f"KIND 파싱 결과: {len(items)}건")
        return items
    except Exception as e:
        print("KIND 크롤링 오류:", e)
        return []


def fmt_dart_msg(item, is_amendment=False):
    corp_info = get_corp_info(item.get("corp_code", ""))
    details = get_offering_details(item["rcept_no"])
    tag = "🔄 [DART] 증권신고서 <b>정정</b>" if is_amendment else "📋 [DART] <b>새 IPO 증권신고서</b>"
    link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + item["rcept_no"]
    lines = [tag, ""]
    lines.append("🏢 기업명: " + item["corp_name"])
    if corp_info.get("induty_code"):
        lines.append("🏭 업종: " + corp_info.get("induty_code", ""))
    if corp_info.get("est_dt"):
        lines.append("📆 설립일: " + corp_info.get("est_dt", ""))
    if corp_info.get("hm_url"):
        lines.append("🌐 홈페이지: " + corp_info.get("hm_url", ""))
    lines.append("")
    lines.append("📄 공시명: " + item["report_nm"])
    lines.append("📅 접수일: " + item["rcept_dt"])
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


def main():
    now = datetime.today().strftime("%Y-%m-%d %H:%M")
    print(f"=== IPO Alert 실행: {now} ===")
    seen = load_seen()
    print(f"기존 seen 항목 수: {len(seen)}")
    has_new = False

    # DART D001
    dart_new = get_dart_list("D001")
    new_d001 = [i for i in dart_new if i["rcept_no"] not in seen]
    print(f"D001 신규 미발송: {len(new_d001)}건")
    for item in new_d001:
        send_telegram(fmt_dart_msg(item, False))
        seen.add(item["rcept_no"])
        has_new = True

    # DART D003 (정정)
    dart_amend = get_dart_list("D003")
    new_d003 = [i for i in dart_amend if i["rcept_no"] not in seen]
    print(f"D003 정정 미발송: {len(new_d003)}건")
    for item in new_d003:
        send_telegram(fmt_dart_msg(item, True))
        seen.add(item["rcept_no"])
        has_new = True

    # KIND
    kind_items = get_kind_prelim()
    new_kind = [i for i in kind_items if i["id"] not in seen]
    print(f"KIND 신규 미발송: {len(new_kind)}건")
    for item in new_kind:
        send_telegram(fmt_kind_msg(item))
        seen.add(item["id"])
        has_new = True

    if not has_new:
        send_telegram("ℹ️ IPO Alert 실행 완료 (" + now + ")\n새 공시/예비심사 없음")
        print("새 항목 없음")

    save_seen(seen)
    print("완료")


if __name__ == "__main__":
    main()
