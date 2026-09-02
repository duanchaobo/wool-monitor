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
    scrollTop: 0,           // 滚动位置
    _stateRestored: false   // 标记是否已恢复状态
  },

  onLoad() {
    this.loadData();
  },

  onShow() {
    if (this.data._stateRestored) {
      // 从淘宝切回，恢复滚动位置即可，不重新加载数据
      this.setData({ _stateRestored: false });
      if (this.data.scrollTop > 0) {
        wx.pageScrollTo({
          scrollTop: this.data.scrollTop,
          duration: 0
        });
      }
      return;
    }
    this.loadData();
  },

  onHide() {
    // 切换到淘宝前保存当前浏览状态
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

      // 尝试恢复之前保存的浏览状态
      const savedState = wx.getStorageSync('indexState');
      let activeCategory = '全部';
      let activeSubCategory = '';
      let currentSubs = [];
      let filteredDeals = allDeals;

      if (savedState && savedState.allDeals) {
        // 检查数据是否有更新（通过updateTime判断）
        if (savedState.updateTime === (data.updateTime || '')) {
          // 数据未变化，恢复之前的筛选状态
          activeCategory = savedState.activeCategory || '全部';
          activeSubCategory = savedState.activeSubCategory || '';

          const catObj = newCategories.find(c => c.name === activeCategory);
          currentSubs = catObj ? (catObj.subs || []) : [];

          if (activeCategory === '全部') {
            filteredDeals = allDeals;
          } else {
            filteredDeals = allDeals.filter(d => d.category === activeCategory);
          }

          if (activeSubCategory) {
            filteredDeals = filteredDeals.filter(d => d.sub_category === activeSubCategory);
          }
        }
        // 清除已使用的状态
        wx.removeStorageSync('indexState');
      }

      this.setData({
        categories: newCategories,
        allDeals: allDeals,
        filteredDeals: filteredDeals,
        activeCategory: activeCategory,
        activeSubCategory: activeSubCategory,
        currentSubs: currentSubs,
        loading: false,
        updateTime: data.updateTime || '',
        _stateRestored: true
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
