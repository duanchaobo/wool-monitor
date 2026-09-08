"""
collect_step2.py - Workflow 2: 读取原始名单 → 分批补充价格 → 折扣过滤 → 生成小程序JSON

每小时执行一次（从北京时间 7:00 开始），每次处理 200 条商品。
读取 raw_deals.json → 调用 optional.upgrade 补充价格 → 保存到 enriched_deals.json
处理完毕后生成最终的 deals.json 和 categories.json 供小程序使用。

进度记录在 docs/enrich_progress.json 中，确保每次接着上次处理。

用法:
  python3 collect_step2.py --output docs [--batch-size 200] [--reset]
"""

import os
import sys
import json
import argparse
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tb_api import enrich_deals_batch, filter_by_discount, generate_taokouling


def load_progress(output_dir):
    """加载处理进度"""
    progress_file = os.path.join(output_dir, "enrich_progress.json")
    if os.path.exists(progress_file):
        with open(progress_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"start_index": 0, "total": 0, "last_run": None, "completed": False}


def save_progress(output_dir, progress):
    """保存处理进度"""
    progress_file = os.path.join(output_dir, "enrich_progress.json")
    progress["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def load_raw_deals(output_dir):
    """加载原始商品名单"""
    raw_file = os.path.join(output_dir, "raw_deals.json")
    if not os.path.exists(raw_file):
        print(f"❌ 原始商品名单不存在: {raw_file}")
        print("   请先运行 Workflow 1 (collect_step1.py)")
        return None
    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("deals", [])


def load_enriched_deals(output_dir):
    """加载已处理的商品列表"""
    enriched_file = os.path.join(output_dir, "enriched_deals.json")
    if os.path.exists(enriched_file):
        with open(enriched_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("deals", [])
    return []


def save_enriched_deals(output_dir, deals):
    """保存已处理的商品列表"""
    enriched_file = os.path.join(output_dir, "enriched_deals.json")
    data = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(deals),
        "deals": deals
    }
    with open(enriched_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ========== 小程序 JSON 生成（从 generate_deals_json.py 提取） ==========

CATEGORY_KEYWORDS = {
    "美妆护肤": [
        "面膜", "口红", "护肤", "精华", "防晒", "粉底", "眼影", "腮红",
        "卸妆", "洁面", "水乳", "眼霜", "眉笔", "气垫", "隔离", "遮瑕",
        "素颜霜", "定妆", "美甲", "香水", "素颜", "美白", "补水", "保湿",
        "抗皱", "紧致", "控油", "祛痘", "祛斑", "面霜", "乳液", "爽肤水",
        "精华液", "眼霜", "唇膏", "唇釉", "睫毛", "双眼皮", "美妆",
        "卸妆油", "卸妆水", "洗面奶", "洁面乳", "护肤套装", "彩妆",
        "粉底液", "散粉", "高光", "修容", "假睫毛", "美瞳", "指甲油",
    ],
    "个人护理/洗护": [
        "洗发", "沐浴", "牙膏", "牙刷", "卫生巾", "护垫", "毛巾", "剃须",
        "脱毛", "私处", "护理", "沐浴露", "洗发水", "护发素", "发膜",
        "漱口水", "牙线", "假牙", "棉条", "纸尿裤", "成人尿", "止汗",
        "除臭", "香皂", "洗手液", "沐浴露", "身体乳", "润肤乳", "足浴",
        "泡脚", "剃须刀", "刮毛", "脱毛膏", "女性护理", "卫生棉",
    ],
    "食品饮料": [
        "零食", "牛奶", "咖啡", "坚果", "大米", "食用油", "茶叶", "饮料",
        "饼干", "巧克力", "糖果", "白酒", "红酒", "啤酒", "蜂蜜", "燕麦",
        "豆浆", "奶茶", "果汁", "矿泉水", "方便面", "火腿肠", "腊肉",
        "香肠", "酱", "醋", "调料", "调味品", "面粉", "面条", "米粉",
        "面包", "蛋糕", "糕点", "果脯", "蜜饯", "肉干", "肉脯", "鱼干",
        "海苔", "薯片", "膨化", "冲饮", "奶粉", "酸奶", "奶酪", "黄油",
        "蛋白粉", "代餐", "膳食纤维", "维生素", "鱼油", "钙片",
    ],
    "家用电器": [
        "电饭煲", "微波炉", "烤箱", "空气炸锅", "扫地机", "吸尘器", "洗衣机",
        "冰箱", "空调", "电视", "热水器", "净水器", "加湿器", "除湿机",
        "电风扇", "暖风机", "挂烫机", "除螨仪", "破壁机", "豆浆机", "电磁炉",
        "电压力锅", "电炖锅", "电蒸锅", "电饼铛", "电水壶", "养生壶",
        "咖啡机", "榨汁机", "料理机", "绞肉机", "和面机", "面包机",
        "洗碗机", "消毒柜", "油烟机", "燃气灶", "集成灶", "蒸烤一体机",
        "干衣机", "烘干机", "除湿", "新风", "空气净化器", "风扇",
        "取暖器", "暖脚宝", "电热毯", "毛球修剪器", "灭蚊灯", "驱蚊",
    ],
    "数码3C": [
        "手机", "耳机", "平板", "电脑", "键盘", "鼠标", "相机", "充电宝",
        "数据线", "充电器", "U盘", "硬盘", "路由器", "摄像头", "智能手表",
        "手环", "投影仪", "打印机", "手机壳", "贴膜", "保护套", "支架",
        "蓝牙", "音箱", "音响", "麦克风", "游戏机", "手柄", "VR", "AR",
        "无人机", "稳定器", "三脚架", "自拍杆", "转接头", "扩展坞",
        "内存条", "显卡", "主板", "CPU", "机箱", "电源", "散热器",
        "显示器", "键鼠", "数码", "电子", "智能设备", "智能家居",
    ],
    "服饰鞋包": [
        "T恤", "衬衫", "羽绒服", "棉服", "外套", "裤子", "裙子", "连衣裙",
        "内衣", "袜子", "运动鞋", "皮鞋", "靴子", "包包", "行李箱", "帽子",
        "围巾", "手套", "皮带", "领带", "卫衣", "毛衣", "针织", "牛仔",
        "风衣", "大衣", "西装", "夹克", "皮衣", "打底", "塑身", "泳装",
        "睡衣", "家居服", "拖鞋", "高跟鞋", "帆布鞋", "板鞋", "雪地靴",
        "登山鞋", "跑步鞋", "训练鞋", "休闲鞋", "凉鞋", "双肩包", "单肩包",
        "手提包", "钱包", "斜挎包", "公文包", "旅行包", "运动包",
    ],
    "运动户外": [
        "瑜伽", "跑步", "健身", "帐篷", "睡袋", "登山", "钓鱼", "自行车",
        "游泳", "球拍", "篮球", "足球", "滑板", "护具", "运动服", "哑铃",
        "拉力器", "弹力带", "呼啦圈", "跳绳", "拳击", "护腕", "护膝",
        "护踝", "运动", "户外", "徒步", "露营", "野餐", "烧烤", "钓具",
        "泳镜", "泳帽", "冲浪", "滑雪", "滑冰", "溜冰", "滑板车", "平衡车",
        "登山杖", "户外鞋", "冲锋衣", "速干", "防晒衣", "运动帽",
    ],
    "母婴": [
        "奶粉", "纸尿裤", "奶瓶", "婴儿", "孕妇", "辅食", "推车", "安全座椅",
        "童装", "玩具", "尿不湿", "吸奶器", "温奶器", "婴儿床", "餐椅",
        "哺乳", "月子", "待产", "产后", "孕产妇", "宝宝", "幼儿", "儿童",
        "积木", "绘本", "早教", "启蒙", "安抚", "磨牙", "牙胶", "围兜",
        "隔尿垫", "护臀", "润肤", "驱蚊", "蚊虫", "儿童鞋", "童鞋",
        "学步", "背腰凳", "婴儿车", "伞车", "高脚椅", "床围栏",
    ],
    "家居日用": [
        "纸巾", "洗衣液", "洗洁精", "垃圾袋", "收纳", "床上用品", "枕头",
        "被子", "床垫", "窗帘", "地毯", "毛巾", "浴巾", "餐具", "锅具",
        "刀具", "保鲜盒", "保温杯", "雨伞", "电池", "拖把", "扫帚",
        "簸箕", "抹布", "百洁布", "钢丝球", "清洁剂", "消毒液", "香薰",
        "空气清新", "除湿盒", "干燥剂", "防霉", "驱虫", "蟑螂", "蚂蚁",
        "老鼠", "粘鼠板", "花洒", "马桶", "下水", "地漏", "挂钩", "置物架",
        "衣架", "晾衣架", "收纳箱", "收纳盒", "整理箱", "真空袋", "压缩袋",
        "桌布", "餐垫", "围裙", "手套", "清洁刷", "马桶刷", "垃圾桶",
    ],
    "文具办公": [
        "笔", "笔记本", "文件夹", "胶带", "订书机", "计算器", "白板",
        "便签", "文具", "画笔", "墨水", "钢笔", "中性笔", "圆珠笔", "铅笔",
        "马克笔", "荧光笔", "蜡笔", "彩铅", "水彩", "国画", "油画", "素描",
        "书法", "字帖", "画板", "画架", "颜料", "橡皮", "尺子", "圆规",
        "剪刀", "美工刀", "裁纸刀", "削笔器", "笔袋", "笔盒", "书包",
        "文件袋", "档案袋", "资料册", "相册", "证书", "奖状", "信封",
        "信纸", "打印纸", "复印纸", "传真纸", "收银纸", "不干胶", "标签",
        "便利贴", "记事本", "日记本", "手账", "贴纸", "修正带", "修正液",
        "胶水", "胶棒", "双面胶", "透明胶", "长尾夹", "回形针", "图钉",
        "打孔机", "装订机", "塑封机", "碎纸机", "过塑膜", "塑封膜",
    ],
    "医药保健": [
        "维生素", "蛋白粉", "血压计", "按摩仪", "血糖", "轮椅", "制氧机",
        "雾化器", "体温计", "创可贴", "口罩", "消毒", "保健", "养生",
        "阿胶", "燕窝", "枸杞", "药", "药房", "药房", "中药", "西药",
        "中成药", "草药", "人参", "鹿茸", "三七", "灵芝", "冬虫夏草",
        "蜂蜜", "蜂胶", "蜂王浆", "螺旋藻", "叶酸", "钙", "铁", "锌",
        "硒", "益生菌", "酵素", "胶原蛋白", "葡萄籽", "叶黄素",
        "褪黑素", "辅酶Q10", "鱼肝油", "DHA", "氨基酸", "微量元素",
        "护肝", "养胃", "补肾", "壮阳", "减肥", "瘦身", "通便", "止咳",
        "感冒", "退烧", "消炎", "止痛", "过敏", "湿疹", "皮炎", "痔疮",
        "眼药水", "滴鼻液", "口腔溃疡", "跌打", "扭伤", "膏药", "贴膏",
        "理疗", "牵引", "矫正", "护腰带", "护颈", "护膝", "护踝",
    ],
    "宠物": [
        "猫粮", "狗粮", "猫砂", "宠物", "猫", "狗", "鱼缸", "鱼食",
        "猫窝", "狗窝", "猫爬架", "狗链", "牵引", "宠物服", "宠物鞋",
        "宠物食品", "宠物零食", "宠物玩具", "宠物用品", "猫罐头", "狗罐头",
        "猫条", "冻干", "营养膏", "化毛膏", "驱虫", "洗护", "美容",
        "指甲剪", "梳子", "刷子", "尿垫", "训狗", "狗笼", "猫笼",
        "鸟", "兔", "仓鼠", "龙猫", "乌龟", "爬虫", "水族",
    ],
    "图书音像": [
        "图书", "小说", "教材", "考试", "漫画", "绘本", "音乐", "CD",
        "DVD", "电子书", "书籍", "图书", "出版", "名著", "文学", "历史",
        "哲学", "心理", "社会", "科学", "技术", "工程", "数学", "物理",
        "化学", "生物", "地理", "天文", "医学", "农业", "工业", "交通",
        "航空", "航天", "环境", "能源", "经济", "金融", "会计", "管理",
        "营销", "法律", "政治", "军事", "教育", "体育", "美术", "书法",
        "音乐", "舞蹈", "戏剧", "电影", "摄影", "设计", "建筑", "计算机",
        "编程", "算法", "网络", "安全", "数据库", "操作系统", "移动开发",
        "前端", "后端", "人工智能", "机器学习", "深度学习", "大数据",
        "公务员考试", "考研", "英语四六级", "托福", "雅思", "GRE",
        "绘本", "故事", "童话", "寓言", "成语", "百科", "百科",
        "字典", "词典", "手册", "工具书", "杂志", "期刊", "报纸",
    ],
    "珠宝配饰": [
        "项链", "戒指", "手镯", "耳环", "珠宝", "黄金", "钻石", "翡翠",
        "玉", "手表", "眼镜", "太阳镜", "钻戒", "吊坠", "手链", "脚链",
        "胸针", "发饰", "头饰", "项链", "项圈", "玉佩", "琥珀", "珍珠",
        "宝石", "水晶", "玛瑙", "碧玺", "石榴石", "橄榄石", "托帕石",
        "锆石", "铂金", "K银", "银饰", "纯银", "千足金", "足金",
        "近视镜", "老花镜", "墨镜", "偏光镜", "护目镜", "游泳镜",
        "智能手表", "运动手表", "机械表", "石英表", "电子表",
    ],
}

CATEGORY_LIST = list(CATEGORY_KEYWORDS.keys())


def classify_by_keywords(title, api_category="", api_sub_category=""):
    """根据关键词匹配商品所属一级分类"""
    text = f"{title} {api_category} {api_sub_category}".lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return category
    return None


def extract_number(text):
    """从文本中提取数字"""
    if not text:
        return 0
    text = text.replace(",", "").replace("，", "")
    import re
    nums = re.findall(r"(\d+\.?\d*)", text)
    return float(nums[0]) if nums else 0


def format_deal(deal, index):
    """将 deal 格式化为小程序需要的格式"""
    price = str(deal.get("price", "")).replace("¥", "").replace("￥", "")
    predict = str(deal.get("predict_price", "")).replace("¥", "").replace("￥", "")
    coupon_price = str(deal.get("coupon_price", "")).replace("¥", "").replace("￥", "")
    gov_subsidy = str(deal.get("gov_subsidy", "")).replace("¥", "").replace("￥", "")

    discount_pct = deal.get("discount", 0)
    if not discount_pct:
        price_num = extract_number(price)
        predict_num = extract_number(predict)
        if price_num > 0 and predict_num > 0 and price_num > predict_num:
            discount_pct = int(round((1 - predict_num / price_num) * 100))

    tags_str = deal.get("tags", "")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

    coupon_details = deal.get("coupon_details", "")
    if coupon_details:
        tags.append(coupon_details)
    if gov_subsidy and float(gov_subsidy) > 0:
        tags.append(f"国家补贴¥{gov_subsidy}")

    taokouling = deal.get("taokouling", "")
    url = deal.get("url", "")

    title = deal.get("title", "")
    api_category = deal.get("category", "")
    api_sub_category = deal.get("sub_category", "")
    matched_category = classify_by_keywords(title, api_category, api_sub_category)

    return {
        "id": index,
        "title": deal.get("title", ""),
        "price": price,
        "predict_price": predict,
        "coupon_price": coupon_price,
        "gov_subsidy": gov_subsidy,
        "discount": discount_pct,
        "category": matched_category,
        "sub_category": deal.get("sub_category", ""),
        "shop": deal.get("shop", ""),
        "img_url": deal.get("img_url", ""),
        "url": url,
        "taokouling": taokouling,
        "tags": tags,
        "source": deal.get("source", ""),
        "annual_vol": deal.get("annual_vol", ""),
        "tk_total_sales": deal.get("tk_total_sales", ""),
    }


def generate_mini_program_json(output_dir):
    """生成小程序用的 deals.json 和 categories.json"""
    # 加载已enrichment的商品
    enriched_deals = load_enriched_deals(output_dir)
    if not enriched_deals:
        print("⚠️ 暂无已处理的商品数据")
        return

    print(f"\n📊 生成小程序 JSON（{len(enriched_deals)} 条已处理商品）")

    # 折扣过滤
    final_deals = filter_by_discount(enriched_deals, min_discount=10)

    # 基础过滤
    valid_deals = []
    for d in final_deals:
        price = str(d.get("price", "")).replace("¥", "").replace("￥", "")
        predict = str(d.get("predict_price", "")).replace("¥", "").replace("￥", "")
        price_num = extract_number(price)
        predict_num = extract_number(predict)
        if price_num <= 0:
            continue
        url = d.get("url", "")
        if not url:
            continue
        if predict_num > 0 and predict_num >= price_num:
            continue
        valid_deals.append(d)

    # 格式化
    formatted = [format_deal(d, i) for i, d in enumerate(valid_deals)]

    # 只保留匹配到分类的商品
    categorized = [d for d in formatted if d["category"] is not None]
    print(f"  分类匹配: {len(categorized)} 条")

    # 按品类分组
    by_category = defaultdict(list)
    for d in categorized:
        by_category[d["category"]].append(d)

    cat_list = CATEGORY_LIST
    cat_order = {name: idx for idx, name in enumerate(cat_list)}

    # 生成两级类目列表
    categories = []
    for cat in sorted(by_category.keys(), key=lambda x: cat_order.get(x, 999)):
        items = by_category[cat]
        sub_cat_count = defaultdict(int)
        for item in items:
            sub = item.get("sub_category", "") or "其他"
            sub_cat_count[sub] += 1
        sub_cats = sorted(sub_cat_count.items(), key=lambda x: -x[1])
        categories.append({
            "name": cat,
            "count": len(items),
            "subs": [{"name": s[0], "count": s[1]} for s in sub_cats]
        })

    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 保存 deals.json
    deals_data = {
        "total": len(categorized),
        "updateTime": update_time,
        "deals": categorized
    }
    with open(os.path.join(output_dir, "deals.json"), "w", encoding="utf-8") as f:
        json.dump(deals_data, f, ensure_ascii=False, indent=2)

    # 保存 categories.json
    with open(os.path.join(output_dir, "categories.json"), "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    print(f"✅ 生成完成: {len(categorized)} 条商品, {len(categories)} 个品类")
    print(f"   - deals.json ({len(categorized)} 条)")
    print(f"   - categories.json ({len(categories)} 个品类)")

    # 输出分类统计
    print(f"\n[分类统计]")
    cat_count = defaultdict(int)
    for d in categorized:
        cat_count[d["category"]] += 1
    for cat in cat_list:
        cnt = cat_count.get(cat, 0)
        if cnt > 0:
            print(f"  {cat}: {cnt} 条")


def main():
    parser = argparse.ArgumentParser(description="Workflow 2: 分批补充价格 → 生成小程序JSON")
    parser.add_argument("--output", default="docs", help="输出目录")
    parser.add_argument("--batch-size", type=int, default=200, help="每批处理数量")
    parser.add_argument("--reset", action="store_true", help="重置进度，从头开始处理")
    parser.add_argument("--skip-enrich", action="store_true", help="跳过enrichment，直接生成JSON")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    print("=" * 60)
    print("Workflow 2: 分批补充价格 → 折扣过滤 → 生成小程序JSON")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 加载原始商品名单
    raw_deals = load_raw_deals(args.output)
    if raw_deals is None:
        sys.exit(1)

    print(f"原始商品名单: {len(raw_deals)} 条")

    # 加载进度
    progress = load_progress(args.output)
    if args.reset:
        progress = {"start_index": 0, "total": len(raw_deals), "last_run": None, "completed": False}
        print("🔄 重置进度，从头开始处理")

    # 检查是否已完成
    if progress.get("completed"):
        print("✅ 所有商品已处理完毕，直接生成小程序JSON")
        generate_mini_program_json(args.output)
        sys.exit(0)

    # 检查是否有需要处理的商品
    start_index = progress.get("start_index", 0)
    if start_index >= len(raw_deals):
        print(f"✅ 所有商品已处理完毕（{start_index}/{len(raw_deals)}）")
        progress["completed"] = True
        save_progress(args.output, progress)
        generate_mini_program_json(args.output)
        sys.exit(0)

    # 执行enrichment
    print(f"\n📦 开始处理: 从第 {start_index+1} 条开始，本批 {args.batch_size} 条")
    enriched_batch, end_index, total = enrich_deals_batch(
        raw_deals,
        batch_size=args.batch_size,
        start_index=start_index
    )

    if not enriched_batch:
        print("⚠️ 本批无商品需要处理")
        sys.exit(0)

    # 加载已有的enriched商品并追加
    existing_enriched = load_enriched_deals(args.output)

    # 如果是重置后的第一批，覆盖；否则追加
    if args.reset or start_index == 0:
        all_enriched = enriched_batch
    else:
        all_enriched = existing_enriched + enriched_batch

    # 保存
    save_enriched_deals(args.output, all_enriched)

    # 更新进度
    progress["start_index"] = end_index
    progress["total"] = total
    if end_index >= total:
        progress["completed"] = True
        print(f"\n🎉 所有商品处理完毕！（{total}/{total}）")
    save_progress(args.output, progress)

    print(f"\n进度: {end_index}/{total} ({end_index/total*100:.1f}%)")
    print(f"已处理商品: {len(all_enriched)} 条")

    # 生成小程序JSON
    generate_mini_program_json(args.output)

    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
