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
  1. 采集各物料ID的商品（每ID只取第1页）
  2. 只筛选天猫旗舰店商品（店铺名含"旗舰店"）
  3. 按关键词匹配归类到14个一级分类
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


# ========== 一级分类关键词配置 ==========
# 14个一级分类，每个分类对应一组关键词（匹配商品标题/API分类名）
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

# 构建分类列表（固定顺序）
CATEGORY_LIST = list(CATEGORY_KEYWORDS.keys())


def classify_by_keywords(title, api_category="", api_sub_category=""):
    """
    根据关键词匹配商品所属一级分类

    Args:
        title: 商品标题
        api_category: API返回的一级分类名
        api_sub_category: API返回的二级分类名

    Returns:
        分类名称，未匹配返回 None
    """
    # 合并所有文本信息用于匹配
    text = f"{title} {api_category} {api_sub_category}".lower()

    # 按关键词匹配，找到第一个匹配的分类
    # 优先匹配更具体的分类（按CATEGORY_LIST顺序）
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text:
                return category

    return None


def get_category_list():
    """获取一级分类列表（固定顺序）"""
    return CATEGORY_LIST


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

    # 采集全部63个物料ID的商品（每ID只取第1页）
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
    """将 deal 格式化为小程序需要的格式"""
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

    # 关键词匹配确定分类
    title = deal.get("title", "")
    api_category = deal.get("category", "")
    api_sub_category = deal.get("sub_category", "")
    matched_category = classify_by_keywords(title, api_category, api_sub_category)

    return {
        "id": index,
        "title": deal.get("title", ""),
        "price": price,                    # 销售价
        "predict_price": predict,          # 实际到手价
        "coupon_price": coupon_price,      # 券后价
        "gov_subsidy": gov_subsidy,        # 政府补贴
        "discount": discount_pct,          # 优惠力度%
        "category": matched_category,      # 关键词匹配的分类（未匹配为None）
        "sub_category": deal.get("sub_category", ""),
        "shop": deal.get("shop", ""),
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

    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if search_keyword:
        # 搜索模式
        print(f"🔍 搜索: {search_keyword}")
        from tb_api import collect_tb_material_search
        raw_deals = collect_tb_material_search(q=search_keyword, has_coupon=True, page_size=30)
        # 搜索模式：也进行旗舰店筛选+关键词分类
        deals = [format_deal(d, i) for i, d in enumerate(raw_deals)]
        # 过滤：有价格 + 天猫 + 匹配到分类
        deals = [d for d in deals if d["price"] and d.get("user_type") == 1 and d["category"]]

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

        # 2. 基础过滤
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

        # 3. 格式化（含关键词分类）
        formatted = [format_deal(d, i) for i, d in enumerate(valid_deals)]

        # 4. 只保留天猫商品（user_type=1）
        flagship = [d for d in formatted if d.get("user_type") == 1]
        print(f"  天猫筛选: {len(flagship)} 条")

        # 5. 只保留匹配到分类的商品
        categorized = [d for d in flagship if d["category"] is not None]
        print(f"  分类匹配: {len(categorized)} 条")

        # 6. 过滤优惠<10%的商品
        categorized = [d for d in categorized if d["discount"] >= 10]
        print(f"  优惠≥10%: {len(categorized)} 条")

        # 7. 按品类分组（按固定分类顺序）
        from collections import defaultdict
        by_category = defaultdict(list)
        for d in categorized:
            by_category[d["category"]].append(d)

        cat_list = get_category_list()
        cat_order = {name: idx for idx, name in enumerate(cat_list)}

        # 8. 生成两级类目列表（按品类顺序，同品类内按数量降序）
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

        # 9. 保存 deals.json
        deals_data = {
            "total": len(categorized),
            "updateTime": update_time,
            "deals": categorized
        }
        with open(os.path.join(output_dir, "deals.json"), "w", encoding="utf-8") as f:
            json.dump(deals_data, f, ensure_ascii=False, indent=2)

        # 10. 保存 categories.json
        with open(os.path.join(output_dir, "categories.json"), "w", encoding="utf-8") as f:
            json.dump(categories, f, ensure_ascii=False, indent=2)

        print(f"✅ 生成完成: {len(categorized)} 条商品, {len(categories)} 个品类")
        print(f"📁 输出目录: {output_dir}/")
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
        unmatched_flagship = len(flagship) - len(categorized)
        print(f"  未匹配分类: {unmatched_flagship} 条（已过滤）")

        return deals_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成小程序优惠数据 JSON")
    parser.add_argument("--output", default="deals-data", help="输出目录")
    parser.add_argument("--search", default=None, help="搜索关键词")
    args = parser.parse_args()

    generate_deals_json(args.output, args.search)
