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


# 淘宝二级类目 → 9大精简类目映射（覆盖所有API返回的category_name值）
CATEGORY_MERGE_MAP = {
    # ========== 母婴 ==========
    "0-6月": "母婴", "1-3岁": "母婴", "4-6岁": "母婴",
    "7-12月": "母婴", "7-12岁": "母婴",
    "备孕": "母婴", "待产包/待产礼盒": "母婴", "产妇卫生巾": "母婴",
    "婴童柔巾": "母婴", "儿童水杯": "母婴", "吸奶器": "母婴",
    "奶瓶": "母婴", "连身衣/爬服/哈衣": "母婴", "防撞角": "母婴",
    "床护栏": "母婴", "高佣母婴": "母婴", "高佣综合": "母婴",
    "钙铁锌": "母婴", "钙铁锌/钙镁": "母婴", "钙镁锌": "母婴",
    "维生素D": "母婴", "鱼油/深海鱼油": "母婴", "益生菌": "母婴",
    "鼻毛修剪器/电动修眉器": "母婴",
    "婴童用品": "母婴", "婴童尿裤": "母婴", "婴童洗护": "母婴",
    "孕妇装/孕产妇用品/营养": "母婴", "童装/婴儿装/亲子装": "母婴",
    "儿童奶粉（非4段）": "母婴", "哺乳文胸": "母婴",
    "孕产妇bb霜": "母婴", "乳房乳霜/羊脂膏": "母婴",
    "看护垫/一次性床垫": "母婴", "名字贴": "母婴",
    "儿童机器人/变形玩具": "母婴", "其他益生菌": "母婴",
    "DHA/鱼油/藻油": "母婴", "褪黑素/γ-氨基丁酸/圣约翰草": "母婴",
    "氨糖软骨素/骨胶原": "母婴",

    # ========== 日用品 ==========
    "洗护清洁剂/卫生巾/纸/香薰": "日用品", "居家日用": "日用品",
    "收纳整理": "日用品", "个人护理/保健/按摩器材": "日用品",
    "餐饮具": "日用品", "床上用品": "日用品",
    "箱包皮具/热销女包/男包": "日用品", "运动包/户外包/配件": "日用品",
    "户外/登山/野营/旅行用品": "日用品",
    "家用垃圾袋": "日用品", "抹布": "日用品",
    "礼品袋/塑料袋": "日用品", "塑料自封袋": "日用品",
    "缠绕膜": "日用品", "气泡膜": "日用品", "包装胶带": "日用品",
    "马桶刷/厕所刷": "日用品", "垃圾桶": "日用品",
    "围裙": "日用品", "杯架": "日用品",
    "搁板/置物架/家用陈列架": "日用品", "刀架": "日用品",
    "蔬果刨丝器/瓜果刀": "日用品", "车掸/蜡拖": "日用品",
    "卫生巾": "日用品", "抽纸": "日用品", "保湿纸巾/乳霜纸/云柔巾": "日用品",
    "保鲜膜套": "日用品", "内衣洗衣液": "日用品",
    "一次性擦脚纸/巾": "日用品", "一次性内裤/日抛裤": "日用品",
    "乳胶枕": "日用品", "便携/折叠餐具": "日用品",
    "保健护具(护腰/膝/腿/颈)": "日用品", "保冷/保温杯": "日用品",
    "其他收纳盒": "日用品", "冲锋衣": "日用品",
    "剃须刀配件": "日用品", "定制纸巾": "日用品",
    "家居服套装": "日用品", "床单": "日用品",
    "床垫/床褥/床护垫/榻榻米床垫": "日用品", "桌面收纳盒": "日用品",
    "棉柔巾/洗脸巾": "日用品", "毛巾": "日用品",
    "湿厕纸": "日用品", "餐具笼/架": "日用品",
    "餐巾纸": "日用品", "饭盒/保温桶/保温提锅": "日用品",
    "马克杯": "日用品", "马桶清洁剂/洁厕剂": "日用品",
    "保鲜袋/食品袋/密封袋": "日用品", "除螨喷雾": "日用品",
    "空气芳香剂": "日用品", "香包/香囊": "日用品",
    "鞋拔": "日用品", "雨鞋/雨靴": "日用品",
    "高佣家居家装": "日用品", "高佣鞋包": "日用品",
    "高佣内衣": "日用品", "高佣男装": "日用品",
    "高佣女装": "日用品", "高佣美妆": "日用品",
    "高佣运动户外": "日用品", "高佣食品": "日用品",
    # 补充遗漏
    "被子压缩袋": "日用品", "被套": "日用品",
    "头灯": "日用品", "咖啡杯": "日用品",
    "其它": "日用品", "内裤": "母婴",
    "套装": "母婴", "乳贴": "服饰",
    "板鞋": "服饰", "山楂类制品": "美食",
    "有好货精品": "日用品",
    # 家居家具
    "懒人沙发": "日用品", "布艺沙发": "日用品", "沙发床": "日用品",
    "高低/子母床": "日用品", "靠垫/抱枕": "日用品", "午睡枕": "日用品",
    "平板拖把": "日用品", "杀虫剂（卫生农药）": "日用品",
    # 其他日用
    "节日装扮用品": "日用品", "车条/幅条": "日用品",
    "制动弹簧": "日用品", "理发器": "日用品",
    "皮肤消毒护理（消）": "日用品", "祛疤产品": "日用品",
    "安睡裤/安心裤": "日用品",
    "膏药贴（器械）": "日用品", "眼部清洁": "日用品",
    "耳部清洁": "日用品", "按摩温熏调理器配件": "日用品",
    "厨房置物架/置物柜/角架": "日用品", "挂钩/粘钩": "日用品",
    "漏勺/滤网勺": "日用品", "蚊帐": "日用品",
    "麻将垫": "日用品", "胶水": "日用品",
    "胶带/胶纸/胶条": "日用品", "油污清洁剂": "日用品",
    "牙膏": "日用品", "牙刷头": "日用品",
    "湿巾": "日用品", "手帕纸": "日用品",
    "浴巾": "日用品", "松紧带": "日用品",
    "摩托车轮胎": "日用品", "汽车电路测电笔": "日用品",
    "普通干电池": "日用品", "配方介质/营养土": "日用品",

    # ========== 数码 ==========
    "3C数码配件": "数码", "电脑硬件/显示器/电脑周边": "数码",
    "影音电器": "数码", "硒鼓/粉盒": "数码", "网络工具": "数码",
    "手机": "数码", "智能手表": "数码",
    "接线板": "数码", "插头": "数码",
    "手机保护套/壳": "数码", "手机充电器": "数码",
    "手机数据线": "数码", "手机零部件": "数码",
    "数据线": "数码", "无线/蓝牙音箱": "数码",
    "普通真无线耳机": "数码", "真无线降噪耳机": "数码",
    "智能手表手环表带/腕带": "数码", "蓝牙耳机": "数码",
    "儿童手表充电/数据线": "数码", "手写笔": "数码",
    "键盘刷": "数码", "平板电脑屏幕贴膜": "数码",
    "移动电源": "数码",

    # ========== 家电 ==========
    "数码家电": "家电",  # 淘宝一级类目，必须放在数码区之后
    "高佣数码家电": "家电",
    "净水/饮水机配件耗材": "家电", "绞肉机/碎肉宝": "家电",
    "面包机": "家电", "养生壶/煎药壶/养生杯": "家电",
    "破壁机": "家电", "烧烤炉": "家电", "面条机/压面机": "家电",
    "砂锅/石锅": "家电", "炒锅": "家电", "蒸锅/蒸桶": "家电",
    "菜刀": "家电", "剃须刀": "家电",
    "净水器": "家电", "电饼铛/华夫饼机/薄饼机": "家电",
    "厨房/烹饪用具": "家电", "厨房电器": "家电",
    "生活电器": "家电", "大家电": "家电",

    # ========== 美食 ==========
    "咖啡/麦片/冲饮": "美食", "零食/坚果/特产": "美食",
    "粮油调味/速食/干货/烘焙": "美食", "茶": "美食",
    "保健食品/膳食营养补充食品": "美食", "医疗器械": "美食",
    "保健用品": "美食", "宠物/宠物食品及用品": "美食",
    "鸡蛋": "美食", "冰淇淋/冻品": "美食",
    "腌制/榨菜/泡菜": "美食", "其他药食同源食品": "美食",
    "蜂蜜糖/蜂制品": "美食", "牛肉饼/汉堡饼": "美食",
    "阿胶糕/固元糕": "美食", "鹿制膏/鹿制品": "美食",
    "滋补经典方/精制中药材": "美食",
    "B族维生素": "美食", "乳清蛋白": "美食",
    "中式糕点/新中式糕点": "美食", "传统糖果": "美食",
    "传统西式糕点": "美食", "全家营养奶粉": "美食",
    "再制奶酪": "美食", "曲奇饼干": "美食",
    "月饼": "美食", "火锅调料": "美食",
    "特色干货及养生干料": "美食", "特色米/面粉/杂粮": "美食",
    "玉米": "美食", "氨基酸/支链氨基酸/谷氨酰胺": "美食",
    "纯果蔬汁/纯果汁": "美食", "纯牛奶": "美食",
    "速溶咖啡": "美食", "酥性饼干": "美食",
    "酵母粉": "美食", "豆腐皮/腐竹/豆制品干货": "美食",
    "调制乳（风味奶）": "美食", "笋类制品": "美食",
    "蟹系列": "美食", "食盐": "美食",
    "蓟类": "美食", "水果叉/水果签": "美食",
    "野餐餐具": "美食", "狗笼子": "美食",
    "下饭/拌饭酱/拌饭料": "美食", "冲泡方便面/拉面/面皮": "美食",
    "包点": "美食", "夹心饼干": "美食",
    "干脆面": "美食", "巧克力制品": "美食",
    "方便粉丝/粉条": "美食", "水饺/煎饺/虾饺": "美食",
    "杂粮组合/膳食混合谷物": "美食", "白酒/调香白酒": "美食",
    "碳酸饮料": "美食", "豆浆": "美食",
    "辣椒酱": "美食", "速食粥": "美食",
    "酱油": "美食", "酱类调料": "美食",
    "银耳/冻干银耳及银耳制品": "美食", "陈皮": "美食",
    "面粉/食用粉": "美食", "香肠/腊肠/烤肠": "美食",
    "笋干": "美食", "猫全价膨化粮": "美食",
    "大蒜": "美食", "复合食品调味剂": "美食",

    # ========== 美妆 ==========
    "彩妆/香水/美妆工具": "美妆", "美容护肤/美体/精油": "美妆",
    "美发护发/假发": "美妆", "彩色隐形眼镜": "美妆",
    "乳液/面霜": "美妆", "化妆/美容工具": "美妆",
    "化妆水/爽肤水": "美妆", "卸妆": "美妆",
    "发胶/发泥/发蜡": "美妆", "护手霜": "美妆",
    "气垫": "美妆", "洁面": "美妆",
    "洗发水": "美妆", "男士护理套装": "美妆",
    "盖白": "美妆", "眉笔/眉粉/眉膏": "美妆",
    "粉底液/膏": "美妆", "蜜粉/散粉": "美妆",
    "贴片面膜": "美妆", "身体乳/霜": "美妆",
    "面部护理套装": "美妆", "香水": "美妆",
    "维生素/复合维生素": "美妆",
    "发膜/蒸汽发膜/焗油膏": "美妆", "涂抹面膜": "美妆",
    "液态精华": "美妆", "身体乳液": "美妆",
    "隔离/妆前/素颜霜": "美妆", "面部护理用品": "美妆",
    "按摩油": "美妆",

    # ========== 服饰 ==========
    "女装/女士精品": "服饰", "男装": "服饰",
    "女士内衣/男士内衣/家居服": "服饰", "流行男鞋": "服饰",
    "运动鞋new": "服饰", "高跟鞋": "服饰", "运动鞋": "服饰",
    "运动长裤": "服饰", "腰带/皮带/腰链": "服饰",
    "耳环": "服饰", "耳钉": "服饰", "手镯": "服饰", "手链": "服饰",
    "潮流范": "服饰", "国产腕表": "服饰",
    "儿童棉拖鞋": "服饰", "梳子/化妆梳/按摩梳": "服饰",
    "T恤": "服饰", "中山装": "服饰", "中筒袜": "服饰",
    "中老年上装": "服饰", "休闲裤": "服饰", "其他民族服装": "服饰",
    "塑身美体裤": "服饰", "女三角裤": "服饰", "少女文胸": "服饰",
    "平角裤": "服饰", "打底裤": "服饰", "文胸": "服饰",
    "时尚休闲鞋": "服饰", "时尚防晒服": "服饰",
    "牛仔裤": "服饰", "短外套": "服饰",
    "棉衣": "服饰", "正装皮鞋": "服饰",
    "男三角内裤": "服饰", "男平角内裤": "服饰",
    "登山鞋/徒步鞋": "服饰", "衬衫": "服饰",
    "连衣裙": "服饰", "连裤袜/打底袜": "服饰",
    "羽绒服": "服饰", "睡衣/家居服套装": "服饰",
    "泳镜": "服饰", "高佣鞋包": "服饰",
    "高佣女装": "服饰", "高佣男装": "服饰",
    "一字拖": "服饰", "洞洞鞋": "服饰",
    "毛衣": "服饰", "真丝上装": "服饰",
    "头巾/遮耳": "服饰", "大码内搭": "服饰",
    "发饰": "服饰", "颈饰": "服饰",
    "手饰": "服饰", "高跟凉鞋": "服饰",
    "跑步鞋": "服饰", "运动裤卫裤": "服饰",
    "护膝/护腰/护肩/护颈": "服饰", "床品套件/四件套/多件套": "服饰",

    # ========== 图书 ==========
    "文具用品/文化用品/商务用品": "图书", "小学教辅": "图书",
    "中学教辅": "图书", "笔": "图书", "打印纸": "图书",
    "漫画书籍": "图书", "漫画类原版书": "图书", "生活类原版书": "图书",
    "青春/都市/言情/轻小说": "图书", "兴趣/生活": "图书",
    "桌游配件/卡套/保护膜": "图书",
    "中性笔": "图书", "书皮/书衣": "图书",
    "地球仪": "图书", "折纸/手工纸/衍纸": "图书",
    "毛笔": "图书", "马克笔": "图书",

    # ========== 玩具 ==========
    "玩具/童车/益智/早教/游乐设备": "玩具",
    "合金车/玩具仿真车/收藏车模": "玩具", "高达模型专区": "玩具",
    "普通塑料积木": "玩具", "火车/摩托/汽车模型": "玩具",
    "变形金刚模型专区": "玩具", "手办/手办景品": "玩具",
    "机器人/机甲成品/变形系列": "玩具",
    "数学学习板/计算架": "玩具", "色子/骰子": "玩具",
    "篮球": "玩具", "马夹": "玩具",
    "潮玩盲盒": "玩具", "游戏/电竞实物周边": "玩具",
    "球类玩具/球类运动": "玩具", "飞盘/飞碟/竹蜻蜓类": "玩具",
    "海报/色纸": "玩具", "点心包装盒/包装袋/包装纸": "玩具",
    "期刊杂志": "图书",
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


# 9大目标类目
TARGET_CATEGORIES = ["母婴", "日用品", "数码", "家电", "美食", "美妆", "服饰", "图书", "玩具"]

# 硅基流动 API 配置
SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
SILICONFLOW_API_URL = "https://api.siliconflow.cn/v1/chat/completions"

# LLM 分类缓存（避免重复调用）
_llm_category_cache = {}

# LLM 调用统计
_llm_stats = {
    "total_calls": 0,       # 总调用次数（不含缓存命中）
    "success": 0,           # 成功分类次数（返回非"其他"）
    "failed": 0,            # 调用失败次数
    "cache_hits": 0,        # 缓存命中次数
    "returned_other": 0,    # LLM返回"其他"的次数
    "api_invalid": False,   # API Key 是否无效（检测到后跳过后续调用）
}


def llm_classify_category(title, raw_category=""):
    """
    使用硅基流动 LLM 对商品标题进行一级类目分类

    Args:
        title: 商品标题
        raw_category: 原始类目（辅助判断）

    Returns:
        分类名称（8大类之一）
    """
    global _llm_stats

    # API Key 未配置或已判定无效时直接跳过
    if not SILICONFLOW_API_KEY or _llm_stats["api_invalid"]:
        return "其他"

    # 缓存 key
    cache_key = f"{title[:30]}|{raw_category}"
    if cache_key in _llm_category_cache:
        _llm_stats["cache_hits"] += 1
        return _llm_category_cache[cache_key]

    _llm_stats["total_calls"] += 1

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
                "model": "deepseek-ai/DeepSeek-V3.2",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 10,
                "temperature": 0
            },
            timeout=10
        )
        result = resp.json()

        # 检测 API Key 是否无效（硅基流动返回 code 30014）
        if result.get("code") == 30014 or "invalid" in str(result.get("message", "")).lower():
            _llm_stats["api_invalid"] = True
            print(f"[LLM] API Key 无效，跳过后续分类调用: {result.get('message', '')}")
            return "其他"

        answer = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

        # 验证返回值是否在目标类目中
        for cat in TARGET_CATEGORIES:
            if cat in answer:
                _llm_stats["success"] += 1
                _llm_category_cache[cache_key] = cat
                return cat

        # LLM 返回了非目标类目的内容
        _llm_stats["returned_other"] += 1
        _llm_category_cache[cache_key] = "其他"
        return "其他"
    except Exception as e:
        _llm_stats["failed"] += 1
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
    """将 deal 格式化为小程序需要的格式"""
    # 价格字段（来自 optional.upgrade API）
    # price = 销售价(zk_final_price)
    # predict_price = 实际到手价(final_promotion_price - gov_subsidy)
    # coupon_price = 券后价(final_promotion_price)
    # gov_subsidy = 政府补贴金额
    # discount = 优惠力度%（已预计算）
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

    # 合并类目：先查映射表，映射不到用LLM判断
    raw_cat = deal.get("category", "")
    merged_cat = merge_category(raw_cat)
    if merged_cat == "其他":
        title = deal.get("title", "")
        if title:
            llm_result = llm_classify_category(title, raw_cat)
            if llm_result != "其他":
                merged_cat = llm_result
        # 统计"其他"类数量
        _other_count = getattr(format_deal, '_other_count', 0) + 1
        format_deal._other_count = _other_count

    return {
        "id": index,
        "title": deal.get("title", ""),
        "price": price,                    # 销售价
        "predict_price": predict,          # 实际到手价
        "coupon_price": coupon_price,      # 券后价
        "gov_subsidy": gov_subsidy,        # 政府补贴
        "discount": discount_pct,          # 优惠力度%
        "category": merged_cat,
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

    # 调试：检查 API Key 是否加载
    print(f"[DEBUG] SILICONFLOW_API_KEY: {'已配置' if SILICONFLOW_API_KEY else '未配置'}")
    format_deal._other_count = 0
    # 重置 LLM 统计
    global _llm_stats
    _llm_stats = {"total_calls": 0, "success": 0, "failed": 0, "cache_hits": 0, "returned_other": 0}

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

        # 输出 LLM 分类统计
        print(f"\n[LLM分类统计]")
        print(f"  映射表归类为'其他': {getattr(format_deal, '_other_count', 0)} 条")
        print(f"  LLM 总调用次数: {_llm_stats['total_calls']}")
        print(f"  缓存命中次数: {_llm_stats['cache_hits']}")
        print(f"  成功分类次数: {_llm_stats['success']}")
        print(f"  返回'其他'次数: {_llm_stats['returned_other']}")
        print(f"  调用失败次数: {_llm_stats['failed']}")
        if _llm_stats['total_calls'] > 0:
            success_rate = _llm_stats['success'] / _llm_stats['total_calls'] * 100
            print(f"  分类成功率: {success_rate:.1f}%")

        return deals_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成小程序优惠数据 JSON")
    parser.add_argument("--output", default="deals-data", help="输出目录")
    parser.add_argument("--search", default=None, help="搜索关键词")
    args = parser.parse_args()

    generate_deals_json(args.output, args.search)
