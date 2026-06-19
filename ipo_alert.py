import requests, os, re, json
from datetime import datetime, timedelta

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
DART_KEY = os.environ["DART_API_KEY"]
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


def send_telegram(msg):
    try:
        r = requests.post(
            "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
        print("텔레그램:", r.status_code)
    except Exception as e:
        print("텔레그램 오류:", e)


def get_38_data():
    """38커뮤니케이션에서 IPO 데이터 파싱"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": "https://www.38.co.kr/",
    }
    result = {
        "recent_apply": [],    # 최근 청구
        "recent_approve": [],  # 최근 승인
        "upcoming_ipo": [],    # 공모청약 일정
        "new_listing": [],     # 신규상장 일정
        "subscription_list": [], # 공모청약 상세 목록
    }
    try:
        r = requests.get("https://www.38.co.kr/html/fund/index.htm?o=k",
                        headers=headers, timeout=20, verify=False)
        r.encoding = 'euc-kr'
        text = r.text

        # 최근 청구 파싱
        apply_section = re.search(r'최근 IPO 청구종목(.*?)최근 IPO 승인종목', text, re.DOTALL)
        if apply_section:
            applies = re.findall(r'(\d{2}/\d{2})\s+([^\n<]+)', apply_section.group(1))
            result["recent_apply"] = [{"date": a[0], "name": a[1].strip()} for a in applies[:6]]

        # 최근 승인 파싱
        approve_section = re.search(r'최근 IPO 승인종목(.*?)IPO 공모주 청약일정', text, re.DOTALL)
        if approve_section:
            approves = re.findall(r'(\d{2}/\d{2})\s+([^\n<]+)', approve_section.group(1))
            result["recent_approve"] = [{"date": a[0], "name": a[1].strip()} for a in approves[:6]]

        # 공모청약 일정 파싱
        sub_section = re.search(r'IPO 공모주 청약일정(.*?)IPO 신규상장 일정', text, re.DOTALL)
        if sub_section:
            subs = re.findall(r'(\d{2}/\d{2})\s+([^\n<]+)', sub_section.group(1))
            result["upcoming_ipo"] = [{"date": s[0], "name": s[1].strip()} for s in subs[:6]]

        # 신규상장 일정
        listing_section = re.search(r'IPO 신규상장 일정(.*?)빨간색 매매', text, re.DOTALL)
        if listing_section:
            listings = re.findall(r'(\d{2}/\d{2})\s+([^\n<]+)', listing_section.group(1))
            result["new_listing"] = [{"date": l[0], "name": l[1].strip()} for l in listings[:6]]

        # 공모청약 상세 테이블 파싱 (최근 5개, 스팩 제외)
        rows = re.findall(
            r'<tr[^>]*>.*?</tr>', text, re.DOTALL
        )
        for row in rows:
            cols = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            cols = [re.sub(r'<[^>]+>', '', c).strip() for c in cols]
            if len(cols) >= 5 and re.search(r'\d{4}\.\d{2}\.\d{2}', cols[1] if len(cols) > 1 else ''):
                name = cols[0]
                if '스팩' in name or 'SPAC' in name.upper():
                    continue
                result["subscription_list"].append({
                    "name": name,
                    "sub_date": cols[1] if len(cols) > 1 else "",
                    "confirmed_price": cols[2] if len(cols) > 2 else "",
                    "price_range": cols[3] if len(cols) > 3 else "",
                    "competition": cols[4] if len(cols) > 4 else "",
                    "underwriter": cols[5] if len(cols) > 5 else "",
                })
        result["subscription_list"] = result["subscription_list"][:5]
        print("38.co.kr 파싱 성공")

    except Exception as e:
        print("38.co.kr 파싱 오류:", e)

    return result


def get_dart_ipo_detail(corp_name):
    """DART에서 특정 기업 증권신고서 상세 정보"""
    try:
        end = datetime.today()
        start = end - timedelta(days=60)
        r = requests.get(
            "https://opendart.fss.or.kr/api/list.json",
            params={
                "crtfc_key": DART_KEY,
                "pblntf_ty": "C",
                "pblntf_detail_ty": "C001",
                "bgn_de": start.strftime("%Y%m%d"),
                "end_de": end.strftime("%Y%m%d"),
                "page_count": 40,
            },
            timeout=10
        )
        items = r.json().get("list", [])
        for item in items:
            if corp_name in item.get("corp_name", ""):
                return item
    except Exception as e:
        print("DART 조회 오류:", e)
    return None


def fmt_daily_summary(data, now_str, seen):
    """매일 확인 메시지"""
    L = ["✅ <b>IPO Alert 실행 완료</b> (" + now_str + ")", ""]

    # 새 청구 기업 (seen에 없는 것)
    new_applies = [a for a in data["recent_apply"] if "apply_" + a["name"] not in seen]
    new_approves = [a for a in data["recent_approve"] if "approve_" + a["name"] not in seen]

    if new_applies:
        L.append("📨 <b>신규 예비심사 청구</b>")
        for a in new_applies:
            L.append(f"  • {a['name']} ({a['date']})")
        L.append("")

    if new_approves:
        L.append("✅ <b>예비심사 승인</b>")
        for a in new_approves:
            L.append(f"  • {a['name']} ({a['date']})")
        L.append("")

    if not new_applies and not new_approves:
        L.append("오늘 새 청구/승인 없음")
        L.append("")

    # 최근 청구 3개
    L.append("📨 <b>최근 KIND 예비심사 청구</b>")
    for a in data["recent_apply"][:3]:
        L.append(f"  {a['date']} {a['name']}")
    L.append("")

    # 최근 승인 3개
    L.append("✅ <b>최근 KIND 예비심사 승인</b>")
    for a in data["recent_approve"][:3]:
        L.append(f"  {a['date']} {a['name']}")
    L.append("")

    # 공모청약 일정
    L.append("📋 <b>최근 DART 증권신고서 발행 IPO 기업</b>")
    for s in data["subscription_list"][:3]:
        line = f"  • <b>{s['name']}</b> | 청약: {s['sub_date']}"
        if s["price_range"] and s["price_range"] != "-":
            line += f"\n    💰 {s['price_range']}"
        if s["confirmed_price"] and s["confirmed_price"] != "-":
            line += f" → 확정: {s['confirmed_price']}"
        if s["competition"] and s["competition"] != "-":
            line += f" | 경쟁률: {s['competition']}"
        L.append(line)
    L.append("")

    # 다가오는 공모청약
    L.append("🗓 <b>공모청약 일정</b>")
    for u in data["upcoming_ipo"][:4]:
        L.append(f"  {u['date']} {u['name']}")
    L.append("")

    # 신규상장
    L.append("🔔 <b>신규상장 일정</b>")
    for nl in data["new_listing"][:4]:
        L.append(f"  {nl['date']} {nl['name']}")

    return "\n".join(L)


def main():
    import urllib3
    urllib3.disable_warnings()

    now_str = datetime.today().strftime("%Y-%m-%d %H:%M")
    print("=== 실행:", now_str, "===")
    seen = load_seen()

    # 38.co.kr에서 데이터 수집
    data = get_38_data()

    # 새 청구/승인 seen에 추가
    for a in data["recent_apply"]:
        seen.add("apply_" + a["name"])
    for a in data["recent_approve"]:
        seen.add("approve_" + a["name"])

    # 요약 메시지 발송
    msg = fmt_daily_summary(data, now_str, seen)
    send_telegram(msg)

    save_seen(seen)
    print("완료")


if __name__ == "__main__":
    main()
