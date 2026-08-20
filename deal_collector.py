"""
deal_collector.py - 优惠信息采集器

数据来源：
1. 预置热门优惠模板（确保始终有内容推送）
2. LLM 生成（方舟火山 API，需配置 ARK_API_KEY）
3. 什么值得买爬虫（反爬严重，默认关闭）

策略：先尝试 LLM 生成，失败则用预置模板数据
"""

import requests
import json
import re
import os
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ============ 自定义推广商品 ============
PROMOTED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "promoted_deals.json")


def load_promoted_deals():
    """加载自定义推广商品列表"""
    if not os.path.exists(PROMOTED_FILE):
        return []
    try:
        with open(PROMOTED_FILE, "r", encoding="utf-8") as f:
            deals = json.load(f)
        active = [d for d in deals if d.get("active", True)]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        for d in active:
            d["time"] = now_str
            pn = extract_number(d.get("price", "0"))
            opn = extract_number(d.get("old_price", "0"))
            d["discount"] = round(1 - pn / opn, 2) if pn > 0 and opn > 0 else 0
        print(f"[自定义推广] 加载 {len(active)} 条（共 {len(deals)} 条，{len(deals)-len(active)} 条未启用）")
        return active
    except Exception as e:
        print(f"[自定义推广] 加载失败: {e}")
        return []


def extract_number(text):
    """从文本中提取数字"""
    if not text:
        return 0
    text = text.replace(",", "").replace("，", "")
    nums = re.findall(r"(\d+\.?\d*)", text)
    return float(nums[0]) if nums else 0


