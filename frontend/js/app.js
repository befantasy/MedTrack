/**
 * MedTrack 核心应用交互逻辑
 */

let currentProfile = {};

document.addEventListener('DOMContentLoaded', async () => {
  initAuthUI();

  // 绑定登录输入框回车快捷键 (支持任意输入框直接回车登录)
  ['auth-username', 'auth-password'].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          handleLogin();
        }
      });
    }
  });

  // 绑定拖拽上传单据事件
  const dropzone = document.getElementById('upload-dropzone');
  if (dropzone) {
    ['dragenter', 'dragover'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.style.borderColor = '#0284c7';
        dropzone.style.background = '#f0f9ff';
      });
    });
    ['dragleave', 'drop'].forEach(eventName => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.style.borderColor = '#cbd5e1';
        dropzone.style.background = '#fafafa';
      });
    });
    dropzone.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length > 0) {
        onFileSelected(dt.files[0]);
      }
    });
  }

  if (API.getToken()) {
    await initApp();
  }
});

// ==================== 用户鉴权与初始化 ====================
function initAuthUI() {
  const token = API.getToken();
  const user = API.getUser() || {};

  const userBar = document.getElementById('user-bar');
  const authModal = document.getElementById('auth-modal');
  const mainApp = document.getElementById('main-app');
  const adminNavBtn = document.getElementById('nav-btn-admin');

  if (!token) {
    if (authModal) authModal.style.display = 'flex';
    if (mainApp) mainApp.style.display = 'none';
  } else {
    if (authModal) authModal.style.display = 'none';
    if (mainApp) mainApp.style.display = 'block';

    const isAdmin = Boolean(user && (user.is_admin || (user.username && user.username.toLowerCase() === 'admin')));
    if (adminNavBtn) {
      adminNavBtn.style.display = isAdmin ? 'inline-flex' : 'none';
    }

    if (userBar) {
      const adminBadge = isAdmin ? `<span class="badge" style="background:#fef3c7; color:#b45309; border:1px solid #fde68a;">🛡️ 管理员</span>` : '';
      const adminBtn = isAdmin ? `<button class="btn btn-primary btn-sm" style="background:#0284c7; font-weight:600;" onclick="switchTab('admin')">🛡️ 系统管理</button>` : '';
      userBar.innerHTML = `
        <span style="font-size:0.9rem; color:#475569;">👤 <strong>${escapeHtml(user.username || '患者')}</strong> ${adminBadge}</span>
        ${adminBtn}
        <button class="btn btn-secondary btn-sm" onclick="openProfileModal()">档案设置</button>
        <button class="btn btn-secondary btn-sm" onclick="openChangePasswordModal()">修改密码</button>
        <button class="btn btn-danger btn-sm" onclick="logout()">退出</button>
      `;
    }
  }
}

async function initApp() {
  try {
    const res = await API.getMe();
    if (res.user) {
      localStorage.setItem('medtrack_user', JSON.stringify(res.user));
      initAuthUI();
    }
    currentProfile = res.profile || {};
    renderProfileHeader();

    // 默认加载时间轴
    await switchTab('timeline');
  } catch (err) {
    console.error('Init app error:', err);
  }
}

function logout() {
  API.clearAuth();
  window.location.reload();
}

async function handleLogin() {
  const u = document.getElementById('auth-username').value.trim();
  const p = document.getElementById('auth-password').value.trim();
  const tip = document.getElementById('auth-tip');

  if (!u || !p) {
    tip.textContent = '请输入用户名和密码';
    return;
  }
  tip.textContent = '正在登录...';
  try {
    await API.login(u, p);
    tip.textContent = '';
    initAuthUI();
    await initApp();
  } catch (err) {
    tip.textContent = err.message;
  }
}

async function handleRegister() {
  const u = document.getElementById('auth-username').value.trim();
  const p = document.getElementById('auth-password').value.trim();
  const tip = document.getElementById('auth-tip');

  if (!u || !p) {
    tip.textContent = '请输入用户名和密码';
    return;
  }
  tip.textContent = '正在创建账户...';
  try {
    await API.register(u, p);
    tip.textContent = '';
    initAuthUI();
    await initApp();
  } catch (err) {
    tip.textContent = err.message;
  }
}

// ==================== 年龄与工具辅助函数 ====================
function calculateAge(birthDateStr) {
  if (!birthDateStr) return '';
  const parts = String(birthDateStr).trim().split('-');
  if (parts.length < 1 || !parts[0]) return '';
  const birthYear = parseInt(parts[0], 10);
  if (isNaN(birthYear) || birthYear < 1900 || birthYear > 2100) return '';
  const birthMonth = parts.length >= 2 ? parseInt(parts[1], 10) : 1;
  const birthDay = parts.length >= 3 ? parseInt(parts[2], 10) : 1;

  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth() + 1;
  const currentDay = today.getDate();

  let age = currentYear - birthYear;
  if (currentMonth < birthMonth || (currentMonth === birthMonth && currentDay < birthDay)) {
    age--;
  }
  return age >= 0 ? `${age}岁` : '';
}

if (typeof escapeHtml !== 'function') {
  window.escapeHtml = function(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  };
}

