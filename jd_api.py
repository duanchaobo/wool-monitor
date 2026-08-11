"""
jd_api.py - 京东联盟京粉精选采集

使用 jd.union.open.goods.jingfen.query 接口
导购媒体 AppKey 可用此接口获取高佣优惠券商品

所需凭证:
  JD_APP_KEY     - AppKey
  JD_APP_SECRET  - AppSecret
  JD_PID         - 推广位ID（可选）
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

JD_APP_KEY = os.environ.get("JD_APP_KEY", "")
JD_APP_SECRET = os.environ.get("JD_APP_SECRET", "")
JD_PID = os.environ.get("JD_PID", "")

API_GATEWAY = "https://router.jd.com/api"

# 京粉精选频道ID
ELITE_IDS = {
    1: "好券商品",
    2: "精选卖场",
    3: "9.9专区",
    5: "京东配送",
    35: "数码家电",
    36: "超市",
    37: "母婴玩具",
    38: "家具日用",
    39: "美妆穿搭",
    40: "医药保健",
    41: "图书文具",
    42: "户外运动",
    43: "生鲜美食",
    45: "京东秒杀",
    52: "充值中心",
    53: "机票酒店",
    54: "虚拟商品",
    55: "工业品",
}


def _make_sign(params, secret):
    """生成京东联盟 API 签名"""
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    sign_str = secret
    for k, v in sorted_params:
        sign_str += k + str(v)
    sign_str += secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def _call_jd_api(method, biz_params):
    """调用京东联盟 API"""
    if not JD_APP_KEY or not JD_APP_SECRET:
        print("[京东联盟] 未配置 AppKey/AppSecret，跳过")
        return None

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    params = {
        "app_key": JD_APP_KEY,
        "method": method,
        "timestamp": timestamp,
        "v": "1.0",
        "sign_method": "md5",
        "format": "json",
        "param_json": json.dumps(biz_params, ensure_ascii=False),
    }
    params["sign"] = _make_sign(params, JD_APP_SECRET)

    try:
        resp = requests.get(API_GATEWAY, params=params, timeout=15)
        return resp.json()
    except Exception as e:
        print(f"[京东联盟] API 调用失败: {e}")
        return None


def collect_jingfen_deals(elite_id=1, page=1, page_size=10):
    """
    采集京粉精选商品（导购媒体可用）
    """
    deals = []

    biz_params = {
        "goodsReq": {
            "eliteId": elite_id,
            "pageIndex": page,
            "pageSize": page_size,
            "sortName": "inOrderComm30Days",
            "sort": "desc",
        }
    }
    if JD_PID:
        biz_params["goodsReq"]["pid"] = JD_PID

    result = _call_jd_api("jd.union.open.goods.jingfen.query", biz_params)
    if not result:
        return deals

    # 解析响应
    try:
        resp_key = "jd_union_open_goods_jingfen_query_response"
        inner = result.get(resp_key, {})
        result_str = inner.get("result", "")

        if isinstance(result_str, str):
            result_obj = json.loads(result_str) if result_str else {}
        else:
            result_obj = result_str

        if result_obj.get("code") != 200:
            print(f"[京东联盟] 接口错误: {result_obj.get('message', 'unknown')}")
            return deals

        data_list = result_obj.get("data", [])

        for item in data_list:
            title = item.get("skuName", "") or item.get("goodsName", "")
            if not title:
                continue

            # 价格信息
            price_info = item.get("priceInfo", {})
            price = price_info.get("lowestCouponPrice", 0) or price_info.get("price", 0) or 0
            original_price = price_info.get("price", 0) or 0

            # 优惠券信息
            coupon_info = item.get("couponInfo", {})
            coupon_list = coupon_info.get("couponList", [])
            coupon_str = ""
            coupon_link = ""
            if coupon_list:
                best = coupon_list[0]
                discount = best.get("discount", 0)
                quota = best.get("quota", 0)
                coupon_str = f"满{int(quota)}减{int(discount)}"
                coupon_link = best.get("link", "")

            # 商品详情链接（优先 materialUrl，其次 coupon_link）
            material_url = item.get("materialUrl", "")
            if material_url:
                product_url = "https://" + material_url if not material_url.startswith("http") else material_url
            else:
                product_url = coupon_link

            # 佣金
            commission_info = item.get("commissionInfo", {})
            commission_share = commission_info.get("commissionShare", 0)

            # 品类
            category = item.get("categoryInfo", {})
            cat_name = category.get("cid2Name", "") or category.get("cid1Name", "")

            # 图片
            image_info = item.get("imageInfo", {})
            image_list = image_info.get("imageList", [])
            img_url = image_list[0].get("url", "") if image_list else ""
            if img_url and not img_url.startswith("http"):
                img_url = "https:" + img_url

            # 计算折扣
            discount = 0
            if original_price > 0 and price > 0 and original_price > price:
                discount = round(1 - price / original_price, 2)

            deal = {
                "source": "京东",
                "title": title[:60],
                "price": f"¥{price}" if price else "",
                "old_price": f"¥{original_price}" if original_price and original_price != price else "",
                "discount": discount,
                "url": product_url,
                "coupon_url": coupon_link,
                "coupon_quota": coupon_list[0].get("quota", 0) if coupon_list else 0,
                "tag": coupon_str if coupon_str else ELITE_IDS.get(elite_id, "京粉精选"),
                "category": cat_name,
                "img_url": img_url,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            deals.append(deal)

    except Exception as e:
        print(f"[京东联盟] 解析失败: {e}")

    return deals


def collect_jd_all_channels(max_pages=3):
    """
    采集多个频道的精选商品，支持翻页
    max_pages: 每个频道最多翻几页（每页30条）
    """
    # 可用的频道：1=好券, 2=精选卖场, 40=医药保健, 41=图书文具
    target_channels = [1, 2, 40, 41]
    all_deals = []

    for elite_id in target_channels:
        for page in range(1, max_pages + 1):
            deals = collect_jingfen_deals(elite_id=elite_id, page=page, page_size=30)
            if not deals:
                break  # 没有更多数据，跳到下一个频道
            all_deals.extend(deals)
            time.sleep(0.3)

    print(f"[京东联盟] 总计采集 {len(all_deals)} 条优惠券商品")
    return all_deals


if __name__ == "__main__":
    print("测试京东联盟京粉精选 API...")
    print(f"AppKey: {JD_APP_KEY[:10]}..." if JD_APP_KEY else "AppKey: 未配置")

    deals = collect_jingfen_deals(elite_id=1, page_size=5)
    for d in deals:
        print(f"  [{d['tag']}] {d['title'][:40]} - {d['price']}")
