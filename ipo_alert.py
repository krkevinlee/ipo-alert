import requests, os, re, json, traceback
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


def get_38():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = requests.get("https://www.38.co.kr/html/fund/index.htm?o=k",
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

    # 테이블 파싱: 날짜 패턴 앞 줄이 기업명
    for i, line in enumerate(lines):
        if re.match(r'^2026\.\d{2}\.\d{2}~\d{2}\.\d{2}', line) and i > 0:
            name = lines[i-1]
            if len(name) < 2 or '스팩' in name or re.search(r'\d{4}\.', name): continue
            parts = line.split()
            result["table"].append({
                "name": name,
                "date": parts[0],
                "confirmed": parts[1] if len(parts) > 1 else "-",
                "range": parts[2] if len(parts) > 2 else "-",
                "competition": parts[3] if len(parts) > 3 else "-",
                "underwriter": " ".join(parts[4:])[:25] if len(parts) > 4 else "-",
            })

    return result


def main():
    now = datetime.today().strftime("%Y-%m-%d %H:%M")
    seen = load_seen()

    try:
        data = get_38()
        send("🔍 디버그: 청구=" + str(len(data["apply"])) +
             " 승인=" + str(len(data["approve"])) +
             " 테이블=" + str(len(data["table"])) +
             "\n청구목록: " + str([a["name"] for a in data["apply"][:3]]) +
             "\n승인목록: " + str([a["name"] for a in data["approve"][:3]]) +
             "\n테이블: " + str([t["name"] for t in data["table"][:3]]), parse_mode="")
    except Exception as e:
        send("❌ 38.co.kr 파싱 오류:\n" + traceback.format_exc()[-500:], parse_mode="")
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

    # 일일 요약
    has_new = bool(new_apply or new_approve)
    L = ["✅ <b>IPO Alert</b> (" + now + ")",
         "위 항목 외 추가 없음" if has_new else "오늘 새 청구/승인 없음", ""]

    apply_f = [a for a in data["apply"] if "스팩" not in a["name"]][:3]
    L.append("📨 <b>최근 예비심사 청구</b>")
    for a in apply_f: L.append("  " + a["date"] + " " + a["name"])
    if not apply_f: L.append("  (없음)")
    L.append("")

    approve_f = [a for a in data["approve"] if "스팩" not in a["name"]][:3]
    L.append("✅ <b>최근 예비심사 승인</b>")
    for a in approve_f: L.append("  " + a["date"] + " " + a["name"])
    if not approve_f: L.append("  (없음)")
    L.append("")

    table_f = [t for t in data["table"] if "스팩" not in t["name"]][:3]
    L.append("📋 <b>최근 IPO 공모기업</b>")
    if table_f:
        for t in table_f:
            line = "  • <b>" + t["name"] + "</b> | 청약: " + t["date"]
            if t["range"] != "-": line += "\n    💰 " + t["range"]
            if t["confirmed"] != "-": line += " → 확정: " + t["confirmed"]
            if t["competition"] != "-": line += " | 경쟁률: " + t["competition"]
            if t["underwriter"] != "-": line += "\n    🏛 " + t["underwriter"]
            L.append(line)
    else:
        L.append("  (없음)")
    L.append("")

    sub_f = [s for s in data["sub"] if "스팩" not in s["name"]][:4]
    L.append("🗓 <b>공모청약 일정</b>")
    for s in sub_f: L.append("  " + s["date"] + " " + s["name"])
    if not sub_f: L.append("  (없음)")
    L.append("")

    list_f = [l for l in data["listing"] if "스팩" not in l["name"]][:4]
    L.append("🔔 <b>신규상장 일정</b>")
    for l in list_f: L.append("  " + l["date"] + " " + l["name"])
    if not list_f: L.append("  (없음)")

    send("\n".join(L))
    save_seen(seen)
    print("완료")


if __name__ == "__main__":
    main()
