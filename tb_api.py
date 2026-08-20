"""
tb_api.py - 淘宝联盟淘宝客优惠券采集

使用淘宝开放平台 API:
  - taobao.tbk.dg.optimus.promotion  权益物料精选（大额店铺券/天猫店铺券等）
  - taobao.tbk.dg.optimus.material   官方物料精选
  - taobao.tbk.tpwd.create           淘口令生成

所需凭证:
  TB_APP_KEY     - AppKey
  TB_APP_SECRET  - AppSecret
  TB_ADZONE_ID   - 推广位ID（数字，如 116310150006）
"""

import os
import json
import time
import hashlib
import requests
from datetime import datetime

# 加载 .env 文件
_env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_file):
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                if val:
                    os.environ[key.strip()] = val

TB_APP_KEY = os.environ.get("TB_APP_KEY", "")
TB_APP_SECRET = os.environ.get("TB_APP_SECRET", "")
TB_ADZONE_ID = os.environ.get("TB_ADZONE_ID", "")

API_GATEWAY = "https://eco.taobao.com/router/rest"

# 权益物料ID -> 名称映射
PROMOTION_IDS = {
    37104: "有价券",
    37116: "大额店铺券",
    62191: "天猫店铺券",
    61809: "券券补",
}


def _make_sign(params, secret):
    """生成淘宝开放平台 API 签名（MD5）"""
    sorted_params = sorted(params.items(), key=lambda x: str(x[0]))
    sign_str = secret
    for k, v in sorted_params:
        sign_str += str(k) + str(v)
    sign_str += secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def _call_tb_api(method, **biz_params):
    """调用淘宝开放平台 API"""
    if not TB_APP_KEY or not TB_APP_SECRET:
        print("[淘宝联盟] 未配置 AppKey/AppSecret，跳过")
        return None

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    params = {
        "app_key": TB_APP_KEY,
        "method": method,
        "timestamp": timestamp,
        "v": "2.0",
        "sign_method": "md5",
        "format": "json",
    }
    params.update(biz_params)
    params["sign"] = _make_sign(params, TB_APP_SECRET)

    try:
        resp = requests.get(API_GATEWAY, params=params, timeout=15)
        result = resp.json()
        if "error_response" in result:
            err = result["error_response"]
            print(f"[淘宝联盟] API 错误: code={err.get('code')}, msg={err.get('msg')}")
            return None
        return result
    except Exception as e:
        print(f"[淘宝联盟] API 调用失败: {e}")
        return None