// ==================== 顶部档案面板渲染 ====================
function renderProfileHeader() {
  const box = document.getElementById('profile-summary-bar');
  if (!box) return;

  const age = calculateAge(currentProfile.birth_date);
  const gender = (currentProfile.gender || '').trim();
  let genderAgeParts = [];
  if (gender) genderAgeParts.push(gender);
  if (age) genderAgeParts.push(age);
  const genderAgeText = genderAgeParts.join(' · ');

  let markers = {};
  try {
    markers = JSON.parse(currentProfile.molecular_markers || '{}');
  } catch {}

  const markerList = Object.entries(markers).map(([k, v]) => `${k}: ${v}`).join(' | ') || '未录入/待检测';

  let comorbidities = [];
  try {
    comorbidities = JSON.parse(currentProfile.chronic_comorbidities || '[]');
  } catch {}
  const comorbText = comorbidities.length > 0 ? comorbidities.join(', ') : '无明显记录';

  box.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:12px;">
      <div>
        <h2 style="font-size:1.25rem; font-weight:700; color:#0f172a; display:flex; align-items:center; flex-wrap:wrap; gap:8px;">
          <span>${escapeHtml(currentProfile.patient_name || '未命名患者')}</span>
          ${genderAgeText ? `<span class="badge" style="background:#e0f2fe; color:#0369a1; font-size:0.85rem; padding:3px 10px; font-weight:600;">👤 ${escapeHtml(genderAgeText)}</span>` : ''}
          <span class="badge badge-purple">${escapeHtml(currentProfile.primary_site || '原发部位未注')}</span>
          <span class="badge badge-blue">${escapeHtml(currentProfile.pathology_type || '病理未录')}</span>
          <span class="badge badge-green">${escapeHtml(currentProfile.current_staging || '维持治疗/随访')}</span>
        </h2>
        <div style="font-size:0.88rem; color:#475569; margin-top:6px; display:flex; flex-wrap:wrap; gap:16px;">
          ${currentProfile.birth_date ? `<span>出生年月: <strong>${escapeHtml(currentProfile.birth_date)}</strong></span>` : ''}
          <span>初诊分期: <strong>${escapeHtml(currentProfile.initial_staging || '未详')}</strong></span>
          <span>确诊时间: <strong>${escapeHtml(currentProfile.initial_diagnosis_date || '未详')}</strong></span>
          <span>分子突变/靶点: <strong style="color:#0284c7;">${escapeHtml(markerList)}</strong></span>
          <span>合并慢病: <strong style="color:#d97706;">${escapeHtml(comorbText)}</strong></span>
        </div>
      </div>
      <div>
        <button class="btn btn-secondary btn-sm" onclick="openProfileModal()">✏️ 编辑肿瘤基准档案</button>
      </div>
    </div>
  `;
}

// ==================== 标签页切换 ====================
async function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));

  const target = document.getElementById(`tab-${tabId}`);
  const btn = document.getElementById(`nav-btn-${tabId}`);
  if (target) target.style.display = 'block';
  if (btn) btn.classList.add('active');

  if (tabId === 'timeline') {
    await TimelineModule.load('timeline-container');
  } else if (tabId === 'upload') {
    await loadUploadedDocs();
  } else if (tabId === 'charts') {
    await ChartsModule.initAll();
  } else if (tabId === 'treatments') {
    await loadTreatmentsList();
  } else if (tabId === 'report') {
    await loadConsultationReport();
  } else if (tabId === 'admin') {
    await AdminModule.loadDashboard();
  }
}

// ==================== AI 单据识别与自动提取 ====================
let parsedDocsQueue = [];

async function onFileSelected(event) {
  let files = [];
  if (event && event.target && event.target.files) {
    files = Array.from(event.target.files);
    event.target.value = ''; 
  } else if (event instanceof FileList) {
    files = Array.from(event);
  } else if (event instanceof File) {
    files = [event];
  }
  if (files.length === 0) return;

  const docType = document.getElementById('upload-doc-type').value;
  const statusBox = document.getElementById('upload-status');
  const previewBox = document.getElementById('upload-preview');

  statusBox.style.display = 'block';
  previewBox.style.display = 'none';

  parsedDocsQueue = [];

  for (let i = 0; i < files.length; i++) {
    statusBox.innerHTML = `
      <div style="display:flex; align-items:center; justify-content:center; gap:10px; color:#0284c7; padding:12px;">
        <div style="width:20px; height:20px; border:3px solid #e0f2fe; border-top-color:#0284c7; border-radius:50%; animation:spin 1s linear infinite;"></div>
        <span>正在解析第 ${i + 1} / ${files.length} 张单据...</span>
      </div>
      <style>@keyframes spin { 0% { transform:rotate(0deg); } 100% { transform:rotate(360deg); } }</style>
    `;
    try {
      const res = await API.uploadAndParseDoc(files[i], docType);
      parsedDocsQueue.push(res);
    } catch (err) {
      alert(`第 ${i + 1} 张解析失败: ${err.message}`);
    }
  }

  statusBox.style.display = 'none';
  if (parsedDocsQueue.length > 0) {
    renderParsedPreviewQueue();
  }
}

function renderParsedPreviewQueue() {
  const box = document.getElementById('upload-preview');
  box.style.display = 'block';

  let html = `
    <div class="card" style="border:1px solid #0284c7; background:#ffffff;">
      <div class="card-title" style="color:#0284c7; display:flex; justify-content:space-between; align-items:center;">
        <span>📋 待入库清单 (${parsedDocsQueue.length}份单据)</span>
        <button class="btn btn-primary" onclick="confirmSaveAllParsedDocs()">💾 一键全部存入病历档案</button>
      </div>
      <div style="color:#64748b; font-size:0.85rem; margin-bottom:10px;">
        💡 提示：您可以展开下列卡片核对 AI 提取的数据，直接在表格内修改纠错后再存入。
      </div>
      <div style="display:flex; flex-direction:column; gap:10px;">
  `;

  parsedDocsQueue.forEach((res, qIndex) => {
    const docType = res.doc_type;
    const data = res.parsed_data || {};
    
    let contentHtml = '';
    
    if (docType === 'lab') {
      const items = data.items || [];
      let rows = items.map((it, itemIdx) => {
        return `
          <tr>
            <td><input class="form-control form-control-sm" id="edit-lab-${qIndex}-${itemIdx}-name" value="${escapeHtml(it.item_name || it.name || '')}"></td>
            <td><input class="form-control form-control-sm" id="edit-lab-${qIndex}-${itemIdx}-code" value="${escapeHtml(it.item_code || it.code || '')}"></td>
            <td><input class="form-control form-control-sm" id="edit-lab-${qIndex}-${itemIdx}-value" value="${it.value !== null && it.value !== undefined ? it.value : (it.value_text || '')}"></td>
            <td><input class="form-control form-control-sm" id="edit-lab-${qIndex}-${itemIdx}-unit" value="${escapeHtml(it.unit || '')}"></td>
            <td><input class="form-control form-control-sm" id="edit-lab-${qIndex}-${itemIdx}-range" value="${escapeHtml(it.ref_range || '')}"></td>
          </tr>
        `;
      }).join('');
      
      contentHtml = `
        <div style="display:flex; gap:10px; margin-bottom:10px;">
          <input class="form-control form-control-sm" id="edit-lab-${qIndex}-type" value="${escapeHtml(data.report_type || '化验单')}" placeholder="类型">
          <input type="date" class="form-control form-control-sm" id="edit-lab-${qIndex}-date" value="${escapeHtml(data.report_date || '')}">
          <input class="form-control form-control-sm" id="edit-lab-${qIndex}-hospital" value="${escapeHtml(data.hospital || '')}" placeholder="医院">
        </div>
        <div class="table-responsive">
          <table class="med-table">
            <thead>
              <tr><th>项目名称</th><th>代码</th><th>测定值</th><th>单位</th><th>参考区间</th></tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      `;
    } else if (docType === 'imaging') {
      contentHtml = `
        <div style="display:flex; gap:10px; margin-bottom:10px;">
          <input class="form-control form-control-sm" id="edit-img-${qIndex}-modality" value="${escapeHtml(data.modality || '')}" placeholder="类别 (如 CT)">
          <input class="form-control form-control-sm" id="edit-img-${qIndex}-part" value="${escapeHtml(data.body_part || '')}" placeholder="部位">
          <input type="date" class="form-control form-control-sm" id="edit-img-${qIndex}-date" value="${escapeHtml(data.report_date || '')}">
        </div>
        <div style="margin-bottom:10px;">
          <label class="form-label" style="font-size:0.85rem;">检查所见</label>
          <textarea class="form-control" id="edit-img-${qIndex}-findings" rows="3">${escapeHtml(data.findings || '')}</textarea>
        </div>
        <div>
          <label class="form-label" style="font-size:0.85rem;">诊断结论 (Impression)</label>
          <textarea class="form-control" id="edit-img-${qIndex}-impression" rows="2">${escapeHtml(data.impression || '')}</textarea>
        </div>
      `;
    } else if (docType === 'pathology') {
      contentHtml = `
        <div style="display:flex; gap:10px; margin-bottom:10px;">
          <input class="form-control form-control-sm" id="edit-path-${qIndex}-type" value="${escapeHtml(data.sample_type || '')}" placeholder="标本类型">
          <input type="date" class="form-control form-control-sm" id="edit-path-${qIndex}-date" value="${escapeHtml(data.report_date || '')}">
        </div>
        <div style="margin-bottom:10px;">
          <label class="form-label" style="font-size:0.85rem;">病理诊断</label>
          <textarea class="form-control" id="edit-path-${qIndex}-diag" rows="3">${escapeHtml(data.histological_diagnosis || '')}</textarea>
        </div>
      `;
    } else {
      contentHtml = `<div style="font-size:0.9rem; color:#64748b;">支持自动入库，无需编辑。</div>`;
    }

    html += `
      <div style="border:1px solid #e2e8f0; border-radius:6px; background:#f8fafc;">
        <div style="padding:10px 14px; font-weight:600; font-size:0.95rem; background:#f1f5f9; border-bottom:1px solid #e2e8f0;">
          📄 单据 ${qIndex + 1}: ${docType.toUpperCase()}
        </div>
        <div style="padding:14px;">
          ${contentHtml}
        </div>
      </div>
    `;
  });

  html += `</div></div>`;
  box.innerHTML = html;
}

async function confirmSaveAllParsedDocs() {
  if (parsedDocsQueue.length === 0) return;
  const statusBox = document.getElementById('upload-status');
  statusBox.style.display = 'block';
  statusBox.innerHTML = '<div style="color:#0284c7; padding:10px; text-align:center;">正在批量保存...</div>';
  
  let successCount = 0;

  for (let qIndex = 0; qIndex < parsedDocsQueue.length; qIndex++) {
    const res = parsedDocsQueue[qIndex];
    const docType = res.doc_type;
    const data = res.parsed_data || {};
    
    try {
      if (docType === 'lab') {
        const typeVal = document.getElementById(`edit-lab-${qIndex}-type`)?.value || '化验单';
        const dateVal = document.getElementById(`edit-lab-${qIndex}-date`)?.value || new Date().toISOString().slice(0, 10);
        const hospVal = document.getElementById(`edit-lab-${qIndex}-hospital`)?.value || '';
        
        const items = [];
        (data.items || []).forEach((_, itemIdx) => {
          const vCode = document.getElementById(`edit-lab-${qIndex}-${itemIdx}-code`)?.value || 'OTHER';
          let vValStr = document.getElementById(`edit-lab-${qIndex}-${itemIdx}-value`)?.value || '';
          
          let parsedVal = parseFloat(vValStr.replace(/[^\d.-]/g, ''));
          
          items.push({
            item_name: document.getElementById(`edit-lab-${qIndex}-${itemIdx}-name`)?.value || '未知',
            item_code: vCode.toUpperCase().trim(),
            value: isNaN(parsedVal) ? null : parsedVal,
            value_text: vValStr,
            unit: document.getElementById(`edit-lab-${qIndex}-${itemIdx}-unit`)?.value || '',
            ref_range: document.getElementById(`edit-lab-${qIndex}-${itemIdx}-range`)?.value || '',
            test_date: dateVal
          });
        });

        await API.createLabReport({
          report_type: typeVal,
          report_date: dateVal,
          hospital: hospVal,
          raw_file_url: res.raw_file_url || '',
          ai_summary: data.ai_summary || '',
          items: items
        });
      } else if (docType === 'imaging') {
        await API.createImagingReport({
          modality: document.getElementById(`edit-img-${qIndex}-modality`)?.value || 'CT',
          body_part: document.getElementById(`edit-img-${qIndex}-part`)?.value || '',
          report_date: document.getElementById(`edit-img-${qIndex}-date`)?.value || new Date().toISOString().slice(0, 10),
          findings: document.getElementById(`edit-img-${qIndex}-findings`)?.value || '',
          impression: document.getElementById(`edit-img-${qIndex}-impression`)?.value || '',
          raw_file_url: res.raw_file_url
        });
      } else if (docType === 'pathology') {
        await API.createPathology({
          sample_type: document.getElementById(`edit-path-${qIndex}-type`)?.value || '',
          report_date: document.getElementById(`edit-path-${qIndex}-date`)?.value || new Date().toISOString().slice(0, 10),
          histological_diagnosis: document.getElementById(`edit-path-${qIndex}-diag`)?.value || '',
          raw_file_url: res.raw_file_url
        });
      }
      successCount++;
    } catch (err) {
      alert(`单据 ${qIndex + 1} 保存失败: ${err.message}`);
    }
  }

  statusBox.style.display = 'none';
  if (successCount > 0) {
    alert(`🎉 成功存入 ${successCount} 份单据档案！`);
    parsedDocsQueue = [];
    document.getElementById('upload-preview').style.display = 'none';
    
    if (window.ChartsModule) {
      window.ChartsModule.tumorChartInstance = null;
      window.ChartsModule.safetyChartInstance = null;
      window.ChartsModule.chronicChartInstance = null;
      window.ChartsModule.focusChartInstance = null;
    }
    await loadUploadedDocs();
  }
}

// ==================== 专科治疗管理 (手术/放疗/药物) ====================
let currentSurgeries = [];
let currentRadios = [];
let currentTherapies = [];

async function loadTreatmentsList() {
  const container = document.getElementById('treatments-list-container');
  if (!container) return;

  try {
    const [surgeries, radios, therapies] = await Promise.all([
      API.getSurgeries(),
      API.getRadiotherapies(),
      API.getTherapies()
    ]);
    currentSurgeries = surgeries || [];
    currentRadios = radios || [];
    currentTherapies = therapies || [];

    let surgHtml = currentSurgeries.map(s => `
      <div class="card" style="margin-bottom:12px; padding:14px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px;">
          <div style="flex:1;">
            <strong>${escapeHtml(s.surgery_name)}</strong>
            <span class="badge badge-red" style="margin-left:8px;">切缘: ${escapeHtml(s.margins || 'R0')}</span>
            <div style="font-size:0.85rem; color:#64748b; margin-top:4px;">
              日期: ${s.surgery_date} | 医院: ${escapeHtml(s.hospital || '未注')} | 淋巴结清扫: ${escapeHtml(s.lymph_nodes || '未详')}
            </div>
            ${s.pathology_summary ? `<div style="font-size:0.85rem; color:#334155; margin-top:4px;">病理摘要: ${escapeHtml(s.pathology_summary)}</div>` : ''}
          </div>
          <div style="display:flex; gap:6px; flex-shrink:0;">
            <button class="btn btn-secondary btn-sm" onclick="openEditSurgeryModal(${s.id})">编辑</button>
            <button class="btn btn-danger btn-sm" onclick="deleteSurgeryItem(${s.id})">删除</button>
          </div>
        </div>
      </div>
    `).join('') || '<p style="color:#94a3b8; font-size:0.9rem;">暂无手术记录</p>';

    let radioHtml = currentRadios.map(r => `
      <div class="card" style="margin-bottom:12px; padding:14px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px;">
          <div style="flex:1;">
            <strong>放疗靶区: ${escapeHtml(r.site)}</strong>
            <span class="badge badge-orange" style="margin-left:8px;">${escapeHtml(r.total_dose || '')} ${r.fractions ? '/ ' + escapeHtml(r.fractions) : ''}</span>
            <div style="font-size:0.85rem; color:#64748b; margin-top:4px;">
              技术: ${escapeHtml(r.technique || '标准')} | 周期: ${r.start_date} ~ ${r.end_date || '进行中'}
            </div>
            ${r.toxicity_notes ? `<div style="font-size:0.85rem; color:#d97706; margin-top:4px;">反应: ${escapeHtml(r.toxicity_notes)}</div>` : ''}
          </div>
          <div style="display:flex; gap:6px; flex-shrink:0;">
            <button class="btn btn-secondary btn-sm" onclick="openEditRadioModal(${r.id})">编辑</button>
            <button class="btn btn-danger btn-sm" onclick="deleteRadioItem(${r.id})">删除</button>
          </div>
        </div>
      </div>
    `).join('') || '<p style="color:#94a3b8; font-size:0.9rem;">暂无放疗记录</p>';

    let therapyHtml = currentTherapies.map(t => `
      <div class="card" style="margin-bottom:12px; padding:14px;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px;">
          <div style="flex:1;">
            <span class="badge badge-blue">${escapeHtml(t.treatment_line)}</span>
            <strong style="margin-left:6px;">${escapeHtml(t.regimen_name)} (第 ${t.cycle_number} 周期)</strong>
            <div style="font-size:0.85rem; color:#64748b; margin-top:4px;">
              类别: ${escapeHtml(t.therapy_type)} | 周期: ${t.start_date} ~ ${t.end_date || '用药中'}
            </div>
            ${t.drugs_detail ? `<div style="font-size:0.85rem; color:#0369a1; margin-top:4px;">用药规格: ${escapeHtml(t.drugs_detail)}</div>` : ''}
            ${t.adverse_events ? `<div style="font-size:0.85rem; color:#dc2626; margin-top:4px;">不良反应: ${escapeHtml(t.adverse_events)}</div>` : ''}
          </div>
          <div style="display:flex; gap:6px; flex-shrink:0;">
            <button class="btn btn-secondary btn-sm" onclick="openEditTherapyModal(${t.id})">编辑</button>
            <button class="btn btn-danger btn-sm" onclick="deleteTherapyItem(${t.id})">删除</button>
          </div>
        </div>
      </div>
    `).join('') || '<p style="color:#94a3b8; font-size:0.9rem;">暂无药物治疗记录</p>';

    container.innerHTML = `
      <div class="grid-3">
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="font-size:1.05rem; font-weight:700;">🔪 手术</h3>
            <button class="btn btn-primary btn-sm" onclick="openAddSurgeryModal()">+ 新增手术</button>
          </div>
          ${surgHtml}
        </div>
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="font-size:1.05rem; font-weight:700;">⚡ 放疗</h3>
            <button class="btn btn-primary btn-sm" onclick="openAddRadioModal()">+ 新增放疗</button>
          </div>
          ${radioHtml}
        </div>
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="font-size:1.05rem; font-weight:700;">💊 药物</h3>
            <button class="btn btn-primary btn-sm" onclick="openAddTherapyModal()">+ 新增药物</button>
          </div>
          ${therapyHtml}
        </div>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<p style="color:red;">加载失败: ${err.message}</p>`;
  }
}

async function deleteSurgeryItem(id) {
  if (!confirm('确认删除该手术记录？')) return;
  try {
    await API.deleteSurgery(id);
    await loadTreatmentsList();
  } catch (err) {
    alert('删除失败: ' + err.message);
  }
}
async function deleteRadioItem(id) {
  if (!confirm('确认删除该放疗记录？')) return;
  try {
    await API.deleteRadiotherapy(id);
    await loadTreatmentsList();
  } catch (err) {
    alert('删除失败: ' + err.message);
  }
}
async function deleteTherapyItem(id) {
  if (!confirm('确认删除该药物治疗记录？')) return;
  try {
    await API.deleteTherapy(id);
    await loadTreatmentsList();
  } catch (err) {
    alert('删除失败: ' + err.message);
  }
}

async function deleteTimelineEvent(type, id) {
  const typeNameMap = { lab: '化验单', imaging: '影像报告', pathology: '病理报告' };
  if (!confirm(`确认删除这份${typeNameMap[type] || '记录'}吗？删除后将无法恢复，且图表中的指标点也将被一并移除。`)) return;
  try {
    if (type === 'lab') await API.deleteLabReport(id);
    else if (type === 'imaging') await API.deleteImagingReport(id);
    else if (type === 'pathology') await API.deletePathology(id);
    
    alert('删除成功！');
    await TimelineModule.load();
    if (ChartsModule && typeof ChartsModule.load === 'function') {
       ChartsModule.load(); // 刷新图表
    }
  } catch (err) {
    alert('删除失败: ' + err.message);
  }
}
window.deleteTimelineEvent = deleteTimelineEvent;

// ==================== 单据识别管理 (Uploaded Docs) ====================
async function loadUploadedDocs() {
  const container = document.getElementById('uploaded-docs-list');
  if (!container) return;
  container.innerHTML = '<div style="color:#64748b; padding:20px; text-align:center;">正在加载归档记录...</div>';
  
  try {
    const targetUserId = window.inspectTargetUserId || null;
    const events = await API.getTimeline(targetUserId);
    const docs = events.filter(e => ['lab', 'imaging', 'pathology'].includes(e.event_type));
    
    if (docs.length === 0) {
      container.innerHTML = '<div style="color:#94a3b8; padding:20px; text-align:center;">暂无已归档的化验单、影像或病理报告记录。</div>';
      return;
    }
    
    const typeConfig = {
      imaging: { badge: 'badge-green', icon: '🩻', name: '影像报告' },
      lab: { badge: 'badge-blue', icon: '🧪', name: '化验单' },
      pathology: { badge: 'badge-purple', icon: '🔬', name: '病理报告' }
    };
    
    let html = '<div style="display:flex; flex-direction:column; gap:12px;">';
    docs.forEach(doc => {
      const cfg = typeConfig[doc.event_type];
      const realId = doc.id.split('_')[1];
      html += `
        <div style="background:#f8fafc; border:1px solid #e2e8f0; padding:14px; border-radius:8px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <div style="margin-bottom:6px;">
              <span style="margin-right:6px;">${cfg.icon}</span>
              <span class="badge ${cfg.badge}" style="margin-right:8px;">${cfg.name}</span>
              <strong style="color:#0f172a;">${escapeHtml(doc.title)}</strong>
              <span style="font-size:0.85rem; color:#64748b; margin-left:8px;">📅 ${doc.event_date}</span>
            </div>
            <div style="font-size:0.9rem; color:#475569;">${escapeHtml(doc.summary)}</div>
          </div>
          <div>
            <button class="btn btn-secondary btn-sm" style="color:#ef4444; border-color:#fee2e2; background:#fef2f2;" onclick="deleteUploadedDoc('${doc.event_type}', ${realId})">🗑️ 删除记录</button>
          </div>
        </div>
      `;
    });
    html += '</div>';
    container.innerHTML = html;
  } catch (err) {
    container.innerHTML = `<div style="color:#ef4444; padding:20px;">加载失败: ${err.message}</div>`;
  }
}

async function deleteUploadedDoc(type, id) {
  const typeNameMap = { lab: '化验单', imaging: '影像报告', pathology: '病理报告' };
  if (!confirm(`确认彻底删除这份「${typeNameMap[type] || '记录'}」吗？\n删除后将无法恢复，且图表中的相关指标数据也将从看板中移除。`)) return;
  try {
    if (type === 'lab') await API.deleteLabReport(id);
    else if (type === 'imaging') await API.deleteImagingReport(id);
    else if (type === 'pathology') await API.deletePathology(id);
    
    alert('删除成功！');
    await loadUploadedDocs();
    
    // 清理图表缓存使其下次切换时刷新
    if (window.ChartsModule) {
      window.ChartsModule.tumorChartInstance = null;
      window.ChartsModule.safetyChartInstance = null;
      window.ChartsModule.chronicChartInstance = null;
      window.ChartsModule.focusChartInstance = null;
    }
  } catch (err) {
    alert('删除失败: ' + err.message);
  }
}
window.loadUploadedDocs = loadUploadedDocs;
window.deleteUploadedDoc = deleteUploadedDoc;

// ==================== 就诊病历汇总与分享 ====================
async function loadConsultationReport() {
  const container = document.getElementById('report-container');
  if (!container) return;

  container.innerHTML = '<div style="text-align:center; padding:30px; color:#64748b;">正在综合病史与时序指标生成就诊报告...</div>';

  try {
    const report = await API.getMyConsultationReport();
    renderConsultationReport(report, container);
  } catch (err) {
    container.innerHTML = `<p style="color:red;">生成报告失败: ${err.message}</p>`;
  }
}

function renderConsultationReport(rep, container) {
  const p = rep.profile;
  const t = rep.treatment_summary;
  const img = rep.latest_imaging || [];
  const labTrend = rep.lab_trend_comparison || { dates: [], indicators: [] };

  const markerText = Object.entries(p.molecular_markers || {}).map(([k, v]) => `${k}: ${v}`).join('；') || '未行基因突变检测';
  const comorbText = (p.chronic_comorbidities || []).join('、') || '无明确合并症';

  let labRows = (labTrend.indicators || []).map(row => {
    let cells = row.values.map(v => {
      let stClass = '';
      if (v.status === 'HIGH') stClass = 'style="color:#ef4444; font-weight:600;"';
      if (v.status === 'LOW') stClass = 'style="color:#f59e0b; font-weight:600;"';
      return `<td ${stClass}>${v.val !== null ? v.val : v.val_text}</td>`;
    }).join('');
    return `
      <tr>
        <td><strong>${escapeHtml(row.name)}</strong> (${row.code})</td>
        <td>${escapeHtml(row.ref_range)} ${row.unit}</td>
        ${cells}
      </tr>
    `;
  }).join('');

  let dateHeaders = (labTrend.dates || []).map(d => `<th>${d}</th>`).join('');

  container.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
      <h2 style="font-size:1.3rem; font-weight:700;">📑 门诊就诊与会诊摘要</h2>
      <div style="display:flex; gap:8px;">
        <button class="btn btn-primary" onclick="window.print()">🖨️ 打印 / 导出 PDF</button>
        <button class="btn btn-success" onclick="openCreateShareModal()">🔗 生成 7 天加密分享链接</button>
      </div>
    </div>

    <div class="card" style="border-top:4px solid var(--primary); padding:24px;">
      <div style="border-bottom:1px solid #e2e8f0; padding-bottom:14px; margin-bottom:16px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h1 style="font-size:1.4rem; font-weight:800; color:#0f172a;">${escapeHtml(p.name)} - 就诊病程汇报单</h1>
          <span style="font-size:0.85rem; color:#64748b;">报告生成时间: ${rep.generated_at}</span>
        </div>
        <div style="font-size:0.92rem; color:#334155; margin-top:8px; display:flex; flex-wrap:wrap; gap:16px;">
          ${(p.gender || p.birth_date) ? `<span><strong>基本信息:</strong> ${[p.gender, calculateAge(p.birth_date)].filter(Boolean).join(' · ')}${p.birth_date ? ` (${p.birth_date})` : ''}</span>` : ''}
          <span><strong>原发诊断:</strong> ${escapeHtml(p.primary_site)} ${escapeHtml(p.pathology_type)}</span>
          <span><strong>初诊分期:</strong> ${escapeHtml(p.initial_staging || '未详')}</span>
          <span><strong>当前阶段:</strong> ${escapeHtml(p.current_staging || '维持/随访')}</span>
          <span><strong>ECOG评分:</strong> ${escapeHtml(p.ecog_score)}分</span>
        </div>
        <div style="font-size:0.88rem; color:#475569; margin-top:6px;">
          <span><strong>分子检测/靶点:</strong> <span style="color:#0284c7;">${markerText}</span></span>
        </div>
        <div style="font-size:0.88rem; color:#475569; margin-top:4px;">
          <span><strong>合并慢性病与用药:</strong> ${comorbText} | 过敏史: ${escapeHtml(p.allergies)}</span>
        </div>
      </div>

      <div style="margin-bottom:18px;">
        <h3 style="font-size:1.05rem; font-weight:700; color:#1e293b; margin-bottom:8px; border-left:3px solid var(--secondary); padding-left:8px;">
          一、 既往主要抗肿瘤治疗历程
        </h3>
        <div style="font-size:0.9rem; line-height:1.7; color:#334155;">
          ${t.has_surgery ? `
            <div><strong>手术史:</strong> ${t.surgeries.map(s => `[${s.date}] ${s.name} (切缘: ${s.margins}, 淋巴结: ${s.lymph_nodes})`).join('； ')}</div>
          ` : '<div><strong>手术史:</strong> 无手术干预</div>'}
          
          ${t.has_radiotherapy ? `
            <div><strong>放疗史:</strong> ${t.radiotherapies.map(r => `[${r.date}] 靶区: ${r.site} (${r.dose}, ${r.fractions})`).join('； ')}</div>
          ` : ''}

          ${t.has_systemic_therapy ? `
            <div><strong>系统药物治疗:</strong> ${t.systemic_therapies.map(th => `[${th.date}] ${th.line}: ${th.regimen} (${th.cycle})`).join('； ')}</div>
          ` : '<div><strong>系统用药:</strong> 暂未记录</div>'}
        </div>
      </div>

      <div style="margin-bottom:18px;">
        <h3 style="font-size:1.05rem; font-weight:700; color:#1e293b; margin-bottom:8px; border-left:3px solid var(--secondary); padding-left:8px;">
          二、 近期影像学 (CT/MRI) 疗效随访
        </h3>
        ${img.length > 0 ? img.map(im => `
          <div style="background:#f8fafc; padding:10px 14px; border-radius:6px; margin-bottom:8px; font-size:0.88rem;">
            <div>📅 <strong>${im.date} ${im.modality} (${im.body_part})</strong> - 疗效评估: <span class="badge badge-blue">${im.recist}</span></div>
            <div style="color:#475569; margin-top:4px;"><strong>诊断结论:</strong> ${escapeHtml(im.impression)}</div>
          </div>
        `).join('') : '<p style="font-size:0.88rem; color:#94a3b8;">暂无近期影像学记录</p>'}
      </div>

      <div>
        <h3 style="font-size:1.05rem; font-weight:700; color:#1e293b; margin-bottom:8px; border-left:3px solid var(--secondary); padding-left:8px;">
          三、 关键肿瘤标志物与毒副安全性指标横向对比
        </h3>
        <div class="table-responsive">
          <table class="med-table">
            <thead>
              <tr><th>检验项目</th><th>参考范围</th>${dateHeaders}</tr>
            </thead>
            <tbody>${labRows || '<tr><td colspan="5" style="text-align:center;color:#94a3b8;">暂无多采样点对比数据</td></tr>'}</tbody>
          </table>
        </div>
      </div>

      ${(rep.recent_lab_reports && rep.recent_lab_reports.length > 0) ? `
      <div style="margin-top:20px;">
        <h3 style="font-size:1.05rem; font-weight:700; color:#1e293b; margin-bottom:8px; border-left:3px solid var(--secondary); padding-left:8px;">
          四、 近期化验单归档明细与 AI 综合解读
        </h3>
        <div style="display:flex; flex-direction:column; gap:8px;">
          ${rep.recent_lab_reports.map(lr => `
            <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:10px 14px; font-size:0.88rem;">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span><strong>📅 ${escapeHtml(lr.date || '未注日期')}</strong> · ${escapeHtml(lr.type || '检验化验单')} (${escapeHtml(lr.hospital || '未注机构')})</span>
                <span class="badge badge-green">已归档</span>
              </div>
              ${lr.summary ? `<div style="color:#0369a1; background:#f0f9ff; padding:6px 10px; border-radius:4px; margin-top:4px;">💡 <strong>AI 综合解读:</strong> ${escapeHtml(lr.summary)}</div>` : ''}
            </div>
          `).join('')}
        </div>
      </div>
      ` : ''}
    </div>
  `;
}

