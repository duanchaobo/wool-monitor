// pages/index/index.js
const api = require('../../utils/api.js');

Page({
  data: {
    categories: [],        // 品类列表
    activeCategory: '全部', // 当前选中品类
    allDeals: [],          // 所有商品
    filteredDeals: [],     // 当前品类过滤后的商品
    loading: true,
    updateTime: ''
  },

  onLoad() {
    this.loadData();
  },

  onShow() {
    // 每次显示页面时刷新数据
    this.loadData();
  },

  onPullDownRefresh() {
    this.loadData().then(() => {
      wx.stopPullDownRefresh();
    });
  },

  /**
   * 加载数据
   */
  async loadData() {
    this.setData({ loading: true });
    try {
      const data = await api.fetchDealsData();
      const categories = await api.fetchCategories();

      // 为每个品类添加商品
      const categoriesWithDeals = categories.map(cat => ({
        name: cat.name,
        count: cat.count || 0
      }));

      this.setData({
        categories: [{ name: '全部', count: data.total || 0 }, ...categoriesWithDeals],
        allDeals: data.deals || [],
        filteredDeals: data.deals || [],
        loading: false,
        updateTime: data.updateTime || ''
      });
    } catch (err) {
      console.error('加载数据失败:', err);
      this.setData({ loading: false });
      wx.showToast({
        title: '数据加载失败，请下拉刷新',
        icon: 'none'
      });
    }
  },

  /**
   * 切换品类
   */
  switchCategory(e) {
    const category = e.currentTarget.dataset.category;
    if (category === '全部') {
      this.setData({
        activeCategory: category,
        filteredDeals: this.data.allDeals
      });
    } else {
      const filtered = this.data.allDeals.filter(d => d.category === category);
      this.setData({
        activeCategory: category,
        filteredDeals: filtered
      });
    }
  },

  /**
   * 跳转到搜索页
   */
  goToSearch() {
    wx.switchTab({
      url: '/pages/search/search'
    });
  },

  /**
   * 复制淘口令/链接
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
