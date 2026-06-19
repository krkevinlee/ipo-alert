import requests, os, re
from datetime import datetime

DART_KEY = os.environ["DART_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg}, timeout=10)

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. 38커뮤니케이션 테스트
try:
    r = requests.get("https://www.38.co.kr/html/fund/index.htm?o=k", headers=headers, timeout=10)
    send("38.co.kr 응답: " + str(r.status_code) + " / 길이: " + str(len(r.text)) + "\n앞200자:\n" + r.text[:200])
except Exception as e:
    send("38.co.kr 오류: " + str(e))

# 2. ipostock 테스트
try:
    r2 = requests.get("https://www.ipostock.co.kr/sub03/ipo_new.asp", headers=headers, timeout=10)
    send("ipostock 응답: " + str(r2.status_code) + " / 길이: " + str(len(r2.text)))
except Exception as e:
    send("ipostock 오류: " + str(e))

# 3. IPO 전문 - 한국거래소 IPO 정보
try:
    r3 = requests.get("https://listing.krx.co.kr/contents/STA/07/07010100/STA07010100.jsp", headers=headers, timeout=10)
    send("KRX listing 응답: " + str(r3.status_code) + " / 길이: " + str(len(r3.text)))
except Exception as e:
    send("KRX 오류: " + str(e))