// ==================== 肿瘤与慢病基准档案编辑交互 ====================
let editingMarkers = {};
let editingComorbidities = [];

const COMMON_COMORBIDITIES_PRESETS = [
  '高血压', '2型糖尿病', '冠心病', '高脂血症',
  '乙肝/脂肪肝', '慢性胃炎/消化道溃疡', '慢性肾脏病', '骨质疏松'
];

function handlePrimarySiteChange() {
  const sel = document.getElementById('prof-site-select');
  const custom = document.getElementById('prof-site-custom');
  if (!sel || !custom) return;
  if (sel.value === '__other__') {
    custom.style.display = 'block';
    custom.focus();
  } else {
    custom.style.display = 'none';
    custom.value = '';
  }
}

function handlePathologyTypeChange() {
  const sel = document.getElementById('prof-type-select');
  const custom = document.getElementById('prof-type-custom');
  if (!sel || !custom) return;
  if (sel.value === '__other__') {
    custom.style.display = 'block';
    custom.focus();
  } else {
    custom.style.display = 'none';
    custom.value = '';
  }
}

function handleGeneSelectChange() {
  const sel = document.getElementById('prof-gene-select');
  const custom = document.getElementById('prof-gene-custom');
  if (!sel || !custom) return;
  if (sel.value === '__custom__') {
    custom.style.display = 'block';
    custom.focus();
  } else {
    custom.style.display = 'none';
    custom.value = '';
  }
}

