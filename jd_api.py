"""
jd_api.py - 京东联盟优惠券采集

API 文档: https://union.jd.com/openplatform

所需凭证:
  JD_APP_KEY     - AppKey（从联盟后台"我的API"获取）
  JD_APP_SECRET  - AppSecret（同上）
  JD_PID         - 推广位ID（从"推广位管理"获取）

环境变量读取，或在 .env 文件中配置
"""

import os
import json
import time
import hashlib
import requests
from datetime import datetime
from urllib.parse import urlencode

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

# 京东联盟 API 网关地址
API_GATEWAY = "https://router.jd.com/api"


def _make_sign(params, secret):
    """生成京东联盟 API 签名"""
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    sign_str = secret
    for k, v in sorted_params:
        sign_str += k + str(v)
    sign_str += secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def _call_jd_api(method, biz_params):
    """调用京东联盟 API 通用方法"""
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
        data = resp.json()
        return data
    except Exception as e:
        print(f"[京东联盟] API 调用失败: {e}")
        return None


def collect_jd_coupon_deals(keyword="", page=1, page_size=10):
    """
    采集京东优惠券商品

    使用京粉精选接口或优惠券查询接口
    """
    if not JD_APP_KEY:
        return []

    deals = []

    # 方式1: 通过"京粉精选"接口获取高佣商品
    biz_params = {
        "goodsReq": {
            "keyword": keyword if keyword else "优惠券",
            "pageSize": page_size,
            "pageIndex": page,
            "pid": JD_PID,
            "eliteId": 1,  # 好券商品: 1
        }
    }

    result = _call_jd_api("jd.union.open.goods.query", biz_params)

    if not result:
        return deals

    # 解析返回数据
    try:
        data_list = result.get("jd_union_open_goods_query_response", {}).get("data", [])
        if isinstance(data_list, str):
            data_list = json.loads(data_list) if data_list else []

        for item in data_list:
            sku = item.get("skuId", "")
            title = item.get("skuName", item.get("goodsName", ""))
            price_info = item.get("priceInfo", {})
            commission_info = item.get("commissionInfo", {})
            coupon_info = item.get("couponInfo", {})

            price = price_info.get("price", 0)
            lowest_price = price_info.get("lowestPrice", 0)
            original_price = price_info.get("originalPrice", lowest_price)

            # 优惠券信息
            coupon_list = coupon_info.get("couponList", [])
            coupon_str = ""
            if coupon_list:
                c = coupon_list[0]
                discount = c.get("discount", 0)
                quota = c.get("quota", 0)
                coupon_str = f"满{quota}减{int(discount)}"

            # 佣金
            commission_share = commission_info.get("commissionShare", 0)

            if not title or not price:
                continue

            deal = {
                "source": "京东",
                "title": title[:60],
                "price": f"¥{lowest_price}",
                "old_price": f"¥{original_price}",
                "discount": round(1 - lowest_price / original_price, 2) if original_price > 0 else 0,
                "url": f"https://item.jd.com/{sku}.html" if sku else "",
                "tag": coupon_str if coupon_str else "京粉精选",
                "img_url": item.get("imageInfo", {}).get("imageList", [{}])[0].get("url", "") if item.get("imageInfo") else "",
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            deals.append(deal)

    except Exception as e:
        print(f"[京东联盟] 解析失败: {e}")

    print(f"[京东联盟] 采集到 {len(deals)} 条优惠券商品")
    return deals


def collect_jd_coupon_search(keywords=None):
    """
    按关键词批量采集京东优惠券商品
    """
    if keywords is None:
        keywords = ["手机", "电脑", "家电", "零食", "日用品"]

    all_deals = []
    for kw in keywords:
        deals = collect_jd_coupon_deals(keyword=kw, page_size=5)
        all_deals.extend(deals)
        time.sleep(0.5)  # 避免频率限制

    return all_deals


if __name__ == "__main__":
    print("测试京东联盟 API...")
    print(f"AppKey: {JD_APP_KEY[:10]}..." if JD_APP_KEY else "AppKey: 未配置")

    deals = collect_jd_coupon_deals(keyword="手机", page_size=3)
    for d in deals:
        print(f"  [{d['tag']}] {d['title'][:40]} - {d['price']} (原价{d['old_price']})")
