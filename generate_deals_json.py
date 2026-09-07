"""
generate_deals_json.py - 生成小程序用的 JSON 数据

用法:
  python3 generate_deals_json.py --output deals-data            # 全品类采集
  python3 generate_deals_json.py --search "面膜" --output deals-data  # 搜索指定关键词

输出:
  deals-data/deals.json       - 全品类商品数据
  deals-data/categories.json  - 品类列表
  deals-data/search/{关键词}.json - 搜索结果

商品归类逻辑：
  1. 全量采集所有物料ID的商品（翻页获取全部）
  2. 按店铺名匹配知名品牌列表（famous_brands.txt）
  3. 匹配到的商品按品牌所属品类直接归类
  4. 未匹配的商品丢弃
"""

import os
import sys
import json
import re
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


# ========== 品牌过滤配置 ==========
# 品牌列表文件路径（相对于本脚本所在目录）
FAMOUS_BRANDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "famous_brands.txt")

# 店铺名后缀（用于提取品牌名）
_SHOP_SUFFIXES = [
    "官方旗舰店", "旗舰店", "官方专卖店", "专卖店", "专营店",
    "官方专营店", "直营店", "旗舰店", "旗舰", "专卖",
    "官方海外旗舰店", "海外旗舰店", "海外官方旗舰店",
    "官方旗舰店", "品牌旗舰店", "品牌专卖店",
    "outlets店", "outlet店", "奥莱旗舰店", "奥莱店",
    "旗舰店", "官方店", "直营旗舰店",
]

# 全局品牌→品类映射 {品牌名: 品类}
_brand_category_map = None

# 全局品类列表（从famous_brands.txt读取的顺序）
_category_order = []


def load_brand_category_map():
    """
    从 famous_brands.txt 加载品牌→品类映射

    Returns:
        dict: {品牌名: 品类}
    """
    global _brand_category_map, _category_order
    if _brand_category_map is not None:
        return _brand_category_map

    _brand_category_map = {}
    _category_order = []

    if not os.path.exists(FAMOUS_BRANDS_FILE):
        print(f"[警告] 品牌列表文件不存在: {FAMOUS_BRANDS_FILE}")
        return _brand_category_map

    with open(FAMOUS_BRANDS_FILE, "r", encoding="utf-8") as f:
        current_category = None
        for line in f:
            line = line.strip()
            if not line:
                continue
            # 匹配品类行：【品类名】(数量)
            cat_match = re.match(r'^【(.+?)】', line)
            if cat_match:
                current_category = cat_match.group(1)
                if current_category not in _category_order:
                    _category_order.append(current_category)
                continue
            # 匹配店铺行：  序号. 店铺名
            shop_match = re.match(r'^\s*\d+\.\s*(.+)$', line)
            if shop_match and current_category:
                shop_name = shop_match.group(1).strip()
                # 从店铺名提取品牌名
                brand = extract_brand_from_shop(shop_name)
                if brand:
                    # 一个品牌可能出现在多个品类中，优先保留第一个
                    if brand not in _brand_category_map:
                        _brand_category_map[brand] = current_category

    print(f"[品牌过滤] 加载 {len(_brand_category_map)} 个品牌，{len(_category_order)} 个品类")
    return _brand_category_map


def extract_brand_from_shop(shop_name):
    """
    从店铺名提取品牌名

    示例:
        "小米官方旗舰店" → "小米"
        "LA MER海蓝之谜官方旗舰店" → "LA MER海蓝之谜"
        "adidas官方旗舰店" → "adidas"
        "361度云腾专卖店" → "361度"
    """
    if not shop_name:
        return ""
    name = shop_name.strip()
    # 按后缀长度降序匹配（优先匹配长后缀）
    for suffix in sorted(_SHOP_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix):
            return name[:-len(suffix)].strip()
    # 没有匹配到后缀，返回原名
    return name