function renderComorbidPresetPills() {
  const container = document.getElementById('comorb-preset-pills');
  if (!container) return;
  container.innerHTML = COMMON_COMORBIDITIES_PRESETS.map(name => {
    const isSelected = editingComorbidities.includes(name);
    return `<button type="button" class="pill-select-btn ${isSelected ? 'active' : ''}" onclick="toggleComorbidPreset('${escapeHtml(name)}')">
      ${isSelected ? '✓ ' : '＋ '}${escapeHtml(name)}
    </button>`;
  }).join('');
}

function toggleComorbidPreset(name) {
  const idx = editingComorbidities.indexOf(name);
  if (idx >= 0) {
    editingComorbidities.splice(idx, 1);
  } else {
    editingComorbidities.push(name);
  }
  renderEditingComorbidities();
}

function addCustomComorbid() {
  const input = document.getElementById('prof-custom-comorbid');
  if (!input) return;
  const val = (input.value || '').trim();
  if (!val) return;
  if (!editingComorbidities.includes(val)) {
    editingComorbidities.push(val);
  }
  input.value = '';
  renderEditingComorbidities();
}

function removeComorbid(name) {
  editingComorbidities = editingComorbidities.filter(c => c !== name);
  renderEditingComorbidities();
}

function renderEditingComorbidities() {
  renderComorbidPresetPills();
  const container = document.getElementById('prof-comorb-container');
  if (!container) return;
  if (editingComorbidities.length === 0) {
    container.innerHTML = '<span style="color:#94a3b8; font-size:0.82rem; line-height:30px;">暂未添加合并慢病（可从上方直接点击预置疾病，或输入添加）</span>';
    return;
  }
  container.innerHTML = editingComorbidities.map(c => `
    <span class="pill-badge" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0;">
      <span>🩺 ${escapeHtml(c)}</span>
      <span class="pill-badge-remove" title="删除此慢病" onclick="removeComorbid('${escapeHtml(c)}')">✕</span>
    </span>
  `).join('');
}

function addMolecularMarker() {
  const geneSel = document.getElementById('prof-gene-select');
  const geneCustom = document.getElementById('prof-gene-custom');
  const valInput = document.getElementById('prof-gene-val');
  if (!geneSel || !valInput) return;

  let gene = '';
  if (geneSel.value === '__custom__') {
    gene = (geneCustom.value || '').trim();
  } else {
    gene = (geneSel.value || '').trim();
  }

  const val = (valInput.value || '').trim();
  if (!gene) {
    alert('请选择或输入基因/分子靶点名称 (如: EGFR)');
    if (geneSel.value === '__custom__') geneCustom.focus();
    else geneSel.focus();
    return;
  }
  if (!val) {
    alert('请输入该靶点的检测结果或突变分型 (如: 19-del 或 阳性)');
    valInput.focus();
    return;
  }
  editingMarkers[gene] = val;
  geneSel.value = '';
  if (geneCustom) {
    geneCustom.value = '';
    geneCustom.style.display = 'none';
  }
  valInput.value = '';
  renderEditingMarkers();
  geneSel.focus();
}

function removeMolecularMarker(gene) {
  delete editingMarkers[gene];
  renderEditingMarkers();
}

function renderEditingMarkers() {
  const container = document.getElementById('prof-markers-container');
  if (!container) return;
  const entries = Object.entries(editingMarkers);
  if (entries.length === 0) {
    container.innerHTML = '<span style="color:#94a3b8; font-size:0.82rem; line-height:30px;">暂未添加分子靶点（可从上方选择靶点并填写检测结果）</span>';
    return;
  }
  container.innerHTML = entries.map(([gene, val]) => `
    <span class="pill-badge" style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe;">
      <strong>🧬 ${escapeHtml(gene)}:</strong>
      <span>${escapeHtml(val)}</span>
      <span class="pill-badge-remove" title="删除此靶点" onclick="removeMolecularMarker('${escapeHtml(gene)}')">✕</span>
    </span>
  `).join('');
}

