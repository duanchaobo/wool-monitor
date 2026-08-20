// app.js
App({
  globalData: {
    // GitHub Pages 数据托管地址
    dataBaseUrl: 'https://duanchaobo.github.io/wool-monitor/deals-data/',
    // GitHub Actions 触发地址
    githubApiUrl: 'https://api.github.com/repos/duanchaobo/wool-monitor/actions/workflows/deals-query.yml/dispatches',
    githubToken: '' // 用户需配置自己的 GitHub Token
  },

  onLaunch() {
    console.log('小程序启动');
  }
});
