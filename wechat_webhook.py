"""
wechat_webhook.py - 企业微信群机器人推送

Webhook 地址从环境变量读取：
  WECHAT_WEBHOOK_URL

设置方法：
1. 微信群 → 右上角「...」→ 群机器人 → 添加企业微信群机器人
2. 复制 Webhook 地址
3. 设为环境变量或在 .env 文件中配置
"""

import os
import requests
import json
from datetime import datetime


def push_deal(deal):
    """推送一条优惠信息到微信群"""
    webhook_url = os.environ.get("WECHAT_WEBHOOK_URL", "")
    if not webhook_url:
        print("[推送] 未配置 Webhook URL，跳过推送")
        return

    discount_str = ""
    if deal.get("discount") and deal["discount"] > 0:
        d = int(deal["discount"] * 100)
        if d >= 90:
            d = 100 - d
        discount_str = f" ▸ {d}% OFF"

    tag = deal.get("tag", "")
    title = deal.get("title", "")
    price = deal.get("price", "")
    old_price = deal.get("old_price", "")
    url = deal.get("url", "")
    source = deal.get("source", "")

    icon = "🟢"
    if "历史低价" in tag or "绝对值" in tag:
        icon = "🔴"
    elif "神价格" in tag or "神价" in tag:
        icon = "🔴"
    elif "限时" in tag or "秒杀" in tag:
        icon = "🟠"
    elif "bug" in tag.lower() or "漏洞" in tag:
        pass

    msg_lines = [
        f"{icon} 【{icon_to_name(icon)}】",
        f"📦 {title}",
    ]

    if old_price:
        # price/old_price 可能已带 ¥ 前缀
        p = price.replace("¥", "").replace("￥", "")
        op = old_price.replace("¥", "").replace("￥", "")
        msg_lines.append(f"💰 {op} → ¥{p}{discount_str}")
    else:
        p = price.replace("¥", "").replace("￥", "")
        msg_lines.append(f"💰 ¥{p}")

    if source:
        msg_lines.append(f"🏪 来源: {source}")

    # 优惠券信息
    coupon_url = deal.get("coupon_url", "")
    if coupon_url:
        msg_lines.append(f"🎫 [点击领券]({coupon_url})")

    # 商品购买链接
    if url:
        msg_lines.append(f"🛒 [购买链接]({url})")

    msg_lines.append(f"⏰ {datetime.now().strftime('%H:%M')}")

    content = "\n".join(msg_lines)

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }

    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )
        result = resp.json()
        if result.get("errcode") == 0:
            print(f"[✅ 推送成功] {title[:30]}...")
            return True
        else:
            print(f"[❌ 推送失败] {result}")
            return False
    except Exception as e:
        print(f"[❌ 推送异常] {e}")
        return False


def push_batch(deals):
    """批量推送，自动限速（企微限制每分钟20条）"""
    if not deals:
        print("[推送] 无数据可推")
        return

    import time
    print(f"\n推送 {len(deals)} 条信息到微信群...")
    success = 0
    fail = 0

    for i, deal in enumerate(deals):
        # 每推 15 条暂停 60 秒，避免频率限制
        if i > 0 and i % 15 == 0:
            print(f"  ⏸ 已推 {i} 条，暂停 60 秒...")
            time.sleep(60)

        result = push_deal(deal)
        if result:
            success += 1
        else:
            fail += 1

        time.sleep(3)  # 每条间隔 3 秒

    print(f"\n推送完成: 成功 {success} 条, 失败 {fail} 条")


def icon_to_name(icon):
    """图标转文字"""
    mapping = {
        "🔴": "神价/历史低价",
        "🟠": "限时秒杀",
        "🟡": "好价",
        "🟢": "普通优惠",
    }
    return mapping.get(icon, "优惠信息")


if __name__ == "__main__":
    # 测试推送
    test_deal = {
        "source": "测试",
        "title": "【测试】这是一条测试优惠信息",
        "price": "99.0",
        "old_price": "299.0",
        "discount": 0.67,
        "url": "https://example.com/test",
        "tag": "历史低价",
        "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    push_deal(test_deal)
