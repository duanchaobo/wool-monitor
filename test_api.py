"""
测试淘宝联盟 API 在 AutoDL 实例上是否可用
"""
import os
import sys
import json
import hashlib
import requests
from datetime import datetime

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

TB_APP_KEY = os.environ.get('TB_APP_KEY', '')
TB_APP_SECRET = os.environ.get('TB_APP_SECRET', '')
TB_ADZONE_ID = os.environ.get('TB_ADZONE_ID', '')

API_GATEWAY = 'https://eco.taobao.com/router/rest'


def _make_sign(params, secret):
    sorted_params = sorted(params.items(), key=lambda x: str(x[0]))
    sign_str = secret
    for k, v in sorted_params:
        sign_str += str(k) + str(v)
    sign_str += secret
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()


def call_api(method, **biz_params):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    params = {
        'app_key': TB_APP_KEY,
        'method': method,
        'timestamp': timestamp,
        'v': '2.0',
        'sign_method': 'md5',
        'format': 'json',
    }
    params.update(biz_params)
    params['sign'] = _make_sign(params, TB_APP_SECRET)
    resp = requests.get(API_GATEWAY, params=params, timeout=15)
    return resp.json()


if __name__ == '__main__':
    print(f'AppKey: {TB_APP_KEY[:10]}...')
    print(f'AdzoneID: {TB_ADZONE_ID}')

    # 测试 recommend
    print('\n测试 recommend API...')
    result = call_api('taobao.tbk.dg.material.recommend',
                      adzone_id=int(TB_ADZONE_ID), material_id=13371,
                      page_no=1, page_size=2)
    if 'error_response' in result:
        err = result['error_response']
        print(f'  ❌ code={err.get("code")}, msg={err.get("msg")}')
    else:
        items = result.get('tbk_dg_material_recommend_response', {}) \
            .get('result_list', {}).get('map_data', [])
        print(f'  ✅ 返回 {len(items)} 条')

    # 测试 optional.upgrade（连续3次）
    print('\n测试 optional.upgrade API（连续3次）...')
    for i in range(3):
        result = call_api('taobao.tbk.dg.material.optional.upgrade',
                          adzone_id=int(TB_ADZONE_ID), q=f'面膜{i}',
                          page_no=1, page_size=2, platform=2)
        if 'error_response' in result:
            err = result['error_response']
            print(f'  第{i+1}次: ❌ code={err.get("code")}, msg={err.get("msg")}')
        else:
            items = result.get('tbk_dg_material_optional_upgrade_response', {}) \
                .get('result_list', {}).get('map_data', [])
            print(f'  第{i+1}次: ✅ 返回 {len(items)} 条')

    print('\n测试完成')
