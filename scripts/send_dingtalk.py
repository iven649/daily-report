import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
from datetime import datetime


def sign_dingtalk(secret: str):
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign


def build_action_card(report_url: str):
    today = datetime.now().strftime("%Y-%m-%d")

    return {
        "msgtype": "actionCard",
        "actionCard": {
            "title": f"📊 分销日报 {today}",
            "text": (
                f"### 日报已生成\n\n"
                f"- 日期：{today}\n"
                f"- 点击下方按钮查看日报\n"
                f"- 备用链接：[打开日报]({report_url})\n\n"
                f"> 日报"
            ),
            "singleTitle": "打开日报",
            "singleURL": report_url
        }
    }


def send():
    webhook = os.getenv("DINGTALK_WEBHOOK")
    secret = os.getenv("DINGTALK_SECRET")
    report_url = os.getenv("REPORT_URL")

    if not webhook:
        raise ValueError("Missing environment variable: DINGTALK_WEBHOOK")
    if not secret:
        raise ValueError("Missing environment variable: DINGTALK_SECRET")
    if not report_url:
        raise ValueError("Missing environment variable: REPORT_URL")

    timestamp, sign = sign_dingtalk(secret)
    signed_url = f"{webhook}&timestamp={timestamp}&sign={sign}"

    payload = build_action_card(report_url)

    response = requests.post(
        signed_url,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=20
    )
    response.raise_for_status()

    data = response.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"DingTalk push failed: {data}")

    print("[OK] DingTalk pushed successfully.")


if __name__ == "__main__":
    send()
