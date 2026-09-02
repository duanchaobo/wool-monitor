// pages/index/index.js
const api = require('../../utils/api.js');

Page({
  data: {
    categories: [],         // 一级类目列表（含subs二级类目）
    currentSubs: [],        // 当前一级类目下的二级类目列表
    activeCategory: '全部', // 当前选中一级类目
    activeSubCategory: '',  // 当前选中二级类目
    allDeals: [],           // 所有商品
    filteredDeals: [],      // 过滤后的商品
    loading: true,
    updateTime: '',
    scrollTop: 0            // 滚动位置
  },

  onLoad() {
    this.loadData();
  },

  onShow() {
    // 切回时检查保存的状态，若数据未变化则直接恢复滚动位置，不重新加载
    const savedState = wx.getStorageSync('indexState');
    if (savedState && savedState.updateTime === this.data.updateTime && this.data.allDeals.length > 0) {
      if (savedState.scrollTop > 0) {
        wx.pageScrollTo({
          scrollTop: savedState.scrollTop,
          duration: 0
        });
      }
      return;
    }
    // 首次加载或数据已更新时才请求网络
    if (this.data.allDeals.length === 0) {
      this.loadData();
    }
  },

  onHide() {
    // 切换到淘宝前保存当前浏览状态（含筛选和滚动位置）
    wx.setStorageSync('indexState', {
      activeCategory: this.data.activeCategory,
      activeSubCategory: this.data.activeSubCategory,
      scrollTop: this.data.scrollTop,
      allDeals: this.data.allDeals,
      categories: this.data.categories,
      updateTime: this.data.updateTime
    });
  },

  onPageScroll(e) {
    this.setData({ scrollTop: e.scrollTop });
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

      // 构建一级类目（含二级类目），按商品数降序
      const categoriesWithDeals = categories
        .map(cat => ({
          name: cat.name,
          count: cat.count || 0,
          subs: cat.subs || []
        }))
        .filter(cat => cat.count > 0)
        .sort((a, b) => b.count - a.count);

      const newCategories = [{ name: '全部', count: allDeals.length, subs: [] }, ...categoriesWithDeals];

      // 缓存到本地，供搜索页使用
      wx.setStorageSync('allDeals', allDeals);

      this.setData({
        categories: newCategories,
        allDeals: allDeals,
        filteredDeals: allDeals,
        activeCategory: '全部',
        activeSubCategory: '',
        currentSubs: [],
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
   * 切换一级类目
   */
  switchCategory(e) {
    const category = e.currentTarget.dataset.category;
    // 找到当前一级类目对应的二级类目
    const catObj = this.data.categories.find(c => c.name === category);
    const subs = catObj ? (catObj.subs || []) : [];

    if (category === '全部') {
      this.setData({
        activeCategory: category,
        activeSubCategory: '',
        currentSubs: [],
        filteredDeals: this.data.allDeals
      });
    } else {
      const filtered = this.data.allDeals.filter(d => d.category === category);
      this.setData({
        activeCategory: category,
        activeSubCategory: '',
        currentSubs: subs,
        filteredDeals: filtered
      });
    }
  },

  /**
   * 切换二级类目
   */
  switchSubCategory(e) {
    const subCategory = e.currentTarget.dataset.sub;
    const activeCategory = this.data.activeCategory;
    const filtered = this.data.allDeals.filter(d =>
      d.category === activeCategory && d.sub_category === subCategory
    );
    this.setData({
      activeSubCategory: subCategory,
      filteredDeals: filtered
    });
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
