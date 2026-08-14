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
    elif "大额" in tag or "店铺券" in tag:
        icon = "🟠"
    elif "搜:" in tag or "推荐" in tag:
        icon = "🔵"
    elif "bug" in tag.lower() or "漏洞" in tag:
        pass

    msg_lines = [
        f"{icon} 【{icon_to_name(icon)}】",
        f"📦 {title}",
    ]

    coupon_discount = deal.get("coupon_discount", 0)
    coupon_quota = deal.get("coupon_quota", 0)
    price_type = deal.get("price_type", "")
    predict_price = deal.get("predict_price", "")
    commission_rate = deal.get("commission_rate", "")
    shop = deal.get("shop", "")
    sales = deal.get("sales", "")
    tags = deal.get("tags", "")

    if old_price:
        # price/old_price 可能已带 ¥ 前缀
        p = price.replace("¥", "").replace("￥", "")
        op = old_price.replace("¥", "").replace("￥", "")
        type_hint = f"（{price_type}价）" if price_type else ""
        if coupon_discount > 0:
            msg_lines.append(f"💰 京东价{op} → ¥{p}{type_hint}{discount_str}")
        else:
            msg_lines.append(f"💰 {op} → ¥{p}{type_hint}{discount_str}")
    else:
        p = price.replace("¥", "").replace("￥", "")
        price_parts = [f"¥{p}"]
        if predict_price:
            price_parts.append(f"到手{predict_price}")
        msg_lines.append(f"💰 {' / '.join(price_parts)}")

    # 店铺信息
    if shop:
        shop_parts = [shop]
        if sales:
            shop_parts.append(f"月销{sales}")
        if commission_rate:
            shop_parts.append(f"佣金{commission_rate}")
        msg_lines.append(f"🏪 {' | '.join(shop_parts)}")

    # 促销标签
    if tags:
        msg_lines.append(f"🏷 {tags}")

    if source:
        msg_lines.append(f"🏪 来源: {source}")

    # 优惠券信息
    coupon_url = deal.get("coupon_url", "")
    if coupon_url and coupon_discount > 0:
        if coupon_quota > 0:
            msg_lines.append(f"🎫 [领取满{int(coupon_quota)}减{int(coupon_discount)}券]({coupon_url})")
        else:
            msg_lines.append(f"🎫 [领取¥{int(coupon_discount)}券]({coupon_url})")

    # 京东价格可能存在多层优惠叠加，标注提示
    source = deal.get("source", "")
    if source == "京东" and price != old_price:
        msg_lines.append("_⚠️ 京东商品有隐藏优惠，实际到手价以页面为准_")

    # 淘宝商品：生成淘口令（解决企微无法跳转s.click.taobao.com的问题）
    taokouling = deal.get("taokouling", "")
    if source == "淘宝" and not taokouling:
        # 尝试实时生成淘口令
        try:
            from tb_api import generate_taokouling
            taokouling = generate_taokouling(title, url)
        except:
            pass

    if taokouling:
        # 淘口令格式：'18￥ CZ028 xxxx￥ https://m.tb.cn/...  商品标题'
        # 提取纯淘口令（￥xxxx￥部分）
        import re
        tk_match = re.search(r'(￥\s*\S+?\s*￥)', taokouling)
        tk_code = tk_match.group(1).strip() if tk_match else taokouling
        msg_lines.append(f"🔑 淘口令：`{tk_code}`")
        msg_lines.append(f"_复制本条消息，打开淘宝App自动跳转_")
    elif url:
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
        "🟠": "大额店铺券",
        "🟡": "好价",
        "🟢": "普通优惠",
        "🔵": "淘宝好物推荐",
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
