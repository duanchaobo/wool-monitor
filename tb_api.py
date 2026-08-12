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
                "category": PROMOTION_IDS.get(promotion_id, "淘宝"),
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


def collect_tb_all(max_pages=3):
    """
    淘宝联盟全量采集 - 多种优惠券类型

    Args:
        max_pages: 每种优惠券最多翻几页
    """
    # 可用的权益物料（大额店铺券和天猫店铺券有数据）
    target_promotions = [37116, 62191, 37104, 61809]
    all_deals = []

    for promotion_id in target_promotions:
        for page in range(1, max_pages + 1):
            deals = collect_tb_promotion_deals(
                promotion_id=promotion_id,
                page_num=page,
                page_size=10
            )
            if not deals:
                break
            all_deals.extend(deals)
            time.sleep(0.5)

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
