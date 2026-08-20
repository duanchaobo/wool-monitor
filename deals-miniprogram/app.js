// app.js
App({
  globalData: {
    // GitHub Pages 数据托管地址
    dataBaseUrl: 'https://duanchaobo.github.io/wool-monitor/deals-data/',
    // GitHub Actions 触发地址
    githubApiUrl: 'https://api.github.com/repos/duanchaobo/wool-monitor/actions/workflows/deals-search.yml/dispatches',
    // Token 从本地存储读取（用户在搜索页设置）
    githubToken: wx.getStorageSync('githubToken') || ''
  },

  onLaunch() {
    // 读取用户配置的 Token
    this.globalData.githubToken = wx.getStorageSync('githubToken') || '';
    console.log('小程序启动，Token 已' + (this.globalData.githubToken ? '配置' : '未配置'));
  }
});
