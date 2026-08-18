"""
deal_filter.py - 优惠筛选引擎

规则：
1. 折扣力度 ≥ 50%（至少5折）
2. 商品价格 ≥ 20元
3. 优先推品牌商品、历史低价、神价格标签
4. 去重（标题近似+价格相近 → 调用硅基流动大模型判断是否重复）
"""

import json
import hashlib
import os
import requests
from datetime import datetime, timedelta

# 硅基流动 API 配置
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
SILICONFLOW_MODEL = "deepseek-ai/DeepSeek-V3.2"
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"

# ============ 配置 ============

MIN_DISCOUNT = 0.0      # 不限折扣
MIN_PRICE = 0.0         # 不限价格
CACHE_FILE = "push_cache.json"  # 去重缓存
CACHE_EXPIRE_MIN = 0    # 0 = 永久去重，不再推送历史已推过的优惠

# 品类过滤：白名单（淘宝实际品类名称，只推这些）
# 基于MATERIAL_ID_REFERENCE.md中63个有效物料ID的实际返回类目整理
ALLOWED_CATEGORIES = [
    # === 母婴类 ===
    # 奶粉/营养
    "咖啡/麦片/冲饮", "奶粉", "婴童奶粉",
    # 尿裤/用品
    "婴童尿裤", "婴童用品", "婴童洗护", "童车/童床/婴儿推车",
    # 玩具/书籍/童装
    "玩具/童车/益智/早教/游乐设备", "拼搭/积木/模型/拼图/拼板",
    "书籍/杂志/报纸",
    "童装/婴儿装/亲子装", "童鞋/婴儿鞋/亲子鞋",
    # 孕产
    "孕妇装/孕产妇用品/营养",
    # 母婴相关
    "个人护理/保健/按摩器材", "医疗器械",

    # === 美妆个护 ===
    "美容护肤/美体/精油", "彩妆/香水/美妆工具",
    "美发护发/假发", "美发护发", "身体护理",
    "面部护理", "眼部护理", "唇部护理",
    "隐形眼镜/护理液",

    # === 日用/家清 ===
    "洗发水", "沐浴露",
    "洗护清洁剂/卫生巾/纸/香薰", "纸品/湿巾",
    "家庭清洁", "衣物护理", "家居清洁",
    "家庭/个人清洁工具", "居家日用", "收纳整理",

    # === 食品饮料 ===
    "零食/坚果/特产", "饮品/营养冲调", "乳品/冰品",
    "粮油调味/速食/干货/烘焙", "粮油调味/速食/罐头",
    "滋补养生", "传统滋补营养品",
    "保健食品/膳食营养补充食品",
    "水产肉类/新鲜蔬果/熟食", "餐饮具",

    # === 服饰内衣 ===
    "内衣/家居服", "女士内衣/男士内衣/家居服",
    "女装/女士精品", "男装", "袜子", "服饰", "家纺",

    # === 家居/家装 ===
    "厨房/烹饪用具", "厨房电器", "床上用品",
    "居家布艺", "住宅家具", "家装主材",
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
    """生成去重key（基于完整标题+价格，去除空白字符）"""
    title = deal.get("title", "").strip().replace(" ", "").replace("\u3000", "")
    price = str(deal.get("price", "")).strip()
    text = title + price
    return hashlib.md5(text.encode()).hexdigest()


def is_duplicate(deal, cache):
    """检查是否已推送过（先用规则快速过滤，疑似重复时调用大模型确认）"""
    # 1. 精确匹配：完整标题+价格完全相同
    key = make_cache_key(deal)
    if key in cache:
        return True

    # 2. 疑似重复：标题高度相似 + 价格相同/相近
    title = deal.get("title", "").strip().replace(" ", "").replace("\u3000", "")
    price = str(deal.get("price", "")).strip()
    for cached_key, cached_val in cache.items():
        cached_title = cached_val.get("full_title", cached_val.get("title", "")).strip().replace(" ", "").replace("\u3000", "")
        cached_price = cached_val.get("price", "").strip()
        # 价格相同或相近（≤2元误差视为同一商品不同规格）
        price_match = (cached_price == price or _price_similar(cached_price, price, threshold=2.0))
        # 标题相似度：完整标题比较，允许部分差异（如规格/包装不同）
        title_similar = (title == cached_title or
                         title[:20] == cached_title[:20] or
                         (len(title) > 10 and len(cached_title) > 10 and
                          (title in cached_title or cached_title in title)))
        if title_similar and price_match:
            # 标题高度相似，调用大模型确认（传入完整标题+价格）
            if SILICONFLOW_API_KEY:
                is_dup = _llm_check_duplicate(
                    f"{deal.get('title', '')} 价格:{price}",
                    f"{cached_val.get('full_title', cached_title)} 价格:{cached_price}"
                )
                if is_dup:
                    print(f"  [AI去重] 跳过: {deal.get('title', '')[:25]}")
                    return True
            else:
                # 无API Key时按规则去重
                return True
    return False


def _price_similar(p1, p2, threshold=2.0):
    """判断两个价格是否相近（默认误差≤threshold元视为相同）"""
    import re
    n1 = re.findall(r"(\d+\.?\d*)", str(p1))
    n2 = re.findall(r"(\d+\.?\d*)", str(p2))
    if n1 and n2:
        return abs(float(n1[0]) - float(n2[0])) <= threshold
    return p1 == p2


def _llm_check_duplicate(title1, title2):
    """调用硅基流动 DeepSeek 判断两个商品标题是否指向同一商品"""
    try:
        prompt = f"""判断以下两个电商商品标题是否指向同一个商品（同一SKU/同一链接）。只回答 yes 或 no。

商品1：{title1}
商品2：{title2}

注意：名称略有差异但核心商品相同（如仅规格/包装/促销词不同）也算同一个。"""

        resp = requests.post(
            SILICONFLOW_API_URL,
            headers={
                "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": SILICONFLOW_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 10,
                "temperature": 0,
            },
            timeout=15,
        )
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip().lower()
        return "yes" in content
    except Exception as e:
        print(f"  [AI去重异常] {e}")
        return False


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

        # 2.2 过滤有折扣的商品：到手价(final_promotion_price) < 现价(zk_final_price)
        # 折扣 = 1 - 到手价/现价
        discount_pct = deal.get("discount", 0)
        if discount_pct == 0:
            from deal_collector import extract_number
            current = extract_number(str(deal.get("price", "")))      # 现价(zk_final_price)
            predict = extract_number(str(deal.get("predict_price", "")))  # 到手价(final_promotion_price)
            if current > 0 and predict > 0 and current > predict:
                discount_pct = round(1 - predict / current, 2)
                deal["discount"] = discount_pct
        if discount_pct < 0.1:
            print(f"  [优惠力度低] 跳过: {deal.get('title', '')[:20]} ({discount_pct*100:.0f}%OFF)")
            continue

        # 3. 品类过滤：白名单制（只推指定品类）
        category = deal.get("category", "")
        if category and not any(allowed in category for allowed in ALLOWED_CATEGORIES):
            print(f"  [品类不符] 跳过: {deal.get('title', '')[:25]} ({category})")
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

        # 7. 立即缓存并保存（同一批次内的后续重复能立刻拦截）
        key = make_cache_key(deal)
        cache[key] = {
            "time": datetime.now().isoformat(),
            "title": deal.get("title", "")[:30],
            "full_title": deal.get("title", ""),
            "price": deal.get("price", ""),
        }
        save_cache(cache)  # 每条推送后立即写入文件

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
