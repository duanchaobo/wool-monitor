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
import re
import time
import base64
import hashlib
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

    # 价格显示（区分淘宝/京东）
    if source == "淘宝":
        # 淘宝页面价格：zk_final_price(现价) → final_promotion_price(到手价)
        # 折扣 = 1 - 到手价/现价
        p = price.replace("¥", "").replace("￥", "")              # 现价 = zk_final_price
        final = predict_price.replace("¥", "").replace("￥", "") if predict_price else ""  # 到手价 = final_promotion_price
        cur_f = float(p) if p else 0
        final_f = float(final) if final else 0
        if final and final != p and cur_f > 0 and final_f > 0:
            d_pct = int(round((1 - final_f / cur_f) * 100))
            msg_lines.append(f"💰 ¥{p} → ¥{final}  [{d_pct}%OFF]")
        else:
            msg_lines.append(f"💰 ¥{p}")
    elif old_price:
        # 京东：原价 → 现价
        p = price.replace("¥", "").replace("￥", "")
        op = old_price.replace("¥", "").replace("￥", "")
        type_hint = f"（{price_type}价）" if price_type else ""
        if coupon_discount > 0:
            msg_lines.append(f"💰 京东价{op} → ¥{p}{type_hint}{discount_str}")
        else:
            msg_lines.append(f"💰 {op} → ¥{p}{type_hint}{discount_str}")
    else:
        # 无原价，只显示现价
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

    # 使用 text 类型而非 markdown：
    # - markdown 在企微是卡片消息，转发到微信会显示"不支持的消息类型"
    # - text 是纯文本，企微和微信都能正常显示和转发
    payload = {
        "msgtype": "text",
        "text": {
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
            # 推送成功后，紧跟发送商品图片（叠加优惠信息）
            push_image(webhook_url, deal.get("img_url", ""), deal=deal)
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


def _load_font(size):
    """加载中文字体（兼容 macOS/Linux）"""
    from PIL import ImageFont
    font_paths = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
    return ImageFont.load_default()


def _draw_text_stroke(draw, pos, text, font, fill, stroke_color, stroke_width=3):
    """绘制描边文字（先画白色边框，再画红色主体）"""
    x, y = pos
    # 描边：向8个方向偏移绘制白色边框
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=stroke_color)
    # 主体文字
    draw.text(pos, text, font=font, fill=fill)


def _add_text_overlay(img, deal):
    """在图片上叠加居中信息：现价→到手价、优惠力度"""
    from PIL import Image, ImageDraw

    w, h = img.size
    # 蒙条高度不超过图片30%（避免遮挡商品主体）
    bar_h = int(h * 0.30)
    # 字体大小在蒙条内自适应（2行文字）
    font_size = max(36, min(int(bar_h * 0.35), int(w * 0.10)))
    line_h = font_size + 14

    # 半透明黑色底色条（覆盖底部）
    img = img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    draw_ov.rectangle([(0, h - bar_h), (w, h)], fill=(0, 0, 0, 180))
    img = Image.alpha_composite(img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    font = _load_font(font_size)

    # 解析价格：现价=price(zk_final_price)，到手价=predict_price(final_promotion_price)
    current = str(deal.get("price", "")).replace("¥", "").replace("￥", "")
    final = str(deal.get("predict_price", "")).replace("¥", "").replace("￥", "")

    # 折扣 = 1 - 到手价/现价
    cur_f = float(current) if current else 0
    final_f = float(final) if final else 0
    off_pct = 0
    if cur_f > 0 and final_f > 0 and cur_f > final_f:
        off_pct = int(round((1 - final_f / cur_f) * 100))

    # 文字行（居中）
    if final and final != current:
        lines = [
            (f"¥{current} → ¥{final}", (255, 255, 255)),  # 白色：现价→到手价
            (f"{off_pct}%OFF", (255, 230, 0)),              # 黄色：折扣
        ]
    else:
        lines = [(f"现价 ¥{current}", (255, 255, 255))]  # 白色

    start_y = h - bar_h + (bar_h - len(lines) * line_h) // 2  # 垂直居中
    for i, (text, color) in enumerate(lines):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        x = (w - tw) // 2  # 居中
        y = start_y + i * line_h
        _draw_text_stroke(draw, (x, y), text, font, fill=color, stroke_color=(0, 0, 0), stroke_width=5)

    return img


def push_image(webhook_url, img_url, deal=None):
    """
    推送一条图片消息（紧跟在优惠消息后）
    下载图片 → 叠加优惠信息文字 → 转 PNG → base64 发送
    """
    if not img_url:
        return

    try:
        # 下载图片
        resp = requests.get(
            img_url, timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://s.click.taobao.com/"
            }
        )
        if resp.status_code != 200 or len(resp.content) < 500:
            return

        from io import BytesIO
        from PIL import Image

        img = Image.open(BytesIO(resp.content)).convert("RGB")

        # 限制图片最大尺寸（企微限制2MB，过大会报invalid image size）
        max_size = 1200
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        # 叠加优惠信息文字
        if deal:
            img = _add_text_overlay(img, deal)

        # 转 PNG（限制文件大小<2MB）
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        img_bytes = buf.getvalue()
        # 如果还是太大，转 JPEG 压缩
        if len(img_bytes) > 1.8 * 1024 * 1024:
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=80, optimize=True)
            img_bytes = buf.getvalue()

        img_base64 = base64.b64encode(img_bytes).decode()
        md5_hash = hashlib.md5(img_bytes).hexdigest()

        payload = {
            "msgtype": "image",
            "image": {
                "base64": img_base64,
                "md5": md5_hash
            }
        }

        resp = requests.post(webhook_url, json=payload, timeout=15)
        result = resp.json()
        if result.get("errcode") == 0:
            print(f"  [📷 图片发送成功]")
        else:
            print(f"  [📷 图片发送失败] {result.get('errmsg', '')}")
    except Exception as e:
        print(f"  [📷 图片异常] {e}")


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
