import requests, os, re, json, ssl
from datetime import datetime
import urllib3
urllib3.disable_warnings()

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg, parse_mode=""):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg[:4000], "parse_mode": parse_mode}, timeout=10)

def make_session():
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context
    class A(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            ctx = create_urllib3_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.set_ciphers('DEFAULT:@SECLEVEL=0')
            kwargs['ssl_context'] = ctx
            super().init_poolmanager(*args, **kwargs)
    s = requests.Session()
    s.mount('https://', A())
    return s

session = make_session()
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 여러 URL 시도
urls = [
    "https://www.38.co.kr/html/fund/index.htm?o=k&n=0",
    "https://www.38.co.kr/html/fund/subscribe.htm",
    "https://www.38.co.kr/html/fund/index.htm?o=s",
]

for url in urls:
    try:
        r = session.get(url, headers=headers, timeout=15, verify=False)
        r.encoding = 'euc-kr'
        text = re.sub(r'<[^>]+>', '\n', r.text)
        text = re.sub(r'&nbsp;', ' ', text)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        # 날짜 패턴 있는 줄 찾기
        date_lines = [l for l in lines if re.search(r'2026\.\d{2}\.\d{2}', l)]
        send(f"URL: {url}\n상태: {r.status_code}\n날짜포함줄({len(date_lines)}개):\n" + "\n".join(date_lines[:10]))
    except Exception as e:
        send(f"URL: {url}\n오류: {str(e)[:100]}")