def collect_tb_promotion_deals(promotion_id=37116, page_num=1, page_size=10):
    """
    淘宝客权益物料精选 - 获取店铺优惠券及推荐商品

    Args:
        promotion_id: 权益物料ID（37104有价券, 37116大额店铺券, 62191天猫店铺券, 61809券券补）
        page_num: 页码
        page_size: 每页条数（最大10）
    """
    deals = []

    biz_params = {
        "adzone_id": TB_ADZONE_ID,
        "promotion_id": promotion_id,
        "page_num": page_num,
        "page_size": min(page_size, 10),
    }

    result = _call_tb_api("taobao.tbk.dg.optimus.promotion", **biz_params)
    if not result:
        return deals

    try:
        resp_key = "tbk_dg_optimus_promotion_response"
        inner = result.get(resp_key, {})
        result_list = inner.get("result_list", {})
        items = result_list.get("map_data", [])

        for item in items:
            shop_name = item.get("nick", "") or item.get("shop_title", "")
            if not shop_name:
                continue

            # 优惠券信息
            promotion_list = item.get("promotion_list", {})
            coupon_details = promotion_list.get("promotion_list", [])

            # 推广链接
            promotion_extend = item.get("promotion_extend", {})
            coupon_url = promotion_extend.get("promotion_url", "")
            if coupon_url and coupon_url.startswith("//"):
                coupon_url = "https:" + coupon_url

            # 推荐商品列表
            recommend_items = promotion_extend.get("recommend_item_list", {})
            recommend_list = recommend_items.get("recommend_item_list", [])

            # 库存信息
            total_count = item.get("total_count", 0)
            remain_count = item.get("remain_count", 0)

            # 时间信息
            end_time_ms = item.get("display_end_time", 0)
            if end_time_ms:
                end_time = datetime.fromtimestamp(int(end_time_ms) / 1000).strftime("%Y-%m-%d")
            else:
                end_time = ""

            # 取第一个优惠券信息作为主要展示
            if coupon_details:
                coupon = coupon_details[0]
                entry_condition = coupon.get("entry_condition", "0")  # 门槛金额
                entry_discount = coupon.get("entry_discount", "0")  # 优惠金额
                condition_type = item.get("condition_type", "1")  # 1满元 2满件
                discount_type = item.get("discount_type", "1")  # 1减钱 2打折

                # 构造优惠券描述
                if condition_type == "1":  # 满元
                    if discount_type == "1":  # 减钱
                        coupon_desc = f"满{entry_condition}减{entry_discount}"
                    else:  # 打折
                        coupon_desc = f"满{entry_condition}打{entry_discount}折"
                else:  # 满件
                    coupon_desc = f"满{entry_condition}件减{entry_discount}"
            else:
                coupon_desc = "店铺优惠券"
                entry_condition = "0"
                entry_discount = "0"

            # 取第一个推荐商品作为展示
            if recommend_list:
                main_item = recommend_list[0]
                item_id = main_item.get("item_id", "")
                item_url = main_item.get("url", "")
                if item_url and item_url.startswith("//"):
                    item_url = "https:" + item_url
            else:
                item_id = ""
                item_url = coupon_url

            # 构造 deal 对象
            deal = {
                "source": "淘宝",
                "title": f"[{shop_name}] {coupon_desc}",
                "price": f"减{entry_discount}元",
                "old_price": f"满{entry_condition}元可用",
                "discount": 0,
                "url": coupon_url if coupon_url else item_url,
                "coupon_url": coupon_url,
                "coupon_quota": float(entry_condition) if entry_condition else 0,
                "coupon_amount": float(entry_discount) if entry_discount else 0,
                "tag": PROMOTION_IDS.get(promotion_id, "淘宝优惠券"),
                "category": "优惠券",
                "sub_category": PROMOTION_IDS.get(promotion_id, "店铺券"),
                "img_url": "",
                "shop": shop_name,
                "sales": int(total_count) if total_count else 0,
                "remain": int(remain_count) if remain_count else 0,
                "coupon_end": end_time,
                "item_id": item_id,
                "item_url": item_url,
                "recommend_count": len(recommend_list),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            deals.append(deal)

    except Exception as e:
        print(f"[淘宝联盟] 解析失败: {e}")
        import traceback
        traceback.print_exc()

    return deals


def generate_taokouling(title, url):
    """
    生成淘口令（用于微信群分享）

    Args:
        title: 商品标题
        url: 推广链接或优惠券链接

    Returns:
        淘口令字符串，失败返回空字符串
    """
    if not title or not url:
        return ""

    biz_params = {
        "text": title[:50],
        "url": url,
    }

    result = _call_tb_api("taobao.tbk.tpwd.create", **biz_params)
    if not result:
        return ""

    try:
        resp_key = "tbk_tpwd_create_response"
        inner = result.get(resp_key, {})
        data = inner.get("data", {})
        model = data.get("model", "")
        return model
    except Exception as e:
        print(f"[淘口令] 解析失败: {e}")
        return ""


def get_tb_material_ids(subject=1, material_type=1, page_size=20):
    """
    获取物料ID列表
    使用 taobao.tbk.optimus.tou.material.ids.get API

    Args:
        subject: 物料主题 (1=综合)
        material_type: 物料类型 (1=通用物料)
        page_size: 每页条数
    """
    material_ids = []

    biz_params = {
        "adzone_id": int(TB_ADZONE_ID),
        "material_query": json.dumps({
            "subject": subject,
            "material_type": material_type,
            "page_no": 1,
            "page_size": page_size,
        }),
    }

    result = _call_tb_api("taobao.tbk.optimus.tou.material.ids.get", **biz_params)
    if not result:
        return material_ids

    try:
        data = result.get("tbk_optimus_tou_material_ids_get_response", {}).get("data", {})
        materials = data.get("tou_materials", [])
        for m in materials:
            mid = m.get("material_id", "")
            name = m.get("material_name", "")
            if mid:
                material_ids.append({"material_id": mid, "name": name})
    except Exception as e:
        print(f"[物料ID获取] 解析失败: {e}")

    return material_ids


def collect_tb_material_recommend(material_id, page_size=20, sub_name=None):
    """
    淘宝客物料推荐 - 根据物料ID获取推荐商品
    使用 taobao.tbk.dg.material.recommend API

    Args:
        material_id: 物料ID (从 optimus.tou.material.ids.get 获取，如 117935)
        page_size: 每页条数（最大100）
        sub_name: 二级类目名称（物料主题名）
    """
    deals = []

    biz_params = {
        "adzone_id": int(TB_ADZONE_ID),
        "material_id": int(material_id),
        "page_no": 1,
        "page_size": min(page_size, 100),
    }

    result = _call_tb_api("taobao.tbk.dg.material.recommend", **biz_params)
    if not result:
        return deals

    try:
        resp_key = "tbk_dg_material_recommend_response"
        inner = result.get(resp_key, {})
        result_list = inner.get("result_list", {})
        items = result_list.get("map_data", [])

        for item in items:
            basic = item.get("item_basic_info", {})
            price_info = item.get("price_promotion_info", {})
            publish_info = item.get("publish_info", {})

            title = basic.get("title", "") or basic.get("short_title", "")
            if not title:
                continue

            # 价格（页面实际显示：zk_final_price → final_promotion_price）
            # zk_final_price         = 销售价格（页面主价格，如 ¥65.8）
            # final_promotion_price  = 预估到手价（实际支付金额，如 ¥14.9）
            # 折扣 = 1 - final_promotion_price / zk_final_price
            zk_price = price_info.get("zk_final_price", "")
            final_price = price_info.get("final_promotion_price", "")

            # 页面主价格（现价）= zk_final_price
            show_price = zk_price or final_price
            # 到手价 = final_promotion_price（比现价低时才有折扣）
            pay_price = final_price if final_price and final_price != show_price else ""

            # 图片
            pict_url = basic.get("pict_url", "")
            if pict_url and not pict_url.startswith("http"):
                pict_url = "https:" + pict_url

            # 店铺
            shop_title = basic.get("shop_title", "")

            # 销量
            annual_vol = basic.get("annual_vol", "")
            tk_sales = basic.get("tk_total_sales", "")

            # 推广链接
            click_url = publish_info.get("click_url", "")
            if click_url and click_url.startswith("//"):
                click_url = "https:" + click_url

            # 佣金（原始值需除以100，如180=1.8%）
            income_info = publish_info.get("income_info", {})
            commission_rate_raw = income_info.get("commission_rate", "")
            if commission_rate_raw:
                commission_rate = f"{float(commission_rate_raw)/100:.1f}%"
            else:
                commission_rate = ""

            # 促销标签
            promo_tags = price_info.get("promotion_tag_list", {})
            tag_list = promo_tags.get("promotion_tag_map_data", [])
            tags = [t.get("tag_name", "") for t in tag_list if t.get("tag_name")]

            deal = {
                "source": "淘宝",
                "title": title[:60],
                "price": f"¥{show_price}" if show_price else "",          # 现价（页面主价格/zk_final_price）
                "old_price": "",  # 不再使用划线价
                "predict_price": f"¥{pay_price}" if pay_price else "",    # 到手价（final_promotion_price）
                "coupon_price": "",
                "discount": 0,
                "url": click_url,
                "coupon_url": "",
                "coupon_quota": 0,
                "coupon_discount": 0,
                "tag": f"物料推荐",
                "category": basic.get("level_one_category_name", ""),
                "sub_category": basic.get("category_name", "") or sub_name or "",
                "img_url": pict_url,
                "shop": shop_title,
                "sales": annual_vol or tk_sales,
                "commission_rate": commission_rate,
                "tags": ", ".join(tags),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            deals.append(deal)

    except Exception as e:
        print(f"[物料推荐] 解析失败: {e}")
        import traceback
        traceback.print_exc()

    return deals


def collect_tb_material_search(q, has_coupon=True, page_size=20):
    """
    淘宝客物料搜索升级版 - 关键词搜索商品
    使用 taobao.tbk.dg.material.optional.upgrade API

    Args:
        q: 搜索关键词
        has_coupon: 是否只查有券商品
        page_size: 每页条数
    """
    deals = []

    biz_params = {
        "adzone_id": int(TB_ADZONE_ID),
        "q": q,
        "page_no": 1,
        "page_size": min(page_size, 100),
        "platform": 2,
    }
    if has_coupon:
        biz_params["has_coupon"] = "true"

    result = _call_tb_api("taobao.tbk.dg.material.optional.upgrade", **biz_params)
    if not result:
        return deals

    try:
        resp_key = "tbk_dg_material_optional_upgrade_response"
        inner = result.get(resp_key, {})
        result_list = inner.get("result_list", {})
        items = result_list.get("map_data", [])

        for item in items:
            basic = item.get("item_basic_info", {})
            price_info = item.get("price_promotion_info", {})
            publish_info = item.get("publish_info", {})

            title = basic.get("title", "") or basic.get("short_title", "")
            if not title:
                continue

            # 价格（页面实际显示：zk_final_price → final_promotion_price）
            # zk_final_price         = 销售价格（页面主价格，如 ¥65.8）
            # final_promotion_price  = 预估到手价（实际支付金额，如 ¥14.9）
            # 折扣 = 1 - final_promotion_price / zk_final_price
            zk_price = price_info.get("zk_final_price", "")
            final_price = price_info.get("final_promotion_price", "")

            # 页面主价格（现价）= zk_final_price
            show_price = zk_price or final_price
            # 到手价 = final_promotion_price（比现价低时才有折扣）
            pay_price = final_price if final_price and final_price != show_price else ""

            # 图片
            pict_url = basic.get("pict_url", "")
            if pict_url and not pict_url.startswith("http"):
                pict_url = "https:" + pict_url

            # 店铺
            shop_title = basic.get("shop_title", "")

            # 销量
            annual_vol = basic.get("annual_vol", "")

            # 推广链接
            click_url = publish_info.get("click_url", "")
            if click_url and click_url.startswith("//"):
                click_url = "https:" + click_url

            # 佣金（原始值需除以100，如180=1.8%）
            income_info = publish_info.get("income_info", {})
            commission_rate_raw = income_info.get("commission_rate", "")
            if commission_rate_raw:
                commission_rate = f"{float(commission_rate_raw)/100:.1f}%"
            else:
                commission_rate = ""

            # 促销标签
            promo_tags = price_info.get("promotion_tag_list", {})
            tag_list = promo_tags.get("promotion_tag_map_data", [])
            tags = [t.get("tag_name", "") for t in tag_list if t.get("tag_name")]

            deal = {
                "source": "淘宝",
                "title": title[:60],
                "price": f"¥{show_price}" if show_price else "",          # 现价（页面主价格/zk_final_price）
                "old_price": "",  # 不再使用划线价
                "predict_price": f"¥{pay_price}" if pay_price else "",    # 到手价（final_promotion_price）
                "coupon_price": "",
                "discount": 0,
                "url": click_url,
                "coupon_url": "",
                "coupon_quota": 0,
                "coupon_discount": 0,
                "tag": f"搜:{q}",
                "category": basic.get("level_one_category_name", ""),
                "sub_category": basic.get("level_two_category_name", "") or q,
                "img_url": pict_url,
                "shop": shop_title,
                "sales": annual_vol,
                "commission_rate": commission_rate,
                "tags": ", ".join(tags),
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            deals.append(deal)

    except Exception as e:
        print(f"[物料搜索] 解析失败: {e}")
        import traceback
        traceback.print_exc()

    return deals


def collect_tb_all(max_pages=3):
    """
    淘宝联盟全量采集 - 多种优惠券类型 + 物料推荐 + 关键词搜索

    Args:
        max_pages: 每种优惠券最多翻几页
    """
    all_deals = []

    # 1. 权益物料精选（店铺券）
    target_promotions = [37116, 62191, 37104, 61809]
    promotion_count = 0
    seen_promo_titles = set()
    for promotion_id in target_promotions:
        for page in range(1, max_pages + 1):
            deals = collect_tb_promotion_deals(
                promotion_id=promotion_id,
                page_num=page,
                page_size=10
            )
            if not deals:
                break
            # 翻页去重：本页全部是重复数据则停止翻页
            new_deals = []
            for d in deals:
                key = d.get("title", "")[:20]
                if key not in seen_promo_titles:
                    seen_promo_titles.add(key)
                    new_deals.append(d)
            if not new_deals:
                break  # 本页全是重复，停止翻页
            all_deals.extend(new_deals)
            promotion_count += len(new_deals)
            time.sleep(0.5)
    print(f"[权益物料精选] {promotion_count} 条")

    # 2. 物料推荐 - 母婴+日用品（基于MATERIAL_ID_REFERENCE.md验证有效的ID）
    # === 母婴类 ===
    # 4040-4045: 母婴主题(备孕/0-6月/7-12月/1-3岁/4-6岁/7-12岁)
    # 13374: 高佣榜-母婴, 27454: 大额券-母婴, 84226: 高佣母婴, 86616: 品牌券-母婴
    # 87579: 母婴团精选, 87578: 品牌团精选
    # === 日用/美妆/食品类 ===
    # 13371: 高佣榜-美妆个护, 13375: 高佣榜-食品
    # 27451: 大额券-食品, 27453: 大额券-美妆个护, 27798: 大额券-家居家装
    # 84227: 高佣美妆, 84228: 高佣美食
    # 86589: 天猫国际直营类目爆款清单
    # 86614: 品牌券-食品, 86619: 品牌券-美妆个护, 86622: 品牌券-家居家装
    # 87575: 美妆物料精选, 91356: 618快消精选
    # 物料ID -> 二级类目名称映射（全部63个有效ID）
    MATERIAL_ID_NAMES = {
        # === 母婴类 ===
        4040: "备孕", 4041: "0-6月", 4042: "7-12月", 4043: "1-3岁", 4044: "4-6岁", 4045: "7-12岁",
        13374: "高佣母婴", 27454: "大额券母婴", 84226: "高佣母婴", 86616: "品牌券母婴",
        87579: "母婴团精选", 87578: "品牌团精选",
        # === 服饰类 ===
        13367: "高佣女装", 13370: "高佣鞋包", 13372: "高佣男装", 13373: "高佣内衣",
        27448: "大额券女装", 28029: "热销大服饰", 84222: "高佣服饰", 84223: "高佣新内衣",
        86617: "品牌券内衣", 86618: "品牌券男装", 86620: "品牌券鞋包", 86623: "品牌券女装",
        92183: "淘宝服饰精选", 4093: "潮流范",
        # === 数码家电 ===
        13369: "高佣数码家电", 84224: "高佣数码", 86621: "品牌券数码", 92182: "天猫品牌团",
        # === 运动户外 ===
        13376: "高佣运动户外", 86615: "品牌券运动", 88344: "运动精选",
        # === 美妆 ===
        13371: "高佣美妆", 27453: "大额券美妆", 84227: "高佣美妆", 86619: "品牌券美妆",
        87575: "美妆精选", 86589: "天猫国际",
        # === 美食 ===
        13375: "高佣食品", 27451: "大额券食品", 84228: "高佣美食", 86614: "品牌券食品",
        # === 日用品/家居 ===
        13368: "高佣家居家装", 27798: "大额券家居", 86622: "品牌券家居",
        13366: "高佣综合", 27446: "大额券综合", 28026: "热销综合",
        28027: "热销大快消", 28028: "热销电器美家",
        # === 其他 ===
        84229: "高佣猫超", 84230: "高佣精选", 84225: "高佣文娱",
        86592: "国际直营爆款", 86594: "天天特卖", 86595: "品牌精选",
        86637: "猜你喜欢", 4092: "有好货精品",
        117935: "直播闪降", 98168: "品牌精选", 92184: "珠宝精选",
        91356: "快消精选",
    }
    TARGET_MATERIAL_IDS = list(MATERIAL_ID_NAMES.keys())
    recommend_count = 0
    seen_recommend_ids = set()
    for mid in TARGET_MATERIAL_IDS:
        sub_name = MATERIAL_ID_NAMES.get(mid, "")
        deals = collect_tb_material_recommend(material_id=mid, page_size=5, sub_name=sub_name)
        new_deals = []
        for d in deals:
            key = d.get("title", "")[:20] + "|" + d.get("price", "")
            if key not in seen_recommend_ids:
                seen_recommend_ids.add(key)
                new_deals.append(d)
        if new_deals:
            all_deals.extend(new_deals)
            recommend_count += len(new_deals)
        time.sleep(0.5)
    print(f"[物料推荐] {recommend_count} 条")

    # 3. 关键词搜索 - 多品类（有券商品）
    search_keywords = [
        # 母婴
        "纸尿裤", "奶粉", "奶瓶", "玩具", "童装",
        # 日用洗护
        "纸巾", "洗衣液", "洗发水", "沐浴露", "牙膏",
        # 食品饮料
        "零食", "牛奶", "咖啡", "坚果", "大米",
        # 服饰
        "T恤", "运动鞋", "袜子", "内衣", "羽绒服",
        # 美妆
        "面膜", "口红", "护肤套装", "防晒霜",
        # 数码家电
        "数据线", "充电宝", "耳机", "鼠标",
        # 家居
        "床上用品", "收纳", "保温杯", "雨伞",
    ]
    search_count = 0
    seen_search_ids = set()
    for kw in search_keywords:
        deals = collect_tb_material_search(q=kw, has_coupon=True, page_size=5)
        new_deals = []
        for d in deals:
            key = d.get("title", "")[:20] + "|" + d.get("price", "")
            if key not in seen_search_ids:
                seen_search_ids.add(key)
                new_deals.append(d)
        if new_deals:
            all_deals.extend(new_deals)
            search_count += len(new_deals)
        time.sleep(0.5)
    print(f"[关键词搜索] {search_count} 条")

    print(f"[淘宝联盟] 总计采集 {len(all_deals)} 条优惠券商品")
    return all_deals


if __name__ == "__main__":
    print("测试淘宝联盟 API...")
    print(f"AppKey: {TB_APP_KEY[:10]}..." if TB_APP_KEY else "AppKey: 未配置")
    print(f"AdzoneID: {TB_ADZONE_ID}" if TB_ADZONE_ID else "AdzoneID: 未配置")

    # 测试权益物料精选
    print("\n--- 测试权益物料精选 ---")
    for pid in [37116, 62191]:
        print(f"\n--- {PROMOTION_IDS.get(pid, pid)} ---")
        deals = collect_tb_promotion_deals(promotion_id=pid, page_size=3)
        for d in deals:
            print(f"  [{d['tag']}] {d['title'][:40]} - {d['price']} (推荐{d['recommend_count']}件商品)")

    # 测试全量采集
    print("\n--- 测试全量采集 ---")
    all_deals = collect_tb_all(max_pages=1)
    print(f"全量采集: {len(all_deals)} 条")
