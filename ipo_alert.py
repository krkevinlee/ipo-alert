import requests, os, re, json
from datetime import datetime

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
    import urllib3
    urllib3.disable_warnings()

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

    try:
        r = requests.get("https://www.38.co.kr/html/fund/index.htm?o=k",
                        headers=headers, timeout=20, verify=False)
        r.encoding = 'euc-kr'
        text = r.text
        print("38.co.kr 응답:", r.status_code, "길이:", len(text))

        # 텍스트 기반 파싱 (get_page_text 결과와 동일한 구조)
        # "최근 IPO 청구종목" 이후 줄 파싱
        lines = text.replace('\r', '').split('\n')
        lines = [re.sub(r'<[^>]+>', '', l).strip() for l in lines]
        lines = [l for l in lines if l]

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
            elif '빨간색 매매' in line or 'Copyright' in line:
                mode = None
                continue

            m = re.match(r'^(\d{2}/\d{2})\s+(.+)$', line)
            if m and mode:
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

        # 공모청약 테이블 파싱
        # 패턴: "기업명 2026.MM.DD~MM.DD 확정가 희망가범위 경쟁률 주간사"
        table_pattern = re.compile(
            r'([가-힣A-Za-z0-9\(\)\.·\s]+?)\s+(2026\.\d{2}\.\d{2}~\d{2}\.\d{2})\s+([\-\d,]+)\s+([\d,~\s]+)\s+([\d\.:]+|[-])\s+([가-힣A-Za-z,\s]+)'
        )
        for line in lines:
            m = table_pattern.match(line)
            if m:
                name = m.group(1).strip()
                if '스팩' in name:
                    continue
                result["sub_table"].append({
                    "name": name,
                    "sub_date": m.group(2),
                    "confirmed": m.group(3).strip(),
                    "range": m.group(4).strip(),
                    "competition": m.group(5).strip(),
                    "underwriter": m.group(6).strip()[:20],
                })

        # 테이블 파싱 안 됐으면 라인 기반으로 시도
        if not result["sub_table"]:
            for i, line in enumerate(lines):
                if re.search(r'2026\.\d{2}\.\d{2}~\d{2}\.\d{2}', line):
                    # 이전 줄이 기업명
                    if i > 0:
                        name = lines[i-1]
                        if '스팩' in name or len(name) < 2:
                            continue
                        parts = line.split()
                        result["sub_table"].append({
                            "name": name,
                            "sub_date": parts[0] if parts else line,
                            "confirmed": parts[1] if len(parts) > 1 else "-",
                            "range": parts[2] if len(parts) > 2 else "-",
                            "competition": parts[3] if len(parts) > 3 else "-",
                            "underwriter": parts[4] if len(parts) > 4 else "-",
                        })

        print("청구:", len(result["recent_apply"]), "승인:", len(result["recent_approve"]),
              "청약일정:", len(result["upcoming_sub"]), "신규상장:", len(result["new_listing"]),
              "테이블:", len(result["sub_table"]))

    except Exception as e:
        print("38.co.kr 오류:", e)
        import traceback
        traceback.print_exc()

    return result


def main():
    now_str = datetime.today().strftime("%Y-%m-%d %H:%M")
    print("=== 실행:", now_str, "===")
    seen = load_seen()
    data = get_38_data()

    # 새 청구/승인 감지
    new_applies = [a for a in data["recent_apply"] if "apply_" + a["name"] not in seen]
    new_approves = [a for a in data["recent_approve"] if "approve_" + a["name"] not in seen]

    # 새 항목 있으면 즉시 알림
    for a in new_applies:
        send_telegram("📨 <b>[KIND] 신규 예비심사 청구</b>\n\n🏢 " + a["name"] + " (" + a["date"] + ")\n\n🔗 <a href=\"https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain\">KIND 예비심사 현황</a>")
        seen.add("apply_" + a["name"])

    for a in new_approves:
        send_telegram("✅ <b>[KIND] 예비심사 승인</b>\n\n🏢 " + a["name"] + " (" + a["date"] + ")\n\n🔗 <a href=\"https://kind.krx.co.kr/listinvstg/listinvstgcom.do?method=searchListInvstgCorpMain\">KIND 예비심사 현황</a>")
        seen.add("approve_" + a["name"])

    # 매일 확인 메시지
    has_new = bool(new_applies or new_approves)
    status = "위 항목 외 추가 신규 없음" if has_new else "오늘 새 청구/승인 없음"

    L = ["✅ <b>IPO Alert 실행 완료</b> (" + now_str + ")", status, ""]

    # 최근 청구 (스팩 제외)
    applies = [a for a in data["recent_apply"] if "스팩" not in a["name"]][:3]
    L.append("📨 <b>최근 예비심사 청구</b>")
    if applies:
        for a in applies:
            L.append("  " + a["date"] + " " + a["name"])
    else:
        L.append("  (없음)")
    L.append("")

    # 최근 승인 (스팩 제외)
    approves = [a for a in data["recent_approve"] if "스팩" not in a["name"]][:3]
    L.append("✅ <b>최근 예비심사 승인</b>")
    if approves:
        for a in approves:
            L.append("  " + a["date"] + " " + a["name"])
    else:
        L.append("  (없음)")
    L.append("")

    # 공모청약 상세 테이블 (스팩 제외, 최근 3개)
    subs = [s for s in data["sub_table"] if "스팩" not in s["name"]][:3]
    L.append("📋 <b>최근 IPO 공모기업 (증권신고서 발행)</b>")
    if subs:
        for s in subs:
            line = "  • <b>" + s["name"] + "</b> | 청약: " + s["sub_date"]
            if s["range"] and s["range"] != "-":
                line += "\n    💰 " + s["range"]
            if s["confirmed"] and s["confirmed"] != "-":
                line += " → 확정: " + s["confirmed"]
            if s["competition"] and s["competition"] != "-":
                line += " | 경쟁률: " + s["competition"]
            if s["underwriter"] and s["underwriter"] != "-":
                line += "\n    🏛 " + s["underwriter"]
            L.append(line)
    else:
        L.append("  (없음)")
    L.append("")

    # 다가오는 청약일정
    upcoming = [u for u in data["upcoming_sub"] if "스팩" not in u["name"]][:4]
    L.append("🗓 <b>공모청약 일정</b>")
    if upcoming:
        for u in upcoming:
            L.append("  " + u["date"] + " " + u["name"])
    else:
        L.append("  (없음)")
    L.append("")

    # 신규상장
    listings = [nl for nl in data["new_listing"] if "스팩" not in nl["name"]][:4]
    L.append("🔔 <b>신규상장 일정</b>")
    if listings:
        for nl in listings:
            L.append("  " + nl["date"] + " " + nl["name"])
    else:
        L.append("  (없음)")

    send_telegram("\n".join(L))
    save_seen(seen)
    print("완료")


if __name__ == "__main__":
    main()