def get_fallback_deals():
    """
    预置热门优惠模板 —— 始终有内容可推送
    根据当前日期星期动态选择品类
    """
    now = datetime.now()
    weekday = now.weekday()  # 0=周一

    # 不同品类的模板数据，每天轮换
    templates = {
        0: [  # 周一：数码3C
            {"source": "京东", "title": "Redmi K80 5G智能手机 12GB+256GB", "price": "¥1999", "old_price": "¥2499", "tag": "限时秒杀"},
            {"source": "京东", "title": "联想小新Pro 16 2025 轻薄本 i5-13500H", "price": "¥4499", "old_price": "¥5299", "tag": "PLUS专享"},
            {"source": "淘宝", "title": "漫步者G2 Pro 无线游戏耳机 7.1环绕声", "price": "¥199", "old_price": "¥299", "tag": "百亿补贴"},
            {"source": "京东", "title": "小米Redmi Pad SE 11英寸 8+256G 平板", "price": "¥999", "old_price": "¥1299", "tag": "历史低价"},
            {"source": "拼多多", "title": "Apple AirPods Pro 2 无线降噪耳机 USB-C", "price": "¥1399", "old_price": "¥1899", "tag": "百亿补贴"},
        ],
        1: [  # 周二：食品饮料
            {"source": "京东", "title": "三只松鼠每日坚果礼盒 750g/30袋", "price": "¥49.9", "old_price": "¥89", "tag": "限时秒杀"},
            {"source": "天猫", "title": "蒙牛特仑苏纯牛奶 250ml×24盒", "price": "¥49.9", "old_price": "¥72", "tag": "优惠券"},
            {"source": "京东", "title": "良品铺子肉类零食大礼包 1kg", "price": "¥59.9", "old_price": "¥108", "tag": "PLUS专享"},
            {"source": "美团", "title": "星巴克中度烘焙咖啡豆 200g 买一送一", "price": "¥89", "old_price": "¥178", "tag": "限时秒杀"},
            {"source": "拼多多", "title": "百草味夏威夷果仁 250g×2袋", "price": "¥29.9", "old_price": "¥59.8", "tag": "百亿补贴"},
        ],
        2: [  # 周三：日用百货
            {"source": "京东", "title": "蓝月亮洗衣液 薰衣草 12斤套装", "price": "¥39.9", "old_price": "¥69.9", "tag": "限时秒杀"},
            {"source": "天猫", "title": "维达超韧抽纸 3层110抽×30包", "price": "¥49.9", "old_price": "¥79.9", "tag": "优惠券"},
            {"source": "京东", "title": "苏泊尔不粘锅三件套装 电磁炉通用", "price": "¥199", "old_price": "¥399", "tag": "历史低价"},
            {"source": "拼多多", "title": "网易严选懒人沙发 豆袋榻榻米", "price": "¥159", "old_price": "¥279", "tag": "百亿补贴"},
            {"source": "京东", "title": "小米空气净化器4 Pro 除甲醛", "price": "¥1299", "old_price": "¥1999", "tag": "PLUS专享"},
        ],
        3: [  # 周四：服饰鞋包
            {"source": "京东", "title": "李宁超轻21代跑鞋 男女同款", "price": "¥299", "old_price": "¥599", "tag": "限时秒杀"},
            {"source": "天猫", "title": "优衣库男士轻薄羽绒服 便携款", "price": "¥299", "old_price": "¥499", "tag": "优惠券"},
            {"source": "拼多多", "title": "安踏冠军跑鞋2代 氮科技中底", "price": "¥249", "old_price": "¥499", "tag": "百亿补贴"},
            {"source": "京东", "title": "新秀丽双肩包 商务休闲15.6英寸", "price": "¥299", "old_price": "¥599", "tag": "历史低价"},
            {"source": "天猫", "title": "海澜之家纯棉衬衫 长袖商务", "price": "¥99", "old_price": "¥199", "tag": "优惠券"},
        ],
        4: [  # 周五：美妆个护
            {"source": "京东", "title": "SK-II 神仙水230ml 护肤精华露", "price": "¥899", "old_price": "¥1590", "tag": "限时秒杀"},
            {"source": "天猫", "title": "欧莱雅复颜玻尿酸水乳套装", "price": "¥269", "old_price": "¥429", "tag": "优惠券"},
            {"source": "拼多多", "title": "雅诗兰黛DW持妆粉底液 30ml", "price": "¥199", "old_price": "¥395", "tag": "百亿补贴"},
            {"source": "京东", "title": "飞利浦电动牙刷HX9352 钻石亮白", "price": "¥299", "old_price": "¥599", "tag": "PLUS专享"},
            {"source": "天猫", "title": "珀莱雅双抗精华液 2.0 30ml", "price": "¥139", "old_price": "¥249", "tag": "优惠券"},
        ],
        5: [  # 周六：家居生活
            {"source": "京东", "title": "米家智能窗帘 电动窗帘轨道", "price": "¥499", "old_price": "¥799", "tag": "限时秒杀"},
            {"source": "天猫", "title": "野兽派香薰礼盒 扩香石套装", "price": "¥159", "old_price": "¥259", "tag": "优惠券"},
            {"source": "拼多多", "title": "南极人四件套 纯棉 简约风", "price": "¥99", "old_price": "¥199", "tag": "百亿补贴"},
            {"source": "京东", "title": "格力冷暖空调 1.5匹 新一级能效", "price": "¥2499", "old_price": "¥3299", "tag": "PLUS专享"},
            {"source": "天猫", "title": "戴森V12 Detect Slim 无线吸尘器", "price": "¥2990", "old_price": "¥4290", "tag": "历史低价"},
        ],
        6: [  # 周日：综合精选
            {"source": "京东", "title": "Apple iPhone 16e 128GB 黑色", "price": "¥4499", "old_price": "¥5499", "tag": "限时秒杀"},
            {"source": "淘宝", "title": "小米巨省电空调 1.5匹 一级能效", "price": "¥1999", "old_price": "¥2699", "tag": "百亿补贴"},
            {"source": "京东", "title": "华为MatePad 11.5 柔光版 8+256G WiFi", "price": "¥1899", "old_price": "¥2499", "tag": "PLUS专享"},
            {"source": "拼多多", "title": "索尼WH-1000XM5 头戴式降噪耳机", "price": "¥1899", "old_price": "¥2999", "tag": "百亿补贴"},
            {"source": "美团", "title": "美团外卖红包 满30减8 全场通用", "price": "¥0.01", "old_price": "¥8", "tag": "优惠券"},
        ],
    }

    deals = templates.get(weekday, templates[0])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    result = []
    for d in deals:
        d["discount"] = round(1 - extract_number(d["price"]) / extract_number(d["old_price"]), 2)
        d["img_url"] = ""
        d["time"] = now_str
        d["url"] = ""
        result.append(d)

    print(f"[模板] 加载 {len(result)} 条当日轮换优惠（星期{weekday+1}）")
    return result


