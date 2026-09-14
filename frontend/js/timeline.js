/**
 * MedTrack 肿瘤全病程全景时间轴渲染引擎
 */

const TimelineModule = {
  events: [],
  currentFilter: 'all',

  async load(containerId = 'timeline-container') {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
      container.innerHTML = '<div style="text-align:center; padding:30px; color:#64748b;">正在加载全病程事件脉络...</div>';
      const targetUserId = window.inspectTargetUserId || null;
      this.events = await API.getTimeline(targetUserId);
      this.render(containerId);
    } catch (err) {
      container.innerHTML = `<div style="text-align:center; padding:30px; color:#ef4444;">加载失败: ${err.message}</div>`;
    }
  },

  setFilter(filterType, containerId = 'timeline-container') {
    this.currentFilter = filterType;
    this.render(containerId);
  },

  render(containerId = 'timeline-container') {
    const container = document.getElementById(containerId);
    if (!container) return;

    let filtered = this.events;
    if (this.currentFilter === 'treatment') {
      filtered = this.events.filter(e => ['surgery', 'radio', 'therapy'].includes(e.event_type));
    } else if (this.currentFilter === 'imaging') {
      filtered = this.events.filter(e => e.event_type === 'imaging');
    } else if (this.currentFilter === 'lab') {
      filtered = this.events.filter(e => e.event_type === 'lab');
    } else if (this.currentFilter === 'pathology') {
      filtered = this.events.filter(e => e.event_type === 'pathology');
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div style="text-align:center; padding:40px 20px; background:#f8fafc; border-radius:12px; border:1px dashed #cbd5e1;">
          <div style="font-size:36px; margin-bottom:10px;">🩺</div>
          <p style="font-weight:600; color:#475569; margin-bottom:6px;">暂无该类别的病程事件记录</p>
          <p style="font-size:0.88rem; color:#94a3b8;">您可以点击上方“单据识别”上传化验单/出院单，或在“治疗记录”中手动添加手术与用药记录。</p>
        </div>
      `;
      return;
    }

    const typeConfig = {
      surgery: { dotClass: 'dot-surgery', badgeClass: 'badge-red', icon: '🔪' },
      radio: { dotClass: 'dot-radio', badgeClass: 'badge-orange', icon: '⚡' },
      therapy: { dotClass: 'dot-therapy', badgeClass: 'badge-blue', icon: '💊' },
      imaging: { dotClass: 'dot-imaging', badgeClass: 'badge-green', icon: '🩻' },
      lab: { dotClass: 'dot-lab', badgeClass: 'badge-blue', icon: '🧪' },
      pathology: { dotClass: 'dot-pathology', badgeClass: 'badge-purple', icon: '🔬' },
      visit: { dotClass: 'dot-visit', badgeClass: 'badge-green', icon: '📋' }
    };

    let html = '<div class="timeline">';
    filtered.forEach(item => {
      const cfg = typeConfig[item.event_type] || { dotClass: 'dot-therapy', badgeClass: 'badge-blue', icon: '📌' };
      
      let extraHtml = '';
      if (item.details) {
        if (item.details.abnormal_codes && item.details.abnormal_codes.length > 0) {
          extraHtml += `<div style="margin-top:6px; font-size:0.82rem; color:#ef4444;">
            异常指标提示: <strong>${item.details.abnormal_codes.join(', ')}</strong>
          </div>`;
        }
        if (item.details.recist) {
          extraHtml += `<div style="margin-top:4px; font-size:0.84rem; color:#0d9488;">
            RECIST疗效: <strong>${item.details.recist}</strong>
          </div>`;
        }
      }

      html += `
        <div class="timeline-item">
          <div class="timeline-dot ${cfg.dotClass}"></div>
          <div class="timeline-content">
            <div class="timeline-header">
              <div>
                <span style="margin-right:6px;">${cfg.icon}</span>
                <span class="badge ${cfg.badgeClass}" style="margin-right:8px;">${item.category_label}</span>
                <strong style="font-size:1rem; color:#1e293b;">${escapeHtml(item.title)}</strong>
              </div>
              <div style="font-size:0.85rem; color:#64748b; font-weight:500;">
                📅 ${item.event_date}
              </div>
            </div>
            
            <p style="color:#475569; font-size:0.9rem; margin-top:6px;">
              ${escapeHtml(item.summary)}
            </p>
            
            ${extraHtml}

            </div>
        </div>
      `;
    });
    html += '</div>';

    container.innerHTML = html;
  }
};

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

window.TimelineModule = TimelineModule;
