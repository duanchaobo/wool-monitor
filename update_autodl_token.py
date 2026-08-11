"""
update_autodl_token.py - 获取 AutoDL Session Token 并更新到 GitHub Secret

使用方式：
  1. 确保已安装 GitHub CLI: brew install gh
  2. 确保已登录 GitHub: gh auth login
  3. 运行: python update_autodl_token.py

流程：
  - 从 Chrome 登录态提取 autodl.com 的 token
  - 如果 Chrome 没有，尝试微信快捷登录
  - 如果都没有，使用手机号+密码登录（需手动拖滑块）
  - 获取成功后自动更新 GitHub Secret: AUTODL_SESSION_TOKEN

前置条件：
  - macOS + Chrome 已登录 autodl.com（推荐，零操作）
  - 或：桌面微信已登录 + AutoDL 绑定微信
  - 或：config 中配置了 AUTO_LOGIN_PHONE/AUTO_LOGIN_PASSWORD
"""

import os
import sys
import subprocess
import re
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
AUTODL_DIR = os.path.join(PROJECT_DIR, "..", "autodl定时开机关机")


def check_gh_cli():
    """检查 GitHub CLI 是否安装并已登录"""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            logger.info("✅ GitHub CLI 已登录")
            return True
        else:
            logger.error("❌ GitHub CLI 未登录，请先运行: gh auth login")
            return False
    except FileNotFoundError:
        logger.error("❌ GitHub CLI 未安装，请先: brew install gh")
        return False


def get_token_from_chrome():
    """从 Chrome 用户数据目录提取 token"""
    logger.info("🔍 策略1: 从 Chrome 登录态提取 token...")

    user_data_dir = os.path.expanduser(
        "~/Library/Application Support/Google/Chrome"
    )
    if not os.path.isdir(user_data_dir):
        logger.info("Chrome 用户数据目录不存在")
        return None

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                viewport={"width": 1280, "height": 800},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://www.autodl.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # 从 localStorage 提取
            token = page.evaluate("""() => {
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    if (key && key.toLowerCase().includes('token')) {
                        const val = localStorage.getItem(key);
                        if (val && val.length > 50) return val;
                    }
                }
                return null;
            }""")
            context.close()

            if token and len(token) > 50:
                logger.info("✅ 从 Chrome 提取到有效 token")
                return token
            return None
    except ImportError:
        logger.warning("playwright 未安装，跳过 Chrome 提取")
        return None
    except Exception as e:
        logger.debug(f"Chrome 提取失败: {e}")
        return None


def get_token_from_autodl_project():
    """从 autodl定时开机关机 项目的 login.py 获取 token"""
    logger.info("🔍 策略2: 使用 autodl项目的 login 模块...")

    login_path = os.path.join(AUTODL_DIR, "login.py")
    if not os.path.exists(login_path):
        logger.warning(f"未找到 {login_path}")
        return None

    try:
        # 添加 autodl 项目目录到 path
        sys.path.insert(0, AUTODL_DIR)
        from login import fetch_token_via_playwright
        from config import AUTO_LOGIN_PHONE, AUTO_LOGIN_PASSWORD

        phone = os.environ.get("AUTO_LOGIN_PHONE", "") or AUTO_LOGIN_PHONE
        password = os.environ.get("AUTO_LOGIN_PASSWORD", "") or AUTO_LOGIN_PASSWORD

        token = fetch_token_via_playwright(phone=phone, password=password)
        if token:
            logger.info("✅ 通过 autodl 登录模块获取到 token")
            return token
        return None
    except ImportError as e:
        logger.warning(f"导入 autodl 模块失败: {e}")
        return None
    except Exception as e:
        logger.error(f"autodl 登录失败: {e}")
        return None


def verify_token(token):
    """验证 token 是否有效"""
    logger.info("🔍 验证 token 有效性...")
    try:
        import requests
        headers = {
            "Authorization": token,
            "Content-Type": "application/json;charset=UTF-8",
            "User-Agent": "Mozilla/5.0"
        }
        resp = requests.post(
            "https://www.autodl.com/api/v1/instance",
            json={
                "page_index": 1, "page_size": 10,
                "status": [], "charge_type": [],
                "sub_name": "", "unbind_sub_user": False
            },
            headers=headers, timeout=15
        )
        result = resp.json()
        if result.get("code") == "Success":
            data = result.get("data", {})
            instances = data.get("list", [])
            logger.info(f"✅ Token 有效！账号下有 {len(instances)} 个实例")
            for inst in instances:
                name = inst.get("machine_alias", "") or inst.get("name", "")
                uuid = inst.get("uuid", "")
                status = inst.get("status", "")
                logger.info(f"   - {name} ({uuid[:8]}...) 状态: {status}")
            return True
        else:
            logger.error(f"❌ Token 无效: {result.get('msg', 'unknown')}")
            return False
    except Exception as e:
        logger.error(f"验证失败: {e}")
        return False


def update_github_secret(token):
    """更新 GitHub Secret: AUTODL_SESSION_TOKEN 到所有相关仓库"""
    repos = ["duanchaobo/wool-monitor", "duanchaobo/autodl_keep_alive"]
    logger.info(f"🔄 更新 GitHub Secret 到 {len(repos)} 个仓库...")

    all_ok = True
    for repo in repos:
        try:
            proc = subprocess.run(
                ["gh", "secret", "set", "AUTODL_SESSION_TOKEN",
                 "--repo", repo],
                input=token,
                capture_output=True, text=True, timeout=15,
            )
            if proc.returncode == 0:
                logger.info(f"   ✅ {repo}")
            else:
                logger.error(f"   ❌ {repo}: {proc.stderr.strip()}")
                all_ok = False
        except Exception as e:
            logger.error(f"   ❌ {repo}: {e}")
            all_ok = False

    return all_ok


def main():
    print("=" * 50)
    print("🔑 AutoDL Token 获取 & GitHub Secret 更新工具")
    print("=" * 50)

    # 检查 GitHub CLI
    if not check_gh_cli():
        sys.exit(1)

    # 尝试获取 token
    token = None

    # 策略1: Chrome
    token = get_token_from_chrome()

    # 策略2: autodl 项目登录
    if not token:
        token = get_token_from_autodl_project()

    if not token:
        logger.error("❌ 所有方式均无法获取 token")
        logger.info("请先在 Chrome 中登录 autodl.com，或确保 autodl 项目配置了登录凭据")
        sys.exit(1)

    # 验证
    if not verify_token(token):
        sys.exit(1)

    # 更新 GitHub Secret
    if update_github_secret(token):
        print("\n" + "=" * 50)
        print("🎉 全部完成！Token 已更新到 GitHub Secret")
        print("   下次 GitHub Actions 运行时将使用新 Token")
        print("=" * 50)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
