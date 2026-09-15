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
      window.loadedDocsMap = window.loadedDocsMap || {};
      this.events.forEach(e => {
        window.loadedDocsMap[e.id] = e;
      });
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
              <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <span style="margin-right:2px;">${cfg.icon}</span>
                <span class="badge ${cfg.badgeClass}">${item.category_label}</span>
                <strong class="doc-detail-trigger" role="button" tabindex="0"
                        style="font-size:1rem; color:#1e293b; cursor:pointer;"
                        onclick="handleDocDetailClick(event, '${item.id}')"
                        onmouseenter="handleDocDetailMouseEnter(event, '${item.id}')" 
                        onmouseleave="handleDocDetailMouseLeave(event)"
                        title="点击或悬停查看详细数据">${escapeHtml(item.title)}</strong>
              </div>
              <div style="display:flex; align-items:center; gap:8px; flex-shrink:0;">
                <button type="button" class="btn btn-secondary btn-sm doc-detail-trigger" 
                        style="padding:2px 8px; font-size:0.78rem; color:#0284c7; border-color:#bae6fd; background:#f0f9ff; cursor:pointer; display:inline-flex; align-items:center; gap:3px; border-radius:4px; line-height:1.4;"
                        onclick="handleDocDetailClick(event, '${item.id}')"
                        onmouseenter="handleDocDetailMouseEnter(event, '${item.id}')" 
                        onmouseleave="handleDocDetailMouseLeave(event)"
                        title="点击或悬停查看详细数据">📋 详情</button>
                <span style="font-size:0.85rem; color:#64748b; font-weight:500; white-space:nowrap;">
                  📅 ${item.event_date}
                </span>
              </div>
            </div>
            
            <p style="color:#475569; font-size:0.9rem; margin-top:6px; line-height:1.5;">
              ${formatSummaryWithHighlights(item.summary)}
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

// 异常摘要标红高亮与结构化展示辅助函数 (客观陈述 + 异常指标单列 + 建议单列)
function formatSummaryWithHighlights(text) {
  if (!text) return '';
  let safe = escapeHtml(text).trim();

  // 1. 提取并分离建议部分 (如果存在)
  let suggestion = null;
  const sugRegex = /(?:【建议】|【就医与随访建议】|【医学建议】|建议[:：]|医学建议[:：])\s*([\s\S]+)$/;
  const sugMatch = safe.match(sugRegex);
  if (sugMatch) {
    suggestion = sugMatch[1].trim();
    safe = safe.slice(0, sugMatch.index).trim();
    safe = safe.replace(/[；;。，, ]+$/, '');
  }

  // 2. 识别并提取异常指标部分 (单列成独立红色提醒卡片)
  let abnormal = null;
  const abnormalKw = /(↑|↓|偏高|偏低|轻度偏高|明显偏高|异常|阳性|强阳性|弱阳性|突变|超出参考|转移|进展|恶性)/;
  const normalExclusions = /^(?:无|未见异常|正常参考|正常范围|阴性\(-?\)|未见异常指标|各项均在正常范围|未见特殊异常)[。；;\s]*$/;

  const abnRegex = /(?:【异常指标】|【异常指标提示】|【关注】|【关注指标】|异常指标[:：]|异常指标提示[:：]|关注[:：]|关注指标[:：])\s*([\s\S]+)$/;
  const abnMatch = safe.match(abnRegex);

  if (abnMatch && abnormalKw.test(abnMatch[1]) && !normalExclusions.test(abnMatch[1].trim())) {
    abnormal = abnMatch[1].trim();
    safe = safe.slice(0, abnMatch.index).trim().replace(/[；;。，, ]+$/, '');

    // 如果异常指标后面跟着“；其余指标均在正常参考范围内”，将该句移回客观陈述
    const trailingNormal = abnormal.match(/[；;。，, ]+((?:其余|各项|其他)[\s\S]*?均在正常[\s\S]*)$/);
    if (trailingNormal) {
      const normalTail = trailingNormal[1].trim();
      abnormal = abnormal.slice(0, trailingNormal.index).trim().replace(/[；;。，, ]+$/, '');
      safe = safe ? (safe + '；' + normalTail) : normalTail;
    }
  } else if (!abnMatch) {
    // 兼容没有明确前缀的历史/自由文本
    if (abnormalKw.test(safe)) {
      const sentences = safe.split(/(?<=[。；;])\s*/);
      const normalParts = [];
      const abnormalParts = [];
      const normalPhrase = /(均在正常|未见异常|正常参考|正常范围|阴性\(-?\))/;
      for (const s of sentences) {
        if (abnormalKw.test(s) && !normalPhrase.test(s)) {
          abnormalParts.push(s.trim());
        } else if (s.trim()) {
          normalParts.push(s.trim());
        }
      }
      if (abnormalParts.length > 0) {
        abnormal = abnormalParts.join(' ');
        safe = normalParts.join(' ');
      }
    }
  }

  // 3. 清理客观总结陈述标题与前缀
  safe = safe.replace(/^【客观总结(?:陈述)?】[:：]?\s*/g, '');
  safe = safe.replace(/【客观总结(?:陈述)?】[:：]?/g, '');
  safe = safe.replace(/^客观总结(?:陈述)?[:：]\s*/g, '');
  safe = safe.trim();

  // 4. 组装展示 HTML (客观总结陈述 + 关注单列 + 建议单列)
  let result = '';
  if (safe) {
    result += `<div style="color:#334155; line-height:1.6;">${safe}</div>`;
  }
  if (abnormal) {
    result += `<div style="margin-top:6px; font-size:0.86rem; color:#991b1b; background:#fef2f2; padding:4px 10px; border-radius:4px; border-left:3px solid #ef4444; border-top:1px solid #fee2e2; border-right:1px solid #fee2e2; border-bottom:1px solid #fee2e2; line-height:1.5;"><strong>⚠️ 关注:</strong> ${abnormal}</div>`;
  }
  if (suggestion) {
    result += `<div style="margin-top:6px; font-size:0.86rem; color:#0369a1; background:#f0f9ff; padding:4px 10px; border-radius:4px; border-left:3px solid #0284c7; border-top:1px solid #e0f2fe; border-right:1px solid #e0f2fe; border-bottom:1px solid #e0f2fe; line-height:1.5;"><strong>💡 建议:</strong> ${suggestion}</div>`;
  }

  return result || `<div>${safe}</div>`;
}

window.escapeHtml = escapeHtml;
window.formatSummaryWithHighlights = formatSummaryWithHighlights;
window.TimelineModule = TimelineModule;
