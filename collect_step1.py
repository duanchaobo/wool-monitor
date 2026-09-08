"""
collect_step1.py - Workflow 1: recommend API 采集 → 筛选知名品牌天猫旗舰店 → 去重

每天北京时间 6:00 执行，输出原始商品名单到 docs/raw_deals.json
供 Workflow 2 读取并补充价格信息。

用法:
  python3 collect_step1.py --output docs
"""

import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tb_api import collect_recommend_then_filter


def main():
    parser = argparse.ArgumentParser(description="Workflow 1: 采集并筛选知名品牌天猫旗舰店商品")
    parser.add_argument("--output", default="docs", help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    output_file = os.path.join(args.output, "raw_deals.json")

    print("=" * 60)
    print("Workflow 1: recommend API 采集 → 筛选 → 去重")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 执行采集 + 筛选 + 去重
    filtered_deals = collect_recommend_then_filter()

    # 保存原始商品名单
    output_data = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(filtered_deals),
        "deals": filtered_deals
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 保存原始商品名单: {len(filtered_deals)} 条 → {output_file}")

    # 重置进度文件：新一天的原始名单生成后，清空进度让 Workflow 2 从头处理
    progress_file = os.path.join(args.output, "enrich_progress.json")
    progress = {
        "start_index": 0,
        "total": len(filtered_deals),
        "last_run": None,
        "completed": False
    }
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    print(f"🔄 重置进度文件: start_index=0, total={len(filtered_deals)}")

    # 清空旧的 enriched_deals.json，避免 Workflow 2 追加到旧数据
    enriched_file = os.path.join(args.output, "enriched_deals.json")
    if os.path.exists(enriched_file):
        os.remove(enriched_file)
        print(f"🗑️ 清除旧的 enriched_deals.json")

    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return len(filtered_deals)


if __name__ == "__main__":
    count = main()
    sys.exit(0 if count > 0 else 1)