def match_brand_category(shop_title):
    """
    根据店铺名匹配品牌品类

    匹配策略（双向包含）：
      1. 品牌名 in 店铺名（如 "小米" in "小米官方旗舰店"）
      2. 店铺核心名 in 品牌名（如 "雅诗兰黛" in "Estee Lauder雅诗兰黛"）

    Args:
        shop_title: 店铺名（如 "小米官方旗舰店"）

    Returns:
        品类名称，未匹配返回 None
    """
    brand_map = load_brand_category_map()
    if not shop_title:
        return None

    # 提取店铺核心名（去除后缀）
    shop_core = extract_brand_from_shop(shop_title)

    for brand, category in brand_map.items():
        # 策略1: 品牌名在店铺名中
        if brand.lower() in shop_title.lower():
            return category
        # 策略2: 店铺核心名在品牌名中（处理中英文混合品牌，如 Estee Lauder雅诗兰黛）
        if shop_core and len(shop_core) >= 2 and shop_core.lower() in brand.lower():
            return category

    return None


def get_category_list():
    """获取品类列表（按famous_brands.txt中的顺序）"""
    load_brand_category_map()
    return _category_order


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
    """采集全品类数据（遍历全部物料ID），并生成淘口令"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from tb_api import collect_tb_all, generate_taokouling

    # 采集全部63个物料ID的商品
    all_deals = collect_tb_all()

    # 为每个商品生成淘口令
    for d in all_deals:
        title = d.get("title", "")
        url = d.get("url", "")
        if title and url:
            try:
                tk = generate_taokouling(title, url)
                if tk:
                    d["taokouling"] = tk
            except:
                pass

    return all_deals


def format_deal(deal, index):
    """将 deal 格式化为小程序需要的格式（带品牌过滤）"""
    # 价格字段（来自 optional.upgrade API）
    price = str(deal.get("price", "")).replace("¥", "").replace("￥", "")
    predict = str(deal.get("predict_price", "")).replace("¥", "").replace("￥", "")
    coupon_price = str(deal.get("coupon_price", "")).replace("¥", "").replace("￥", "")
    gov_subsidy = str(deal.get("gov_subsidy", "")).replace("¥", "").replace("￥", "")

    # 使用预计算的折扣百分比（基于实际到手价）
    discount_pct = deal.get("discount", 0)
    if not discount_pct:
        # 备用计算
        price_num = extract_number(price)
        predict_num = extract_number(predict)
        if price_num > 0 and predict_num > 0 and price_num > predict_num:
            discount_pct = int(round((1 - predict_num / price_num) * 100))

    # 处理标签
    tags_str = deal.get("tags", "")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    # 添加优惠券信息和政府补贴到标签
    coupon_details = deal.get("coupon_details", "")
    if coupon_details:
        tags.append(coupon_details)
    if gov_subsidy and float(gov_subsidy) > 0:
        tags.append(f"国家补贴¥{gov_subsidy}")

    # 获取淘口令（优先用已有的，没有则用链接）
    taokouling = deal.get("taokouling", "")
    url = deal.get("url", "")

    # 品牌匹配确定品类
    shop_title = deal.get("shop", "")
    matched_category = match_brand_category(shop_title)

    return {
        "id": index,
        "title": deal.get("title", ""),
        "price": price,                    # 销售价
        "predict_price": predict,          # 实际到手价
        "coupon_price": coupon_price,      # 券后价
        "gov_subsidy": gov_subsidy,        # 政府补贴
        "discount": discount_pct,          # 优惠力度%
        "category": matched_category,      # 品牌匹配的品类（未匹配为None）
        "sub_category": deal.get("sub_category", ""),
        "shop": shop_title,
        "img_url": deal.get("img_url", ""),
        "url": url,
        "taokouling": taokouling,
        "tags": tags,
        "source": deal.get("source", ""),
        # 销量数据
        "annual_vol": deal.get("annual_vol", ""),          # 年化销量（如 "10万+"）
        "tk_total_sales": deal.get("tk_total_sales", ""),  # 淘宝客总销量
    }


def generate_deals_json(output_dir, search_keyword=None):
    """生成 JSON 数据文件"""
    os.makedirs(output_dir, exist_ok=True)

    # 加载品牌列表
    load_brand_category_map()

    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if search_keyword:
        # 搜索模式
        print(f"🔍 搜索: {search_keyword}")
        from tb_api import collect_tb_material_search
        raw_deals = collect_tb_material_search(q=search_keyword, has_coupon=True, page_size=30)
        # 搜索模式：也进行品牌过滤
        deals = [format_deal(d, i) for i, d in enumerate(raw_deals)]
        # 过滤：有价格 + 匹配到品牌
        deals = [d for d in deals if d["price"] and d["category"]]

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

        # 3. 格式化（含品牌匹配）
        formatted = [format_deal(d, i) for i, d in enumerate(valid_deals)]

        # 4. 品牌过滤（只保留匹配到知名品牌的商品）
        branded = [d for d in formatted if d["category"] is not None]
        print(f"  品牌匹配: {len(branded)} 条")

        # 5. 过滤优惠<10%的商品
        branded = [d for d in branded if d["discount"] >= 10]
        print(f"  优惠≥10%: {len(branded)} 条")

        # 5. 按品类分组（按 famous_brands.txt 中的品类顺序）
        from collections import defaultdict
        by_category = defaultdict(list)
        for d in branded:
            by_category[d["category"]].append(d)

        cat_list = get_category_list()
        cat_order = {name: idx for idx, name in enumerate(cat_list)}

        # 6. 生成两级类目列表（按品类顺序，同品类内按数量降序）
        categories = []
        for cat in sorted(by_category.keys(), key=lambda x: cat_order.get(x, 999)):
            items = by_category[cat]
            # 统计二级类目
            sub_cat_count = defaultdict(int)
            for item in items:
                sub = item.get("sub_category", "") or "其他"
                sub_cat_count[sub] += 1
            # 按数量降序排列二级类目
            sub_cats = sorted(sub_cat_count.items(), key=lambda x: -x[1])
            categories.append({
                "name": cat,
                "count": len(items),
                "subs": [{"name": s[0], "count": s[1]} for s in sub_cats]
            })

        # 7. 保存 deals.json
        deals_data = {
            "total": len(branded),
            "updateTime": update_time,
            "deals": branded
        }
        with open(os.path.join(output_dir, "deals.json"), "w", encoding="utf-8") as f:
            json.dump(deals_data, f, ensure_ascii=False, indent=2)

        # 8. 保存 categories.json
        with open(os.path.join(output_dir, "categories.json"), "w", encoding="utf-8") as f:
            json.dump(categories, f, ensure_ascii=False, indent=2)

        print(f"✅ 生成完成: {len(branded)} 条商品, {len(categories)} 个品类")
        print(f"📁 输出目录: {output_dir}/")
        print(f"   - deals.json ({len(branded)} 条)")
        print(f"   - categories.json ({len(categories)} 个品类)")

        # 输出品牌分类统计
        print(f"\n[品牌分类统计]")
        brand_count = defaultdict(int)
        for d in branded:
            brand_count[d["category"]] += 1
        for cat in cat_list:
            cnt = brand_count.get(cat, 0)
            if cnt > 0:
                print(f"  {cat}: {cnt} 条")
        unmatched = len(valid_deals) - len(branded)
        print(f"  未匹配品牌: {unmatched} 条（已过滤）")

        return deals_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成小程序优惠数据 JSON")
    parser.add_argument("--output", default="deals-data", help="输出目录")
    parser.add_argument("--search", default=None, help="搜索关键词")
    args = parser.parse_args()

    generate_deals_json(args.output, args.search)
