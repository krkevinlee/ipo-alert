import requests
import json
import os
import re
from datetime import datetime, timedelta

DART_KEY = os.environ["DART_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
SEEN_FILE = "seen.json"

IPO_EXCLUDE = ["유상증자", "전환사채", "신주인수권", "교환사채", "합병", "대량보유", "임원", "소유상황"]
IPO_INCLUDE = ["증권신고서"]


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
    try:
        url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
        print("텔레그램:", r.status_code)
    except Exception as e:
        print("텔레그램 오류:", e)


def get_dart_ipo(days=3):
    """증권신고서(지분증권) D001만 조회"""
    try:
        end = datetime.today()
        start = end - timedelta(days=days)
        r = requests.get(
            "https://opendart.fss.or.kr/api/list.json",
            params={
                "crtfc_key": DART_KEY,
                "pblntf_detail_ty": "D001",  # 증권신고서(지분증권)만
                "bgn_de": start.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "page_count": 40,
            },
            timeout=10
        )
        data = r.json()
        print("DART D001 응답:", r.status_code, "총:", data.get("total_count", 0), "건")
        items = data.get("list", [])
        filtered = []
        for i in items:
            nm = i.get("report_nm", "")
            if any(x in nm for x in IPO_EXCLUDE):
                continue
            if "증권신고서" in nm:
                print("  IPO 후보:", i["corp_name"], "|", nm)
                filtered.append(i)
        return filtered
    except Exception as e:
        print("DART 조회 오류:", e)
        return []


def get_dart_amendment(days=3):
    """증권신고서 정정 D003"""
    try:
        end = datetime.today()
        start = end - timedelta(days=days)
        r = requests.get(
            "https://opendart.fss.or.kr/api/list.json",
            params={
                "crtfc_key": DART_KEY,
                "pblntf_detail_ty": "D003",
                "bgn_de": start.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "page_count": 40,
            },
            timeout=10
        )
        items = r.json().get("list", [])
        return [i for i in items if "증권신고서" in i.get("report_nm", "")
                and not any(x in i.get("report_nm", "") for x in IPO_EXCLUDE)]
    except Exception as e:
        print("DART 정정 조회 오류:", e)
        return []


def get_recent_dart_ipo(count=3):
    """최근 30일 증권신고서 IPO 기업"""
    try:
        end = datetime.today()
        start = end - timedelta(days=30)
        r = requests.get(
            "https://opendart.fss.or.kr/api/list.json",
            params={
                "crtfc_key": DART_KEY,
                "pblntf_detail_ty": "D001",
                "bgn_de": start.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "page_count": 40,
            },
            timeout=10
        )
        items = r.json().get("list", [])
        filtered = [i for i in items
                    if "증권신고서" in i.get("report_nm", "")
                    and not any(x in i.get("report_nm", "") for x in IPO_EXCLUDE)]
        seen_names = set()
        unique = []
        for i in filtered:
            if i["corp_name"] not in seen_names:
                seen_names.add(i["corp_name"])
                unique.append(i)
        return unique[:count]
    except Exception as e:
        print("최근 DART 조회 오류:", e)
        return []


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
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def calc_rate(a, b):
    try:
        n = float(re.sub(r"[^0-9]", "", str(a)))
        d = float(re.sub(r"[^0-9]", "", str(b)))
        return f"{n/d*100:.1f}%" if d else ""
    except Exception:
        return ""


def fmt_krw(v):
    try:
        sign = "-" if str(v).startswith(("△","▲","-")) else ""
        n = int(re.sub(r"[^0-9]", "", str(v)))
        if n >= 100000000:
            return sign + f"{n//100000000:,}억"
        elif n >= 10000:
            return sign + f"{n//10000:,}만"
        return sign + f"{n:,}"
    except Exception:
        return str(v)


def get_full_details(rcept_no):
    d = {
        "price_range": "", "confirmed_price": "",
        "total_amount": "", "shares": "", "underwriter": "",
        "largest_shareholder": "", "largest_shareholder_ratio": "",
        "market_cap_ipo": "", "market_cap_method": "",
        "listing_date": "", "float_ratio": "",
        "listing_track": "", "tech_grade": "",
        "demand_forecast": "", "subscription": "",
        "rev_3y": [], "op_3y": [], "op_rate_3y": [],
        "net_3y": [], "net_rate_3y": [], "fiscal_years": [],
    }
    try:
        r = requests.get(
            "https://opendart.fss.or.kr/api/index.json",
            params={"crtfc_key": DART_KEY, "rcept_no": rcept_no},
            timeout=8
        )
        docs = r.json().get("list", [])
        target = next((doc for doc in docs if "증권신고서" in doc.get("dc_nm","") and "정정" not in doc.get("dc_nm","")), docs[0] if docs else None)
        if not target:
            return d

        r2 = requests.get("https://dart.fss.or.kr" + target.get("dc_url",""), timeout=15)
        r2.encoding = "utf-8"
        p = clean(r2.text)

        def find(patterns, text=p):
            for pat in (patterns if isinstance(patterns, list) else [patterns]):
                m = re.search(pat, text)
                if m:
                    return m
            return None

        m = find(r"희망\s*공모가[^0-9]*([0-9,]+)\s*원?\s*[~～∼\-]\s*([0-9,]+)\s*원")
        if m:
            d["price_range"] = m.group(1) + "원 ~ " + m.group(2) + "원"

        m = find(r"확정\s*공모가[^0-9]*([0-9,]+)\s*원")
        if m:
            d["confirmed_price"] = m.group(1) + "원"

        m = find(r"총\s*공모금액[^0-9]*([0-9,]+)")
        if m:
            amt = int(m.group(1).replace(",",""))
            d["total_amount"] = f"{amt//100000000:,}억원" if amt >= 100000000 else f"{amt:,}원"

        m = find(r"공모\s*주식\s*수[^0-9]*([0-9,]+)\s*주")
        if m:
            d["shares"] = m.group(1) + "주"

        m = find([r"대표\s*주관\s*회사[^\n]*?([가-힣A-Za-z]+(?:증권|투자증권|금융투자))",
                  r"주관\s*회사[^\n]*?([가-힣A-Za-z]+(?:증권|투자증권|금융투자))"])
        if m:
            d["underwriter"] = m.group(1).strip()

        m = find(r"최대\s*주주[^가-힣]*([가-힣A-Za-z\s()]+?)\s+([0-9,\.]+)\s*%")
        if m:
            d["largest_shareholder"] = m.group(1).strip()[:20]
            d["largest_shareholder_ratio"] = m.group(2) + "%"

        m = find([r"공모\s*후\s*시가총액[^0-9]*([0-9,]+)",
                  r"시가총액[^0-9]*([0-9,]+)\s*억\s*원"])
        if m:
            d["market_cap_ipo"] = f"{int(m.group(1).replace(',','')):,}억원"

        m = find(r"(PER|EV/EBITDA|PSR|PBR|DCF)\s*[0-9\.]+\s*배")
        if m:
            d["market_cap_method"] = m.group(0)

        m = find(r"수요\s*예측[^0-9]*([0-9]{4}[.\-][0-9]{1,2}[.\-][0-9]{1,2})[^0-9~～\-]*[~～\-]\s*([0-9]{4}[.\-][0-9]{1,2}[.\-][0-9]{1,2})")
        if m:
            d["demand_forecast"] = m.group(1) + " ~ " + m.group(2)

        m = find([r"일반\s*청약[^0-9]*([0-9]{4}[.\-][0-9]{1,2}[.\-][0-9]{1,2})[^0-9~～\-]*[~～\-]\s*([0-9]{4}[.\-][0-9]{1,2}[.\-][0-9]{1,2})",
                  r"청약\s*기간[^0-9]*([0-9]{4}[.\-][0-9]{1,2}[.\-][0-9]{1,2})[^0-9~～\-]*[~～\-]\s*([0-9]{4}[.\-][0-9]{1,2}[.\-][0-9]{1,2})"])
        if m:
            d["subscription"] = m.group(1) + " ~ " + m.group(2)

        m = find(r"상장\s*예정일[^0-9]*([0-9]{4}[.\-년][0-9]{1,2}[.\-월][0-9]{1,2})")
        if m:
            d["listing_date"] = m.group(1)

        m = find([r"유통\s*가능\s*주식[^0-9]*([0-9,\.]+)\s*%",
                  r"상장일\s*유통[^0-9]*([0-9,\.]+)\s*%"])
        if m:
            d["float_ratio"] = m.group(1) + "%"

        if "기술성장" in p or "기술특례" in p:
            d["listing_track"] = "기술특례"
        elif "이익미실현" in p:
            d["listing_track"] = "이익미실현"
        elif "성장성" in p and "추천" in p:
            d["listing_track"] = "성장성 추천"
        else:
            d["listing_track"] = "일반"

        m = find([r"전문평가기관[^\n]*([A-Z]{1,3})\s*[,/]\s*([A-Z]{1,3})",
                  r"기술\s*평가\s*등급[^A-Za-z]*([A-Za-z]{1,3})"])
        if m:
            d["tech_grade"] = (m.group(1)+"/"+m.group(2)) if len(m.groups())==2 else m.group(1)

        years = re.findall(r"20[12][0-9]년?\s*(?:제[0-9]+기)?", p[:5000])
        d["fiscal_years"] = [y.replace("년","").strip() for y in list(dict.fromkeys(years))[:3]]

        for key, pat in [("rev_3y", r"매출액[^0-9]*([0-9,]+)"),
                          ("op_3y", r"영업이익[^0-9△▲\-]*([△▲\-]?[0-9,]+)"),
                          ("net_3y", r"당기순이익[^0-9△▲\-]*([△▲\-]?[0-9,]+)")]:
            matches = re.findall(pat, p)
            if matches:
                d[key] = [v.replace(",","") for v in matches[:3]]

        for i in range(min(len(d["rev_3y"]), len(d["op_3y"]))):
            d["op_rate_3y"].append(calc_rate(d["op_3y"][i], d["rev_3y"][i]))
        for i in range(min(len(d["rev_3y"]), len(d["net_3y"]))):
            d["net_rate_3y"].append(calc_rate(d["net_3y"][i], d["rev_3y"][i]))

    except Exception as e:
        print("공시 파싱 오류:", e)
    return d


def fmt_dart_msg(item, is_amendment=False):
    try:
        corp_info = get_corp_info(item.get("corp_code",""))
        d = get_full_details(item["rcept_no"])
        tag = "🔄 [DART] 증권신고서 <b>정정</b>" if is_amendment else "📋 [DART] <b>신규 IPO 증권신고서</b>"
        link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + item["rcept_no"]
        L = [tag, "", "🏢 <b>" + item["corp_name"] + "</b>"]
        if corp_info.get("induty_code"):
            L.append("🏭 업종: " + corp_info["induty_code"])
        if corp_info.get("est_dt"):
            e = corp_info["est_dt"]
            L.append("📆 설립: " + e[:4]+"."+e[4:6]+"."+e[6:])
        L += ["", "━━━ 공모 정보 ━━━"]
        if d["price_range"]: L.append("💰 희망 공모가: " + d["price_range"])
        if d["confirmed_price"]: L.append("💰 확정 공모가: " + d["confirmed_price"])
        if d["shares"]: L.append("📊 공모주식수: " + d["shares"])
        if d["total_amount"]: L.append("💵 총 공모금액: " + d["total_amount"])
        if d["market_cap_ipo"]: L.append("🏦 공모 후 시총: " + d["market_cap_ipo"])
        if d["market_cap_method"]: L.append("📐 밸류에이션: " + d["market_cap_method"])
        if d["underwriter"]: L.append("🏛 대표주관사: " + d["underwriter"])
        L += ["", "━━━ 일정 ━━━"]
        if d["demand_forecast"]: L.append("📅 수요예측: " + d["demand_forecast"])
        if d["subscription"]: L.append("📅 일반청약: " + d["subscription"])
        if d["listing_date"]: L.append("📅 상장예정일: " + d["listing_date"])
        L += ["", "━━━ 상장 정보 ━━━"]
        if d["listing_track"]:
            t = "📌 상장트랙: " + d["listing_track"]
            if d["tech_grade"] and d["listing_track"] == "기술특례":
                t += " | 기술평가: " + d["tech_grade"]
            L.append(t)
        if d["float_ratio"]: L.append("🔓 유통비율: " + d["float_ratio"])
        if d["largest_shareholder"]:
            r2 = " (" + d["largest_shareholder_ratio"] + ")" if d["largest_shareholder_ratio"] else ""
            L.append("👤 최대주주: " + d["largest_shareholder"] + r2)
        if d["rev_3y"]:
            L += ["", "━━━ 최근 재무 (억원) ━━━"]
            yrs = d["fiscal_years"] or ["3년전","2년전","최근"]
            L.append("<code>      | " + " | ".join(y[:4] for y in yrs[:len(d["rev_3y"])]))
            L.append("매출  | " + " | ".join(fmt_krw(v) for v in d["rev_3y"]))
            if d["op_3y"]: L.append("영업익| " + " | ".join(fmt_krw(v) for v in d["op_3y"]))
            if d["op_rate_3y"]: L.append("영업률| " + " | ".join(d["op_rate_3y"]))
            if d["net_3y"]: L.append("순이익| " + " | ".join(fmt_krw(v) for v in d["net_3y"]))
            if d["net_rate_3y"]: L.append("순이률| " + " | ".join(d["net_rate_3y"]))
            L.append("</code>")
        L += ["", "🔗 <a href=\"" + link + "\">공시 원문 보기</a>"]
        return "\n".join(L)
    except Exception as e:
        print("DART 메시지 포맷 오류:", e)
        return "📋 " + item.get("corp_name","") + " 증권신고서 접수"


# ── KIND: 네이버 금융 뉴스 검색으로 우회 ──────────────────
def get_kind_via_news():
    """KIND IP 차단 우회 - 네이버 금융/뉴스에서 예비심사 정보 수집"""
    items = []
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        # 네이버 검색으로 최근 예비심사 청구/승인 뉴스 수집
        query = "IPO 예비심사 청구 승인"
        r = requests.get(
            "https://search.naver.com/search.naver",
            params={"where": "news", "query": query, "sort": "1", "ds": "", "de": ""},
            headers=headers,
            timeout=10
        )
        # 뉴스 제목/링크 파싱
        titles = re.findall(r'<a[^>]+class="news_tit"[^>]*title="([^"]+)"', r.text)
        links = re.findall(r'<a[^>]+class="news_tit"[^>]*href="([^"]+)"', r.text)
        print("네이버 뉴스 검색 결과:", len(titles), "건")
        for title in titles[:5]:
            print(" ", title)
        # 기업명 추출 시도
        for title in titles:
            m = re.search(r"([가-힣A-Za-z0-9]+(?:바이오|테크|시스템|솔루션|네트웍스|코리아|글로벌)?)\s*(예비심사|상장예비심사)\s*(청구|승인|통과|철회)", title)
            if m:
                items.append({
                    "name": m.group(1),
                    "result": m.group(3),
                    "date": "",
                    "source": "뉴스",
                    "id": "news_" + m.group(1) + "_" + m.group(3)
                })
    except Exception as e:
        print("뉴스 검색 오류:", e)
    return items


def fmt_summary(now_str, has_new, kind_news, recent_dart):
    status = "위 항목 외 추가 신규 없음" if has_new else "오늘 새 공시/예비심사 없음"
    L = ["✅ <b>IPO Alert 실행 완료</b> (" + now_str + ")", status, ""]

    # KIND - 뉴스 기반
    L.append("📨 <b>최근 KIND 예비심사</b> (뉴스 기반)")
    if kind_news:
        for i, item in enumerate(kind_news[:3], 1):
            emoji = "✅" if "승인" in item["result"] or "통과" in item["result"] else "⚠️" if "철회" in item["result"] else "📨"
            L.append(str(i) + ". " + emoji + " " + item["name"] + " | " + item["result"])
    else:
        L.append("  (관련 뉴스 없음)")
    L.append("  🔗 <a href=\"https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain\">KIND 전체 현황 보기</a>")
    L.append("")

    # DART
    L.append("📋 <b>최근 DART 증권신고서 발행 IPO 기업</b>")
    if recent_dart:
        for i, item in enumerate(recent_dart, 1):
            d = get_full_details(item["rcept_no"])
            link = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=" + item["rcept_no"]
            date_s = item["rcept_dt"][4:6] + "-" + item["rcept_dt"][6:] if len(item["rcept_dt"]) == 8 else item["rcept_dt"]
            line = str(i) + ". <a href=\"" + link + "\">" + item["corp_name"] + "</a> | " + date_s
            if d["price_range"]:
                line += "\n    💰 " + d["price_range"]
            elif d["confirmed_price"]:
                line += "\n    💰 확정: " + d["confirmed_price"]
            if d["market_cap_ipo"]:
                line += "  시총: " + d["market_cap_ipo"]
            if d["demand_forecast"]:
                line += "\n    수요예측: " + d["demand_forecast"]
            if d["subscription"]:
                line += "  청약: " + d["subscription"]
            L.append(line)
    else:
        L.append("  (최근 30일 내 없음)")
    return "\n".join(L)


def main():
    now_str = datetime.today().strftime("%Y-%m-%d %H:%M")
    print("=== 실행:", now_str, "===")
    seen = load_seen()
    has_new = False

    # 1. DART 신규 증권신고서
    for item in get_dart_ipo(days=3):
        if item["rcept_no"] not in seen:
            send_telegram(fmt_dart_msg(item, False))
            seen.add(item["rcept_no"])
            print("DART 신규:", item["corp_name"])
            has_new = True

    # 2. DART 정정 증권신고서
    for item in get_dart_amendment(days=3):
        if item["rcept_no"] not in seen:
            send_telegram(fmt_dart_msg(item, True))
            seen.add(item["rcept_no"])
            print("DART 정정:", item["corp_name"])
            has_new = True

    # 3. 확인 메시지 (KIND 뉴스 기반 + DART 최근 3개)
    kind_news = get_kind_via_news()
    recent_dart = get_recent_dart_ipo(3)
    send_telegram(fmt_summary(now_str, has_new, kind_news, recent_dart))

    save_seen(seen)
    print("완료")


if __name__ == "__main__":
    main()
