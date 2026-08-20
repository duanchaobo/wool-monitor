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
   * 加载数据（过滤掉优惠力度<10%的商品）
   */
  async loadData() {
    this.setData({ loading: true });
    try {
      const data = await api.fetchDealsData();
      const categories = await api.fetchCategories();

      // 过滤：只保留优惠力度 >= 10% 的商品
      const allDeals = (data.deals || []).filter(d => d.discount >= 10);

      // 按品类分组统计
      const catCount = {};
      allDeals.forEach(d => {
        const cat = d.category || '其他';
        catCount[cat] = (catCount[cat] || 0) + 1;
      });

      // 构建品类列表（按商品数降序）
      const categoriesWithDeals = categories
        .map(cat => ({
          name: cat.name,
          count: catCount[cat.name] || 0
        }))
        .filter(cat => cat.count > 0)
        .sort((a, b) => b.count - a.count);

      // 缓存到本地，供搜索页使用（同样过滤）
      wx.setStorageSync('allDeals', allDeals);

      this.setData({
        categories: [{ name: '全部', count: allDeals.length }, ...categoriesWithDeals],
        allDeals: allDeals,
        filteredDeals: allDeals,
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
