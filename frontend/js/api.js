/**
 * MedTrack API 客户端交互封装
 */


// ==================== 全局 UI 交互组件 ====================
window.showToast = function(message, type = null) {
  if (!type) {
    if (/失败|错误|异常|error|failed/i.test(message)) {
      type = 'error';
    } else {
      type = 'success';
    }
  }
  let toastContainer = document.getElementById('toast-container');
  const isMobile = window.innerWidth <= 768;
  const topPos = isMobile ? '115px' : '80px';

  if (!toastContainer) {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    toastContainer.className = 'toast-container';
    toastContainer.style.cssText = `position:fixed; top:${topPos}; left:50%; transform:translateX(-50%); z-index:100000; display:flex; flex-direction:column; gap:10px; pointer-events:none; max-width:90vw;`;
    document.body.appendChild(toastContainer);
  } else {
    toastContainer.style.top = topPos;
  }
  
  const toast = document.createElement('div');
  const bg = type === 'success' ? '#10b981' : (type === 'error' ? '#ef4444' : '#3b82f6');
  const icon = type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️');
  toast.style.cssText = `background:${bg}; color:white; padding:12px 24px; border-radius:10px; box-shadow:0 10px 25px -5px rgba(0,0,0,0.25), 0 8px 10px -6px rgba(0,0,0,0.15); display:flex; align-items:center; gap:10px; font-weight:500; font-size:0.95rem; opacity:0; transform:translateY(-15px); transition:all 0.3s cubic-bezier(0.16, 1, 0.3, 1); pointer-events:auto; max-width: 90vw; word-break: break-word; backdrop-filter:blur(4px);`;
  
  // 简易处理换行符
  const formattedMessage = message.replace(/\n/g, '<br>');
  toast.innerHTML = `<span style="font-size:1.2rem;">${icon}</span><span style="line-height:1.4;">${formattedMessage}</span>`;
  toastContainer.appendChild(toast);
  
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });
  
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-15px)';
    setTimeout(() => toast.remove(), 300);
  }, type === 'error' ? 5000 : 3000);
};

window.showConfirm = function(message, onConfirm) {
  let overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed; inset:0; background:rgba(15,23,42,0.6); z-index:99999; display:flex; align-items:center; justify-content:center; backdrop-filter:blur(3px); opacity:0; transition:opacity 0.2s;';
  
  const modal = document.createElement('div');
  modal.style.cssText = 'background:white; border-radius:12px; width:90%; max-width:400px; padding:24px; box-shadow:0 10px 25px rgba(0,0,0,0.2); transform:scale(0.95); transition:transform 0.2s;';
  
  const formattedMessage = message.replace(/\n/g, '<br>');
  modal.innerHTML = `
    <div style="font-size:1.1rem; font-weight:600; color:#0f172a; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
      <span style="font-size:1.4rem;">⚠️</span>
      <span>操作确认</span>
    </div>
    <div style="color:#475569; font-size:0.95rem; margin-bottom:24px; line-height:1.5; word-break:break-word;">${formattedMessage}</div>
    <div style="display:flex; justify-content:flex-end; gap:12px;">
      <button class="btn btn-secondary" id="confirm-cancel">取消</button>
      <button class="btn btn-primary" id="confirm-ok" style="background:#ef4444; border-color:#ef4444;">确认执行</button>
    </div>
  `;
  
  overlay.appendChild(modal);
  document.body.appendChild(overlay);
  
  requestAnimationFrame(() => {
    overlay.style.opacity = '1';
    modal.style.transform = 'scale(1)';
  });
  
  const close = () => {
    overlay.style.opacity = '0';
    modal.style.transform = 'scale(0.95)';
    setTimeout(() => overlay.remove(), 200);
  };
  
  modal.querySelector('#confirm-cancel').onclick = close;
  modal.querySelector('#confirm-ok').onclick = () => {
    close();
    onConfirm();
  };
};


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
        let msg = data.detail || data.message || `请求失败 (${response.status})`;
        if (Array.isArray(msg)) {
          msg = msg.map(item => {
            const field = item.loc ? item.loc[item.loc.length - 1] : '';
            return `${field ? field + ': ' : ''}${item.msg}`;
          }).join('; ');
        } else if (typeof msg === 'object') {
          msg = JSON.stringify(msg);
        }
        throw new Error(msg);
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

  async changePassword(oldPassword, newPassword) {
    return await this.request('/auth/password', {
      method: 'PUT',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword })
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
  async updateSurgery(id, data) {
    return await this.request(`/oncology/surgeries/${id}`, {
      method: 'PUT',
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
  async updateRadiotherapy(id, data) {
    return await this.request(`/oncology/radiotherapies/${id}`, {
      method: 'PUT',
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
  async updateTherapy(id, data) {
    return await this.request(`/oncology/therapies/${id}`, {
      method: 'PUT',
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
  async updatePathology(id, data) {
    return await this.request(`/oncology/pathologies/${id}`, {
      method: 'PUT',
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
  async updateLabReport(id, data) {
    return await this.request(`/labs/reports/${id}`, {
      method: 'PUT',
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
  async updateImagingReport(id, data) {
    return await this.request(`/imagings/reports/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  },
  async deleteImagingReport(id) {
    return await this.request(`/imagings/reports/${id}`, { method: 'DELETE' });
  },

  // ==================== 文件上传与 AI 识图 ====================
  async uploadAndParseBatch(files, docType) {
    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append('files', files[i]);
    }
    formData.append('doc_type', docType);

    return await this.request('/upload/parse-batch', {
      method: 'POST',
      body: formData
    });
  },

  async getBatchStatus(taskId) {
    return await this.request(`/upload/parse-batch/${taskId}`);
  },

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
  async getChartOverview(targetUserId = null) {
    let url = '/charts/overview';
    if (targetUserId) {
      url += `?target_user_id=${encodeURIComponent(targetUserId)}`;
    }
    return await this.request(url);
  },

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
  },

  // ==================== AI 大模型识别配置 ====================
  async getAISettings() {
    return await this.request('/admin/settings/ai');
  },

  async updateAISettings(data) {
    return await this.request('/admin/settings/ai', {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  },

  async testAISettings(data) {
    return await this.request('/admin/settings/ai/test', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }
};

window.API = API;
