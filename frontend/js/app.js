/**
 * MedTrack-Onco 核心应用交互逻辑
 */

let currentProfile = {};

document.addEventListener('DOMContentLoaded', async () => {
  initAuthUI();
  if (API.getToken()) {
    await initApp();
  }
});

// ==================== 用户鉴权与初始化 ====================
function initAuthUI() {
  const token = API.getToken();
  const user = API.getUser();

  const userBar = document.getElementById('user-bar');
  const authModal = document.getElementById('auth-modal');
  const mainApp = document.getElementById('main-app');

  if (!token) {
    if (authModal) authModal.style.display = 'flex';
    if (mainApp) mainApp.style.display = 'none';
  } else {
    if (authModal) authModal.style.display = 'none';
    if (mainApp) mainApp.style.display = 'block';
    if (userBar) {
      userBar.innerHTML = `
        <span style="font-size:0.9rem; color:#475569;">👤 <strong>${user.username || '患者'}</strong></span>
        <button class="btn btn-secondary btn-sm" onclick="openProfileModal()">档案设置</button>
        <button class="btn btn-danger btn-sm" onclick="logout()">退出</button>
      `;
    }
  }
}

async function initApp() {
  try {
    const res = await API.getMe();
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

// ==================== 顶部档案面板渲染 ====================
function renderProfileHeader() {
  const box = document.getElementById('profile-summary-bar');
  if (!box) return;

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
        <h2 style="font-size:1.25rem; font-weight:700; color:#0f172a; display:flex; align-items:center; gap:8px;">
          <span>${currentProfile.patient_name || '未命名患者'}</span>
          <span class="badge badge-purple">${currentProfile.primary_site || '原发部位未注'}</span>
          <span class="badge badge-blue">${currentProfile.pathology_type || '病理未录'}</span>
          <span class="badge badge-green">${currentProfile.current_staging || '维持治疗/随访'}</span>
        </h2>
        <div style="font-size:0.88rem; color:#475569; margin-top:6px; display:flex; flex-wrap:wrap; gap:16px;">
          <span>初诊分期: <strong>${currentProfile.initial_staging || '未详'}</strong></span>
          <span>确诊时间: <strong>${currentProfile.initial_diagnosis_date || '未详'}</strong></span>
          <span>分子突变/靶点: <strong style="color:#0284c7;">${markerList}</strong></span>
          <span>合并慢病: <strong style="color:#d97706;">${comorbText}</strong></span>
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
  } else if (tabId === 'charts') {
    await ChartsModule.initAll();
  } else if (tabId === 'treatments') {
    await loadTreatmentsList();
  } else if (tabId === 'report') {
    await loadConsultationReport();
  }
}

// ==================== AI 单据识别与自动提取 ====================
let lastParsedDoc = null;

async function onFileSelected(event) {
  const file = event.target.files[0];
  if (!file) return;

  const docType = document.getElementById('upload-doc-type').value;
  const statusBox = document.getElementById('upload-status');
  const previewBox = document.getElementById('upload-preview');

  statusBox.style.display = 'block';
  statusBox.innerHTML = `
    <div style="display:flex; align-items:center; justify-content:center; gap:10px; color:#0284c7; padding:12px;">
      <div style="width:20px; height:20px; border:3px solid #e0f2fe; border-top-color:#0284c7; border-radius:50%; animation:spin 1s linear infinite;"></div>
      <span>多模态视觉 AI 正在精准解析单据（指标、参考范围、异常状态提取中...）</span>
    </div>
    <style>@keyframes spin { 0% { transform:rotate(0deg); } 100% { transform:rotate(360deg); } }</style>
  `;
  previewBox.style.display = 'none';

  try {
    const res = await API.uploadAndParseDoc(file, docType);
    lastParsedDoc = res;
    statusBox.style.display = 'none';
    renderParsedPreview(res);
  } catch (err) {
    statusBox.innerHTML = `<div style="color:#ef4444; padding:10px;">❌ 解析失败: ${err.message}</div>`;
  }
}

function renderParsedPreview(res) {
  const box = document.getElementById('upload-preview');
  box.style.display = 'block';

  const docType = res.doc_type;
  const data = res.parsed_data || {};

  let contentHtml = '';

  if (docType === 'lab') {
    const items = data.items || [];
    let rows = items.map(it => {
      let statusBadge = `<span class="badge badge-green">正常</span>`;
      if (it.status === 'HIGH') statusBadge = `<span class="badge badge-red">偏高 ↑</span>`;
      if (it.status === 'LOW') statusBadge = `<span class="badge badge-orange">偏低 ↓</span>`;
      return `
        <tr>
          <td><strong>${escapeHtml(it.item_name)}</strong></td>
          <td><code>${escapeHtml(it.item_code)}</code></td>
          <td><strong>${it.value !== null ? it.value : it.value_text}</strong></td>
          <td>${escapeHtml(it.unit)}</td>
          <td>${escapeHtml(it.ref_range)}</td>
          <td>${statusBadge}</td>
        </tr>
      `;
    }).join('');

    contentHtml = `
      <div style="margin-bottom:12px; font-size:0.92rem;">
        <span>化验单类型: <strong>${escapeHtml(data.report_type)}</strong></span> | 
        <span>采样日期: <strong>${escapeHtml(data.report_date)}</strong></span> | 
        <span>医院: <strong>${escapeHtml(data.hospital || '未注')}</strong></span>
      </div>
      <div style="background:#eff6ff; padding:10px; border-radius:8px; margin-bottom:12px; font-size:0.88rem; color:#1e40af;">
        💡 <strong>AI 总结:</strong> ${escapeHtml(data.ai_summary || '未检测到重大异常')}
      </div>
      <div class="table-responsive">
        <table class="med-table">
          <thead>
            <tr><th>项目名称</th><th>代码</th><th>测定值</th><th>单位</th><th>参考区间</th><th>状态</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
  } else if (docType === 'imaging') {
    contentHtml = `
      <div style="font-size:0.92rem; margin-bottom:10px;">
        <span>类别: <strong>${escapeHtml(data.modality)}</strong></span> | 
        <span>部位: <strong>${escapeHtml(data.body_part)}</strong></span> | 
        <span>日期: <strong>${escapeHtml(data.report_date)}</strong></span> | 
        <span>疗效: <span class="badge badge-blue">${escapeHtml(data.recist_evaluation || '未注')}</span></span>
      </div>
      <div style="margin-bottom:10px;">
        <h4 style="font-size:0.9rem; color:#334155; margin-bottom:4px;">检查所见:</h4>
        <div style="background:#f8fafc; padding:10px; border-radius:6px; font-size:0.88rem;">${escapeHtml(data.findings)}</div>
      </div>
      <div>
        <h4 style="font-size:0.9rem; color:#334155; margin-bottom:4px;">诊断结论:</h4>
        <div style="background:#f0fdf4; border:1px solid #bbf7d0; padding:10px; border-radius:6px; font-size:0.88rem; color:#166534; font-weight:600;">${escapeHtml(data.impression)}</div>
      </div>
    `;
  } else if (docType === 'pathology') {
    const genes = Object.entries(data.genetic_testing || {}).map(([k, v]) => `<li>${k}: <strong>${v}</strong></li>`).join('');
    contentHtml = `
      <div style="font-size:0.92rem; margin-bottom:10px;">
        <span>标本类型: <strong>${escapeHtml(data.sample_type)}</strong></span> | 
        <span>部位: <strong>${escapeHtml(data.sample_site)}</strong></span> | 
        <span>分化程度: <strong>${escapeHtml(data.differentiation)}</strong></span>
      </div>
      <div style="background:#fdf4ff; border:1px solid #f5d0fe; padding:10px; border-radius:6px; margin-bottom:10px; color:#86198f;">
        <strong>病理诊断:</strong> ${escapeHtml(data.histological_diagnosis)}
      </div>
      <div style="font-size:0.88rem;">
        <strong>驱动基因/分子靶点:</strong>
        <ul style="margin-left:20px; margin-top:4px;">${genes || '<li>未进行基因突变检测</li>'}</ul>
      </div>
    `;
  } else {
    contentHtml = `
      <pre style="background:#f8fafc; padding:12px; border-radius:8px; font-size:0.85rem; overflow-x:auto;">${JSON.stringify(data, null, 2)}</pre>
    `;
  }

  box.innerHTML = `
    <div class="card" style="border:1px solid #0284c7; background:#ffffff;">
      <div class="card-title" style="color:#0284c7;">
        <span>📋 AI 结构化识别预览结果</span>
        <button class="btn btn-primary" onclick="confirmSaveParsedDoc()">💾 确认无误，存入病历档案</button>
      </div>
      ${contentHtml}
    </div>
  `;
}

async function confirmSaveParsedDoc() {
  if (!lastParsedDoc) return;
  const docType = lastParsedDoc.doc_type;
  const data = lastParsedDoc.parsed_data;

  try {
    if (docType === 'lab') {
      await API.createLabReport({
        report_type: data.report_type || '化验单',
        report_date: data.report_date || new Date().toISOString().slice(0, 10),
        hospital: data.hospital || '',
        raw_file_url: lastParsedDoc.raw_file_url,
        ai_summary: data.ai_summary || '',
        items: data.items || []
      });
    } else if (docType === 'imaging') {
      await API.createImagingReport({
        modality: data.modality || 'CT',
        body_part: data.body_part || '',
        report_date: data.report_date || new Date().toISOString().slice(0, 10),
        hospital: data.hospital || '',
        target_lesions: JSON.stringify(data.target_lesions || []),
        recist_evaluation: data.recist_evaluation || '',
        findings: data.findings || '',
        impression: data.impression || '',
        raw_file_url: lastParsedDoc.raw_file_url
      });
    } else if (docType === 'pathology') {
      await API.createPathology({
        sample_type: data.sample_type || '',
        sample_site: data.sample_site || '',
        report_date: data.report_date || new Date().toISOString().slice(0, 10),
        hospital: data.hospital || '',
        histological_diagnosis: data.histological_diagnosis || '',
        differentiation: data.differentiation || '',
        ihc_markers: JSON.stringify(data.ihc_markers || {}),
        genetic_testing: JSON.stringify(data.genetic_testing || {}),
        raw_file_url: lastParsedDoc.raw_file_url
      });
    } else {
      // 出院小结自动同步
      if (data.therapy_info) {
        await API.createTherapy({
          treatment_line: data.therapy_info.treatment_line || '治疗',
          therapy_type: data.therapy_info.therapy_type || '靶向/化疗',
          regimen_name: data.therapy_info.regimen_name || '抗肿瘤方案',
          cycle_number: data.therapy_info.cycle_number || 1,
          start_date: data.record_date || new Date().toISOString().slice(0, 10),
          drugs_detail: data.therapy_info.drugs_detail || '',
          adverse_events: data.therapy_info.adverse_events || ''
        });
      }
    }

    alert('🎉 成功存入您的病历档案！时间轴与图表已自动更新。');
    document.getElementById('upload-preview').style.display = 'none';
    await switchTab('timeline');
  } catch (err) {
    alert(`保存失败: ${err.message}`);
  }
}

// ==================== 专科治疗管理 (手术/放疗/系统药物) ====================
async function loadTreatmentsList() {
  const container = document.getElementById('treatments-list-container');
  if (!container) return;

  try {
    const [surgeries, radios, therapies] = await Promise.all([
      API.getSurgeries(),
      API.getRadiotherapies(),
      API.getTherapies()
    ]);

    let surgHtml = surgeries.map(s => `
      <div class="card" style="margin-bottom:12px; padding:14px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <strong>${escapeHtml(s.surgery_name)}</strong>
            <span class="badge badge-red" style="margin-left:8px;">切缘: ${escapeHtml(s.margins)}</span>
            <div style="font-size:0.85rem; color:#64748b; margin-top:4px;">
              日期: ${s.surgery_date} | 医院: ${escapeHtml(s.hospital || '未注')} | 淋巴结清扫: ${escapeHtml(s.lymph_nodes || '未详')}
            </div>
            ${s.pathology_summary ? `<div style="font-size:0.85rem; color:#334155; margin-top:4px;">病理摘要: ${escapeHtml(s.pathology_summary)}</div>` : ''}
          </div>
          <button class="btn btn-danger btn-sm" onclick="deleteSurgeryItem(${s.id})">删除</button>
        </div>
      </div>
    `).join('') || '<p style="color:#94a3b8; font-size:0.9rem;">暂无手术记录</p>';

    let radioHtml = radios.map(r => `
      <div class="card" style="margin-bottom:12px; padding:14px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <strong>放疗靶区: ${escapeHtml(r.site)}</strong>
            <span class="badge badge-orange" style="margin-left:8px;">${escapeHtml(r.total_dose)} / ${escapeHtml(r.fractions)}</span>
            <div style="font-size:0.85rem; color:#64748b; margin-top:4px;">
              技术: ${escapeHtml(r.technique || '标准')} | 周期: ${r.start_date} ~ ${r.end_date || '进行中'}
            </div>
            ${r.toxicity_notes ? `<div style="font-size:0.85rem; color:#d97706; margin-top:4px;">反应: ${escapeHtml(r.toxicity_notes)}</div>` : ''}
          </div>
          <button class="btn btn-danger btn-sm" onclick="deleteRadioItem(${r.id})">删除</button>
        </div>
      </div>
    `).join('') || '<p style="color:#94a3b8; font-size:0.9rem;">暂无放疗记录</p>';

    let therapyHtml = therapies.map(t => `
      <div class="card" style="margin-bottom:12px; padding:14px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <div>
            <span class="badge badge-blue">${escapeHtml(t.treatment_line)}</span>
            <strong style="margin-left:6px;">${escapeHtml(t.regimen_name)} (第 ${t.cycle_number} 周期)</strong>
            <div style="font-size:0.85rem; color:#64748b; margin-top:4px;">
              类别: ${escapeHtml(t.therapy_type)} | 周期: ${t.start_date} ~ ${t.end_date || '维持用药中'}
            </div>
            ${t.adverse_events ? `<div style="font-size:0.85rem; color:#dc2626; margin-top:4px;">毒副反应: ${escapeHtml(t.adverse_events)}</div>` : ''}
          </div>
          <button class="btn btn-danger btn-sm" onclick="deleteTherapyItem(${t.id})">删除</button>
        </div>
      </div>
    `).join('') || '<p style="color:#94a3b8; font-size:0.9rem;">暂无系统用药记录</p>';

    container.innerHTML = `
      <div class="grid-3">
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="font-size:1.05rem; font-weight:700;">🔪 外科手术记录</h3>
            <button class="btn btn-primary btn-sm" onclick="openAddSurgeryModal()">+ 新增手术</button>
          </div>
          ${surgHtml}
        </div>
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="font-size:1.05rem; font-weight:700;">⚡ 放射治疗记录</h3>
            <button class="btn btn-primary btn-sm" onclick="openAddRadioModal()">+ 新增放疗</button>
          </div>
          ${radioHtml}
        </div>
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="font-size:1.05rem; font-weight:700;">💊 化疗/靶向/免疫周期</h3>
            <button class="btn btn-primary btn-sm" onclick="openAddTherapyModal()">+ 登记周期</button>
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
  await API.deleteSurgery(id);
  await loadTreatmentsList();
}
async function deleteRadioItem(id) {
  if (!confirm('确认删除该放疗记录？')) return;
  await API.deleteRadiotherapy(id);
  await loadTreatmentsList();
}
async function deleteTherapyItem(id) {
  if (!confirm('确认删除该治疗周期记录？')) return;
  await API.deleteTherapy(id);
  await loadTreatmentsList();
}

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
      <h2 style="font-size:1.3rem; font-weight:700;">📑 肿瘤专科门诊 / MDT 会诊结构化摘要</h2>
      <div style="display:flex; gap:8px;">
        <button class="btn btn-primary" onclick="window.print()">🖨️ 打印 / 导出 PDF</button>
        <button class="btn btn-success" onclick="openCreateShareModal()">🔗 生成 7 天加密分享链接</button>
      </div>
    </div>

    <div class="card" style="border-top:4px solid var(--primary); padding:24px;">
      <div style="border-bottom:1px solid #e2e8f0; padding-bottom:14px; margin-bottom:16px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <h1 style="font-size:1.4rem; font-weight:800; color:#0f172a;">${escapeHtml(p.name)} - 肿瘤病程完整汇报单</h1>
          <span style="font-size:0.85rem; color:#64748b;">报告生成时间: ${rep.generated_at}</span>
        </div>
        <div style="font-size:0.92rem; color:#334155; margin-top:8px; display:flex; flex-wrap:wrap; gap:16px;">
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
    </div>
  `;
}

// 模态弹窗控制辅助函数
function openProfileModal() {
  const m = document.getElementById('profile-modal');
  if (!m) return;
  m.style.display = 'flex';
  document.getElementById('prof-name').value = currentProfile.patient_name || '';
  document.getElementById('prof-site').value = currentProfile.primary_site || '';
  document.getElementById('prof-type').value = currentProfile.pathology_type || '';
  document.getElementById('prof-date').value = currentProfile.initial_diagnosis_date || '';
  document.getElementById('prof-staging').value = currentProfile.initial_staging || '';
  document.getElementById('prof-cur-staging').value = currentProfile.current_staging || '';
  document.getElementById('prof-markers').value = currentProfile.molecular_markers || '{}';
  document.getElementById('prof-comorbidities').value = currentProfile.chronic_comorbidities || '[]';
}
function closeProfileModal() {
  document.getElementById('profile-modal').style.display = 'none';
}
async function saveProfile() {
  const updated = {
    patient_name: document.getElementById('prof-name').value.trim(),
    primary_site: document.getElementById('prof-site').value.trim(),
    pathology_type: document.getElementById('prof-type').value.trim(),
    initial_diagnosis_date: document.getElementById('prof-date').value.trim(),
    initial_staging: document.getElementById('prof-staging').value.trim(),
    current_staging: document.getElementById('prof-cur-staging').value.trim(),
    molecular_markers: document.getElementById('prof-markers').value.trim(),
    chronic_comorbidities: document.getElementById('prof-comorbidities').value.trim()
  };
  try {
    currentProfile = await API.updateProfile(updated);
    renderProfileHeader();
    closeProfileModal();
    alert('档案信息已更新！');
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

// 新增手术/放疗/化疗弹窗
function openAddSurgeryModal() { document.getElementById('surgery-modal').style.display = 'flex'; }
function closeAddSurgeryModal() { document.getElementById('surgery-modal').style.display = 'none'; }
async function submitAddSurgery() {
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
  await API.createSurgery(data);
  closeAddSurgeryModal();
  await loadTreatmentsList();
}

function openAddRadioModal() { document.getElementById('radio-modal').style.display = 'flex'; }
function closeAddRadioModal() { document.getElementById('radio-modal').style.display = 'none'; }
async function submitAddRadio() {
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
  await API.createRadiotherapy(data);
  closeAddRadioModal();
  await loadTreatmentsList();
}

function openAddTherapyModal() { document.getElementById('therapy-modal').style.display = 'flex'; }
function closeAddTherapyModal() { document.getElementById('therapy-modal').style.display = 'none'; }
async function submitAddTherapy() {
  const data = {
    regimen_name: document.getElementById('ther-regimen').value.trim(),
    treatment_line: document.getElementById('ther-line').value,
    therapy_type: document.getElementById('ther-type').value,
    cycle_number: parseInt(document.getElementById('ther-cycle').value) || 1,
    start_date: document.getElementById('ther-start').value.trim(),
    end_date: document.getElementById('ther-end').value.trim(),
    drugs_detail: document.getElementById('ther-drugs').value.trim(),
    adverse_events: document.getElementById('ther-adverse').value.trim()
  };
  if (!data.regimen_name || !data.start_date) {
    alert('请填写方案名称和开始日期');
    return;
  }
  await API.createTherapy(data);
  closeAddTherapyModal();
  await loadTreatmentsList();
}
