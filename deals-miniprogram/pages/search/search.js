// pages/search/search.js
const api = require('../../utils/api.js');

Page({
  data: {
    keyword: '',
    searchHistory: [],
    deals: [],
    loading: false,
    searched: false,
    message: '',
    allDeals: []  // 全量数据（从首页缓存读取）
  },

  onLoad() {
    const history = wx.getStorageSync('searchHistory') || [];
    this.setData({ searchHistory: history });
    // 读取首页缓存的全量数据
    const allDeals = wx.getStorageSync('allDeals') || [];
    this.setData({ allDeals });
  },

  /**
   * 输入框变化
   */
  onInputChange(e) {
    this.setData({ keyword: e.detail.value });
  },

  /**
   * 执行搜索（本地过滤，无需 Token）
   */
  doSearch() {
    const keyword = this.data.keyword.trim();
    if (!keyword) {
      wx.showToast({ title: '请输入搜索关键词', icon: 'none' });
      return;
    }

    this.saveSearchHistory(keyword);

    this.setData({
      loading: true,
      searched: false,
      deals: [],
      message: ''
    });

    // 本地搜索：标题/品类/店铺 匹配关键词
    const allDeals = this.data.allDeals;
    if (!allDeals || allDeals.length === 0) {
      // 缓存失效，先拉取数据
      this.loadAllDeals().then(() => {
        this.filterDeals(keyword);
      });
    } else {
      this.filterDeals(keyword);
    }
  },

  /**
   * 本地过滤商品
   */
  filterDeals(keyword) {
    const allDeals = this.data.allDeals || [];
    const kw = keyword.toLowerCase();
    const matched = allDeals.filter(d => {
      return (d.title && d.title.toLowerCase().includes(kw)) ||
             (d.category && d.category.toLowerCase().includes(kw)) ||
             (d.shop && d.shop.toLowerCase().includes(kw)) ||
             (d.tags && d.tags.some(t => t.toLowerCase().includes(kw)));
    });

    this.setData({
      deals: matched,
      loading: false,
      searched: true,
      message: matched.length > 0 ? '' : `未找到"${keyword}"相关优惠`
    });
  },

  /**
   * 加载全量数据
   */
  async loadAllDeals() {
    try {
      const data = await api.fetchDealsData();
      const deals = data.deals || [];
      this.setData({ allDeals: deals });
      wx.setStorageSync('allDeals', deals); // 缓存到本地
    } catch (e) {
      console.error('加载数据失败:', e);
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
   * 保存搜索历史
   */
  saveSearchHistory(keyword) {
    let history = wx.getStorageSync('searchHistory') || [];
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
   * 复制淘口令/链接（优先淘口令）
   */
  copyLink(e) {
    const taokouling = e.currentTarget.dataset.taokouling || '';
    const url = e.currentTarget.dataset.url || '';
    const copyData = taokouling || url;
    wx.setClipboardData({
      data: copyData,
      success: () => {
        wx.showToast({
          title: taokouling ? '淘口令已复制' : '链接已复制',
          icon: 'success'
        });
      }
    });
  }
});