// 模态弹窗控制辅助函数
function openProfileModal() {
  const m = document.getElementById('profile-modal');
  if (!m) return;
  m.style.display = 'flex';

  document.getElementById('prof-name').value = currentProfile.patient_name || '';
  const genderEl = document.getElementById('prof-gender');
  if (genderEl) genderEl.value = currentProfile.gender || '';
  const birthEl = document.getElementById('prof-birth-date');
  if (birthEl) birthEl.value = currentProfile.birth_date || '';

  // 1. 原发部位 (过滤历史默认占位符 '未录入')
  let site = (currentProfile.primary_site || '').trim();
  if (site === '未录入') site = '';
  const siteSelect = document.getElementById('prof-site-select');
  const siteCustom = document.getElementById('prof-site-custom');
  let matchedSite = false;
  if (siteSelect) {
    for (let opt of siteSelect.options) {
      if (opt.value && opt.value !== '__other__' && (site === opt.value || site.startsWith(opt.value))) {
        siteSelect.value = opt.value;
        matchedSite = true;
        break;
      }
    }
    if (!matchedSite && site) {
      siteSelect.value = '__other__';
      siteCustom.value = site;
      siteCustom.style.display = 'block';
    } else {
      if (!matchedSite) siteSelect.value = '';
      siteCustom.value = '';
      siteCustom.style.display = 'none';
    }
  }

  // 2. 病理分型 (过滤历史默认占位符 '未录入')
  let pathology = (currentProfile.pathology_type || '').trim();
  if (pathology === '未录入') pathology = '';
  const typeSelect = document.getElementById('prof-type-select');
  const typeCustom = document.getElementById('prof-type-custom');
  let matchedType = false;
  if (typeSelect) {
    for (let opt of typeSelect.options) {
      if (opt.value && opt.value !== '__other__' && pathology === opt.value) {
        typeSelect.value = opt.value;
        matchedType = true;
        break;
      }
    }
    if (!matchedType && pathology) {
      typeSelect.value = '__other__';
      typeCustom.value = pathology;
      typeCustom.style.display = 'block';
    } else {
      if (!matchedType) typeSelect.value = '';
      typeCustom.value = '';
      typeCustom.style.display = 'none';
    }
  }

  // 3. 确诊时间
  document.getElementById('prof-date').value = currentProfile.initial_diagnosis_date || '';

  // 4. 初诊分期 (智能拆解主要分期与 TNM 备注，过滤历史 '未录入')
  let staging = (currentProfile.initial_staging || '').trim();
  if (staging === '未录入') staging = '';
  const stagingSelect = document.getElementById('prof-staging-select');
  const stagingDetail = document.getElementById('prof-staging-detail');
  if (stagingSelect && stagingDetail) {
    let matchedStaging = '';
    const stageOptions = Array.from(stagingSelect.options).map(o => o.value).filter(v => v);
    stageOptions.sort((a, b) => b.length - a.length);
    for (let optVal of stageOptions) {
      if (staging.includes(optVal)) {
        matchedStaging = optVal;
        break;
      }
    }
    if (matchedStaging) {
      stagingSelect.value = matchedStaging;
      stagingDetail.value = staging.replace(matchedStaging, '').trim();
    } else {
      stagingSelect.value = '';
      stagingDetail.value = staging;
    }
  }

  // 5. 当前阶段 (平滑映射历史值 '初诊/治疗中' -> '初诊评估中')
  let curStaging = (currentProfile.current_staging || '').trim();
  if (curStaging === '初诊/治疗中') curStaging = '初诊评估中';
  const curStagingSelect = document.getElementById('prof-cur-staging');
  if (curStagingSelect) {
    let matchedCur = false;
    for (let opt of curStagingSelect.options) {
      if (opt.value === curStaging) {
        curStagingSelect.value = curStaging;
        matchedCur = true;
        break;
      }
    }
    if (!matchedCur && curStaging) {
      const newOpt = new Option(curStaging, curStaging, true, true);
      curStagingSelect.add(newOpt);
    } else if (!matchedCur) {
      curStagingSelect.value = '';
    }
  }

  // 6. 驱动基因与分子靶点
  const geneSel = document.getElementById('prof-gene-select');
  const geneCustom = document.getElementById('prof-gene-custom');
  const geneVal = document.getElementById('prof-gene-val');
  if (geneSel) geneSel.value = '';
  if (geneCustom) { geneCustom.value = ''; geneCustom.style.display = 'none'; }
  if (geneVal) geneVal.value = '';
  try {
    editingMarkers = JSON.parse(currentProfile.molecular_markers || '{}');
    if (typeof editingMarkers !== 'object' || Array.isArray(editingMarkers)) editingMarkers = {};
  } catch {
    editingMarkers = {};
  }
  renderEditingMarkers();

  // 7. 合并慢性病
  try {
    editingComorbidities = JSON.parse(currentProfile.chronic_comorbidities || '[]');
    if (!Array.isArray(editingComorbidities)) editingComorbidities = [];
  } catch {
    editingComorbidities = [];
  }
  renderEditingComorbidities();
}

function closeProfileModal() {
  const m = document.getElementById('profile-modal');
  if (m) m.style.display = 'none';
}

async function saveProfile() {
  const siteSel = document.getElementById('prof-site-select').value;
  const siteCustom = document.getElementById('prof-site-custom').value.trim();
  const primarySite = siteSel === '__other__' ? siteCustom : siteSel;

  const typeSel = document.getElementById('prof-type-select').value;
  const typeCustom = document.getElementById('prof-type-custom').value.trim();
  const pathologyType = typeSel === '__other__' ? typeCustom : typeSel;

  const stageSel = document.getElementById('prof-staging-select').value;
  const stageDetail = document.getElementById('prof-staging-detail').value.trim();
  let initialStaging = '';
  if (stageSel && stageDetail) {
    initialStaging = `${stageDetail} ${stageSel}`.trim();
  } else {
    initialStaging = stageSel || stageDetail;
  }

  const updated = {
    patient_name: document.getElementById('prof-name').value.trim(),
    gender: document.getElementById('prof-gender') ? document.getElementById('prof-gender').value.trim() : '',
    birth_date: document.getElementById('prof-birth-date') ? document.getElementById('prof-birth-date').value.trim() : '',
    primary_site: primarySite,
    pathology_type: pathologyType,
    initial_diagnosis_date: document.getElementById('prof-date').value.trim(),
    initial_staging: initialStaging,
    current_staging: document.getElementById('prof-cur-staging').value.trim(),
    molecular_markers: JSON.stringify(editingMarkers),
    chronic_comorbidities: JSON.stringify(editingComorbidities)
  };

  try {
    currentProfile = await API.updateProfile(updated);
    renderProfileHeader();
    closeProfileModal();
    alert('基准档案已成功保存！');
  } catch (err) {
    alert(`保存失败: ${err.message}`);
  }
}

// 分享弹窗
function openCreateShareModal() {
  document.getElementById('share-modal').style.display = 'flex';
  document.getElementById('share-result-box').style.display = 'none';
}
function closeShareModal() {
  document.getElementById('share-modal').style.display = 'none';
}
async function generateShareLink() {
  const days = parseInt(document.getElementById('share-days').value) || 7;
  const pin = document.getElementById('share-pin').value.trim();

  try {
    const res = await API.createShareLink(days, pin);
    const resultBox = document.getElementById('share-result-box');
    const fullUrl = window.location.origin + res.share_url;

    resultBox.style.display = 'block';
    resultBox.innerHTML = `
      <div style="background:#f0fdf4; border:1px solid #bbf7d0; padding:12px; border-radius:8px; margin-top:12px;">
        <div style="color:#166534; font-weight:600; margin-bottom:6px;">✅ 分享链接生成成功！</div>
        <input type="text" class="form-input" id="share-link-input" value="${fullUrl}" readonly style="font-size:0.85rem; margin-bottom:8px;" />
        ${res.access_code ? `<div style="font-size:0.85rem; color:#475569; margin-bottom:8px;">访问提取码: <strong>${res.access_code}</strong></div>` : ''}
        <button class="btn btn-success btn-sm" onclick="copyShareLink()">📋 复制完整链接发给医生</button>
      </div>
    `;
  } catch (err) {
    alert(`生成失败: ${err.message}`);
  }
}

function copyShareLink() {
  const input = document.getElementById('share-link-input');
  if (!input) return;
  input.select();
  document.execCommand('copy');
  alert('已复制到剪贴板！医生无需登录，在手机微信或浏览器中即可直接查阅整份病历。');
}

// ==================== 手术/放疗/药物 弹窗控制与提交 ====================

// --- 手术弹窗控制 ---
function openAddSurgeryModal() {
  document.getElementById('surg-edit-id').value = '';
  document.getElementById('surg-modal-title').textContent = '🔪 记录外科手术';
  document.getElementById('surg-submit-btn').textContent = '保存手术记录';
  document.getElementById('surg-name').value = '';
  document.getElementById('surg-date').value = '';
  document.getElementById('surg-margins').value = 'R0';
  document.getElementById('surg-lymph').value = '';
  document.getElementById('surg-hospital').value = '';
  document.getElementById('surg-pathology').value = '';
  document.getElementById('surgery-modal').style.display = 'flex';
}

function openEditSurgeryModal(id) {
  const item = currentSurgeries.find(s => s.id === id);
  if (!item) return;
  document.getElementById('surg-edit-id').value = item.id;
  document.getElementById('surg-modal-title').textContent = '✏️ 编辑外科手术记录';
  document.getElementById('surg-submit-btn').textContent = '保存修改';
  document.getElementById('surg-name').value = item.surgery_name || '';
  document.getElementById('surg-date').value = item.surgery_date || '';
  document.getElementById('surg-margins').value = item.margins || 'R0';
  document.getElementById('surg-lymph').value = item.lymph_nodes || '';
  document.getElementById('surg-hospital').value = item.hospital || '';
  document.getElementById('surg-pathology').value = item.pathology_summary || '';
  document.getElementById('surgery-modal').style.display = 'flex';
}

function closeAddSurgeryModal() {
  document.getElementById('surgery-modal').style.display = 'none';
}

async function submitAddSurgery() {
  const editId = document.getElementById('surg-edit-id').value;
  const data = {
    surgery_name: document.getElementById('surg-name').value.trim(),
    surgery_date: document.getElementById('surg-date').value.trim(),
    margins: document.getElementById('surg-margins').value,
    lymph_nodes: document.getElementById('surg-lymph').value.trim(),
    hospital: document.getElementById('surg-hospital').value.trim(),
    pathology_summary: document.getElementById('surg-pathology').value.trim()
  };
  if (!data.surgery_name || !data.surgery_date) {
    alert('请填写术式名称和手术日期');
    return;
  }
  try {
    if (editId) {
      await API.updateSurgery(editId, data);
    } else {
      await API.createSurgery(data);
    }
    closeAddSurgeryModal();
    await loadTreatmentsList();
  } catch (err) {
    alert(`保存手术记录失败: ${err.message}`);
  }
}

// --- 放疗弹窗控制 ---
function openAddRadioModal() {
  document.getElementById('radio-edit-id').value = '';
  document.getElementById('radio-modal-title').textContent = '⚡ 记录放射治疗';
  document.getElementById('radio-submit-btn').textContent = '保存放疗记录';
  document.getElementById('radio-site').value = '';
  document.getElementById('radio-tech').value = '';
  document.getElementById('radio-dose').value = '';
  document.getElementById('radio-frac').value = '';
  document.getElementById('radio-start').value = '';
  document.getElementById('radio-end').value = '';
  document.getElementById('radio-tox').value = '';
  document.getElementById('radio-modal').style.display = 'flex';
}

function openEditRadioModal(id) {
  const item = currentRadios.find(r => r.id === id);
  if (!item) return;
  document.getElementById('radio-edit-id').value = item.id;
  document.getElementById('radio-modal-title').textContent = '✏️ 编辑放射治疗记录';
  document.getElementById('radio-submit-btn').textContent = '保存修改';
  document.getElementById('radio-site').value = item.site || '';
  document.getElementById('radio-tech').value = item.technique || '';
  document.getElementById('radio-dose').value = item.total_dose || '';
  document.getElementById('radio-frac').value = item.fractions || '';
  document.getElementById('radio-start').value = item.start_date || '';
  document.getElementById('radio-end').value = item.end_date || '';
  document.getElementById('radio-tox').value = item.toxicity_notes || '';
  document.getElementById('radio-modal').style.display = 'flex';
}

