import requests, os, re, json, traceback, ssl
from datetime import datetime
import urllib3
urllib3.disable_warnings()

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


def send(msg, parse_mode="HTML"):
    try:
        requests.post(
            "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": parse_mode},
            timeout=10
        )
    except Exception as e:
        print("텔레그램 오류:", e)


def make_session():
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context

    class LegacySSLAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            ctx = create_urllib3_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.set_ciphers('DEFAULT:@SECLEVEL=0')
            kwargs['ssl_context'] = ctx
            super().init_poolmanager(*args, **kwargs)

    session = requests.Session()
    session.mount('https://', LegacySSLAdapter())
    return session


def get_38():
    session = make_session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    r = session.get("https://www.38.co.kr/html/fund/index.htm?o=k",
                    headers=headers, timeout=20, verify=False)
    r.encoding = 'euc-kr'

    # HTML 태그 제거
    text = re.sub(r'<[^>]+>', '\n', r.text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]

    result = {"apply": [], "approve": [], "sub": [], "listing": [], "table": []}
    mode = None

    for line in lines:
        if '최근 IPO 청구종목' in line: mode = 'apply'; continue
        if '최근 IPO 승인종목' in line: mode = 'approve'; continue
        if 'IPO 공모주 청약일정' in line: mode = 'sub'; continue
        if 'IPO 신규상장 일정' in line: mode = 'listing'; continue
        if any(x in line for x in ['빨간색', 'Copyright', '팝 니 다']): mode = None; continue

        if mode:
            m = re.match(r'^(\d{2}/\d{2})\s+(.+)$', line)
            if m:
                result[mode].append({"date": m.group(1), "name": m.group(2).strip()})

    # 공모청약 테이블 파싱
    # 구조: 기업명 → 날짜(2026.MM.DD~MM.DD) → 확정가(-또는숫자) → 희망가(숫자~숫자) → 경쟁률(숫자:1 또는-) → 주관사(증권사명)
    UNDERWRITER_KEYWORDS = ['증권', '투자', '은행', '금융', 'IBK', 'KB', 'NH', 'SK', '미래에셋', '삼성', '한국', '신한', '대신', '키움', '유진', '메리츠', '교보', '하나', '유안타']

    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(2026\.\d{2}\.\d{2}~\d{2}\.\d{2})$', line)
        if m and i > 0:
            name = lines[i-1]
            if len(name) >= 2 and '스팩' not in name and not re.search(r'\d{4}\.', name):
                date = m.group(1)
                # 다음 줄들에서 값 추출
                confirmed = "-"
                price_range = "-"
                competition = "-"
                underwriter = "-"

                for j in range(1, 6):
                    if i + j >= len(lines):
                        break
                    val = lines[i + j].strip()
                    # 확정가: 숫자,숫자 또는 "-"
                    if confirmed == "-" and (val == "-" or re.match(r'^[\d,]+$', val)):
                        confirmed = val
                    # 희망가: 숫자~숫자 형태
                    elif price_range == "-" and re.match(r'^[\d,]+~[\d,]+$', val):
                        price_range = val
                    # 경쟁률: 숫자:1 형태
                    elif competition == "-" and re.match(r'^[\d,\.]+:\d+$', val):
                        competition = val
                    # 주관사: 증권사 키워드 포함
                    elif underwriter == "-" and any(k in val for k in UNDERWRITER_KEYWORDS):
                        underwriter = val[:30]
                        break

                result["table"].append({
                    "name": name, "date": date,
                    "confirmed": confirmed,
                    "range": price_range,
                    "competition": competition,
                    "underwriter": underwriter,
                })
        i += 1

    return result


def main():
    now = datetime.today().strftime("%Y-%m-%d %H:%M")
    seen = load_seen()

    try:
        data = get_38()
    except Exception as e:
        send("❌ 오류:\n" + traceback.format_exc()[-500:], parse_mode="")
        return

    # 새 청구/승인 알림
    new_apply = [a for a in data["apply"] if "A:" + a["name"] not in seen]
    new_approve = [a for a in data["approve"] if "P:" + a["name"] not in seen]

    for a in new_apply:
        send("📨 <b>[KIND] 신규 예비심사 청구</b>\n\n🏢 " + a["name"] + " (" + a["date"] + ")\n🔗 <a href=\"https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain\">KIND 바로가기</a>")
        seen.add("A:" + a["name"])

    for a in new_approve:
        send("✅ <b>[KIND] 예비심사 승인</b>\n\n🏢 " + a["name"] + " (" + a["date"] + ")\n🔗 <a href=\"https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain\">KIND 바로가기</a>")
        seen.add("P:" + a["name"])

    has_new = bool(new_apply or new_approve)
    L = ["✅ <b>IPO Alert</b> (" + now + ")",
         "위 항목 외 추가 없음" if has_new else "오늘 새 청구/승인 없음", ""]

    # 최근 예비심사 청구 (스팩 제외 3개)
    apply_f = [a for a in data["apply"] if "스팩" not in a["name"]][:3]
    L.append("📨 <b>최근 예비심사 청구</b>")
    for a in apply_f: L.append("  " + a["date"] + " " + a["name"])
    if not apply_f: L.append("  (없음)")
    L.append("")

    # 최근 예비심사 승인 (스팩 제외 3개)
    approve_f = [a for a in data["approve"] if "스팩" not in a["name"]][:3]
    L.append("✅ <b>최근 예비심사 승인</b>")
    for a in approve_f: L.append("  " + a["date"] + " " + a["name"])
    if not approve_f: L.append("  (없음)")
    L.append("")

    # 최근 IPO 공모기업 상세 (스팩 제외 3개)
    table_f = [t for t in data["table"] if "스팩" not in t["name"]][:3]
    L.append("📋 <b>최근 IPO 공모기업</b>")
    if table_f:
        for t in table_f:
            line = "  • <b>" + t["name"] + "</b>"
            line += "\n    📅 청약: " + t["date"]
            if t["range"] not in ["-", ""]: line += "\n    💰 " + t["range"]
            if t["confirmed"] not in ["-", ""]: line += " → 확정: " + t["confirmed"]
            if t["competition"] not in ["-", ""]: line += "\n    📊 경쟁률: " + t["competition"]
            if t["underwriter"] not in ["-", ""]: line += "\n    🏛 " + t["underwriter"]
            L.append(line)
    else:
        L.append("  (없음)")
    L.append("")

    # 공모청약 일정 (스팩 제외 4개)
    sub_f = [s for s in data["sub"] if "스팩" not in s["name"]][:4]
    L.append("🗓 <b>공모청약 일정</b>")
    for s in sub_f: L.append("  " + s["date"] + " " + s["name"])
    if not sub_f: L.append("  (없음)")
    L.append("")

    # 신규상장 일정 (스팩 제외 4개)
    list_f = [l for l in data["listing"] if "스팩" not in l["name"]][:4]
    L.append("🔔 <b>신규상장 일정</b>")
    for l in list_f: L.append("  " + l["date"] + " " + l["name"])
    if not list_f: L.append("  (없음)")

    send("\n".join(L))
    save_seen(seen)
    print("완료")


if __name__ == "__main__":
    main()
