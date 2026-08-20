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


# 淘宝官方类目 → 8大精简类目映射
CATEGORY_MERGE_MAP = {
    # 母婴
    "婴童用品": "母婴", "婴童尿裤": "母婴", "婴童洗护": "母婴",
    "孕妇装/孕产妇用品/营养": "母婴", "童装/婴儿装/亲子装": "母婴",
    "玩具/童车/益智/早教/游乐设备": "玩具",
    # 日用品
    "洗护清洁剂/卫生巾/纸/香薰": "日用品", "居家日用": "日用品",
    "收纳整理": "日用品", "个人护理/保健/按摩器材": "日用品",
    "餐饮具": "日用品", "床上用品": "日用品",
    "箱包皮具/热销女包/男包": "日用品", "运动包/户外包/配件": "日用品",
    "户外/登山/野营/旅行用品": "日用品",
    # 数码
    "3C数码配件": "数码", "电脑硬件/显示器/电脑周边": "数码",
    "影音电器": "数码",
    # 美食
    "咖啡/麦片/冲饮": "美食", "零食/坚果/特产": "美食",
    "粮油调味/速食/干货/烘焙": "美食", "茶": "美食",
    "保健食品/膳食营养补充食品": "美食", "医疗器械": "美食",
    "保健用品": "美食", "宠物/宠物食品及用品": "美食",
    # 美妆
    "彩妆/香水/美妆工具": "美妆", "美容护肤/美体/精油": "美妆",
    "美发护发/假发": "美妆",
    # 服饰
    "女装/女士精品": "服饰", "男装": "服饰",
    "女士内衣/男士内衣/家居服": "服饰", "流行男鞋": "服饰",
    "运动鞋new": "服饰",
    # 图书
    "文具用品/文化用品/商务用品": "图书",
    # 运动
    "运动/瑜伽/健身/球迷用品": "日用品",
}


def merge_category(raw_category):
    """将淘宝官方类目合并为8大精简类目"""
    if not raw_category:
        return "其他"
    # 精确匹配
    if raw_category in CATEGORY_MERGE_MAP:
        return CATEGORY_MERGE_MAP[raw_category]
    # 模糊匹配（取前缀）
    for key, val in CATEGORY_MERGE_MAP.items():
        if raw_category.startswith(key) or key.startswith(raw_category):
            return val
    return "其他"


# 8大目标类目
TARGET_CATEGORIES = ["母婴", "日用品", "数码", "美食", "美妆", "服饰", "图书", "玩具"]

# 硅基流动 API 配置
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"

# LLM 分类缓存（避免重复调用）
_llm_category_cache = {}


def llm_classify_category(title, raw_category=""):
    """
    使用硅基流动 LLM 对商品标题进行一级类目分类

    Args:
        title: 商品标题
        raw_category: 原始类目（辅助判断）

    Returns:
        分类名称（8大类之一）
    """
    if not SILICONFLOW_API_KEY:
        return "其他"

    # 缓存 key
    cache_key = f"{title[:30]}|{raw_category}"
    if cache_key in _llm_category_cache:
        return _llm_category_cache[cache_key]

    prompt = f"""请根据商品标题判断它属于以下哪个分类：{', '.join(TARGET_CATEGORIES)}

商品标题：{title}
原始类目：{raw_category}

只返回分类名称，不要解释。"""

    try:
        import requests
        resp = requests.post(
            SILICONFLOW_API_URL,
            headers={
                "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 10,
                "temperature": 0
            },
            timeout=10
        )
        result = resp.json()
        answer = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        # 验证返回值是否在目标类目中
        for cat in TARGET_CATEGORIES:
            if cat in answer:
                _llm_category_cache[cache_key] = cat
                return cat

        _llm_category_cache[cache_key] = "其他"
        return "其他"
    except Exception as e:
        print(f"[LLM分类失败] {e}")
        return "其他"


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
    """采集全品类数据，并生成淘口令"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from tb_api import collect_tb_material_search, generate_taokouling

    all_deals = []
    seen_ids = set()

    for kw in ALL_CATEGORY_KEYWORDS:
        try:
            deals = collect_tb_material_search(q=kw, has_coupon=True, page_size=3)
            for d in deals:
                key = d.get("title", "")[:20] + "|" + d.get("price", "")
                if key not in seen_ids:
                    seen_ids.add(key)
                    # 生成淘口令（方便复制后淘宝直接跳转）
                    title = d.get("title", "")
                    url = d.get("url", "")
                    if title and url:
                        try:
                            tk = generate_taokouling(title, url)
                            if tk:
                                d["taokouling"] = tk
                        except:
                            pass
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

    # 获取淘口令（优先用已有的，没有则用链接）
    taokouling = deal.get("taokouling", "")
    url = deal.get("url", "")

    # 合并类目：先查映射表，映射不到用LLM判断
    raw_cat = deal.get("category", "")
    merged_cat = merge_category(raw_cat)
    if merged_cat == "其他":
        # 映射表未命中，用 LLM 根据标题分类
        title = deal.get("title", "")
        if title:
            merged_cat = llm_classify_category(title, raw_cat)
            if merged_cat != "其他":
                print(f"  [LLM分类] {title[:25]}... → {merged_cat}")

    return {
        "id": index,
        "title": deal.get("title", ""),
        "price": price,
        "predict_price": predict,
        "discount": discount_pct,
        "category": merged_cat,
        "sub_category": deal.get("sub_category", ""),
        "shop": deal.get("shop", ""),
        "img_url": deal.get("img_url", ""),
        "url": url,
        "taokouling": taokouling,
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

        # 5. 按一级+二级类目分组
        from collections import defaultdict
        by_category = defaultdict(list)
        for d in formatted:
            by_category[d["category"]].append(d)

        # 6. 生成两级类目列表
        categories = []
        for cat, items in sorted(by_category.items(), key=lambda x: -len(x[1])):
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
