// API 工具类 - 小程序直接读取 GitHub Pages 上的 JSON 数据
const DATA_BASE_URL = 'https://duanchaobo.github.io/wool-monitor/';

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

module.exports = {
  fetchDealsData,
  fetchCategories
};
