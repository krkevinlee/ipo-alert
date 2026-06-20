import requests, os, re, json, ssl
from datetime import datetime
import urllib3
urllib3.disable_warnings()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg, parse_mode=""):
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

session = make_session()
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
r = session.get("https://www.38.co.kr/html/fund/index.htm?o=k",
                headers=headers, timeout=20, verify=False)
r.encoding = 'euc-kr'

# HTML 태그 제거
text = re.sub(r'<[^>]+>', '\n', r.text)
text = re.sub(r'&nbsp;', ' ', text)
text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)
lines = [l.strip() for l in text.split('\n') if l.strip()]

# 우측 사이드바 영역 (청구/승인 목록) 찾아서 전송
output = []
capture = False
for line in lines:
    if '최근 IPO 청구종목' in line:
        capture = True
    if capture:
        output.append(line)
    if capture and len(output) > 40:
        break

send("=== 38.co.kr 원본 텍스트 ===\n" + "\n".join(output))

# 공모청약 테이블 주변 50줄도 전송
output2 = []
capture2 = False
for line in lines:
    if '공모주 청약일정' in line:
        capture2 = True
    if capture2:
        output2.append(line)
    if capture2 and len(output2) > 50:
        break

send("=== 공모청약 테이블 원본 ===\n" + "\n".join(output2[:50]))
