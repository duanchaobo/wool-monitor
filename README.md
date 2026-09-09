# 优惠商品采集与展示系统

自动采集淘宝/天猫优惠商品，通过微信小程序展示，支持一键复制淘口令跳转淘宝App。

## 架构

```
淘宝联盟API → AutoDL实例采集 → GitHub Actions → GitHub Pages → 微信小程序
```

- **采集**: 淘宝联盟 API（物料推荐 → 价格补充 → 淘口令生成）
- **筛选**: 知名品牌天猫店、item_id精确匹配、折扣≥10%
- **展示**: 微信小程序（分类浏览、搜索、一键复制淘口令）

## 工作流程

每天北京时间 6:00 自动执行：

1. **开机** — 启动 AutoDL 实例，动态获取IP和SSH端口
2. **采集** — recommend API 采集商品，筛选知名品牌天猫旗舰店
3. **补充价格** — item_id 精确匹配调用 optional.upgrade API（5线程并行）
4. **生成淘口令** — tpwd.create API（5线程并行）
5. **生成JSON** — 折扣过滤、分类匹配、输出 deals.json 和 categories.json
6. **推送** — git push 到 GitHub
7. **关机** — 关闭 AutoDL 实例

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
| `TB_APP_KEY` | 淘宝联盟 AppKey |
| `TB_APP_SECRET` | 淘宝联盟 AppSecret |
| `TB_ADZONE_ID` | 淘宝联盟 推广位ID |
| `AUTODL_SESSION_TOKEN` | AutoDL 会话令牌 |
| `AUTODL_INSTANCE_UUID` | AutoDL 实例 UUID |
| `AUTODL_SSH_USER` | AutoDL SSH 用户名 |
| `AUTODL_SSH_KEY` | AutoDL SSH 私钥 |
| `PAT_TOKEN` | GitHub Personal Access Token |

### 3. 配置 GitHub Pages

- 进入 GitHub → Settings → Pages
- Source 选择 `Deploy from a branch`
- Branch 选择 `main`，目录选择 `/docs`

### 4. 配置小程序数据源

编辑 `deals-miniprogram/utils/api.js`，将 `dataBaseUrl` 改为你的 GitHub Pages 地址：

```javascript
dataBaseUrl: 'https://duanchaobo.github.io/wool-monitor/'
```

### 5. 上传小程序

使用微信开发者工具打开 `deals-miniprogram/` 目录，上传代码并提交审核。

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 配置 .env 文件
cat > .env << EOF
TB_APP_KEY=你的AppKey
TB_APP_SECRET=你的AppSecret
TB_ADZONE_ID=你的AdzoneId
EOF

# 采集商品名单
python3 collect_step1.py

# 补充价格 + 生成淘口令 + 输出小程序JSON
python3 collect_step2.py --output docs
```

## 目录结构

```
deals-monitor/
├── .github/workflows/
│   └── deals-daily.yml      # 每日采集工作流
├── deals-miniprogram/        # 微信小程序代码
│   ├── pages/index/          # 首页（分类浏览）
│   ├── pages/search/         # 搜索页
│   └── utils/api.js          # 数据请求
├── docs/                     # 小程序数据（自动生成）
│   ├── deals.json            # 商品列表
│   └── categories.json       # 分类数据
├── tb_api.py                 # 淘宝联盟API封装
├── collect_step1.py          # 阶段1：采集商品名单
├── collect_step2.py          # 阶段2：补充价格 + 淘口令
├── famous_brands.txt         # 知名品牌列表
└── requirements.txt          # Python依赖
```

## 小程序功能

- **分类浏览** — 左侧一级类目 + 右侧商品卡片
- **搜索** — 按商品名称/品牌/品类搜索
- **一键复制淘口令** — 点击商品自动复制，弹出引导页面
- **引导跳转** — 教用户打开淘宝App粘贴访问

## 注意事项

- GitHub Actions 免费额度：每月 2000 分钟
- 使用 AutoDL 实例解决海外服务器调用国内 API 的限制
- 每天仅执行一次，避免过度调用 API
- 淘宝联盟 API 需申请权限（taobao.tbk.dg.material.recommend、optional.upgrade、tpwd.create）