def collect_smzdm_deals():
    """
    采集什么值得买（备用，反爬严重时返回空）
    """
    deals = []
    try:
        resp = requests.get(
            "https://www.smzdm.com/",
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                "Referer": "https://www.smzdm.com/",
            },
            timeout=15
        )
        resp.encoding = "utf-8"
        html = resp.text

        if len(html) < 1000:
            print("[什么值得买] 触发反爬，跳过")
            return deals

        soup = BeautifulSoup(html, "lxml")
        selectors = [
            "li.list-item", "div.feed-item", "div.pandora-content",
            "div.item", "li[class*=item]", "div[class*=card]",
        ]

        items = []
        for sel in selectors:
            items = soup.select(sel)
            if items:
                break

        for item in items:
            try:
                title_el = (item.select_one("h5.item-name a")
                            or item.select_one("a[class*=title]")
                            or item.select_one("h2 a"))
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                link = title_el.get("href", "")
                if link and not link.startswith("http"):
                    link = "https://www.smzdm.com" + link

                price_el = (item.select_one("span.red, span.J_red")
                            or item.select_one("span[class*=price]"))
                price = price_el.get_text(strip=True) if price_el else ""

                old_price_el = (item.select_one("span.old_price, del")
                                or item.select_one("span[class*=old]"))
                old_price = old_price_el.get_text(strip=True) if old_price_el else ""

                tag_el = (item.select_one("span.tag, span.J_tag")
                          or item.select_one("span[class*=tag]"))
                tag = tag_el.get_text(strip=True) if tag_el else ""

                deal = {
                    "source": "什么值得买",
                    "title": title,
                    "price": price,
                    "old_price": old_price,
                    "discount": 0,
                    "url": f"https:{link}" if link.startswith("//") else link,
                    "tag": tag,
                    "img_url": "",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }

                price_num = extract_number(price)
                old_price_num = extract_number(old_price)
                if price_num > 0 and old_price_num > 0:
                    deal["discount"] = round(1 - price_num / old_price_num, 2)

                deals.append(deal)
            except Exception:
                continue

        print(f"[什么值得买] 采集到 {len(deals)} 条商品")

    except Exception as e:
        print(f"[什么值得买采集] 错误: {e}")

    return deals


def collect_all():
    """采集所有来源"""
    all_deals = []

    print("=" * 50)
    print(f"开始采集优惠信息... {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 50)

    # 0. 京东联盟 API（京粉精选）- 暂时注释，权限有限商品少
    # from jd_api import collect_jd_all_channels
    # jd_deals = collect_jd_all_channels()
    # all_deals.extend(jd_deals)
    # print(f"京东联盟精选: {len(jd_deals)} 条")

    # 0.2 淘宝联盟（物料精选 - 多品类高佣优惠券）
    from tb_api import collect_tb_all
    tb_deals = collect_tb_all()
    all_deals.extend(tb_deals)
    print(f"淘宝联盟: {len(tb_deals)} 条")

    # 1. 自定义推广商品
    promoted = load_promoted_deals()
    all_deals.extend(promoted)
    print(f"自定义推广: {len(promoted)} 条")

    # 2. 什么值得买（能爬到就追加，不超过总条数）
    smzdm = collect_smzdm_deals()
    if smzdm and len(all_deals) < 8:
        all_deals.extend(smzdm[:8 - len(all_deals)])
    print(f"什么值得买: {len(smzdm)} 条（追加后总计{len(all_deals)}条）")

    print(f"总计: {len(all_deals)} 条")
    print("=" * 50)

    return all_deals


if __name__ == "__main__":
    deals = collect_all()
    for d in deals[:5]:
        print(f"  [{d['tag']}] {d['title']} - {d['price']} (原价{d['old_price']}, {d['discount']*100:.0f}%OFF)")
