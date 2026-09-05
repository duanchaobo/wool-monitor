# 🦙 羊毛信息自动采集器

自动采集全网优惠信息，筛选后通过小程序展示。

## 架构

```
数据源 → 采集器 → 筛选引擎 → JSON 数据 → GitHub Pages → 小程序
```

- **采集器**: 淘宝联盟API（物料精选）
- **筛选**: 折扣≥10%、品类过滤、去重
- **展示**: 微信小程序（通过 GitHub Pages 托管数据）

## 部署步骤

### 1. 克隆项目

```bash
git clone https://github.com/duanchaobo/wool-monitor.git
cd wool-monitor
```

### 2. 配置 GitHub Secrets

在 GitHub 仓库 Settings → Secrets and variables → Actions 中添加：

| Secret 名称 | 说明 |
|-------------|------|
| `TB_APP_KEY` | 淘宝联盟 AppKey（必填） |
| `TB_APP_SECRET` | 淘宝联盟 AppSecret（必填） |
| `TB_ADZONE_ID` | 淘宝联盟 AdzoneId（必填） |
| `SILICONFLOW_API_KEY` | 硅基流动 API Key（可选，用于商品分类） |
| `AUTODL_SESSION_TOKEN` | AutoDL 会话令牌（必填） |
| `AUTODL_INSTANCE_UUID` | AutoDL 实例 UUID（必填） |
| `AUTODL_SSH_HOST` | AutoDL SSH 地址（必填） |
| `AUTODL_SSH_PORT` | AutoDL SSH 端口（必填） |
| `AUTODL_SSH_USER` | AutoDL SSH 用户名（必填） |
| `AUTODL_SSH_KEY` | AutoDL SSH 私钥（必填） |
| `PAT_TOKEN` | GitHub Personal Access Token（必填） |

### 3. 推送到 GitHub

```bash
git add .
git commit -m "初始化羊毛信息采集器"
git push
```

推送后，GitHub Actions 会自动每2小时运行一次数据采集。

### 4. 配置 GitHub Pages

- 进入 GitHub → Settings → Pages
- Source 选择 `Deploy from a branch`
- Branch 选择 `main`，目录选择 `/docs`

### 5. 验证

- 进入 GitHub → Actions 标签页
- 查看工作流运行状态
- 首次可手动触发测试：Actions → 生成优惠数据（小程序） → Run workflow

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 .env 文件
cp .env.example .env
# 编辑 .env 填入你的淘宝联盟凭证

# 生成小程序数据
python3 generate_deals_json.py --output docs
```

## 小程序配置

小程序代码在 `deals-miniprogram/` 目录，使用微信开发者工具打开即可预览。

数据源配置：编辑 `deals-miniprogram/app.js` 中的 `dataBaseUrl` 为你的 GitHub Pages 地址。

## 扩展数据源

编辑 `deal_collector.py`，在 `collect_all()` 函数中添加新的采集器。

## 注意事项

- GitHub Actions 免费额度：每月 2000 分钟
- 使用 AutoDL 远程采集解决海外服务器调用国内 API 的限制
- 谨慎使用爬虫，遵守目标网站 robots.txt
