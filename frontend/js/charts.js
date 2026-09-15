/**
 * MedTrack ECharts 现代化全景指标看板
 * 包含：全局健康态势总览、重点指标快照卡片(Sparkline)、智能筛选与搜索、
 * 深度聚焦与自由对比工作台(安全带 MarkArea + 智能双 Y 轴)、时间跨度快选与移动端适配。
 */

const ChartsModule = {
  tumorChartInstance: null,
  safetyChartInstance: null,
  chronicChartInstance: null,
  focusChartInstance: null,
  availableMetrics: [],
  overviewData: null,
  resizeListenerBound: false,

  // 交互状态
  currentCategoryFilter: 'all', // 'all' | 'abnormal' | 'tumor_marker' | 'safety_toxicity' | 'chronic' | 'other'
  currentSearchQuery: '',
  currentTimeRange: 'all',      // 'all' | '1y' | '6m' | '3m'
  focusedMetrics: [],           // 正在工作台聚焦对比的指标：[{ code, name }]

  // 缓存各图表的日期数组，供快捷时间范围切换使用
  chartDatesMap: {
    focus: [],
    tumor: [],
    safety: [],
    chronic: []
  },

  async refresh() {
    if (this.tumorChartInstance) { this.tumorChartInstance.dispose(); this.tumorChartInstance = null; }
    if (this.safetyChartInstance) { this.safetyChartInstance.dispose(); this.safetyChartInstance = null; }
    if (this.chronicChartInstance) { this.chronicChartInstance.dispose(); this.chronicChartInstance = null; }
    if (this.focusChartInstance) { this.focusChartInstance.dispose(); this.focusChartInstance = null; }
    await this.initAll();
  },

  async initAll() {
    const targetUserId = window.inspectTargetUserId || null;

    // 1. 并行加载概览数据与可用指标
    try {
      const [overview, metrics] = await Promise.all([
        API.getChartOverview(targetUserId).catch(e => {
          console.warn('Failed to load chart overview:', e);
          return null;
        }),
        API.getAvailableMetrics(targetUserId).catch(e => {
          console.warn('Failed to load available metrics:', e);
          return [];
        })
      ]);
      this.overviewData = overview;
      this.availableMetrics = metrics || [];
    } catch (e) {
      console.warn('Init charts error:', e);
      this.overviewData = null;
      this.availableMetrics = [];
    }

    // 2. 渲染顶部健康态势概览条与重点 KPI 卡片
    this.renderExecutiveSummary();

    // 3. 统计并渲染分类过滤角标与药丸清单
    this.updateFilterCounts();
    this.renderPillsBar();

    // 4. 智能推导适合三大分类图表的指标集合
    const tumorDefaults = ['CEA', 'CA199', 'CA125', 'AFP', 'CA153', 'CYFRA21-1', 'NSE'];
    const safetyDefaults = ['WBC', 'PLT', 'NEUT#', 'HGB', 'ALT', 'AST', 'CR'];
    const chronicDefaults = ['GLU', 'HbA1c', 'UA', 'TBIL', 'ALB'];

    let userTumorCodes = (this.availableMetrics || [])
      .filter(m => m.category === 'tumor_marker' || tumorDefaults.includes(m.code.toUpperCase()))
      .map(m => m.code);
    if (userTumorCodes.length === 0) userTumorCodes = ['CEA', 'CA199', 'CA125'];

    let userSafetyCodes = (this.availableMetrics || [])
      .filter(m => m.category === 'safety_toxicity' || safetyDefaults.includes(m.code.toUpperCase()))
      .map(m => m.code);
    if (userSafetyCodes.length === 0) userSafetyCodes = ['WBC', 'PLT', 'ALT', 'CR'];

    let userChronicCodes = (this.availableMetrics || [])
      .filter(m => m.category === 'chronic' || chronicDefaults.includes(m.code.toUpperCase()))
      .map(m => m.code);
    if (userChronicCodes.length === 0) userChronicCodes = ['GLU', 'HbA1c'];

    await Promise.all([
      this.renderTumorMarkers(userTumorCodes, targetUserId),
      this.renderSafetyMarkers(userSafetyCodes, targetUserId),
      this.renderChronicMarkers(userChronicCodes, targetUserId)
    ]);

    // 5. 绑定窗口缩放自适应
    if (!this.resizeListenerBound) {
      window.addEventListener('resize', () => {
        if (this.tumorChartInstance) this.tumorChartInstance.resize();
        if (this.safetyChartInstance) this.safetyChartInstance.resize();
        if (this.chronicChartInstance) this.chronicChartInstance.resize();
        if (this.focusChartInstance) this.focusChartInstance.resize();
      });
      this.resizeListenerBound = true;
    }
  },

  /* ==================== 1. 顶部全局健康态势与 Sparkline 快照 ==================== */
  renderExecutiveSummary() {
    const dateBadge = document.getElementById('charts-latest-date-badge');
    const statTotal = document.getElementById('charts-stat-total');
    const statNormal = document.getElementById('charts-stat-normal');
    const statAbnormal = document.getElementById('charts-stat-abnormal');
    const kpiContainer = document.getElementById('charts-kpi-container');

    if (!kpiContainer) return;

    const ov = this.overviewData;
    if (!ov || !ov.has_data) {
      if (dateBadge) dateBadge.textContent = '📅 最近采样: 暂无检验记录';
      if (statTotal) statTotal.textContent = '检测 0 项';
      if (statNormal) statNormal.textContent = '正常 0 项';
      if (statAbnormal) statAbnormal.textContent = '⚠️ 关注 0 项';
      kpiContainer.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 18px; text-align:center; color:#94a3b8; font-size:0.88rem; background:#f8fafc; border-radius:8px; border:1px dashed #cbd5e1;">
          💡 暂无历史化验单指标数据。请前往【单据识别】上传化验单，系统将自动汇聚关键时序趋势。
        </div>
      `;
      return;
    }

    // 态势数字
    if (dateBadge) dateBadge.textContent = `📅 最近采样: ${ov.latest_date}`;
    if (statTotal) statTotal.textContent = `检测 ${ov.latest_stats.total_items} 项`;
    if (statNormal) statNormal.textContent = `正常 ${ov.latest_stats.normal_count} 项`;
    if (statAbnormal) {
      statAbnormal.textContent = `⚠️ 关注 ${ov.latest_stats.abnormal_count} 项`;
      statAbnormal.className = ov.latest_stats.abnormal_count > 0 ? 'badge badge-red' : 'badge badge-gray';
    }

    // KPI 快照卡片
    const cards = ov.kpi_cards || [];
    if (cards.length === 0) {
      kpiContainer.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 12px; text-align:center; color:#94a3b8; font-size:0.85rem;">
          已录入检验单，暂未提取到核心 KPI 指标
        </div>
      `;
      return;
    }

    const cardsHtml = cards.map(c => {
      const isAbn = c.status !== 'NORMAL';
      const statusClass = c.status === 'HIGH' ? 'status-high' : (c.status === 'LOW' ? 'status-low' : 'status-normal');
      let statusBadge = '<span class="badge badge-green" style="font-size:0.75rem;">正常</span>';
      if (c.status === 'HIGH') {
        statusBadge = '<span class="badge badge-red" style="font-size:0.75rem;">偏高</span>';
      } else if (c.status === 'LOW') {
        statusBadge = '<span class="badge badge-yellow" style="font-size:0.75rem;">偏低</span>';
      } else if (c.status === 'ABNORMAL') {
        statusBadge = '<span class="badge badge-red" style="font-size:0.75rem;">异常</span>';
      }

      let trendText = '<span style="color:#94a3b8;">持平 —</span>';
      if (c.delta !== null && c.delta !== undefined) {
        if (c.delta > 0) {
          trendText = `<span style="color:#ef4444;">较前 +${c.delta} ↑</span>`;
        } else if (c.delta < 0) {
          trendText = `<span style="color:#10b981;">较前 ${c.delta} ↓</span>`;
        }
      }

      const sparkSvg = this.generateSparklineSvg(c.sparkline, isAbn);
      const safeRange = c.ref_range ? `参考: ${c.ref_range} ${c.unit || ''}` : '参考区间: 详见报告';
      const lastPointDate = (c.sparkline && c.sparkline.length > 0) ? c.sparkline[c.sparkline.length - 1].date : '';

      return `
        <div class="charts-kpi-card ${statusClass}" 
             onclick="ChartsModule.focusSingleMetric('${encodeURIComponent(c.code)}', '${encodeURIComponent(c.name || c.code)}')"
             title="点击聚焦查看 ${c.name} 深度演变走势">
          <div class="kpi-header">
            <div>
              <div class="kpi-name">${escapeHtml(c.name)}</div>
              <div class="kpi-code">${escapeHtml(c.code)}</div>
            </div>
            <div>${statusBadge}</div>
          </div>
          <div class="kpi-body">
            <div>
              <span class="kpi-val">${c.latest_value !== null ? c.latest_value : '--'}</span>
              <span class="kpi-unit">${escapeHtml(c.unit || '')}</span>
              <div style="margin-top:2px;">${trendText}</div>
            </div>
            <div style="display:flex; align-items:flex-end;">
              ${sparkSvg}
            </div>
          </div>
          <div class="kpi-footer">
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:140px;">${escapeHtml(safeRange)}</span>
            <span>${escapeHtml(lastPointDate)}</span>
          </div>
        </div>
      `;
    }).join('');

    kpiContainer.innerHTML = cardsHtml;
  },

  generateSparklineSvg(dataPoints, isAbnormal) {
    if (!dataPoints || dataPoints.length <= 1) {
      return `<span style="font-size:0.75rem; color:#94a3b8; font-style:italic;">仅单次记录</span>`;
    }

    const width = 84;
    const height = 30;
    const padding = 5;
    const vals = dataPoints.map(p => Number(p.value) || 0);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const range = (max - min) || 1;

    const points = vals.map((v, i) => {
      const x = padding + (i / (vals.length - 1)) * (width - 2 * padding);
      const y = (max === min)
        ? height / 2
        : height - padding - ((v - min) / range) * (height - 2 * padding);
      return [x, y];
    });

    const pathD = points.map((pt, i) => (i === 0 ? `M ${pt[0]} ${pt[1]}` : `L ${pt[0]} ${pt[1]}`)).join(' ');
    const lastPt = points[points.length - 1];
    const strokeColor = isAbnormal ? '#ef4444' : '#0284c7';
    const dotColor = isAbnormal ? '#ef4444' : '#10b981';

    return `
      <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" style="overflow:visible;">
        <path d="${pathD}" fill="none" stroke="${strokeColor}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="${lastPt[0]}" cy="${lastPt[1]}" r="3" fill="${dotColor}" stroke="#ffffff" stroke-width="1.5"/>
      </svg>
    `;
  },

  /* ==================== 2. 分类过滤、数量角标与药丸清单 ==================== */
  updateFilterCounts() {
    const list = this.availableMetrics || [];
    const countAll = list.length;
    const countAbnormal = list.filter(m => m.status !== 'NORMAL').length;
    const countTumor = list.filter(m => m.category === 'tumor_marker').length;
    const countSafety = list.filter(m => m.category === 'safety_toxicity').length;
    const countChronic = list.filter(m => m.category === 'chronic').length;
    const countOther = list.filter(m => m.category === 'other' || !m.category).length;

    const elAll = document.getElementById('filter-count-all');
    const elAbn = document.getElementById('filter-count-abnormal');
    const elTum = document.getElementById('filter-count-tumor');
    const elSaf = document.getElementById('filter-count-safety');
    const elChr = document.getElementById('filter-count-chronic');
    const elOth = document.getElementById('filter-count-other');

    if (elAll) elAll.textContent = countAll;
    if (elAbn) elAbn.textContent = countAbnormal;
    if (elTum) elTum.textContent = countTumor;
    if (elSaf) elSaf.textContent = countSafety;
    if (elChr) elChr.textContent = countChronic;
    if (elOth) elOth.textContent = countOther;
  },

  setCategoryFilter(category) {
    this.currentCategoryFilter = category;
    const buttons = document.querySelectorAll('#charts-category-filters .charts-filter-btn');
    buttons.forEach(btn => {
      if (btn.getAttribute('data-filter') === category) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
    this.renderPillsBar();
  },

  onSearchInput(value) {
    this.currentSearchQuery = (value || '').trim().toLowerCase();
    const clearBtn = document.getElementById('charts-search-clear');
    if (clearBtn) {
      clearBtn.style.display = this.currentSearchQuery ? 'block' : 'none';
    }
    this.renderPillsBar();
  },

  clearSearch() {
    const input = document.getElementById('charts-search-input');
    if (input) input.value = '';
    this.currentSearchQuery = '';
    const clearBtn = document.getElementById('charts-search-clear');
    if (clearBtn) clearBtn.style.display = 'none';
    this.renderPillsBar();
  },

  renderPillsBar() {
    const bar = document.getElementById('charts-metrics-pills-bar');
    if (!bar) return;

    if (!this.availableMetrics || this.availableMetrics.length === 0) {
      bar.innerHTML = '<span style="font-size:0.85rem; color:#94a3b8;">暂未提取到检验指标，请在【单据识别】上传化验单</span>';
      return;
    }

    // 筛选
    let filtered = this.availableMetrics.filter(m => {
      // 1. 分类匹配
      if (this.currentCategoryFilter === 'abnormal') {
        if (m.status === 'NORMAL') return false;
      } else if (this.currentCategoryFilter !== 'all') {
        if (m.category !== this.currentCategoryFilter) return false;
      }

      // 2. 搜索框模糊匹配
      if (this.currentSearchQuery) {
        const q = this.currentSearchQuery;
        const name = (m.name || '').toLowerCase();
        const code = (m.code || '').toLowerCase();
        const rawCode = (m.raw_code || '').toLowerCase();
        if (!name.includes(q) && !code.includes(q) && !rawCode.includes(q)) {
          return false;
        }
      }

      return true;
    });

    if (filtered.length === 0) {
      bar.innerHTML = `
        <div style="font-size:0.84rem; color:#94a3b8; padding:6px 0;">
          🔍 未找到符合当前筛选条件的检验指标
          <button class="btn btn-secondary btn-sm" style="margin-left:8px; padding:2px 8px; font-size:0.75rem;" onclick="ChartsModule.setCategoryFilter('all'); ChartsModule.clearSearch();">重置筛选</button>
        </div>
      `;
      return;
    }

    const focusedCodes = this.focusedMetrics.map(f => f.code);

    const pillsHtml = filtered.map(m => {
      const isFocused = focusedCodes.includes(m.code);
      const displayName = m.name && m.name !== m.code ? `${m.name} (${m.code})` : m.code;
      const statusDotClass = m.status === 'HIGH' ? 'high' : (m.status === 'LOW' ? 'low' : 'normal');
      const valNumber = (m.latest_value !== null && m.latest_value !== undefined) ? `${m.latest_value}` : '';
      const fullValWithUnit = valNumber ? `${valNumber} ${m.unit || ''}`.trim() : '未测定';

      return `
        <div class="metric-pill ${isFocused ? 'active' : ''}"
             onclick="ChartsModule.handlePillClick(event, '${encodeURIComponent(m.code)}', '${encodeURIComponent(m.name || m.code)}')"
             title="${escapeHtml(displayName)}&#10;最新测定: ${escapeHtml(fullValWithUnit)}&#10;参考区间: ${escapeHtml(m.ref_range || '未提供')}&#10;提示: 单击快速聚焦，按住 Ctrl/Cmd 单击可同屏对比">
          <span class="pill-status-dot ${statusDotClass}"></span>
          <span class="pill-title">${escapeHtml(displayName)}</span>
          ${valNumber ? `<span class="pill-meta" style="font-size:0.75rem; opacity:0.8;">${escapeHtml(valNumber)}</span>` : ''}
        </div>
      `;
    }).join('');

    bar.innerHTML = pillsHtml;
  },

  /* ==================== 3. 快捷时间跨度切换 ==================== */
  setTimeRange(range) {
    this.currentTimeRange = range;
    const buttons = document.querySelectorAll('.charts-time-range-group .time-range-btn');
    buttons.forEach(btn => {
      if (btn.getAttribute('data-range') === range) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // 将时间窗口分发应用到所有已初始化的图表
    this.applyTimeRange(this.focusChartInstance, this.chartDatesMap.focus);
    this.applyTimeRange(this.tumorChartInstance, this.chartDatesMap.tumor);
    this.applyTimeRange(this.safetyChartInstance, this.chartDatesMap.safety);
    this.applyTimeRange(this.chronicChartInstance, this.chartDatesMap.chronic);
  },

  applyTimeRange(chartInstance, dates) {
    if (!chartInstance || !dates || dates.length <= 1) return;
    const range = this.currentTimeRange;
    if (range === 'all') {
      chartInstance.dispatchAction({ type: 'dataZoom', start: 0, end: 100 });
      return;
    }

    const latestDateStr = dates[dates.length - 1];
    const latestDate = new Date(latestDateStr);
    let days = 365;
    if (range === '6m') days = 180;
    else if (range === '3m') days = 90;

    const cutoffTime = latestDate.getTime() - days * 24 * 3600 * 1000;
    const cutoffStr = new Date(cutoffTime).toISOString().slice(0, 10);

    let startIdx = dates.findIndex(d => d >= cutoffStr);
    if (startIdx < 0) startIdx = 0;
    const startPercent = Math.round((startIdx / (dates.length - 1)) * 100);

    chartInstance.dispatchAction({ type: 'dataZoom', start: startPercent, end: 100 });
  },

  /* ==================== 4. 深度聚焦与自由对比工作台 ==================== */
  handlePillClick(event, encodedCode, encodedName) {
    const code = decodeURIComponent(encodedCode);
    const name = decodeURIComponent(encodedName);

    // 若按住 Ctrl / Cmd 或 Shift，则触发多选对比
    if (event.ctrlKey || event.metaKey || event.shiftKey) {
      this.toggleCompareMetric(code, name);
    } else {
      this.focusSingleMetric(code, name);
    }
  },

  async focusSingleMetric(code, name) {
    // 单击直接将工作台重设为此指标
    this.focusedMetrics = [{ code, name }];
    this.renderPillsBar();
    await this.renderWorkbench();
  },

  async toggleCompareMetric(code, name) {
    const idx = this.focusedMetrics.findIndex(m => m.code === code);
    if (idx >= 0) {
      if (this.focusedMetrics.length === 1) {
        // 如果只剩一个，则保持或关闭
        this.closeFocusCard();
        return;
      }
      this.focusedMetrics.splice(idx, 1);
    } else {
      if (this.focusedMetrics.length >= 3) {
        if (typeof showToast === 'function') {
          showToast('工作台最多支持同时对比 3 项指标', 'warning');
        } else {
          alert('工作台最多支持同时对比 3 项指标');
        }
        return;
      }
      this.focusedMetrics.push({ code, name });
    }

    this.renderPillsBar();
    await this.renderWorkbench();
  },

  removeCompareMetric(code) {
    const idx = this.focusedMetrics.findIndex(m => m.code === code);
    if (idx >= 0) {
      this.focusedMetrics.splice(idx, 1);
    }
    if (this.focusedMetrics.length === 0) {
      this.closeFocusCard();
    } else {
      this.renderPillsBar();
      this.renderWorkbench();
    }
  },

  closeFocusCard() {
    const card = document.getElementById('charts-focus-card');
    if (card) card.style.display = 'none';
    this.focusedMetrics = [];
    this.renderPillsBar();
  },

  async renderWorkbench() {
    if (this.focusedMetrics.length === 0) return;

    const card = document.getElementById('charts-focus-card');
    const title = document.getElementById('charts-focus-title');
    const tagsContainer = document.getElementById('charts-focus-active-tags');
    const dom = document.getElementById('chart-focus-container');
    const targetUserId = window.inspectTargetUserId || null;

    if (!card || !dom) return;

    card.style.display = 'block';

    // 渲染顶部活动标签
    if (tagsContainer) {
      tagsContainer.innerHTML = this.focusedMetrics.map(m => `
        <span class="badge badge-blue" style="display:inline-flex; align-items:center; gap:4px; padding:3px 8px; font-size:0.8rem;">
          📈 ${escapeHtml(m.name || m.code)}
          <span style="cursor:pointer; font-weight:bold; margin-left:2px;" onclick="ChartsModule.removeCompareMetric('${escapeHtml(m.code)}')" title="移除此项对比">✖</span>
        </span>
      `).join('');
    }

    if (this.focusedMetrics.length === 1) {
      title.innerHTML = `🔍 <strong>${escapeHtml(this.focusedMetrics[0].name)} (${escapeHtml(this.focusedMetrics[0].code)})</strong> 专属深度时序演变`;
    } else {
      title.innerHTML = `🔍 <strong>多指标综合时序对比工作台</strong> (${this.focusedMetrics.length}项同屏对照)`;
    }

    card.scrollIntoView({ behavior: 'smooth', block: 'start' });

    if (!this.focusChartInstance) {
      this.focusChartInstance = echarts.init(dom);
    }
    this.focusChartInstance.showLoading();

    try {
      const queryCodes = this.focusedMetrics.map(m => m.code).join(',');
      const data = await API.getChartSeries(queryCodes, targetUserId);
      this.focusChartInstance.hideLoading();

      if (!data.dates || data.dates.length === 0 || !data.series || data.series.length === 0) {
        this.focusChartInstance.setOption({
          title: { text: `所选指标暂未匹配到有效测定数值`, left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 13 } }
        }, true);
        return;
      }

      this.chartDatesMap.focus = data.dates;
      const isSinglePoint = data.dates.length === 1;

      // 判断是否需要启用双 Y 轴：当 series 数量 >= 2 且单位不同或数值级差 > 4 时
      let useDualAxis = false;
      let yAxisConfig = [];

      if (data.series.length >= 2) {
        const s0 = data.series[0];
        const s1 = data.series[1];
        const vals0 = (s0.data || []).filter(v => v !== null && v !== undefined);
        const vals1 = (s1.data || []).filter(v => v !== null && v !== undefined);
        const max0 = vals0.length ? Math.max(...vals0) : 0;
        const max1 = vals1.length ? Math.max(...vals1) : 0;

        const unitsDiffer = s0.unit && s1.unit && (s0.unit !== s1.unit);
        const scaleDiffer = (max0 > 0 && max1 > 0) && (max0 / max1 > 4 || max1 / max0 > 4);

        if (unitsDiffer || scaleDiffer) {
          useDualAxis = true;
          yAxisConfig = [
            {
              type: 'value',
              name: `${s0.name || s0.code} (${s0.unit || ''})`,
              scale: true,
              splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
            },
            {
              type: 'value',
              name: `${s1.name || s1.code} (${s1.unit || ''})`,
              scale: true,
              splitLine: { show: false }
            }
          ];
        }
      }

      if (!useDualAxis) {
        const commonUnit = data.series[0].unit || '';
        yAxisConfig = [{
          type: 'value',
          scale: true,
          name: commonUnit,
          splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
        }];
      }

      const palette = ['#0284c7', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899'];

      const seriesList = data.series.map((s, idx) => {
        const color = palette[idx % palette.length];
        const processedData = this.processSeriesData(s);

        // 如果只有单指标，渲染绿色半透明正常安全带 (MarkArea)
        let markAreaOpt = undefined;
        let markLineOpt = undefined;

        if (data.series.length === 1 && (s.ref_max !== null || s.ref_min !== null)) {
          markAreaOpt = {
            silent: true,
            itemStyle: {
              color: 'rgba(16, 185, 129, 0.08)' // 正常参考安全带背景
            },
            data: [[
              {
                yAxis: s.ref_min !== null ? s.ref_min : 0,
                name: '正常安全区间'
              },
              {
                yAxis: s.ref_max !== null ? s.ref_max : undefined
              }
            ]]
          };

          markLineOpt = {
            silent: true,
            symbol: 'none',
            data: [
              ...(s.ref_max ? [{
                yAxis: s.ref_max,
                name: '参考上限',
                lineStyle: { type: 'dashed', color: '#ef4444', width: 1.5 },
                label: { formatter: `上限: ${s.ref_max} ${s.unit || ''}`, position: 'end' }
              }] : []),
              ...(s.ref_min ? [{
                yAxis: s.ref_min,
                name: '参考下限',
                lineStyle: { type: 'dashed', color: '#f59e0b', width: 1.5 },
                label: { formatter: `下限: ${s.ref_min} ${s.unit || ''}`, position: 'end' }
              }] : [])
            ]
          };
        }

        // 双轴分配：前两个指标分别分配 0 和 1，第三个指标根据单位对齐
        let yAxisIndex = 0;
        if (useDualAxis) {
          if (idx === 0) yAxisIndex = 0;
          else if (idx === 1) yAxisIndex = 1;
          else {
            yAxisIndex = (s.unit === data.series[1].unit) ? 1 : 0;
          }
        }

        return {
          name: `${s.name} (${s.code})`,
          type: 'line',
          yAxisIndex: yAxisIndex,
          smooth: true,
          showSymbol: true,
          showAllSymbol: true,
          symbol: 'circle',
          symbolSize: 8,
          itemStyle: { color: color },
          lineStyle: { width: 3, color: color },
          areaStyle: (data.series.length === 1 && !isSinglePoint) ? {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(2, 132, 199, 0.28)' },
              { offset: 1, color: 'rgba(2, 132, 199, 0.02)' }
            ])
          } : undefined,
          label: {
            show: true,
            position: 'top',
            formatter: p => (p.data && p.data.value !== undefined) ? `${p.data.value}${p.data.trend || ''}` : '',
            fontWeight: 600,
            fontSize: 11
          },
          data: processedData,
          markArea: markAreaOpt,
          markLine: markLineOpt
        };
      });

      const option = {
        title: {
          text: data.series.length === 1 ? `${data.series[0].name || data.series[0].code} 历史测定演变走势` : `同屏多指标演变对照图`,
          subtext: isSinglePoint
            ? '💡 当前仅记录了 1 次采样数据（已标明具体数值点），录入新单后将自动连线展示趋势'
            : (useDualAxis ? '💡 已智能启用左右双 Y 轴，消除不同指标量纲差异导致的贴地压平现象' : undefined),
          left: 'left',
          textStyle: { fontSize: 14, fontWeight: 700, color: '#0f172a' },
          subtextStyle: { fontSize: 12, color: '#64748b' }
        },
        legend: {
          show: data.series.length > 1,
          top: '30px',
          type: 'scroll'
        },
        tooltip: {
          trigger: 'axis',
          confine: true,
          formatter: function (params) {
            let res = `<div style="font-weight:600;margin-bottom:4px;">采样日期: ${params[0].axisValue}</div>`;
            params.forEach(p => {
              const dataObj = p.data;
              if (dataObj === null || dataObj === undefined) {
                res += `<div>${p.marker} ${p.seriesName}: <strong>未测定</strong></div>`;
              } else {
                const val = dataObj.value;
                const trendTag = dataObj.trend ? ` <strong style="color:${dataObj.trend === '↑' ? '#ef4444' : '#10b981'}">${dataObj.trend}</strong>` : '';
                const abnTag = dataObj.isHigh ? ' <span style="color:#ef4444;font-size:0.8rem">(偏高)</span>' : (dataObj.isLow ? ' <span style="color:#f59e0b;font-size:0.8rem">(偏低)</span>' : '');
                const convTag = dataObj.isConverted ? ` <span style="font-size:0.75rem; color:#0284c7; background:rgba(2,132,199,0.1); padding:1px 6px; border-radius:4px; margin-left:4px;" title="原始单据数值: ${dataObj.rawValue} ${dataObj.rawUnit}">🔄原单: ${dataObj.rawValue} ${dataObj.rawUnit}</span>` : '';
                res += `<div>${p.marker} ${p.seriesName}: <strong style="color:${dataObj.itemStyle.color}">${val}</strong> ${dataObj.unit || ''}${abnTag}${trendTag}${convTag}</div>`;
              }
            });
            return res;
          }
        },
        grid: {
          left: '4%',
          right: useDualAxis ? '6%' : '4%',
          bottom: '50px',
          top: data.series.length > 1 ? '70px' : '55px',
          containLabel: true
        },
        dataZoom: [
          { type: 'inside', xAxisIndex: 0, filterMode: 'empty' },
          { type: 'slider', xAxisIndex: 0, filterMode: 'empty', bottom: 10, height: 20 }
        ],
        xAxis: {
          type: 'category',
          boundaryGap: isSinglePoint ? ['35%', '35%'] : false,
          data: data.dates,
          axisLabel: { fontWeight: 600 }
        },
        yAxis: yAxisConfig,
        series: seriesList
      };

      this.focusChartInstance.setOption(option, true);
      this.applyTimeRange(this.focusChartInstance, data.dates);
    } catch (err) {
      this.focusChartInstance.hideLoading();
      console.error('Render focus metric error:', err);
    }
  },

  /* ==================== 5. 固定三大分类时序监控看板 ==================== */
  processSeriesData(s) {
    if (!s.data || !s.data.length) return [];
    const rawVals = s.raw_values || [];
    const rawUnits = s.raw_units || [];
    const convertedFlags = s.converted_flags || [];

    return s.data.map((val, idx) => {
      if (val === null || val === undefined) return val;

      let isHigh = s.ref_max !== null && val > s.ref_max;
      let isLow = s.ref_min !== null && val < s.ref_min;

      let trend = '';
      let prevVal = null;
      for (let i = idx - 1; i >= 0; i--) {
        if (s.data[i] !== null && s.data[i] !== undefined) {
          prevVal = s.data[i];
          break;
        }
      }
      if (prevVal !== null) {
        if (val > prevVal) trend = '↑';
        if (val < prevVal) trend = '↓';
      }

      let color = '#0284c7';
      if (isHigh) color = '#ef4444';
      else if (isLow) color = '#f59e0b';

      const isConverted = !!convertedFlags[idx];
      const rawVal = rawVals[idx];
      const rawUnit = rawUnits[idx];

      return {
        value: val,
        isHigh,
        isLow,
        trend,
        isConverted,
        rawValue: rawVal,
        rawUnit: rawUnit,
        unit: s.unit || '',
        itemStyle: { color: color }
      };
    });
  },

  async renderTumorMarkers(codes = ['CEA', 'CA199', 'CA125'], targetUserId = null) {
    const dom = document.getElementById('chart-tumor-markers');
    if (!dom || typeof echarts === 'undefined') return;

    if (!this.tumorChartInstance) {
      this.tumorChartInstance = echarts.init(dom);
    }
    this.tumorChartInstance.showLoading();

    try {
      const data = await API.getChartSeries(codes.join(','), targetUserId);
      this.tumorChartInstance.hideLoading();

      if (!data.dates || data.dates.length === 0 || !data.series || data.series.length === 0) {
        this.tumorChartInstance.setOption({
          title: { text: '暂无肿瘤标志物时序数据 (请上传包含 CEA/CA19-9 等的化验单)', left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14 } }
        }, true);
        return;
      }

      this.chartDatesMap.tumor = data.dates;
      const isSinglePoint = data.dates.length === 1;

      // 智能双 Y 轴检测：CEA（0~5 ng/mL）与 CA19-9/CA125（0~37+ U/mL）量纲平衡
      let useDual = false;
      const ceaSeries = data.series.find(s => s.code === 'CEA');
      const otherSeries = data.series.find(s => s.code !== 'CEA');
      if (ceaSeries && otherSeries && data.series.length >= 2) {
        useDual = true;
      }

      const yAxis = useDual ? [
        {
          type: 'value',
          name: 'CEA (ng/mL)',
          scale: true,
          splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
        },
        {
          type: 'value',
          name: 'CA19-9 / CA125 (U/mL)',
          scale: true,
          splitLine: { show: false }
        }
      ] : {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
      };

      const seriesList = data.series.map(s => {
        const isCea = s.code === 'CEA';
        return {
          name: `${s.name} (${s.code})`,
          type: 'line',
          yAxisIndex: useDual ? (isCea ? 0 : 1) : 0,
          smooth: true,
          showSymbol: true,
          showAllSymbol: true,
          symbol: 'circle',
          symbolSize: 8,
          label: {
            show: true,
            position: 'top',
            fontSize: 11,
            fontWeight: 600,
            formatter: p => (p.data && p.data.value !== undefined) ? `${p.data.value}${p.data.trend || ''}` : ''
          },
          data: this.processSeriesData(s),
          markLine: s.ref_max ? {
            silent: true,
            symbol: 'none',
            data: [{
              yAxis: s.ref_max,
              name: `${s.name}参考上限`,
              lineStyle: { type: 'dashed', color: '#f59e0b' },
              label: { formatter: `${s.code}上限: {c} ${s.unit || ''}`, position: 'end' }
            }]
          } : undefined
        };
      });

      const option = {
        title: {
          text: '肿瘤标志物动态监控演变趋势',
          subtext: isSinglePoint
            ? '💡 当前仅记录了 1 次采样数据（已标明具体测定数值）'
            : (useDual ? '💡 采用 CEA(左轴) 与 糖类抗原(右轴) 双轴平衡展示' : undefined),
          left: 'left',
          textStyle: { fontSize: 15, fontWeight: 700 },
          subtextStyle: { fontSize: 11, color: '#64748b' }
        },
        tooltip: {
          trigger: 'axis',
          confine: true,
          formatter: function (params) {
            let res = `<div style="font-weight:600;margin-bottom:4px;">采样日期: ${params[0].axisValue}</div>`;
            params.forEach(p => {
              const dataObj = p.data;
              if (dataObj === null || dataObj === undefined) {
                res += `<div>${p.marker} ${p.seriesName}: <strong>未测定</strong></div>`;
              } else {
                const val = dataObj.value;
                const unitStr = dataObj.unit ? ` ${dataObj.unit}` : '';
                const trendTag = dataObj.trend ? ` <strong style="color:${dataObj.trend === '↑' ? '#ef4444' : '#10b981'}">${dataObj.trend}</strong>` : '';
                const abnTag = dataObj.isHigh ? ' <span style="color:#ef4444;font-size:0.8rem">(高)</span>' : (dataObj.isLow ? ' <span style="color:#f59e0b;font-size:0.8rem">(低)</span>' : '');
                const convTag = dataObj.isConverted ? ` <span style="font-size:0.75rem; color:#0284c7; background:rgba(2,132,199,0.1); padding:1px 6px; border-radius:4px; margin-left:4px;" title="原始单据数值: ${dataObj.rawValue} ${dataObj.rawUnit}">🔄原单: ${dataObj.rawValue} ${dataObj.rawUnit}</span>` : '';
                res += `<div>${p.marker} ${p.seriesName}: <strong style="color:${dataObj.itemStyle.color}">${val}</strong>${unitStr}${abnTag}${trendTag}${convTag}</div>`;
              }
            });
            return res;
          }
        },
        legend: { top: '30px', type: 'scroll' },
        grid: { left: '3%', right: useDual ? '6%' : '4%', bottom: '50px', top: '75px', containLabel: true },
        dataZoom: [
          { type: 'inside', xAxisIndex: 0, filterMode: 'empty' },
          { type: 'slider', xAxisIndex: 0, filterMode: 'empty', bottom: 10, height: 20 }
        ],
        xAxis: {
          type: 'category',
          boundaryGap: isSinglePoint ? ['25%', '25%'] : false,
          data: data.dates
        },
        yAxis: yAxis,
        series: seriesList
      };

      this.tumorChartInstance.setOption(option, true);
      this.applyTimeRange(this.tumorChartInstance, data.dates);
    } catch (err) {
      this.tumorChartInstance.hideLoading();
      console.error('Render tumor markers error:', err);
    }
  },

  async renderSafetyMarkers(codes = ['WBC', 'PLT', 'ALT', 'CR'], targetUserId = null) {
    const dom = document.getElementById('chart-safety-markers');
    if (!dom || typeof echarts === 'undefined') return;

    if (!this.safetyChartInstance) {
      this.safetyChartInstance = echarts.init(dom);
    }
    this.safetyChartInstance.showLoading();

    try {
      const data = await API.getChartSeries(codes.join(','), targetUserId);
      this.safetyChartInstance.hideLoading();

      if (!data.dates || data.dates.length === 0 || !data.series || data.series.length === 0) {
        this.safetyChartInstance.setOption({
          title: { text: '暂无化疗/靶向毒性监控指标数据 (血常规/肝肾功)', left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14 } }
        }, true);
        return;
      }

      this.chartDatesMap.safety = data.dates;
      const isSinglePoint = data.dates.length === 1;

      // 骨髓抑制双 Y 轴平衡设计：
      // 左 Y 轴：白细胞 WBC、中性粒绝对值 NEUT# (尺度 0~15 10^9/L)，重点监控骨髓抑制！
      // 右 Y 轴：血小板 PLT、ALT、肌酐 Cr (尺度 50~300+)，两不干涉，彻底解决 WBC 贴地平线问题！
      const smallScaleCodes = ['WBC', 'NEUT#', 'LYMPH#', 'MONO#'];
      const hasSmall = data.series.some(s => smallScaleCodes.includes(s.code.toUpperCase()));
      const hasLarge = data.series.some(s => !smallScaleCodes.includes(s.code.toUpperCase()));
      const useDual = hasSmall && hasLarge;

      const yAxis = useDual ? [
        {
          type: 'value',
          name: '白细胞/中性粒 (10^9/L)',
          scale: true,
          splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
        },
        {
          type: 'value',
          name: '血小板/肝肾 (PLT/ALT/Cr)',
          scale: true,
          splitLine: { show: false }
        }
      ] : {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
      };

      const seriesList = data.series.map(s => {
        const isSmall = smallScaleCodes.includes(s.code.toUpperCase());
        return {
          name: `${s.name} (${s.code})`,
          type: 'line',
          yAxisIndex: useDual ? (isSmall ? 0 : 1) : 0,
          smooth: true,
          showSymbol: true,
          showAllSymbol: true,
          symbol: 'circle',
          symbolSize: 8,
          label: {
            show: true,
            position: 'top',
            fontSize: 11,
            fontWeight: 600,
            formatter: p => (p.data && p.data.value !== undefined) ? `${p.data.value}${p.data.trend || ''}` : ''
          },
          data: this.processSeriesData(s)
        };
      });

      const option = {
        title: {
          text: '骨髓抑制与肝肾器官安全性动态监控',
          subtext: isSinglePoint
            ? '💡 当前仅记录了 1 次采样数据（已标明具体测定数值）'
            : (useDual ? '💡 采用 WBC(左轴) 与 PLT/肝肾(右轴) 双轴独立比例尺，精准呈现骨髓抑制波动' : undefined),
          left: 'left',
          textStyle: { fontSize: 15, fontWeight: 700 },
          subtextStyle: { fontSize: 11, color: '#64748b' }
        },
        tooltip: {
          trigger: 'axis',
          confine: true,
          formatter: function (params) {
            let res = `<div style="font-weight:600;margin-bottom:4px;">采样日期: ${params[0].axisValue}</div>`;
            params.forEach(p => {
              const dataObj = p.data;
              if (dataObj === null || dataObj === undefined) {
                res += `<div>${p.marker} ${p.seriesName}: <strong>未测定</strong></div>`;
              } else {
                const val = dataObj.value;
                const unitStr = dataObj.unit ? ` ${dataObj.unit}` : '';
                const trendTag = dataObj.trend ? ` <strong style="color:${dataObj.trend === '↑' ? '#ef4444' : '#10b981'}">${dataObj.trend}</strong>` : '';
                const abnTag = dataObj.isHigh ? ' <span style="color:#ef4444;font-size:0.8rem">(高)</span>' : (dataObj.isLow ? ' <span style="color:#f59e0b;font-size:0.8rem">(低)</span>' : '');
                const convTag = dataObj.isConverted ? ` <span style="font-size:0.75rem; color:#0284c7; background:rgba(2,132,199,0.1); padding:1px 6px; border-radius:4px; margin-left:4px;" title="原始单据数值: ${dataObj.rawValue} ${dataObj.rawUnit}">🔄原单: ${dataObj.rawValue} ${dataObj.rawUnit}</span>` : '';
                res += `<div>${p.marker} ${p.seriesName}: <strong style="color:${dataObj.itemStyle.color}">${val}</strong>${unitStr}${abnTag}${trendTag}${convTag}</div>`;
              }
            });
            return res;
          }
        },
        legend: { top: '30px', type: 'scroll' },
        grid: { left: '3%', right: useDual ? '6%' : '4%', bottom: '50px', top: '75px', containLabel: true },
        dataZoom: [
          { type: 'inside', xAxisIndex: 0, filterMode: 'empty' },
          { type: 'slider', xAxisIndex: 0, filterMode: 'empty', bottom: 10, height: 20 }
        ],
        xAxis: {
          type: 'category',
          boundaryGap: isSinglePoint ? ['25%', '25%'] : false,
          data: data.dates
        },
        yAxis: yAxis,
        series: seriesList
      };

      this.safetyChartInstance.setOption(option, true);
      this.applyTimeRange(this.safetyChartInstance, data.dates);
    } catch (err) {
      this.safetyChartInstance.hideLoading();
      console.error('Render safety markers error:', err);
    }
  },

  async renderChronicMarkers(codes = ['GLU', 'HbA1c', 'UA'], targetUserId = null) {
    const dom = document.getElementById('chart-chronic-markers');
    if (!dom || typeof echarts === 'undefined') return;

    if (!this.chronicChartInstance) {
      this.chronicChartInstance = echarts.init(dom);
    }
    this.chronicChartInstance.showLoading();

    try {
      const data = await API.getChartSeries(codes.join(','), targetUserId);
      this.chronicChartInstance.hideLoading();

      if (!data.dates || data.dates.length === 0 || !data.series || data.series.length === 0) {
        this.chronicChartInstance.setOption({
          title: { text: '暂无伴随慢性病代谢指标 (血糖/尿酸/血脂等)', left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14 } }
        }, true);
        return;
      }

      this.chartDatesMap.chronic = data.dates;
      const isSinglePoint = data.dates.length === 1;

      // 尿酸 UA (umol/L, 150~450) vs 血糖 GLU (mmol/L, 3.9~6.1) 双轴判断
      const hasUA = data.series.some(s => s.code === 'UA');
      const hasGLU = data.series.some(s => s.code === 'GLU' || s.code === 'HbA1c');
      const useDual = hasUA && hasGLU;

      const yAxis = useDual ? [
        {
          type: 'value',
          name: '血糖/糖化 (mmol/L, %)',
          scale: true,
          splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
        },
        {
          type: 'value',
          name: '尿酸 (umol/L)',
          scale: true,
          splitLine: { show: false }
        }
      ] : {
        type: 'value',
        scale: true,
        splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
      };

      const seriesList = data.series.map(s => {
        const isUa = s.code === 'UA';
        return {
          name: `${s.name} (${s.code})`,
          type: 'line',
          yAxisIndex: useDual ? (isUa ? 1 : 0) : 0,
          smooth: true,
          showSymbol: true,
          showAllSymbol: true,
          symbol: 'circle',
          symbolSize: 8,
          label: {
            show: true,
            position: 'top',
            fontSize: 11,
            fontWeight: 600,
            formatter: p => (p.data && p.data.value !== undefined) ? `${p.data.value}${p.data.trend || ''}` : ''
          },
          data: this.processSeriesData(s)
        };
      });

      const option = {
        title: {
          text: '伴随慢性病与代谢指标动态 (血糖/尿酸/血脂等)',
          subtext: isSinglePoint
            ? '💡 当前仅记录了 1 次采样数据（已标明具体测定数值）'
            : (useDual ? '💡 采用 血糖/糖化(左轴) 与 尿酸(右轴) 双轴平衡展示' : undefined),
          left: 'left',
          textStyle: { fontSize: 15, fontWeight: 700 },
          subtextStyle: { fontSize: 11, color: '#64748b' }
        },
        tooltip: {
          trigger: 'axis',
          confine: true,
          formatter: function (params) {
            let res = `<div style="font-weight:600;margin-bottom:4px;">采样日期: ${params[0].axisValue}</div>`;
            params.forEach(p => {
              const dataObj = p.data;
              if (dataObj === null || dataObj === undefined) {
                res += `<div>${p.marker} ${p.seriesName}: <strong>未测定</strong></div>`;
              } else {
                const val = dataObj.value;
                const unitStr = dataObj.unit ? ` ${dataObj.unit}` : '';
                const trendTag = dataObj.trend ? ` <strong style="color:${dataObj.trend === '↑' ? '#ef4444' : '#10b981'}">${dataObj.trend}</strong>` : '';
                const abnTag = dataObj.isHigh ? ' <span style="color:#ef4444;font-size:0.8rem">(高)</span>' : (dataObj.isLow ? ' <span style="color:#f59e0b;font-size:0.8rem">(低)</span>' : '');
                const convTag = dataObj.isConverted ? ` <span style="font-size:0.75rem; color:#0284c7; background:rgba(2,132,199,0.1); padding:1px 6px; border-radius:4px; margin-left:4px;" title="原始单据数值: ${dataObj.rawValue} ${dataObj.rawUnit}">🔄原单: ${dataObj.rawValue} ${dataObj.rawUnit}</span>` : '';
                res += `<div>${p.marker} ${p.seriesName}: <strong style="color:${dataObj.itemStyle.color}">${val}</strong>${unitStr}${abnTag}${trendTag}${convTag}</div>`;
              }
            });
            return res;
          }
        },
        legend: { top: '30px', type: 'scroll' },
        grid: { left: '3%', right: useDual ? '6%' : '4%', bottom: '50px', top: '75px', containLabel: true },
        dataZoom: [
          { type: 'inside', xAxisIndex: 0, filterMode: 'empty' },
          { type: 'slider', xAxisIndex: 0, filterMode: 'empty', bottom: 10, height: 20 }
        ],
        xAxis: {
          type: 'category',
          boundaryGap: isSinglePoint ? ['25%', '25%'] : false,
          data: data.dates
        },
        yAxis: yAxis,
        series: seriesList
      };

      this.chronicChartInstance.setOption(option, true);
      this.applyTimeRange(this.chronicChartInstance, data.dates);
    } catch (err) {
      this.chronicChartInstance.hideLoading();
      console.error('Render chronic markers error:', err);
    }
  }
};

window.ChartsModule = ChartsModule;
