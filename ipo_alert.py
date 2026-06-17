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


def clean(text):
    """HTML 태그 제거 및 공백 정리"""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_number(text):
    """텍스트에서 숫자만 추출 (쉼표 제거)"""
    m = re.search(r'[\d,]+', text)
    if m:
        return m.group().replace(',', '')
    return ''


def calc_rate(num, denom):
    """비율 계산"""
    try:
        n = float(num.replace(',', ''))
        d = float(denom.replace(',', ''))
        if d == 0:
            return ''
        return f"{n/d*100:.1f}%"
    except Exception:
        return ''


def get_full_details(rcept_no):
    """공시 원문에서 상세 정보 파싱"""
    details = {
        "price_range": "", "confirmed_price": "",
        "total_amount": "", "shares": "",
        "underwriter": "",
        "largest_shareholder": "", "largest_shareholder_ratio": "",
        "market_cap_ipo": "", "market_cap_method": "",
        "listing_date": "", "float_ratio": "",
        "listing_track": "", "tech_grade": "",
        "rev_3y": [], "op_3y": [], "op_rate_3y": [],
        "net_3y": [], "net_rate_3y": [], "fiscal_years": [],
    }
    try:
        # 공시 문서 목록
        r = requests.get(
            "https://opendart.fss.or.kr/api/index.json",
            params={"crtfc_key": DART_KEY, "rcept_no": rcept_no},
            timeout=8
        )
        docs = r.json().get("list", [])

        # 핵심 문서 찾기 (증권신고서 본문)
        target = None
        for doc in docs:
            nm = doc.get("dc_nm", "")
            if "증권신고서" in nm and "정정" not in nm:
                target = doc
                break
        if not target and docs:
            target = docs[0]
        if not target:
            return details

        doc_url = "https://dart.fss.or.kr" + target.get("dc_url", "")
        r2 = requests.get(doc_url, timeout=15)
        r2.encoding = 'utf-8'
        text = r2.text
        plain = clean(text)

        # ── 공모가 ──
        m = re.search(r'희망\s*공모가[^0-9]*([0-9,]+)\s*원?\s*[~～∼\-]\s*([0-9,]+)\s*원', plain)
        if m:
            details["price_range"] = m.group(1) + "원 ~ " + m.group(2) + "원"
        m = re.search(r'확정\s*공모가[^0-9]*([0-9,]+)\s*원', plain)
        if m:
            details["confirmed_price"] = m.group(1) + "원"

        # ── 총 공모금액 ──
        m = re.search(r'총\s*공모금액[^0-9]*([0-9,]+)', plain)
        if m:
            amt = int(m.group(1).replace(',', ''))
            if amt > 100000000:
                details["total_amount"] = f"{amt//100000000:,}억원"
            else:
                details["total_amount"] = f"{amt:,}원"

        # ── 공모주식수 ──
        m = re.search(r'공모\s*주식\s*수[^0-9]*([0-9,]+)\s*주', plain)
        if m:
            details["shares"] = m.group(1) + "주"

        # ── 대표주관사 ──
        patterns_uw = [
            r'대표\s*주관\s*회사[^\n]*?([가-힣A-Za-z]+(?:증권|투자증권|금융투자))',
            r'주관\s*회사[^\n]*?([가-힣A-Za-z]+(?:증권|투자증권|금융투자))',
        ]
        for pat in patterns_uw:
            m = re.search(pat, plain)
            if m:
                details["underwriter"] = m.group(1).strip()
                break

        # ── 최대주주 ──
        m = re.search(r'최대\s*주주[^가-힣]*([가-힣A-Za-z\s(주)()]+?)[\s]*([0-9,\.]+)\s*%', plain)
        if m:
            details["largest_shareholder"] = m.group(1).strip()[:20]
            details["largest_shareholder_ratio"] = m.group(2) + "%"

        # ── 공모 시가총액 ──
        m = re.search(r'공모\s*후\s*시가총액[^0-9]*([0-9,]+)', plain)
        if not m:
            m = re.search(r'시가총액[^0-9]*([0-9,]+)\s*억\s*원', plain)
        if m:
            amt = int(m.group(1).replace(',', ''))
            if amt > 10000:
                details["market_cap_ipo"] = f"{amt:,}억원"
            else:
                details["market_cap_ipo"] = f"{amt:,}억원"

        # ── 시가총액 평가방법 ──
        m = re.search(r'(PER|EV/EBITDA|PSR|PBR|DCF)[^\n]*비교\s*평가', plain)
        if not m:
            m = re.search(r'(비교\s*회사|유사\s*회사)[^\n]*(PER|EV/EBITDA|PSR|PBR|DCF)', plain)
        if m:
            details["market_cap_method"] = m.group(0)[:60].strip()
        else:
            m = re.search(r'(PER|EV/EBITDA|PSR|PBR|DCF)\s*[0-9\.]+\s*배', plain)
            if m:
                details["market_cap_method"] = m.group(0)

        # ── 상장일 ──
        m = re.search(r'상장\s*예정일[^0-9]*([0-9]{4}[.\-년][0-9]{1,2}[.\-월][0-9]{1,2})', plain)
        if m:
            details["listing_date"] = m.group(1)

        # ── 상장일 유통주식비율 ──
        m = re.search(r'유통\s*가능\s*주식[^0-9]*([0-9,\.]+)\s*%', plain)
        if not m:
            m = re.search(r'상장일\s*유통[^0-9]*([0-9,\.]+)\s*%', plain)
        if m:
            details["float_ratio"] = m.group(1) + "%"

        # ── 상장 트랙 ──
        if "기술성장" in plain or "기술특례" in plain:
            details["listing_track"] = "기술특례"
        elif "이익미실현" in plain:
            details["listing_track"] = "이익미실현"
        elif "성장성" in plain and "추천" in plain:
            details["listing_track"] = "성장성 추천"
        else:
            details["listing_track"] = "일반"

        # ── 기술평가 등급 ──
        m = re.search(r'기술\s*평가\s*등급[^A-Za-z]*([A-Za-z]{1,3})\s*등급', plain)
        if not m:
            m = re.search(r'기술\s*등급[^A-Za-z]*([A-Za-z]{1,3})', plain)
        if not m:
            # AA, A, BBB 패턴
            m = re.search(r'전문평가기관[^\n]*([A-Z]{1,3})\s*[,/]\s*([A-Z]{1,3})', plain)
        if m:
            if len(m.groups()) == 2:
                details["tech_grade"] = m.group(1) + " / " + m.group(2)
            else:
                details["tech_grade"] = m.group(1)

        # ── 재무정보 (최근 3개년) ──
        # 연도 찾기
        years = re.findall(r'20[12][0-9]년?\s*(?:제[0-9]+기)?', plain[:5000])
        years = list(dict.fromkeys(years))[:3]
        details["fiscal_years"] = [y.replace('년', '').strip() for y in years]

        # 매출액
        rev_matches = re.findall(r'매출액[^0-9]*([0-9,]+)', plain)
        if rev_matches:
            details["rev_3y"] = [v.replace(',', '') for v in rev_matches[:3]]

        # 영업이익
        op_matches = re.findall(r'영업이익[^0-9\-△▲]*([△▲\-]?[0-9,]+)', plain)
        if op_matches:
            details["op_3y"] = [v.replace(',', '') for v in op_matches[:3]]

        # 당기순이익
        net_matches = re.findall(r'당기순이익[^0-9\-△▲]*([△▲\-]?[0-9,]+)', plain)
        if net_matches:
            details["net_3y"] = [v.replace(',', '') for v in net_matches[:3]]

        # 영업이익률, 순이익률 계산
        for i in range(min(len(details["rev_3y"]), len(details["op_3y"]))):
            details["op_rate_3y"].append(calc_rate(details["op_3y"][i], details["rev_3y"][i]))
        for i in range(min(len(details["rev_3y"]), len(details["net_3y"]))):
            details["net_rate_3y"].append(calc_rate(details["net_3y"][i], details["rev_3y"][i]))

    except Exception as e:
        print("공시 원문 파싱 오류:", e)

    return details


