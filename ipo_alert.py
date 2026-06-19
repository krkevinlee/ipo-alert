import requests, os, json
from datetime import datetime, timedelta

DART_KEY = os.environ["DART_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

def send(msg):
    requests.post("https://api.telegram.org/bot"+BOT_TOKEN+"/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg}, timeout=10)

end = datetime.today()
start = end - timedelta(days=30)

# C001: 지분증권 신고서 전체
r = requests.get("https://opendart.fss.or.kr/api/list.json", params={
    "crtfc_key": DART_KEY,
    "pblntf_ty": "C",
    "pblntf_detail_ty": "C001",
    "bgn_de": start.strftime("%Y%m%d"),
    "end_de": end.strftime("%Y%m%d"),
    "page_count": 40,
}, timeout=10)

items = r.json().get("list", [])

# corp_cls: Y=유가증권, K=코스닥, N=코넥스, E=기타
# 미상장(IPO 예정) 기업은 corp_cls가 없거나 빈 값
ipo_candidates = []
for i in items:
    nm = i.get("report_nm", "")
    cls = i.get("corp_cls", "")
    # 정정/소액공모/채무증권 제외
    if any(x in nm for x in ["정정", "소액공모", "채무", "투자설명서", "발행실적"]):
        continue
    # 미상장 기업(corp_cls 없음) = 신규 IPO
    if cls not in ["Y", "K", "N"]:
        ipo_candidates.append(i)
    
lines = [f"IPO 후보 (미상장 기업, 최근30일)", ""]
for i in ipo_candidates:
    lines.append(f"{i['corp_name']} | {i['report_nm']} | cls={i.get('corp_cls','없음')} | {i['rcept_dt']}")

if not ipo_candidates:
    lines.append("(없음)")
    # 전체 corp_cls 분포도 보여주기
    lines.append("")
    lines.append("전체 corp_cls 분포:")
    from collections import Counter
    cls_cnt = Counter(i.get("corp_cls","없음") for i in items)
    for k, v in cls_cnt.items():
        lines.append(f"  {k}: {v}건")

send("\n".join(lines))
