"""
collect_step1.py - 每日采集: recommend API 采集 → 筛选知名品牌天猫旗舰店 → 去重

每天北京时间 6:00 执行，输出原始商品名单到 /tmp/raw_deals.json
供 collect_step2.py 读取并补充价格信息。

用法:
  python3 collect_step1.py
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tb_api import collect_recommend_then_filter


def main():
    print("=" * 60)
    print("阶段1: recommend API 采集 → 筛选 → 去重")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 执行采集 + 筛选 + 去重
    filtered_deals = collect_recommend_then_filter()

    # 保存到 /tmp 供 collect_step2.py 读取
    output_file = "/tmp/raw_deals.json"
    output_data = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(filtered_deals),
        "deals": filtered_deals
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 采集完成: {len(filtered_deals)} 条 → {output_file}")
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return len(filtered_deals)


if __name__ == "__main__":
    count = main()
    sys.exit(0 if count > 0 else 1)