def fmt_krw(val_str):
    """숫자 문자열을 억원 단위로 포맷"""
    try:
        v = int(val_str.lstrip('△▲-'))
        sign = "-" if val_str.startswith(('△', '▲', '-')) else ""
        if abs(v) >= 100000000:
            return sign + f"{abs(v)//100000000:,}억원"
        elif abs(v) >= 10000:
            return sign + f"{abs(v)//10000:,}만원"
        else:
            return sign + f"{abs(v):,}원"
    except Exception:
        return val_str


def fmt_dart_msg(item, is_amendment=False):
    corp_info = get_corp_info(item.get("corp_code", ""))
    d = get_full_details(item["rcept_no"])

    tag = "🔄 [DART] 증권신고서 <b>정정</b>" if is_amendment else "📋 [DART] <b>신규 IPO 증권신고서</b>"
    link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + item["rcept_no"]

    lines = [tag, ""]

    # 기업 기본
    lines.append("🏢 <b>" + item["corp_name"] + "</b>")
    if corp_info.get("induty_code"):
        lines.append("🏭 업종: " + corp_info.get("induty_code", ""))
    if corp_info.get("est_dt"):
        est = corp_info["est_dt"]
        lines.append("📆 설립: " + est[:4] + "." + est[4:6] + "." + est[6:])
    lines.append("")

    # 공모 정보
    lines.append("━━━ 공모 정보 ━━━")
    if d["price_range"]:
        lines.append("💰 희망 공모가: " + d["price_range"])
    if d["confirmed_price"]:
        lines.append("💰 확정 공모가: " + d["confirmed_price"])
    if d["shares"]:
        lines.append("📊 공모주식수: " + d["shares"])
    if d["total_amount"]:
        lines.append("💵 총 공모금액: " + d["total_amount"])
    if d["market_cap_ipo"]:
        lines.append("🏦 공모 후 시총: " + d["market_cap_ipo"])
    if d["market_cap_method"]:
        lines.append("📐 밸류에이션: " + d["market_cap_method"])
    if d["underwriter"]:
        lines.append("🏛 대표주관사: " + d["underwriter"])
    lines.append("")

    # 상장 정보
    lines.append("━━━ 상장 정보 ━━━")
    if d["listing_track"]:
        track_line = "📌 상장트랙: " + d["listing_track"]
        if d["tech_grade"] and d["listing_track"] == "기술특례":
            track_line += "  |  기술평가: " + d["tech_grade"]
        lines.append(track_line)
    if d["listing_date"]:
        lines.append("📅 상장예정일: " + d["listing_date"])
    if d["float_ratio"]:
        lines.append("🔓 상장일 유통비율: " + d["float_ratio"])
    if d["largest_shareholder"]:
        ratio = ("  (" + d["largest_shareholder_ratio"] + ")") if d["largest_shareholder_ratio"] else ""
        lines.append("👤 최대주주: " + d["largest_shareholder"] + ratio)
    lines.append("")

    # 재무 정보
    if d["rev_3y"]:
        lines.append("━━━ 최근 재무 (억원) ━━━")
        years = d["fiscal_years"] or ["3년전", "2년전", "최근"]
        header = "구분    | " + " | ".join(f"{y[:4]}" for y in years[:len(d["rev_3y"])])
        lines.append("<code>" + header)

        rev_row = "매출액  | " + " | ".join(fmt_krw(v) for v in d["rev_3y"])
        lines.append(rev_row)

        if d["op_3y"]:
            op_row = "영업이익| " + " | ".join(fmt_krw(v) for v in d["op_3y"])
            lines.append(op_row)
            if d["op_rate_3y"]:
                opr_row = "영업이익률| " + " | ".join(d["op_rate_3y"])
                lines.append(opr_row)

        if d["net_3y"]:
            net_row = "순이익  | " + " | ".join(fmt_krw(v) for v in d["net_3y"])
            lines.append(net_row)
            if d["net_rate_3y"]:
                netr_row = "순이익률 | " + " | ".join(d["net_rate_3y"])
                lines.append(netr_row)

        lines.append("</code>")

    lines.append("🔗 <a href=\"" + link + "\">공시 원문 보기</a>")
    return "\n".join(lines)


