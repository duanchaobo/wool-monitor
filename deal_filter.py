"""
deal_filter.py - 优惠筛选引擎

规则：
1. 折扣力度 ≥ 50%（至少5折）
2. 商品价格 ≥ 20元
3. 优先推品牌商品、历史低价、神价格标签
4. 去重（同一商品30分钟内不重复推）
"""

import json
import hashlib
import os
from datetime import datetime, timedelta

# ============ 配置 ============

MIN_DISCOUNT = 0.0      # 不限折扣
MIN_PRICE = 0.0         # 不限价格
CACHE_FILE = "push_cache.json"  # 去重缓存
CACHE_EXPIRE_MIN = 0    # 0 = 永久去重，不再推送历史已推过的优惠

# 品类过滤：黑名单（不推的品类）
BLOCKED_CATEGORIES = [
    "汽车用品", "汽车零部件", "汽车装潢", "摩托车",
    "医疗器械", "中药材", "药品",
    "房产", "装修材料", "五金电工",
    "成人用品", "情趣内衣",
    "棋牌麻将", "烟草',
]

# 品牌关键词（可扩展）
BRAND_KEYWORDS = [
    "苹果", "华为", "小米", "OPPO", "vivo", "三星", "联想", "戴尔",
    "惠普", "华硕", "索尼", "松下", "飞利浦", "美的", "格力", "海尔",
    "海信", "TCL", "创维", "方太", "老板", "苏泊尔", "九阳", "小熊",
    "耐克", "阿迪达斯", "安踏", "李宁", "鸿星尔克",
    "茅台", "五粮液", "泸州老窖",
    "雅诗兰黛", "兰蔻", "SK-II", "资生堂", "欧莱雅",
]

# 优先级标签
PRIORITY_TAGS = ["历史低价", "绝对值", "神价格", "神价", "bug", "漏洞"]


# ============================


