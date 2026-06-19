import requests
import os
from datetime import datetime

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send_telegram(msg):
    url = "https://api.telegram.org/bot" + BOT_TOKEN + "/sendMessage"
    r = requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    print("텔레그램 발송:", r.status_code, r.text[:200])
    return r.status_code

now = datetime.today().strftime("%Y-%m-%d %H:%M")
print("실행 시작:", now)

try:
    status = send_telegram("🔧 IPO Alert 테스트\n실행시간: " + now)
    print("발송 완료, 상태코드:", status)
except Exception as e:
    print("발송 오류:", e)
