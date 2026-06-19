import requests, os, re, json
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    result = {
        "recent_apply": [],
        "recent_approve": [],
        "upcoming_sub": [],
        "new_listing": [],
        "sub_table": [],
    }

    r = requests.get("https://www.38.co.kr/html/fund/index.htm?o=k",
                    headers=headers, timeout=20, verify=False)
    r.encoding = 'euc-kr'
    text = r.text
    print("38.co.kr:", r.status_code, len(text), "bytes")

    # HTML 태그 제거 후 라인 파싱
    clean = re.sub(r'<[^>]+>', '\n', text)
    clean = re.sub(r'&nbsp;', ' ', clean)
    clean = re.sub(r'&[a-zA-Z]+;', '', clean)
    lines = [l.strip() for l in clean.split('\n') if l.strip()]

    mode = None
    for line in lines:
        if '최근 IPO 청구종목' in line:
            mode = 'apply'
            continue
        elif '최근 IPO 승인종목' in line:
            mode = 'approve'
            continue
        elif 'IPO 공모주 청약일정' in line:
            mode = 'sub'
            continue
        elif 'IPO 신규상장 일정' in line:
            mode = 'listing'
            continue
        elif any(x in line for x in ['빨간색 매매', 'Copyright', '팝 니 다', '삽 니 다']):
            mode = None
            continue

        if mode:
            m = re.match(r'^(\d{2}/\d{2})\s+(.+)$', line)
            if m:
                date = m.group(1)
                name = m.group(2).strip()
                if mode == 'apply':
                    result["recent_apply"].append({"date": date, "name": name})
                elif mode == 'approve':
                    result["recent_approve"].append({"date": date, "name": name})
                elif mode == 'sub':
                    result["upcoming_sub"].append({"date": date, "name": name})
                elif mode == 'listing':
                    result["new_listing"].append({"date": date, "name": name})

    # 공모청약 테이블: 기업명 줄 다음에 날짜 패턴
    for i, line in enumerate(lines):
        m = re.match(r'^(2026\.\d{2}\.\d{2}~\d{2}\.\d{2})\s*([\-\d,]*)\s*([\d,~\-\s]*)\s*([\d\.:]+|[-]?)\s*(.*)$', line)
        if m and i > 0:
            name = lines[i-1]
            if len(name) < 2 or '스팩' in name or re.search(r'\d{4}', name):
                continue
            result["sub_table"].append({
                "name": name,
                "sub_date": m.group(1),
                "confirmed": m.group(2).strip() or "-",
                "range": m.group(3).strip() or "-",
                "competition": m.group(4).strip() or "-",
                "underwriter": m.group(5).strip()[:25] or "-",
            })

    print("청구:", len(result["recent_apply"]),
          "승인:", len(result["recent_approve"]),
          "청약일정:", len(result["upcoming_sub"]),
          "신규상장:", len(result["new_listing"]),
          "테이블:", len(result["sub_table"]))

    return result


def main():
    now_str = datetime.today().strftime("%Y-%m-%d %H:%M")
    seen = load_seen()
    data = get_38_data()

    # 파싱 결과 디버그
    debug = ["🔍 파싱 결과 디버그\n"]
    debug.append(f"청구: {[a['name'] for a in data['recent_apply'][:3]]}")
    debug.append(f"승인: {[a['name'] for a in data['recent_approve'][:3]]}")
    debug.append(f"청약: {[a['name'] for a in data['upcoming_sub'][:3]]}")
    debug.append(f"상장: {[a['name'] for a in data['new_listing'][:3]]}")
    debug.append(f"테이블({len(data['sub_table'])}): {[s['name'] for s in data['sub_table'][:3]]}")
    send_telegram("\n".join(debug))

    # 새 청구/승인 감지
    new_applies = [a for a in data["recent_apply"] if "apply_" + a["name"] not in seen]
    new_approves = [a for a in data["recent_approve"] if "approve_" + a["name"] not in seen]

    for a in new_applies:
        send_telegram("📨 <b>[KIND] 신규 예비심사 청구</b>\n\n🏢 " + a["name"] + " (" + a["date"] + ")\n🔗 <a href=\"https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain\">KIND 예비심사 현황</a>")
        seen.add("apply_" + a["name"])

    for a in new_approves:
        send_telegram("✅ <b>[KIND] 예비심사 승인</b>\n\n🏢 " + a["name"] + " (" + a["date"] + ")\n🔗 <a href=\"https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain\">KIND 예비심사 현황</a>")
        seen.add("approve_" + a["name"])

    has_new = bool(new_applies or new_approves)
    status = "위 항목 외 추가 신규 없음" if has_new else "오늘 새 청구/승인 없음"

    L = ["✅ <b>IPO Alert 실행 완료</b> (" + now_str + ")", status, ""]

    applies = [a for a in data["recent_apply"] if "스팩" not in a["name"]][:3]
    L.append("📨 <b>최근 예비심사 청구</b>")
    for a in applies:
        L.append("  " + a["date"] + " " + a["name"])
    if not applies: L.append("  (없음)")
    L.append("")

    approves = [a for a in data["recent_approve"] if "스팩" not in a["name"]][:3]
    L.append("✅ <b>최근 예비심사 승인</b>")
    for a in approves:
        L.append("  " + a["date"] + " " + a["name"])
    if not approves: L.append("  (없음)")
    L.append("")

    subs = [s for s in data["sub_table"] if "스팩" not in s["name"]][:3]
    L.append("📋 <b>최근 IPO 공모기업</b>")
    if subs:
        for s in subs:
            line = "  • <b>" + s["name"] + "</b> | 청약: " + s["sub_date"]
            if s["range"] and s["range"] != "-": line += "\n    💰 " + s["range"]
            if s["confirmed"] and s["confirmed"] != "-": line += " → 확정: " + s["confirmed"]
            if s["competition"] and s["competition"] != "-": line += " | 경쟁률: " + s["competition"]
            if s["underwriter"] and s["underwriter"] != "-": line += "\n    🏛 " + s["underwriter"]
            L.append(line)
    else:
        L.append("  (없음)")
    L.append("")

    upcoming = [u for u in data["upcoming_sub"] if "스팩" not in u["name"]][:4]
    L.append("🗓 <b>공모청약 일정</b>")
    for u in upcoming:
        L.append("  " + u["date"] + " " + u["name"])
    if not upcoming: L.append("  (없음)")
    L.append("")

    listings = [nl for nl in data["new_listing"] if "스팩" not in nl["name"]][:4]
    L.append("🔔 <b>신규상장 일정</b>")
    for nl in listings:
        L.append("  " + nl["date"] + " " + nl["name"])
    if not listings: L.append("  (없음)")

    send_telegram("\n".join(L))
    save_seen(seen)
    print("완료")


if __name__ == "__main__":
    main()
