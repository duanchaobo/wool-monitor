"""
generate_deals_json.py - 生成小程序用的 JSON 数据

用法:
  python3 generate_deals_json.py --output deals-data            # 全品类采集
  python3 generate_deals_json.py --search "面膜" --output deals-data  # 搜索指定关键词

输出:
  deals-data/deals.json       - 全品类商品数据
  deals-data/categories.json  - 品类列表
  deals-data/search/{关键词}.json - 搜索结果
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载 .env
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                if v:
                    os.environ[k.strip()] = v

from deal_collector import extract_number


# 全品类搜索关键词（覆盖所有常见品类）
ALL_CATEGORY_KEYWORDS = [
    # 母婴
    "纸尿裤", "奶粉", "奶瓶", "玩具", "童装", "婴儿推车",
    # 日用洗护
    "纸巾", "洗衣液", "洗发水", "沐浴露", "牙膏", "洗洁精",
    # 食品饮料
    "零食", "牛奶", "咖啡", "坚果", "大米", "食用油", "茶叶",
    # 服饰
    "T恤", "运动鞋", "袜子", "内衣", "羽绒服", "连衣裙",
    # 美妆
    "面膜", "口红", "护肤套装", "防晒霜", "粉底液",
    # 数码家电
    "数据线", "充电宝", "耳机", "鼠标", "键盘", "手机壳",
    # 家居
    "床上用品", "收纳", "保温杯", "雨伞", "枕头",
    # 运动户外
    "瑜伽垫", "跑步鞋", "帐篷", "登山包",
    # 医药保健
    "维生素", "蛋白粉", "血压计", "按摩仪",
    # 宠物
    "猫粮", "狗粮", "猫砂",
    # 图书文具
    "笔记本", "钢笔", "书包",
]


def collect_all_categories():
    """采集全品类数据"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from tb_api import collect_tb_material_search

    all_deals = []
    seen_ids = set()

    for kw in ALL_CATEGORY_KEYWORDS:
        try:
            deals = collect_tb_material_search(q=kw, has_coupon=True, page_size=3)
            for d in deals:
                key = d.get("title", "")[:20] + "|" + d.get("price", "")
                if key not in seen_ids:
                    seen_ids.add(key)
                    all_deals.append(d)
        except Exception as e:
            print(f"  [搜索失败] {kw}: {e}")
            continue

    return all_deals


def format_deal(deal, index):
    """将 deal 格式化为小程序需要的格式"""
    price = str(deal.get("price", "")).replace("¥", "").replace("￥", "")
    predict = str(deal.get("predict_price", "")).replace("¥", "").replace("￥", "")

    # 计算折扣百分比
    price_num = extract_number(price)
    predict_num = extract_number(predict)
    discount_pct = 0
    if price_num > 0 and predict_num > 0 and price_num > predict_num:
        discount_pct = int(round((1 - predict_num / price_num) * 100))

    # 处理标签
    tags_str = deal.get("tags", "")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    return {
        "id": index,
        "title": deal.get("title", ""),
        "price": price,
        "predict_price": predict,
        "discount": discount_pct,
        "category": deal.get("category", "其他"),
        "shop": deal.get("shop", ""),
        "img_url": deal.get("img_url", ""),
        "url": deal.get("url", ""),
        "tags": tags,
        "source": deal.get("source", ""),
    }


def generate_deals_json(output_dir, search_keyword=None):
    """生成 JSON 数据文件"""
    os.makedirs(output_dir, exist_ok=True)

    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if search_keyword:
        # 搜索模式
        print(f"🔍 搜索: {search_keyword}")
        from tb_api import collect_tb_material_search
        raw_deals = collect_tb_material_search(q=search_keyword, has_coupon=True, page_size=30)
        # 搜索模式不过滤，直接展示
        deals = [format_deal(d, i) for i, d in enumerate(raw_deals)]
        deals = [d for d in deals if d["price"]]  # 去掉无价格的

        # 按折扣排序
        deals.sort(key=lambda x: x["discount"], reverse=True)

        result = {
            "keyword": search_keyword,
            "total": len(deals),
            "updateTime": update_time,
            "deals": deals
        }

        # 保存搜索结果
        search_dir = os.path.join(output_dir, "search")
        os.makedirs(search_dir, exist_ok=True)
        safe_keyword = "".join(c for c in search_keyword if c.isalnum() or c in "_-")
        with open(os.path.join(search_dir, f"{safe_keyword}.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"✅ 搜索结果: {len(deals)} 条 → {search_dir}/{safe_keyword}.json")
        return result

    else:
        # 全品类模式
        print("📡 采集全品类优惠数据...")

        # 1. 采集
        all_deals = collect_all_categories()
        print(f"  采集到 {len(all_deals)} 条原始数据")

        # 2. 基础过滤（不去重历史商品）
        valid_deals = []
        for d in all_deals:
            price = str(d.get("price", "")).replace("¥", "").replace("￥", "")
            predict = str(d.get("predict_price", "")).replace("¥", "").replace("￥", "")
            price_num = extract_number(price)
            predict_num = extract_number(predict)
            # 必须有价格
            if price_num <= 0:
                continue
            # 有链接（有券/可购买）
            url = d.get("url", "")
            if not url:
                continue
            # 到手价必须低于现价（有折扣）
            if predict_num > 0 and predict_num >= price_num:
                continue
            valid_deals.append(d)

        print(f"  有效商品: {len(valid_deals)} 条")

        # 3. 格式化
        formatted = [format_deal(d, i) for i, d in enumerate(valid_deals)]

        # 4. 过滤优惠<10%的商品
        formatted = [d for d in formatted if d["discount"] >= 10]
        print(f"  优惠≥10%: {len(formatted)} 条")

        # 5. 按品类分组
        from collections import defaultdict
        by_category = defaultdict(list)
        for d in formatted:
            by_category[d["category"]].append(d)

        # 6. 生成品类列表
        categories = []
        for cat, items in sorted(by_category.items(), key=lambda x: -len(x[1])):
            categories.append({"name": cat, "count": len(items)})

        # 7. 保存 deals.json（包含所有有效商品，不去重）
        deals_data = {
            "total": len(formatted),
            "updateTime": update_time,
            "deals": formatted
        }
        with open(os.path.join(output_dir, "deals.json"), "w", encoding="utf-8") as f:
            json.dump(deals_data, f, ensure_ascii=False, indent=2)

        # 8. 保存 categories.json
        with open(os.path.join(output_dir, "categories.json"), "w", encoding="utf-8") as f:
            json.dump(categories, f, ensure_ascii=False, indent=2)

        print(f"✅ 生成完成: {len(formatted)} 条商品, {len(categories)} 个品类")
        print(f"📁 输出目录: {output_dir}/")
        print(f"   - deals.json ({len(formatted)} 条)")
        print(f"   - categories.json ({len(categories)} 个品类)")

        return deals_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成小程序优惠数据 JSON")
    parser.add_argument("--output", default="deals-data", help="输出目录")
    parser.add_argument("--search", default=None, help="搜索关键词")
    args = parser.parse_args()

    generate_deals_json(args.output, args.search)
