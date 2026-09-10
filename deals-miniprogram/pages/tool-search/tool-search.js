// pages/tool-search/tool-search.js
Page({
  data: {
    keyword: '',
    allTools: [
      { name: 'AI每日优惠', desc: '淘宝天猫优惠券', icon: '🎁', color: 'linear-gradient(135deg, #ff6b6b, #ee5a24)', url: '/pages/index/index' },
      { name: 'AI配音', desc: '文字转语音', icon: '🎙️', color: 'linear-gradient(135deg, #a29bfe, #6c5ce7)', url: '/pages/ai-dubbing/ai-dubbing' },
      { name: 'AI声音克隆', desc: '复刻你的声音', icon: '🎤', color: 'linear-gradient(135deg, #fd79a8, #e84393)', url: '/pages/ai-voice-clone/ai-voice-clone' },
      { name: 'AI小说剧本化', desc: '一键生成剧本', icon: '📖', color: 'linear-gradient(135deg, #00b894, #00cec9)', url: '/pages/ai-novel/ai-novel' },
      { name: 'AI翻唱', desc: '秒变歌王', icon: '🎵', color: 'linear-gradient(135deg, #fdcb6e, #f39c12)', url: '/pages/ai-cover/ai-cover' }
    ],
    hotTools: [
      { name: 'AI每日优惠' },
      { name: 'AI配音' },
      { name: 'AI翻唱' }
    ],
    searchResults: []
  },

  onInputChange(e) {
    const keyword = e.detail.value.trim();
    this.setData({ keyword });
    if (keyword) {
      this.doSearch();
    } else {
      this.setData({ searchResults: [] });
    }
  },

  doSearch() {
    const keyword = this.data.keyword.toLowerCase();
    if (!keyword) {
      this.setData({ searchResults: [] });
      return;
    }
    const results = this.data.allTools.filter(tool =>
      tool.name.toLowerCase().includes(keyword) ||
      tool.desc.toLowerCase().includes(keyword)
    );
    this.setData({ searchResults: results });
  },

  clearKeyword() {
    this.setData({ keyword: '', searchResults: [] });
  },

  quickSearch(e) {
    const keyword = e.currentTarget.dataset.keyword;
    this.setData({ keyword });
    this.doSearch();
  },

  goToTool(e) {
    const url = e.currentTarget.dataset.url;
    wx.navigateTo({ url });
  }
});
