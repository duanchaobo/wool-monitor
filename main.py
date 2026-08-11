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

    # Step 3: 推送
    if urgent_deals:
        print("\n🚨 推送紧急信息...")
        push_batch(urgent_deals)

    if normal_deals:
        print("\n📢 推送普通信息...")
        push_batch(normal_deals)

    # Step 4: 总结
    print(f"\n{'='*50}")
    print(f"✅ 巡检完成")
    print(f"  总采集: {len(all_deals)} 条")
    print(f"  紧急推送: {len(urgent_deals)} 条")
    print(f"  普通推送: {min(len(normal_deals), 5)} 条")
    print(f"  过滤/去重: {len(all_deals) - len(urgent_deals) - len(normal_deals)} 条")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
