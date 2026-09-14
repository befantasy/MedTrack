/**
 * MedTrack-Onco API 客户端交互封装
 */

const API_BASE = '/api';

const API = {
  // Token 管理
  getToken() {
    return localStorage.getItem('medtrack_token');
  },
  setToken(token) {
    localStorage.setItem('medtrack_token', token);
  },
  getUser() {
    try {
      return JSON.parse(localStorage.getItem('medtrack_user') || '{}');
    } catch {
      return {};
    }
  },
  setUser(user) {
    localStorage.setItem('medtrack_user', JSON.stringify(user));
  },
  clearAuth() {
    localStorage.removeItem('medtrack_token');
    localStorage.removeItem('medtrack_user');
  },

  // 统一请求底层
  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = options.headers || {};
    
    const token = this.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    options.headers = headers;

    try {
      const response = await fetch(url, options);
      const data = await response.json().catch(() => ({}));

      if (response.status === 401) {
        // 如果是登录或注册请求，直接展示服务端返回的明确原因（如“用户名或密码错误”），绝不重载页面
        if (endpoint.includes('/auth/login') || endpoint.includes('/auth/register')) {
          throw new Error(data.detail || '用户名或密码错误');
        }

        // 其他受保护接口返回 401，才说明已持有的 Token 凭证失效
        this.clearAuth();
        if (!window.location.pathname.includes('share.html')) {
          window.location.reload();
        }
        throw new Error('登录凭据已过期，请重新登录');
      }

      if (!response.ok) {
        throw new Error(data.detail || data.message || `请求失败 (${response.status})`);
      }
      return data;
    } catch (err) {
      console.error(`API Error [${endpoint}]:`, err);
      throw err;
    }
  },

  // ==================== 认证相关 ====================
  async login(username, password) {
    const res = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    this.setToken(res.access_token);
    this.setUser(res.user);
    return res;
  },

  async register(username, password) {
    const res = await this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    this.setToken(res.access_token);
    this.setUser(res.user);
    return res;
  },

  async getMe() {
    return await this.request('/auth/me');
  },

  async updateProfile(profileData) {
    return await this.request('/auth/profile', {
      method: 'PUT',
      body: JSON.stringify(profileData)
    });
  },

  // ==================== 肿瘤专科治疗与时间轴 ====================
  async getTimeline(targetUserId = null) {
    let url = '/oncology/timeline';
    if (targetUserId) {
      url += `?target_user_id=${encodeURIComponent(targetUserId)}`;
    }
    return await this.request(url);
  },

  async getSurgeries() {
    return await this.request('/oncology/surgeries');
  },
  async createSurgery(data) {
    return await this.request('/oncology/surgeries', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  async deleteSurgery(id) {
    return await this.request(`/oncology/surgeries/${id}`, { method: 'DELETE' });
  },

  async getRadiotherapies() {
    return await this.request('/oncology/radiotherapies');
  },
  async createRadiotherapy(data) {
    return await this.request('/oncology/radiotherapies', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  async deleteRadiotherapy(id) {
    return await this.request(`/oncology/radiotherapies/${id}`, { method: 'DELETE' });
  },

  async getTherapies() {
    return await this.request('/oncology/therapies');
  },
  async createTherapy(data) {
    return await this.request('/oncology/therapies', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  async deleteTherapy(id) {
    return await this.request(`/oncology/therapies/${id}`, { method: 'DELETE' });
  },

  async getPathologies() {
    return await this.request('/oncology/pathologies');
  },
  async createPathology(data) {
    return await this.request('/oncology/pathologies', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  async deletePathology(id) {
    return await this.request(`/oncology/pathologies/${id}`, { method: 'DELETE' });
  },

  async getMedicalRecords() {
    return await this.request('/oncology/records');
  },
  async createMedicalRecord(data) {
    return await this.request('/oncology/records', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  async deleteMedicalRecord(id) {
    return await this.request(`/oncology/records/${id}`, { method: 'DELETE' });
  },

  // ==================== 化验单与影像 ====================
  async getLabReports() {
    return await this.request('/labs/reports');
  },
  async createLabReport(data) {
    return await this.request('/labs/reports', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  async deleteLabReport(id) {
    return await this.request(`/labs/reports/${id}`, { method: 'DELETE' });
  },

  async getImagingReports() {
    return await this.request('/imagings/reports');
  },
  async createImagingReport(data) {
    return await this.request('/imagings/reports', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },
  async deleteImagingReport(id) {
    return await this.request(`/imagings/reports/${id}`, { method: 'DELETE' });
  },

  // ==================== 文件上传与 AI 识图 ====================
  async uploadAndParseDoc(file, docType) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('doc_type', docType);

    return await this.request('/upload/parse-doc', {
      method: 'POST',
      body: formData
    });
  },

  // ==================== 指标图表数据 ====================
  async getAvailableMetrics(targetUserId = null) {
    let url = '/charts/available-metrics';
    if (targetUserId) {
      url += `?target_user_id=${encodeURIComponent(targetUserId)}`;
    }
    return await this.request(url);
  },

  async getChartSeries(codes, targetUserId = null) {
    let url = `/charts/series?codes=${encodeURIComponent(codes)}`;
    if (targetUserId) {
      url += `&target_user_id=${encodeURIComponent(targetUserId)}`;
    }
    return await this.request(url);
  },

  // ==================== 就诊病历汇总与分享 ====================
  async getMyConsultationReport() {
    return await this.request('/share/my-report');
  },

  async createShareLink(expireDays = 7, accessCode = '') {
    return await this.request('/share/create-link', {
      method: 'POST',
      body: JSON.stringify({ expire_days: expireDays, access_code: accessCode })
    });
  },

  async viewSharedReport(token, accessCode = '') {
    let url = `/share/view/${token}`;
    if (accessCode) {
      url += `?code=${encodeURIComponent(accessCode)}`;
    }
    return await this.request(url);
  },

  // ==================== 超级管理员运维模块 ====================
  async getAdminStats() {
    return await this.request('/admin/stats');
  },

  async getAdminSettings() {
    return await this.request('/admin/settings');
  },

  async toggleRegistration(value) {
    return await this.request('/admin/settings/registration', {
      method: 'PUT',
      body: JSON.stringify({ value: String(value) })
    });
  },

  async getAdminUsers() {
    return await this.request('/admin/users');
  },

  async createAdminUser(data) {
    return await this.request('/admin/users', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  },

  async toggleUserStatus(userId) {
    return await this.request(`/admin/users/${userId}/status`, {
      method: 'PUT'
    });
  },

  async resetUserPassword(userId, newPassword) {
    return await this.request(`/admin/users/${userId}/password`, {
      method: 'PUT',
      body: JSON.stringify({ new_password: newPassword })
    });
  },

  async deleteAdminUser(userId) {
    return await this.request(`/admin/users/${userId}`, {
      method: 'DELETE'
    });
  },

  async getUserDossier(userId) {
    return await this.request(`/admin/users/${userId}/dossier`);
  }
};

window.API = API;