function closeAddRadioModal() {
  document.getElementById('radio-modal').style.display = 'none';
}

async function submitAddRadio() {
  const editId = document.getElementById('radio-edit-id').value;
  const data = {
    site: document.getElementById('radio-site').value.trim(),
    technique: document.getElementById('radio-tech').value.trim(),
    total_dose: document.getElementById('radio-dose').value.trim(),
    fractions: document.getElementById('radio-frac').value.trim(),
    start_date: document.getElementById('radio-start').value.trim(),
    end_date: document.getElementById('radio-end').value.trim(),
    toxicity_notes: document.getElementById('radio-tox').value.trim()
  };
  if (!data.site || !data.start_date) {
    alert('请填写照射靶区和开始日期');
    return;
  }
  try {
    if (editId) {
      await API.updateRadiotherapy(editId, data);
    } else {
      await API.createRadiotherapy(data);
    }
    closeAddRadioModal();
    await loadTreatmentsList();
  } catch (err) {
    alert(`保存放疗记录失败: ${err.message}`);
  }
}

// --- 药物治疗弹窗控制 ---
function openAddTherapyModal() {
  document.getElementById('ther-edit-id').value = '';
  document.getElementById('ther-modal-title').textContent = '💊 记录药物治疗 (化疗/靶向/免疫)';
  document.getElementById('ther-submit-btn').textContent = '保存药物记录';
  document.getElementById('ther-line').value = '一线治疗';
  document.getElementById('ther-type').value = '靶向治疗';
  document.getElementById('ther-regimen').value = '';
  document.getElementById('ther-cycle').value = '1';
  if (document.getElementById('ther-drugs')) document.getElementById('ther-drugs').value = '';
  document.getElementById('ther-start').value = '';
  document.getElementById('ther-end').value = '';
  document.getElementById('ther-adverse').value = '';
  document.getElementById('therapy-modal').style.display = 'flex';
}

function openEditTherapyModal(id) {
  const item = currentTherapies.find(t => t.id === id);
  if (!item) return;
  document.getElementById('ther-edit-id').value = item.id;
  document.getElementById('ther-modal-title').textContent = '✏️ 编辑药物治疗记录';
  document.getElementById('ther-submit-btn').textContent = '保存修改';
  document.getElementById('ther-line').value = item.treatment_line || '一线治疗';
  document.getElementById('ther-type').value = item.therapy_type || '靶向治疗';
  document.getElementById('ther-regimen').value = item.regimen_name || '';
  document.getElementById('ther-cycle').value = item.cycle_number || 1;
  if (document.getElementById('ther-drugs')) document.getElementById('ther-drugs').value = item.drugs_detail || '';
  document.getElementById('ther-start').value = item.start_date || '';
  document.getElementById('ther-end').value = item.end_date || '';
  document.getElementById('ther-adverse').value = item.adverse_events || '';
  document.getElementById('therapy-modal').style.display = 'flex';
}

function closeAddTherapyModal() {
  document.getElementById('therapy-modal').style.display = 'none';
}

async function submitAddTherapy() {
  const editId = document.getElementById('ther-edit-id').value;
  const data = {
    regimen_name: document.getElementById('ther-regimen').value.trim(),
    treatment_line: document.getElementById('ther-line').value,
    therapy_type: document.getElementById('ther-type').value,
    cycle_number: parseInt(document.getElementById('ther-cycle').value) || 1,
    start_date: document.getElementById('ther-start').value.trim(),
    end_date: document.getElementById('ther-end').value.trim(),
    drugs_detail: document.getElementById('ther-drugs') ? document.getElementById('ther-drugs').value.trim() : '',
    adverse_events: document.getElementById('ther-adverse').value.trim()
  };
  if (!data.regimen_name || !data.start_date) {
    alert('请填写方案名称和开始日期');
    return;
  }
  try {
    if (editId) {
      await API.updateTherapy(editId, data);
    } else {
      await API.createTherapy(data);
    }
    closeAddTherapyModal();
    await loadTreatmentsList();
  } catch (err) {
    alert(`保存药物治疗记录失败: ${err.message}`);
  }
}

