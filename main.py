"""
main.py - 主程序入口

工作流程：
1. 采集多个来源的优惠信息
2. 筛选/去重/排序
3. 优先推送紧急信息，再推普通信息
4. 统计结果输出日志

环境变量配置（通过 GitHub Secrets 或 .env 文件）：
  WECHAT_WEBHOOK_URL  - 企业微信群机器人 Webhook 地址（必填）
  JD_APP_KEY          - 京东联盟 AppKey（可选）
  JD_APP_SECRET       - 京东联盟 AppSecret（可选）
"""

import sys
import os
from datetime import datetime

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载 .env 文件（本地开发用）
env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, _, val = line.partition('=')
                if val:
                    os.environ[key.strip()] = val

from deal_collector import collect_all
from deal_filter import filter_deals
from wechat_webhook import push_deal, push_batch

# 每次执行最多推送条数
MAX_PUSH_PER_RUN = 10


def main():
    print(f"\n{'='*50}")
    print(f"🔄 优惠信息巡检开始")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    # Step 1: 采集
    print("📡 正在采集各平台优惠信息...")
    all_deals = collect_all()

    if not all_deals:
        print("\n⚠️ 没有采集到任何信息，跳过本次推送")
        return

    # Step 2: 筛选
    print("\n🔍 正在筛选高价值信息...")
    normal_deals, urgent_deals = filter_deals(all_deals)

    # Step 3: 按品类去重（每个品类随机取1款，避免原价虚高的商品）
    def pick_random_per_category(deals, max_total=MAX_PUSH_PER_RUN):
        """按品类分组，每组随机取1条，总数不超过max_total"""
        import random
        from collections import defaultdict
        by_cat = defaultdict(list)
        for d in deals:
            cat = d.get("category", "其他") or "其他"
            by_cat[cat].append(d)
        result = []
        for cat, items in by_cat.items():
            result.append(random.choice(items))
        random.shuffle(result)
        return result[:max_total]

    urgent_final = pick_random_per_category(urgent_deals)
    normal_final = pick_random_per_category(normal_deals)

    # Step 4: 推送
    if urgent_final:
        print(f"\n🚨 推送紧急信息（{len(urgent_final)} 条）...")
        push_batch(urgent_final)

    if normal_final:
        print(f"\n📢 推送普通信息（{len(normal_final)} 条）...")
        push_batch(normal_final)

    # Step 5: 总结
    print(f"\n{'='*50}")
    print(f"✅ 巡检完成")
    print(f"  总采集: {len(all_deals)} 条")
    print(f"  紧急推送: {len(urgent_final)} 条")
    print(f"  普通推送: {len(normal_final)} 条")
    print(f"  过滤/去重: {len(all_deals) - len(urgent_deals) - len(normal_deals)} 条")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
