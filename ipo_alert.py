import requests, os, re
from datetime import datetime

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg}, timeout=10)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

results = []

# 38커뮤니케이션 - 공모주 일정
try:
    r = requests.get("https://www.38.co.kr/html/fund/index.htm?o=k", 
                     headers=headers, timeout=20)
    results.append(f"38.co.kr: {r.status_code} / {len(r.text)}bytes")
    if r.status_code == 200 and len(r.text) > 100:
        # 기업명 파싱 시도
        corps = re.findall(r'<td[^>]*class="[^"]*co_name[^"]*"[^>]*>([^<]+)', r.text)
        if not corps:
            corps = re.findall(r'fund/detail[^"]+">([^<]+)</a>', r.text)
        results.append(f"  기업명: {corps[:5]}")
        results.append(f"  본문 앞 300자: {r.text[:300]}")
except Exception as e:
    results.append(f"38.co.kr 오류: {e}")

# ipostock
try:
    r2 = requests.get("https://www.ipostock.co.kr/sub03/ipo_new.asp",
                      headers=headers, timeout=20)
    results.append(f"ipostock: {r2.status_code} / {len(r2.text)}bytes")
    if r2.status_code == 200 and len(r2.text) > 100:
        results.append(f"  본문 앞 200자: {r2.text[:200]}")
except Exception as e:
    results.append(f"ipostock 오류: {e}")

# eipo.co.kr (한국예탁결제원 전자공모)
try:
    r3 = requests.get("https://eipo.co.kr/subscription/pbsrc/newListIpo.do",
                      headers=headers, timeout=20)
    results.append(f"eipo.co.kr: {r3.status_code} / {len(r3.text)}bytes")
except Exception as e:
    results.append(f"eipo 오류: {e}")

send("\n".join(results))
