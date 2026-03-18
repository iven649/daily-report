import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_conf():
    with open(ROOT / "config/local_settings.json", "r", encoding="utf-8") as f:
        return json.load(f)

def sign(secret):
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(secret.encode(), string_to_sign.encode(), hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign

def send():
    conf = load_conf()

    webhook = conf["dingtalk_webhook"]
    secret = conf["dingtalk_secret"]
    url = conf["report_url"]

    timestamp, sign_code = sign(secret)
    full_url = f"{webhook}&timestamp={timestamp}&sign={sign_code}"

    today = datetime.now().strftime("%Y-%m-%d")

    data = {
        "msgtype": "actionCard",
        "actionCard": {
            "title": f"📊 分销日报 {today}",
            "text": f"### 日报已生成\n\n点击查看👇\n\n> 日报",
            "singleTitle": "打开日报",
            "singleURL": url
        }
    }

    r = requests.post(full_url, json=data)
    print(r.text)

if __name__ == "__main__":
    send()