def load_cache():
    """加载推送缓存（用于去重）"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_cache(cache):
    """保存推送缓存"""
    try:
        # CACHE_EXPIRE_MIN=0 时永久保存，不清理
        if CACHE_EXPIRE_MIN > 0:
            now = datetime.now()
            expired = []
            for key, val in cache.items():
                t = datetime.fromisoformat(val["time"])
                if (now - t).total_seconds() > CACHE_EXPIRE_MIN * 60:
                    expired.append(key)
            for k in expired:
                del cache[k]

        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[缓存保存失败] {e}")


def make_cache_key(deal):
    """生成去重key（基于商品标题前20字+价格）"""
    text = (deal.get("title", "")[:20] + str(deal.get("price", "")))
    return hashlib.md5(text.encode()).hexdigest()


def is_duplicate(deal, cache):
    """检查是否已推送过"""
    key = make_cache_key(deal)
    return key in cache


def is_brand_product(title):
    """判断是否为品牌商品"""
    title_lower = title.lower()
    for brand in BRAND_KEYWORDS:
        if brand in title or brand.lower() in title_lower:
            return True
    return False


def get_priority(deal):
    """获取信息优先级（数字越大越紧急）"""
    tag = deal.get("tag", "")
    title = deal.get("title", "")
    source = deal.get("source", "")
    discount = deal.get("discount", 0)

    score = 0

    # 标签加成
    for pt in PRIORITY_TAGS:
        if pt in tag or pt in title:
            score += 30
            break

    # 折扣加成
    if discount >= 0.8:
        score += 20  # 2折以内
    elif discount >= 0.7:
        score += 10  # 3折以内
    elif discount >= 0.5:
        score += 5   # 5折以内

    # 品牌加成
    if is_brand_product(title):
        score += 10

    # 来源加成
    if "漏洞" in tag or "bug" in tag.lower():
        score += 40

    return score


def filter_deals(deals):
    """
    筛选并排序优惠信息
    返回：(普通推送列表, 紧急推送列表)
    """
    if not deals:
        return [], []

    cache = load_cache()
    normal_list = []
    urgent_list = []

    for deal in deals:
        # 1. 去重
        if is_duplicate(deal, cache):
            print(f"  [去重] 跳过: {deal.get('title', '')[:30]}")
            continue

        # 2. 只推送有优惠券或促销的商品
        coupon_url = deal.get("coupon_url", "")
        tag = deal.get("tag", "")
        tags = deal.get("tags", "")
        predict_price = deal.get("predict_price", "")
        url = deal.get("url", "")

        # 判断是否有券/促销
        has_coupon_old = bool(coupon_url) and ("减" in tag or "券" in tag or "满" in tag)
        # 新API数据特征：tag含"搜:"或"物料推荐"，且has_coupon=true已筛选，不依赖coupon_url
        is_new_api = "搜:" in tag or "物料推荐" in tag
        has_coupon_new = is_new_api and bool(url)

        if not (has_coupon_old or has_coupon_new):
            print(f"  [无券] 跳过: {deal.get('title', '')[:30]}")
            continue

        # 2.1 券门槛检查（仅对旧API数据，新API不检查此项）
        if not is_new_api:
            from deal_collector import extract_number
            quota = deal.get("coupon_quota", 0)
            price_num = extract_number(str(deal.get("price", "0")))
            if quota and price_num > 0 and float(quota) > price_num:
                print(f"  [券门槛过高] 跳过: {deal.get('title', '')[:20]} (商品¥{price_num}, 券需满¥{float(quota):.0f})")
                continue

        # 2.2 过滤优惠力度低于10%的商品（新API数据从价格计算折扣）
        discount_pct = deal.get("discount", 0)
        if discount_pct == 0:
            # 尝试从 price/old_price 计算折扣
            from deal_collector import extract_number
            p = extract_number(str(deal.get("price", "0")))
            op = extract_number(str(deal.get("old_price", "0")))
            if op > 0 and p > 0 and op > p:
                discount_pct = round(1 - p / op, 2)
                deal["discount"] = discount_pct
        if discount_pct < 0.1:
            print(f"  [优惠力度低] 跳过: {deal.get('title', '')[:20]} ({discount_pct*100:.0f}%OFF)")
            continue

        # 3. 品类过滤：黑名单制（不在黑名单即通过）
        category = deal.get("category", "")
        if category and any(blocked in category for blocked in BLOCKED_CATEGORIES):
            print(f"  [品类屏蔽] 跳过: {deal.get('title', '')[:25]} ({category})")
            continue

        # 4. 提取价格
        price = 0
        try:
            from deal_collector import extract_number
            price = extract_number(str(deal.get("price", "0")))
        except:
            import re
            nums = re.findall(r"(\d+\.?\d*)", str(deal.get("price", "0")))
            price = float(nums[0]) if nums else 0

        # 4. 最低价格过滤
        if price < MIN_PRICE and price > 0:
            print(f"  [价格过低] 跳过: {deal.get('title', '')[:30]} (¥{price})")
            continue

        # 5. 计算优先级
        priority = get_priority(deal)
        deal["priority"] = priority

        # 6. 放入对应列表
        if priority >= 30:
            urgent_list.append(deal)
        else:
            normal_list.append(deal)

        # 7. 缓存该条
        key = make_cache_key(deal)
        cache[key] = {
            "time": datetime.now().isoformat(),
            "title": deal.get("title", "")[:30],
        }

    # 保存缓存
    save_cache(cache)

    # 按优先级排序
    normal_list.sort(key=lambda x: x["priority"], reverse=True)
    urgent_list.sort(key=lambda x: x["priority"], reverse=True)

    print(f"\n筛选结果:")
    print(f"  紧急推送: {len(urgent_list)} 条")
    print(f"  普通推送: {len(normal_list)} 条")
    print(f"  已去重/过滤: {len(deals) - len(normal_list) - len(urgent_list)} 条")

    return normal_list, urgent_list


if __name__ == "__main__":
    # 测试
    test_deals = [
        {
            "source": "什么值得买",
            "title": "【历史低价】苹果 AirPods Pro 2 无线耳机",
            "price": "1399.0",
            "old_price": "1999.0",
            "discount": 0.3,
            "url": "https://example.com/1",
            "tag": "历史低价",
        },
        {
            "source": "什么值得买",
            "title": "【bug价】某杂牌数据线",
            "price": "5.0",
            "old_price": "29.9",
            "discount": 0.83,
            "url": "https://example.com/2",
            "tag": "",
        },
        {
            "source": "什么值得买",
            "title": "华为MatePad 11 2024款 平板电脑",
            "price": "1999.0",
            "old_price": "2499.0",
            "discount": 0.2,
            "url": "https://example.com/3",
            "tag": "",
        },
    ]

    normal, urgent = filter_deals(test_deals)
    print(f"\n普通推送: {len(normal)} 条")
    print(f"紧急推送: {len(urgent)} 条")
