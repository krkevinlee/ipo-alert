import requests, os, re, json, ssl
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
            data={"chat_id": CHAT_ID, "text": msg[:4000], "parse_mode": parse_mode},
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


def get_lines(url):
    session = make_session()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = session.get(url, headers=headers, timeout=20, verify=False)
    r.encoding = 'euc-kr'
    text = re.sub(r'<[^>]+>', '\n', r.text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
    return [l.strip() for l in text.split('\n') if l.strip()]


def parse_index(lines):
    """메인페이지: 청구/승인/청약일정/신규상장 파싱"""
    result = {"apply": [], "approve": [], "sub": [], "listing": []}
    mode = None
    for line in lines:
        if '최근 IPO 청구종목' in line: mode = 'apply'; continue
        if '최근 IPO 승인종목' in line: mode = 'approve'; continue
        if 'IPO 공모주 청약일정' in line: mode = 'sub'; continue
        if 'IPO 신규상장 일정' in line: mode = 'listing'; continue
        if any(x in line for x in ['슬라이드', 'function', 'Copyright', '//', 'var ']): mode = None; continue
        if mode:
            m = re.match(r'^(\d{2}/\d{2})\s+(.+)$', line)
            if m:
                result[mode].append({"date": m.group(1), "name": m.group(2).strip()})
    return result


def parse_table(lines):
    """공모청약일정 페이지: 테이블 파싱"""
    UNDERWRITERS = ['증권', '투자', '은행', '금융', 'IBK', 'KB', 'NH', 'SK', '미래에셋',
                    '삼성', '한국투자', '신한', '대신', '키움', '유진', '메리츠', '교보',
                    '하나', '유안타', '현대차', '한화', '부국']
    table = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # 날짜 패턴: 2026.MM.DD~MM.DD
        if re.match(r'^2026\.\d{2}\.\d{2}~\d{2}\.\d{2}$', line) and i > 0:
            name = lines[i-1]
            if len(name) >= 2 and not re.search(r'\d{4}\.', name) and not any(x in name for x in ['증권', '청약', '공모', '상장', '분석']):
                entry = {"name": name, "date": line, "confirmed": "-", "range": "-", "competition": "-", "underwriter": "-"}
                for j in range(1, 7):
                    if i + j >= len(lines): break
                    val = lines[i + j].strip()
                    if entry["confirmed"] == "-" and (val == "-" or re.match(r'^[\d,]+$', val)):
                        entry["confirmed"] = val
                    elif entry["range"] == "-" and re.match(r'^[\d,]+~[\d,]+$', val):
                        entry["range"] = val
                    elif entry["competition"] == "-" and re.match(r'^[\d,\.]+:\d+$', val):
                        entry["competition"] = val
                    elif entry["underwriter"] == "-" and any(k in val for k in UNDERWRITERS):
                        entry["underwriter"] = val[:30]
                        break
                if "스팩" not in name:
                    table.append(entry)
        i += 1
    return table


def main():
    now = datetime.today().strftime("%Y-%m-%d %H:%M")
    seen = load_seen()

    # 메인 페이지 (청구/승인/일정)
    index_lines = get_lines("https://www.38.co.kr/html/fund/index.htm?o=k")
    data = parse_index(index_lines)

    # 공모청약 전용 페이지 (테이블)
    table_lines = get_lines("https://www.38.co.kr/html/fund/index.htm?o=k&n=1")
    table = parse_table(table_lines)
    # 없으면 다른 페이지 시도
    if not table:
        table_lines2 = get_lines("https://www.38.co.kr/html/fund/subscribe.htm")
        table = parse_table(table_lines2)

    # 새 청구/승인 알림 (스팩 제외)
    new_apply = [a for a in data["apply"] if "스팩" not in a["name"] and "A:" + a["name"] not in seen]
    new_approve = [a for a in data["approve"] if "스팩" not in a["name"] and "P:" + a["name"] not in seen]

    for a in new_apply:
        send("📨 <b>[KIND] 신규 예비심사 청구</b>\n\n🏢 " + a["name"] + " (" + a["date"] + ")\n🔗 <a href=\"https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain\">KIND 바로가기</a>")
        seen.add("A:" + a["name"])

    for a in new_approve:
        send("✅ <b>[KIND] 예비심사 승인</b>\n\n🏢 " + a["name"] + " (" + a["date"] + ")\n🔗 <a href=\"https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain\">KIND 바로가기</a>")
        seen.add("P:" + a["name"])

    has_new = bool(new_apply or new_approve)

    # 요약 메시지
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

    # 최근 IPO 공모기업 (스팩 제외 3개)
    L.append("📋 <b>최근 IPO 공모기업</b>")
    if table:
        for t in [t for t in table if "스팩" not in t["name"]][:3]:
            line = "  • <b>" + t["name"] + "</b>"
            line += "\n    📅 청약: " + t["date"]
            if t["range"] != "-": line += "\n    💰 " + t["range"]
            if t["confirmed"] != "-": line += " → 확정: " + t["confirmed"]
            if t["competition"] != "-": line += "\n    📊 경쟁률: " + t["competition"]
            if t["underwriter"] != "-": line += "\n    🏛 " + t["underwriter"]
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
