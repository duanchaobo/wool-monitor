// pages/home/home.js
Page({
  data: {},

  /**
   * 跳转到每日优惠页
   */
  goToDeals() {
    wx.switchTab({
      url: '/pages/index/index'
    });
  },

  /**
   * 跳转到AI功能页（空白占位页）
   */
  goToAiPage(e) {
    const url = e.currentTarget.dataset.url;
    wx.navigateTo({
      url: url
    });
  }
});
