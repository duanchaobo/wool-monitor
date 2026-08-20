// pages/search/search.js
const api = require('../../utils/api.js');

Page({
  data: {
    keyword: '',
    searchHistory: [],
    deals: [],
    loading: false,
    searched: false,
    triggerSuccess: false,
    message: ''
  },

  onLoad() {
    // 读取本地搜索历史
    const history = wx.getStorageSync('searchHistory') || [];
    this.setData({ searchHistory: history });
  },

  /**
   * 输入框变化
   */
  onInputChange(e) {
    this.setData({ keyword: e.detail.value });
  },

  /**
   * 执行搜索
   */
  async doSearch() {
    const keyword = this.data.keyword.trim();
    if (!keyword) {
      wx.showToast({ title: '请输入搜索关键词', icon: 'none' });
      return;
    }

    // 保存搜索历史
    this.saveSearchHistory(keyword);

    this.setData({
      loading: true,
      searched: false,
      deals: [],
      triggerSuccess: false,
      message: ''
    });

    // 先尝试读取已有搜索结果
    try {
      const result = await api.fetchSearchResult(keyword);
      this.setData({
        deals: result.deals || [],
        loading: false,
        searched: true,
        message: result.deals && result.deals.length > 0 ? '' : '暂无相关优惠'
      });
      return;
    } catch (e) {
      // 没有缓存结果，触发 GitHub Actions
    }

    // 触发 GitHub Actions 搜索
    const token = wx.getStorageSync('githubToken') || '';
    try {
      const result = await api.triggerSearch(keyword, token);
      this.setData({
        loading: false,
        searched: true,
        triggerSuccess: true,
        message: '搜索任务已提交，正在采集数据...\n请稍后返回首页或刷新搜索查看结果'
      });
    } catch (err) {
      this.setData({
        loading: false,
        searched: true,
        message: '搜索失败: ' + (err.message || '请检查网络')
      });
    }
  },

  /**
   * 快速搜索（点击历史记录） */
  quickSearch(e) {
    const keyword = e.currentTarget.dataset.keyword;
    this.setData({ keyword }, () => {
      this.doSearch();
    });
  },

  /**
   * 刷新搜索结果
   */
  async refreshResult() {
    if (!this.data.keyword) return;
    this.setData({ loading: true });
    try {
      const result = await api.fetchSearchResult(this.data.keyword);
      this.setData({
        deals: result.deals || [],
        loading: false,
        message: result.deals && result.deals.length > 0 ? '' : '暂无更多结果'
      });
    } catch (err) {
      this.setData({
        loading: false,
        message: '数据更新中，请稍后再试'
      });
    }
  },

  /**
   * 保存搜索历史
   */
  saveSearchHistory(keyword) {
    let history = wx.getStorageSync('searchHistory') || [];
    // 去重 + 限存10条
    history = history.filter(h => h !== keyword);
    history.unshift(keyword);
    if (history.length > 10) history = history.slice(0, 10);
    wx.setStorageSync('searchHistory', history);
    this.setData({ searchHistory: history });
  },

  /**
   * 清空搜索历史
   */
  clearHistory() {
    wx.removeStorageSync('searchHistory');
    this.setData({ searchHistory: [] });
  },

  /**
   * 复制链接
   */
  copyLink(e) {
    const url = e.currentTarget.dataset.url;
    wx.setClipboardData({
      data: url,
      success: () => {
        wx.showToast({ title: '链接已复制', icon: 'success' });
      }
    });
  }
});
