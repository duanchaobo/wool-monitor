// API 工具类
const DATA_BASE_URL = 'https://duanchaobo.github.io/wool-monitor/deals-data/';

/**
 * 获取全品类优惠数据
 */
function fetchDealsData() {
  return new Promise((resolve, reject) => {
    wx.request({
      url: DATA_BASE_URL + 'deals.json',
      method: 'GET',
      success: (res) => {
        if (res.statusCode === 200 && res.data) {
          resolve(res.data);
        } else {
          reject(new Error('数据加载失败'));
        }
      },
      fail: (err) => {
        reject(err);
      }
    });
  });
}

/**
 * 获取品类列表
 */
function fetchCategories() {
  return new Promise((resolve, reject) => {
    wx.request({
      url: DATA_BASE_URL + 'categories.json',
      method: 'GET',
      success: (res) => {
        if (res.statusCode === 200 && res.data) {
          resolve(res.data);
        } else {
          reject(new Error('品类加载失败'));
        }
      },
      fail: (err) => {
        reject(err);
      }
    });
  });
}

/**
 * 触发 GitHub Actions 搜索
 * @param {string} keyword - 用户搜索关键词
 * @param {string} token - GitHub Personal Access Token
 */
function triggerSearch(keyword, token) {
  return new Promise((resolve, reject) => {
    if (!token) {
      reject(new Error('请先配置 GitHub Token'));
      return;
    }
    wx.request({
      url: 'https://api.github.com/repos/duanchaobo/wool-monitor/actions/workflows/deals-search.yml/dispatches',
      method: 'POST',
      header: {
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json'
      },
      data: {
        ref: 'main',
        inputs: {
          keyword: keyword
        }
      },
      success: (res) => {
        if (res.statusCode === 204) {
          resolve({ success: true, message: '搜索任务已提交，请稍后刷新查看结果' });
        } else {
          reject(new Error('触发失败: ' + (res.data && res.data.message || res.statusCode)));
        }
      },
      fail: (err) => {
        reject(err);
      }
    });
  });
}

/**
 * 获取搜索结果（搜索完成后从 GitHub Pages 读取）
 */
function fetchSearchResult(keyword) {
  const encodedKeyword = encodeURIComponent(keyword);
  return new Promise((resolve, reject) => {
    wx.request({
      url: DATA_BASE_URL + 'search/' + encodedKeyword + '.json',
      method: 'GET',
      success: (res) => {
        if (res.statusCode === 200 && res.data) {
          resolve(res.data);
        } else {
          reject(new Error('暂无搜索结果，请稍后再试'));
        }
      },
      fail: (err) => {
        reject(err);
      }
    });
  });
}

module.exports = {
  fetchDealsData,
  fetchCategories,
  triggerSearch,
  fetchSearchResult
};