// ==================== 超级管理员运维模块 ====================
const AdminModule = {
  currentSettings: null,
  activeDossier: null,

  async loadDashboard() {
    try {
      // 1. 加载统计概览
      const stats = await API.getAdminStats();
      const elUsers = document.getElementById('admin-stat-users');
      const elActive = document.getElementById('admin-stat-active');
      const elTreatments = document.getElementById('admin-stat-treatments');
      const elLabs = document.getElementById('admin-stat-labs');
      const elStorage = document.getElementById('admin-stat-storage');

      if (elUsers) elUsers.textContent = stats.total_users;
      if (elActive) elActive.textContent = stats.active_users;
      if (elTreatments) elTreatments.textContent = stats.total_treatments;
      if (elLabs) elLabs.textContent = stats.total_labs_imaging;
      if (elStorage) elStorage.textContent = `${stats.storage_usage_mb} MB`;

      // 2. 加载系统设置（注册开关与大模型识别引擎）
      await this.loadSettings();
      await this.loadAISettings();

      // 3. 加载全量用户列表
      await this.loadUsers();
    } catch (err) {
      console.error('加载管理员控制台失败:', err);
      alert('加载管理员数据失败: ' + err.message);
    }
  },

  async loadSettings() {
    try {
      this.currentSettings = await API.getAdminSettings();
      const badge = document.getElementById('reg-status-badge');
      if (badge) {
        if (this.currentSettings.allow_registration) {
          badge.innerHTML = `<span class="badge badge-green">已开放 (允许公开注册)</span>`;
        } else {
          badge.innerHTML = `<span class="badge badge-red">已关闭 (仅管理员手动开通)</span>`;
        }
      }
    } catch (err) {
      console.error('获取系统设置失败:', err);
    }
  },

  async loadAISettings() {
    try {
      const data = await API.getAISettings();
      const statusBadge = document.getElementById('admin-ai-status-badge');
      const keyInput = document.getElementById('admin-ai-key');
      const keyHint = document.getElementById('admin-ai-key-hint');
      const baseUrlInput = document.getElementById('admin-ai-base-url');
      const modelInput = document.getElementById('admin-ai-model');

      if (statusBadge) {
        if (data.configured) {
          statusBadge.innerHTML = `<span class="badge" style="background:#dcfce7; color:#15803d; font-weight:bold;">✅ 真实 AI 模式就绪</span>`;
        } else {
          statusBadge.innerHTML = `<span class="badge" style="background:#ffedd5; color:#c2410c; font-weight:bold;">⚠️ 模拟演示模式 (未配Key)</span>`;
        }
      }

      if (keyInput) {
        keyInput.value = '';
        keyInput.placeholder = data.configured ? `已配置 (${data.masked_key})，留空保持不变` : '填入大模型 API Key (如 AIzaSy... / sk-...)';
      }
      if (keyHint) {
        if (data.configured) {
          keyHint.innerHTML = `<span style="color:#16a34a;">✅ 当前有效密钥: <code>${escapeHtml(data.masked_key)}</code> (${data.is_env_source ? '来自环境变量' : '来自后台配置'})</span>`;
        } else {
          keyHint.innerHTML = `<span style="color:#ea580c;">⚠️ 尚未配置有效密钥，上传单据将展示示例模拟数据</span>`;
        }
      }
      if (baseUrlInput && data.base_url) {
        baseUrlInput.value = data.base_url;
      }
      if (modelInput && data.model) {
        modelInput.value = data.model;
      }
    } catch (err) {
      console.error('获取 AI 配置失败:', err);
    }
  },

  async saveAISettings() {
    try {
      const keyInput = document.getElementById('admin-ai-key');
      const baseUrlInput = document.getElementById('admin-ai-base-url');
      const modelInput = document.getElementById('admin-ai-model');

      const payload = {};
      if (keyInput && keyInput.value.trim()) {
        payload.api_key = keyInput.value.trim();
      }
      if (baseUrlInput && baseUrlInput.value.trim()) {
        payload.base_url = baseUrlInput.value.trim();
      }
      if (modelInput && modelInput.value.trim()) {
        payload.model = modelInput.value.trim();
      }

      const res = await API.updateAISettings(payload);
      await this.loadAISettings();
      alert(`✅ ${res.message || 'AI 识别引擎配置保存成功！'}\n\n即时生效，现在前往【单据识别】上传化验单即可体验真实 AI 解析。`);
    } catch (err) {
      alert('保存 AI 配置失败: ' + err.message);
    }
  },

  toggleAiKeyVisibility() {
    const input = document.getElementById('admin-ai-key');
    if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
  },

  async testAIConnection() {
    const keyInput = document.getElementById('admin-ai-key');
    const baseUrlInput = document.getElementById('admin-ai-base-url');
    const modelInput = document.getElementById('admin-ai-model');

    const payload = {
      api_key: keyInput ? keyInput.value.trim() : '',
      base_url: baseUrlInput ? baseUrlInput.value.trim() : '',
      model: modelInput ? modelInput.value.trim() : ''
    };

    const statusBadge = document.getElementById('admin-ai-status-badge');
    if (statusBadge) {
      statusBadge.innerHTML = `<span class="badge" style="background:#e0f2fe; color:#0369a1;">⚡ 正在测试连通性...</span>`;
    }

    try {
      const res = await API.testAISettings(payload);
      if (res.success) {
        if (statusBadge) {
          statusBadge.innerHTML = `<span class="badge" style="background:#dcfce7; color:#15803d; font-weight:bold;">✅ 连通成功 (${res.latency_ms}ms)</span>`;
        }
        alert(`✅ 连通性测试成功！\n\n• 目标端点: ${res.endpoint}\n• 模型响应: 正常\n• 响应耗时: ${res.latency_ms} ms\n\n大模型识别服务与中转站已成功打通，您可以点击“保存配置”正式启用！`);
      } else {
        if (statusBadge) {
          statusBadge.innerHTML = `<span class="badge" style="background:#fee2e2; color:#b91c1c; font-weight:bold;">❌ 连通失败</span>`;
        }
        alert(`❌ 连通测试未通过:\n\n• 请求端点: ${res.endpoint}\n• 错误信息: ${res.message}\n\n💡 提示: 如果是 sub2api / OneAPI 等中转站，Base URL 建议填写为: https://api.medai.link/v1`);
      }
    } catch (err) {
      if (statusBadge) {
        statusBadge.innerHTML = `<span class="badge" style="background:#fee2e2; color:#b91c1c; font-weight:bold;">❌ 连通失败</span>`;
      }
      alert(`测试请求异常: ${err.message}`);
    }
  },

  async toggleRegistration() {
    try {
      const current = this.currentSettings ? this.currentSettings.allow_registration : true;
      const next = !current;
      await API.toggleRegistration(next);
      await this.loadSettings();
      alert(`注册功能已${next ? '【开放】' : '【关闭】'}。${next ? '新访客可自主注册账户。' : '新访客无法自主注册，保护服务器算力与AI密钥额度。'}`);
    } catch (err) {
      alert('修改注册开关失败: ' + err.message);
    }
  },

  async loadUsers() {
    const tbody = document.getElementById('admin-user-tbody');
    const countBadge = document.getElementById('admin-user-count');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:#94a3b8;">正在拉取用户数据与就诊摘要...</td></tr>`;

    try {
      const users = await API.getAdminUsers();
      if (countBadge) countBadge.textContent = `${users.length} 位用户`;

      if (users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:#94a3b8;">暂无用户数据</td></tr>`;
        return;
      }

      const currentUser = API.getUser() || {};

      tbody.innerHTML = users.map(u => {
        const isSelf = u.id === currentUser.id;
        const roleBadge = u.is_admin 
          ? `<span class="badge" style="background:#fef3c7; color:#b45309; border:1px solid #fde68a;">🛡️ 超管</span>` 
          : `<span class="badge badge-blue">普通用户</span>`;
        const statusBadge = u.is_active 
          ? `<span class="badge badge-green">正常</span>` 
          : `<span class="badge badge-red">已冻结</span>`;

        const summary = u.summary || { surgeries: 0, radiotherapies: 0, therapies: 0, labs: 0, imagings: 0, path: 0 };
        const summaryText = `
          <span title="手术">${summary.surgeries}手</span> | 
          <span title="放疗">${summary.radiotherapies}放</span> | 
          <span title="药物">${summary.therapies}药</span> | 
          <span title="化验">${summary.labs}化</span> | 
          <span title="影像">${summary.imagings}影</span>
        `;

        const dateStr = u.created_at ? u.created_at.slice(0, 10) : '-';
        const primarySite = escapeHtml(u.primary_site || '-');
        const pathologyType = escapeHtml(u.pathology_type || '-');
        const patientName = escapeHtml(u.patient_name || '未填');

        return `
          <tr style="border-bottom:1px solid #f1f5f9; transition:background 0.2s;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='transparent'">
            <td style="padding:10px 8px; font-weight:600; color:#64748b;">${u.id}</td>
            <td style="padding:10px 8px;">
              <strong>${escapeHtml(u.username)}</strong>
              ${isSelf ? '<span class="badge" style="background:#f1f5f9; color:#475569; font-size:0.7rem; margin-left:4px;">当前操作者</span>' : ''}
            </td>
            <td style="padding:10px 8px;">${patientName}</td>
            <td style="padding:10px 8px; font-size:0.85rem; color:#475569;">${primarySite} / ${pathologyType}</td>
            <td style="padding:10px 8px; font-size:0.82rem; color:#0284c7; white-space:nowrap;">${summaryText}</td>
            <td style="padding:10px 8px; font-size:0.82rem; color:#64748b;">${dateStr}</td>
            <td style="padding:10px 8px;">${roleBadge} ${statusBadge}</td>
            <td style="padding:10px 8px; text-align:right; white-space:nowrap;">
              <button class="btn btn-secondary btn-sm" style="padding:3px 8px; font-size:0.8rem; margin-right:4px;" onclick="App.inspectDossier(${u.id})">📑 查看病历全宗</button>
              <button class="btn btn-primary btn-sm" style="padding:3px 8px; font-size:0.8rem; margin-right:4px;" onclick="App.enterInspectMode(${u.id}, '${patientName}', '${escapeHtml(u.username)}')">👁️ 穿透查阅看板</button>
              <button class="btn btn-secondary btn-sm" style="padding:3px 8px; font-size:0.8rem; margin-right:4px;" onclick="App.openResetPwdModal(${u.id}, '${escapeHtml(u.username)}')">🔑 设密</button>
              ${!isSelf ? `
                <button class="btn ${u.is_active ? 'btn-secondary' : 'btn-primary'} btn-sm" style="padding:3px 8px; font-size:0.8rem; margin-right:4px;" onclick="App.toggleUserStatus(${u.id})">${u.is_active ? '❄️ 冻结' : '☀️ 启用'}</button>
                <button class="btn btn-danger btn-sm" style="padding:3px 8px; font-size:0.8rem;" onclick="App.deleteUser(${u.id}, '${escapeHtml(u.username)}')">🗑️ 删除</button>
              ` : ''}
            </td>
          </tr>
        `;
      }).join('');
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:20px; color:#ef4444;">拉取用户失败: ${err.message}</td></tr>`;
    }
  },

  openAdminCreateUserModal() {
    document.getElementById('admin-new-user').value = '';
    document.getElementById('admin-new-pwd').value = '';
    document.getElementById('admin-new-name').value = '';
    document.getElementById('admin-new-site').value = '';
    document.getElementById('admin-new-type').value = '';
    document.getElementById('admin-new-isadmin').checked = false;
    document.getElementById('admin-create-tip').textContent = '';
    document.getElementById('modal-admin-create-user').style.display = 'flex';
  },

  closeAdminCreateUserModal() {
    document.getElementById('modal-admin-create-user').style.display = 'none';
  },

  async submitAdminCreateUser() {
    const username = document.getElementById('admin-new-user').value.trim();
    const password = document.getElementById('admin-new-pwd').value.trim();
    const patient_name = document.getElementById('admin-new-name').value.trim();
    const primary_site = document.getElementById('admin-new-site').value.trim();
    const pathology_type = document.getElementById('admin-new-type').value.trim();
    const is_admin = document.getElementById('admin-new-isadmin').checked;
    const tip = document.getElementById('admin-create-tip');

    if (!username || !password) {
      tip.textContent = '用户名和密码为必填项';
      return;
    }

    try {
      await API.createAdminUser({
        username,
        password,
        patient_name,
        primary_site,
        pathology_type,
        is_admin
      });
      this.closeAdminCreateUserModal();
      await this.loadDashboard();
      alert(`账号【${username}】创建成功！`);
    } catch (err) {
      tip.textContent = err.message;
    }
  },

  openResetPwdModal(userId, username) {
    document.getElementById('admin-pwd-target-id').value = userId;
    document.getElementById('admin-pwd-target-name').textContent = username;
    document.getElementById('admin-pwd-new').value = '';
    document.getElementById('admin-pwd-tip').textContent = '';
    document.getElementById('modal-admin-reset-pwd').style.display = 'flex';
  },

  closeAdminResetPwdModal() {
    document.getElementById('modal-admin-reset-pwd').style.display = 'none';
  },

  async submitAdminResetPwd() {
    const userId = document.getElementById('admin-pwd-target-id').value;
    const newPassword = document.getElementById('admin-pwd-new').value.trim();
    const tip = document.getElementById('admin-pwd-tip');

    if (!newPassword || newPassword.length < 4) {
      tip.textContent = '新密码不能少于4位字符';
      return;
    }

    try {
      await API.resetUserPassword(userId, newPassword);
      this.closeAdminResetPwdModal();
      alert('密码重置成功！');
    } catch (err) {
      tip.textContent = err.message;
    }
  },

  async toggleUserStatus(userId) {
    try {
      const res = await API.toggleUserStatus(userId);
      await this.loadUsers();
      alert(`用户状态已切换为: ${res.is_active ? '【正常】' : '【已冻结】'}`);
    } catch (err) {
      alert('切换状态失败: ' + err.message);
    }
  },

  async deleteUser(userId, username) {
    if (!confirm(`⚠️ 高危操作确认：\n\n您确定要彻底删除用户【${username}】及其所有的肿瘤病历、手术记录、用药周期、化验单和影像记录吗？\n\n此操作将永久级联清除，不可恢复！`)) {
      return;
    }

    try {
      await API.deleteAdminUser(userId);
      await this.loadDashboard();
      alert(`用户【${username}】及其全量档案已删除。`);
    } catch (err) {
      alert('删除用户失败: ' + err.message);
    }
  },

  async inspectDossier(userId) {
    const box = document.getElementById('admin-dossier-content');
    const badge = document.getElementById('dossier-patient-badge');
    box.innerHTML = `<div style="text-align:center; padding:40px; color:#94a3b8;">正在调阅该患者临床病历与检测档案...</div>`;
    document.getElementById('modal-admin-dossier').style.display = 'flex';

    try {
      const dossier = await API.getUserDossier(userId);
      this.activeDossier = dossier;

      const u = dossier.user;
      const p = dossier.profile || {};
      badge.textContent = `${u.username} (患者: ${p.patient_name || '未设姓名'})`;

      let markers = {};
      try { markers = JSON.parse(p.molecular_markers || '{}'); } catch {}
      const markerText = Object.entries(markers).map(([k, v]) => `<span class="badge badge-purple" style="margin-right:4px;">${k}: ${v}</span>`).join('') || '暂无';

      let comorbs = [];
      try { comorbs = JSON.parse(p.chronic_comorbidities || '[]'); } catch {}
      const comorbText = comorbs.length ? comorbs.join('、') : '无';

      // 渲染大抽屉各区块
      box.innerHTML = `
        <!-- 1. 患者肿瘤基准画像 -->
        <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:14px; margin-bottom:14px;">
          <h4 style="margin:0 0 8px 0; color:#0f172a; font-size:1rem; display:flex; align-items:center; gap:6px;">
            <span>🧬 肿瘤基准画像</span>
            <span class="badge badge-blue">${escapeHtml(p.primary_site || '原发部位未填')}</span>
            <span class="badge badge-green">${escapeHtml(p.pathology_type || '病理未填')}</span>
          </h4>
          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:0.88rem; color:#475569;">
            <div>患者姓名: <strong>${escapeHtml(p.patient_name || '未填')}</strong></div>
            <div>性别/年龄: <strong>${[p.gender, calculateAge(p.birth_date)].filter(Boolean).join(' · ') || '未填'}</strong></div>
            <div>初诊分期: <strong>${escapeHtml(p.initial_staging || '未详')}</strong></div>
            <div>当前分期: <strong>${escapeHtml(p.current_staging || '未详')}</strong></div>
            <div>确诊日期: <strong>${escapeHtml(p.initial_diagnosis_date || '未详')}</strong></div>
            <div>ECOG日常活动评分: <strong>${p.ecog_score !== null && p.ecog_score !== undefined ? p.ecog_score + ' 分' : '未评'}</strong></div>
            <div>合并慢性病: <strong>${escapeHtml(comorbText)}</strong></div>
            <div style="grid-column: 1 / -1;">驱动基因/免疫靶点: ${markerText}</div>
          </div>
        </div>

        <!-- 2. 手术记录 -->
        <div style="margin-bottom:14px;">
          <h4 style="margin:0 0 8px 0; color:#0f172a; font-size:0.95rem;">🔪 手术与切除治疗 (${dossier.surgeries?.length || 0})</h4>
          ${dossier.surgeries && dossier.surgeries.length > 0 ? `
            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
              <thead><tr style="background:#f1f5f9; color:#475569;"><th style="padding:6px;">术式名称</th><th>手术日期</th><th>切缘</th><th>淋巴结清扫</th><th>就诊医院</th><th>病理摘要</th></tr></thead>
              <tbody>
                ${dossier.surgeries.map(s => `
                  <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:6px;"><strong>${escapeHtml(s.surgery_name)}</strong></td>
                    <td>${s.surgery_date}</td>
                    <td><span class="badge badge-red">${escapeHtml(s.margins || '-')}</span></td>
                    <td>${escapeHtml(s.lymph_nodes || '-')}</td>
                    <td>${escapeHtml(s.hospital || '-')}</td>
                    <td style="font-size:0.8rem; color:#475569;">${escapeHtml(s.pathology_summary || '-')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : '<p style="color:#94a3b8; font-size:0.85rem; margin:0;">无手术记录</p>'}
        </div>

        <!-- 3. 放疗记录 -->
        <div style="margin-bottom:14px;">
          <h4 style="margin:0 0 8px 0; color:#0f172a; font-size:0.95rem;">⚡ 放射治疗记录 (${dossier.radiotherapies?.length || 0})</h4>
          ${dossier.radiotherapies && dossier.radiotherapies.length > 0 ? `
            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
              <thead><tr style="background:#f1f5f9; color:#475569;"><th style="padding:6px;">照射靶区</th><th>技术</th><th>剂量 / 分次</th><th>起止日期</th><th>放射副反应</th></tr></thead>
              <tbody>
                ${dossier.radiotherapies.map(r => `
                  <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:6px;"><strong>${escapeHtml(r.site)}</strong></td>
                    <td>${escapeHtml(r.technique || '-')}</td>
                    <td>${escapeHtml(r.total_dose || '-')} / ${escapeHtml(r.fractions || '-')}</td>
                    <td>${r.start_date} ~ ${r.end_date || '进行中'}</td>
                    <td style="font-size:0.8rem; color:#d97706;">${escapeHtml(r.toxicity_notes || '-')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : '<p style="color:#94a3b8; font-size:0.85rem; margin:0;">无放疗记录</p>'}
        </div>

        <!-- 4. 药物/靶向/化疗周期 -->
        <div style="margin-bottom:14px;">
          <h4 style="margin:0 0 8px 0; color:#0f172a; font-size:0.95rem;">💊 药物抗肿瘤全身治疗 (${dossier.systemic_therapies?.length || 0})</h4>
          ${dossier.systemic_therapies && dossier.systemic_therapies.length > 0 ? `
            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
              <thead><tr style="background:#f1f5f9; color:#475569;"><th style="padding:6px;">方案名称</th><th>阶段/线数</th><th>类别</th><th>周期</th><th>时间范围</th><th>毒副反应</th></tr></thead>
              <tbody>
                ${dossier.systemic_therapies.map(t => `
                  <tr style="border-bottom:1px solid #f1f5f9;">
                    <td style="padding:6px;"><strong>${escapeHtml(t.regimen_name)}</strong></td>
                    <td><span class="badge badge-blue">${escapeHtml(t.treatment_line)}</span></td>
                    <td>${escapeHtml(t.therapy_type)}</td>
                    <td>第 ${t.cycle_number} 周期</td>
                    <td>${t.start_date} ~ ${t.end_date || '维持'}</td>
                    <td style="font-size:0.8rem; color:#dc2626;">${escapeHtml(t.adverse_events || '-')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          ` : '<p style="color:#94a3b8; font-size:0.85rem; margin:0;">无用药记录</p>'}
        </div>

        <!-- 5. 检验化验单与重要指标 -->
        <div style="margin-bottom:14px;">
          <h4 style="margin:0 0 8px 0; color:#0f172a; font-size:0.95rem;">🧪 临床检验化验 (${dossier.lab_reports?.length || 0})</h4>
          ${dossier.lab_reports && dossier.lab_reports.length > 0 ? `
            <div style="display:flex; flex-direction:column; gap:8px;">
              ${dossier.lab_reports.map(l => {
                const abnormalCount = l.items?.filter(it => it.status !== 'NORMAL').length || 0;
                return `
                  <div style="border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px; background:#fff;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                      <div>
                        <strong>${escapeHtml(l.report_type || '化验报告')}</strong>
                        <span style="font-size:0.82rem; color:#64748b; margin-left:8px;">${l.report_date} | ${escapeHtml(l.hospital || '未注医院')}</span>
                      </div>
                      ${abnormalCount > 0 ? `<span class="badge badge-red">${abnormalCount} 项异常</span>` : `<span class="badge badge-green">全部正常</span>`}
                    </div>
                    ${l.ai_summary ? `<div style="font-size:0.8rem; color:#0284c7; margin-top:4px;">💡 AI解析摘要: ${escapeHtml(l.ai_summary)}</div>` : ''}
                    <div style="margin-top:6px; font-size:0.8rem; color:#475569;">
                      包含测定项: ${l.items?.map(it => `${escapeHtml(it.item_name)}: <strong>${it.value !== null ? it.value : it.value_text}</strong>${it.unit ? ' ' + escapeHtml(it.unit) : ''}${it.status === 'HIGH' ? ' ↑' : (it.status === 'LOW' ? ' ↓' : '')}`).join('， ') || '无指标明细'}
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          ` : '<p style="color:#94a3b8; font-size:0.85rem; margin:0;">无化验记录</p>'}
        </div>

        <!-- 6. 影像学检查 (CT/MRI/PET-CT) -->
        <div style="margin-bottom:14px;">
          <h4 style="margin:0 0 8px 0; color:#0f172a; font-size:0.95rem;">🩻 影像学检查与RECIST评估 (${dossier.imaging_reports?.length || 0})</h4>
          ${dossier.imaging_reports && dossier.imaging_reports.length > 0 ? `
            <div style="display:flex; flex-direction:column; gap:8px;">
              ${dossier.imaging_reports.map(im => `
                <div style="border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px; background:#fff;">
                  <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                      <strong>${escapeHtml(im.modality)} - ${escapeHtml(im.body_part || '全腹/胸部')}</strong>
                      <span style="font-size:0.82rem; color:#64748b; margin-left:8px;">${im.report_date} | ${escapeHtml(im.hospital || '未注医院')}</span>
                    </div>
                    ${im.recist_evaluation ? `<span class="badge badge-blue">RECIST: ${escapeHtml(im.recist_evaluation)}</span>` : ''}
                  </div>
                  ${im.impression ? `<div style="font-size:0.85rem; color:#166534; background:#f0fdf4; padding:6px; border-radius:4px; margin-top:6px;"><strong>结论:</strong> ${escapeHtml(im.impression)}</div>` : ''}
                  ${im.findings ? `<div style="font-size:0.8rem; color:#475569; margin-top:4px;"><strong>征象表现:</strong> ${escapeHtml(im.findings)}</div>` : ''}
                </div>
              `).join('')}
            </div>
          ` : '<p style="color:#94a3b8; font-size:0.85rem; margin:0;">无影像学记录</p>'}
        </div>

        <!-- 7. 病理组织学诊断 -->
        <div style="margin-bottom:14px;">
          <h4 style="margin:0 0 8px 0; color:#0f172a; font-size:0.95rem;">🔬 病理学检测与免疫组化 (${dossier.pathology_reports?.length || 0})</h4>
          ${dossier.pathology_reports && dossier.pathology_reports.length > 0 ? `
            <div style="display:flex; flex-direction:column; gap:8px;">
              ${dossier.pathology_reports.map(p => `
                <div style="border:1px solid #e2e8f0; border-radius:6px; padding:8px 12px; background:#fff;">
                  <div>
                    <strong>${escapeHtml(p.sample_site || '')} ${escapeHtml(p.sample_type || '活检标本')}</strong>
                    <span style="font-size:0.82rem; color:#64748b; margin-left:8px;">${p.report_date} | 分化: ${escapeHtml(p.differentiation || '未详')}</span>
                  </div>
                  <div style="font-size:0.85rem; color:#6b21a8; background:#faf5ff; padding:6px; border-radius:4px; margin-top:6px;">
                    <strong>病理诊断:</strong> ${escapeHtml(p.histological_diagnosis || '无')}
                  </div>
                </div>
              `).join('')}
            </div>
          ` : '<p style="color:#94a3b8; font-size:0.85rem; margin:0;">无病理记录</p>'}
        </div>
      `;
    } catch (err) {
      box.innerHTML = `<div style="color:#ef4444; padding:20px; text-align:center;">调阅档案失败: ${err.message}</div>`;
    }
  },

  closeDossierModal() {
    document.getElementById('modal-admin-dossier').style.display = 'none';
  },

  enterInspectModeFromDossier() {
    if (!this.activeDossier) return;
    const u = this.activeDossier.user;
    const p = this.activeDossier.profile || {};
    this.closeDossierModal();
    this.enterInspectMode(u.id, p.patient_name || u.username, u.username);
  },

  async enterInspectMode(userId, patientName, username) {
    window.inspectTargetUserId = userId;
    const banner = document.getElementById('admin-inspect-banner');
    if (banner) {
      document.getElementById('inspect-patient-name').textContent = patientName || username;
      document.getElementById('inspect-patient-user').textContent = username;
      banner.style.display = 'flex';
    }

    // 自动切换至全病程时间轴选项卡查看该用户的真实生命周期
    await switchTab('timeline');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  },

  async exitInspectMode() {
    window.inspectTargetUserId = null;
    const banner = document.getElementById('admin-inspect-banner');
    if (banner) {
      banner.style.display = 'none';
    }

    // 重新切回管理员选项卡
    await switchTab('admin');
  }
};

window.AdminModule = AdminModule;
window.App = AdminModule;

// ==================== 个人修改密码模块 ====================
function openChangePasswordModal() {
  const elOld = document.getElementById('chg-old-pwd');
  const elNew = document.getElementById('chg-new-pwd');
  const elConfirm = document.getElementById('chg-confirm-pwd');
  const elTip = document.getElementById('chg-pwd-tip');

  if (elOld) elOld.value = '';
  if (elNew) elNew.value = '';
  if (elConfirm) elConfirm.value = '';
  if (elTip) elTip.textContent = '';

  const modal = document.getElementById('modal-change-password');
  if (modal) modal.style.display = 'flex';
}

function closeChangePasswordModal() {
  const modal = document.getElementById('modal-change-password');
  if (modal) modal.style.display = 'none';
}

async function submitChangePassword() {
  const oldPwd = document.getElementById('chg-old-pwd').value.trim();
  const newPwd = document.getElementById('chg-new-pwd').value.trim();
  const confirmPwd = document.getElementById('chg-confirm-pwd').value.trim();
  const tip = document.getElementById('chg-pwd-tip');

  if (!oldPwd) {
    tip.textContent = '请输入当前原密码';
    return;
  }
  if (!newPwd || newPwd.length < 4) {
    tip.textContent = '新密码长度不能少于4位字符';
    return;
  }
  if (newPwd !== confirmPwd) {
    tip.textContent = '两次输入的新密码不一致';
    return;
  }

  tip.textContent = '正在修改...';
  try {
    const res = await API.changePassword(oldPwd, newPwd);
    alert(res.message || '密码修改成功！');
    closeChangePasswordModal();
  } catch (err) {
    tip.textContent = err.message;
  }
}

window.openChangePasswordModal = openChangePasswordModal;
window.closeChangePasswordModal = closeChangePasswordModal;
window.submitChangePassword = submitChangePassword;