def get_kind_prelim():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    try:
        session.get("https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain", timeout=10)
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
            return []
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', r.text, re.DOTALL)
        items = []
        for row in rows:
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
            if len(cols) >= 4 and cols[0] and re.search(r'\d{4}', cols[2] if len(cols) > 2 else ''):
                items.append({
                    "name": cols[0],
                    "listing_type": cols[1] if len(cols) > 1 else "",
                    "date": cols[2] if len(cols) > 2 else "",
                    "result_date": cols[3] if len(cols) > 3 else "",
                    "result": cols[4] if len(cols) > 4 else "청구서 접수",
                    "underwriter": cols[5] if len(cols) > 5 else "",
                    "id": "kind_" + cols[0] + "_" + (cols[2] if len(cols) > 2 else ""),
                })
        return items
    except Exception as e:
        print("KIND 크롤링 오류:", e)
        return []


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
    seen = load_seen()
    has_new = False

    for item in get_dart_list("D001"):
        if item["rcept_no"] not in seen:
            send_telegram(fmt_dart_msg(item, False))
            seen.add(item["rcept_no"])
            print("DART 신규:", item["corp_name"])
            has_new = True

    for item in get_dart_list("D003"):
        if item["rcept_no"] not in seen:
            send_telegram(fmt_dart_msg(item, True))
            seen.add(item["rcept_no"])
            print("DART 정정:", item["corp_name"])
            has_new = True

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
