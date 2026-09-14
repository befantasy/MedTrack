/**
 * MedTrack ECharts 肿瘤标志物、治疗安全性与慢病指标全维度动态看板
 */

const ChartsModule = {
  tumorChartInstance: null,
  safetyChartInstance: null,
  chronicChartInstance: null,
  focusChartInstance: null,
  availableMetrics: [],
  resizeListenerBound: false,

  async refresh() {
    if (this.tumorChartInstance) { this.tumorChartInstance.dispose(); this.tumorChartInstance = null; }
    if (this.safetyChartInstance) { this.safetyChartInstance.dispose(); this.safetyChartInstance = null; }
    if (this.chronicChartInstance) { this.chronicChartInstance.dispose(); this.chronicChartInstance = null; }
    if (this.focusChartInstance) { this.focusChartInstance.dispose(); this.focusChartInstance = null; }
    await this.initAll();
  },

  async initAll() {
    const targetUserId = window.inspectTargetUserId || null;

    // 1. 获取该用户所有实际已记录的指标
    try {
      this.availableMetrics = await API.getAvailableMetrics(targetUserId);
    } catch (e) {
      console.warn('Failed to get available metrics:', e);
      this.availableMetrics = [];
    }

    // 2. 渲染顶部指标药丸条
    this.renderPillsBar();

    // 3. 智能推导适合各大图表的指标集合
    const tumorDefaults = ['CEA', 'CA199', 'CA125', 'AFP', 'CA153', 'CYFRA21-1', 'NSE'];
    const safetyDefaults = ['WBC', 'PLT', 'NEUT#', 'HGB', 'ALT', 'AST', 'CR'];
    const chronicDefaults = ['GLU', 'HbA1c', 'UA', 'TBIL', 'ALB'];

    // 筛选出用户实际拥有的肿瘤标志物
    let userTumorCodes = (this.availableMetrics || [])
      .filter(m => m.category === 'tumor_marker' || tumorDefaults.includes(m.code.toUpperCase()))
      .map(m => m.code);
    if (userTumorCodes.length === 0) {
      userTumorCodes = ['CEA', 'CA199', 'CA125'];
    }

    // 筛选出用户实际拥有的毒副/器官指标
    let userSafetyCodes = (this.availableMetrics || [])
      .filter(m => m.category === 'safety_toxicity' || safetyDefaults.includes(m.code.toUpperCase()))
      .map(m => m.code);
    if (userSafetyCodes.length === 0) {
      userSafetyCodes = ['WBC', 'PLT', 'ALT', 'CR'];
    }

    // 筛选出用户实际拥有的慢病指标
    let userChronicCodes = (this.availableMetrics || [])
      .filter(m => m.category === 'chronic' || chronicDefaults.includes(m.code.toUpperCase()))
      .map(m => m.code);
    if (userChronicCodes.length === 0) {
      userChronicCodes = ['GLU', 'HbA1c'];
    }

    await Promise.all([
      this.renderTumorMarkers(userTumorCodes, targetUserId),
      this.renderSafetyMarkers(userSafetyCodes, targetUserId),
      this.renderChronicMarkers(userChronicCodes, targetUserId)
    ]);

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

  renderPillsBar() {
    const bar = document.getElementById('charts-metrics-pills-bar');
    const countBadge = document.getElementById('charts-metrics-count');
    if (!bar) return;

    if (!this.availableMetrics || this.availableMetrics.length === 0) {
      if (countBadge) {
        countBadge.textContent = '暂未提取到检验指标';
        countBadge.className = 'badge badge-gray';
      }
      bar.innerHTML = '<span style="font-size:0.85rem; color:#94a3b8;">暂无历史化验单指标，请前往首页【智能病历提取】上传化验单</span>';
      return;
    }

    if (countBadge) {
      countBadge.textContent = `已智能汇聚 ${this.availableMetrics.length} 项检验指标`;
      countBadge.className = 'badge badge-green';
    }

    const badgeClasses = {
      'tumor_marker': 'badge-red',
      'safety_toxicity': 'badge-blue',
      'chronic': 'badge-green',
      'other': 'badge-gray'
    };

    const categoryNames = {
      'tumor_marker': '肿瘤标志物',
      'safety_toxicity': '毒副/安全性',
      'chronic': '慢病/代谢',
      'other': '通用指标'
    };

    bar.innerHTML = this.availableMetrics.map(m => {
      const cls = badgeClasses[m.category] || 'badge-gray';
      const catName = categoryNames[m.category] || '指标';
      const displayName = m.name && m.name !== m.code ? `${m.name} (${m.code})` : m.code;
      return `
        <button type="button" 
          onclick="ChartsModule.focusSingleMetric('${encodeURIComponent(m.code)}', '${encodeURIComponent(m.name || m.code)}')"
          class="badge ${cls}" 
          style="cursor:pointer; border:1px solid rgba(0,0,0,0.08); padding:5px 10px; font-size:0.83rem; transition:transform 0.15s, box-shadow 0.15s; display:inline-flex; align-items:center; gap:4px;"
          title="点击查看 ${displayName} 专属演变时序图 [${catName}]"
          onmouseover="this.style.transform='translateY(-1px)'; this.style.boxShadow='0 2px 5px rgba(0,0,0,0.1)'"
          onmouseout="this.style.transform='none'; this.style.boxShadow='none'">
          <span>📈 ${escapeHtml(displayName)}</span>
          ${m.unit ? `<span style="opacity:0.75; font-size:0.75rem;">${escapeHtml(m.unit)}</span>` : ''}
        </button>
      `;
    }).join('');
  },

  async focusSingleMetric(encodedCode, encodedName) {
    const code = decodeURIComponent(encodedCode);
    const name = decodeURIComponent(encodedName);
    const targetUserId = window.inspectTargetUserId || null;

    const card = document.getElementById('charts-focus-card');
    const title = document.getElementById('charts-focus-title');
    const dom = document.getElementById('chart-focus-container');
    if (!card || !dom) return;

    card.style.display = 'block';
    title.innerHTML = `🔍 <strong>${escapeHtml(name)} (${escapeHtml(code)})</strong> 专属深度时序演变`;

    card.scrollIntoView({ behavior: 'smooth', block: 'start' });

    if (!this.focusChartInstance) {
      this.focusChartInstance = echarts.init(dom);
    }
    this.focusChartInstance.showLoading();

    try {
      const data = await API.getChartSeries(code, targetUserId);
      this.focusChartInstance.hideLoading();

      if (!data.dates || data.dates.length === 0 || !data.series || data.series.length === 0) {
        this.focusChartInstance.setOption({
          title: { text: `指标 ${code} 暂未匹配到有效测定数值`, left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 13 } }
        }, true);
        return;
      }

      const s = data.series[0];
      const isSinglePoint = data.dates.length === 1;

      const markLineOpt = (s.ref_max || s.ref_min) ? {
        silent: true,
        symbol: 'none',
        data: [
          ...(s.ref_max ? [{
            yAxis: s.ref_max,
            name: '参考上限',
            lineStyle: { type: 'dashed', color: '#ef4444', width: 1.5 },
            label: { formatter: `参考上限: ${s.ref_max} ${s.unit || ''}`, position: 'end' }
          }] : []),
          ...(s.ref_min ? [{
            yAxis: s.ref_min,
            name: '参考下限',
            lineStyle: { type: 'dashed', color: '#f59e0b', width: 1.5 },
            label: { formatter: `参考下限: ${s.ref_min} ${s.unit || ''}`, position: 'end' }
          }] : [])
        ]
      } : undefined;

      const option = {
        title: {
          text: `${s.name || code} 检验历史数值演变走势`,
          subtext: isSinglePoint ? '💡 当前仅记录了 1 次采样数据，已清晰标注数值点。后续录入新化验单将自动绘制连线趋势' : `共监测到 ${data.dates.length} 次采样周期，单位: ${s.unit || '无'}`,
          left: 'left',
          textStyle: { fontSize: 14, fontWeight: 700, color: '#0f172a' },
          subtextStyle: { fontSize: 12, color: '#64748b' }
        },
        tooltip: {
          trigger: 'axis',
          formatter: function (params) {
            let res = `<div style="font-weight:600;margin-bottom:4px;">采样日期: ${params[0].axisValue}</div>`;
            params.forEach(p => {
              const val = p.value !== null && p.value !== undefined ? p.value : '未测定';
              res += `<div>${p.marker} 测定值: <strong>${val}</strong> ${s.unit || ''}</div>`;
            });
            if (s.ref_range) {
              res += `<div style="font-size:0.8rem; color:#94a3b8; margin-top:2px;">正常参考区间: ${s.ref_range}</div>`;
            }
            return res;
          }
        },
        grid: { left: '4%', right: '8%', bottom: '5%', top: '65px', containLabel: true },
        xAxis: {
          type: 'category',
          boundaryGap: isSinglePoint ? ['35%', '35%'] : false,
          data: data.dates,
          axisLabel: { fontWeight: 600 }
        },
        yAxis: {
          type: 'value',
          scale: true,
          name: s.unit || '',
          splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
        },
        series: [{
          name: `${s.name} (${s.code})`,
          type: 'line',
          smooth: true,
          showSymbol: true,
          showAllSymbol: true,
          symbol: 'circle',
          symbolSize: 10,
          itemStyle: { color: '#0284c7' },
          lineStyle: { width: 3, color: '#0284c7' },
          areaStyle: !isSinglePoint ? {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(2, 132, 199, 0.28)' },
              { offset: 1, color: 'rgba(2, 132, 199, 0.02)' }
            ])
          } : undefined,
          label: {
            show: true,
            position: 'top',
            formatter: '{c}',
            fontWeight: 700,
            fontSize: 12,
            color: '#0369a1'
          },
          data: s.data,
          markLine: markLineOpt
        }]
      };

      this.focusChartInstance.setOption(option, true);
    } catch (err) {
      this.focusChartInstance.hideLoading();
      console.error('Render focus metric error:', err);
    }
  },

  async renderTumorMarkers(codes = ['CEA', 'CA199'], targetUserId = null) {
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

      const isSinglePoint = data.dates.length === 1;

      const seriesList = data.series.map(s => {
        return {
          name: `${s.name} (${s.code})`,
          type: 'line',
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
            formatter: params => (params.value !== null && params.value !== undefined) ? params.value : ''
          },
          data: s.data,
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
          subtext: isSinglePoint ? '💡 当前仅记录了 1 次采样数据（已标明具体测定数值）' : undefined,
          left: 'left',
          textStyle: { fontSize: 15, fontWeight: 600 },
          subtextStyle: { fontSize: 11, color: '#64748b' }
        },
        tooltip: {
          trigger: 'axis',
          formatter: function (params) {
            let res = `<div style="font-weight:600;margin-bottom:4px;">采样日期: ${params[0].axisValue}</div>`;
            params.forEach(p => {
              const val = p.value !== null && p.value !== undefined ? p.value : '未测定';
              res += `<div>${p.marker} ${p.seriesName}: <strong>${val}</strong></div>`;
            });
            return res;
          }
        },
        legend: { top: '30px', type: 'scroll' },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '75px', containLabel: true },
        xAxis: {
          type: 'category',
          boundaryGap: isSinglePoint ? ['25%', '25%'] : false,
          data: data.dates
        },
        yAxis: {
          type: 'value',
          scale: true,
          splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
        },
        series: seriesList
      };

      this.tumorChartInstance.setOption(option, true);
    } catch (err) {
      this.tumorChartInstance.hideLoading();
      console.error('Render tumor markers error:', err);
    }
  },

  async renderSafetyMarkers(codes = ['WBC', 'PLT', 'ALT', 'Cr'], targetUserId = null) {
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

      const isSinglePoint = data.dates.length === 1;

      const seriesList = data.series.map(s => ({
        name: `${s.name} (${s.code})`,
        type: 'line',
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
          formatter: params => (params.value !== null && params.value !== undefined) ? params.value : ''
        },
        data: s.data
      }));

      const option = {
        title: {
          text: '骨髓抑制与肝肾器官安全性动态监控',
          subtext: isSinglePoint ? '💡 当前仅记录了 1 次采样数据（已标明具体测定数值）' : undefined,
          left: 'left',
          textStyle: { fontSize: 15, fontWeight: 600 },
          subtextStyle: { fontSize: 11, color: '#64748b' }
        },
        tooltip: { trigger: 'axis' },
        legend: { top: '30px', type: 'scroll' },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '75px', containLabel: true },
        xAxis: {
          type: 'category',
          boundaryGap: isSinglePoint ? ['25%', '25%'] : false,
          data: data.dates
        },
        yAxis: {
          type: 'value',
          scale: true,
          splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
        },
        series: seriesList
      };

      this.safetyChartInstance.setOption(option, true);
    } catch (err) {
      this.safetyChartInstance.hideLoading();
      console.error('Render safety markers error:', err);
    }
  },

  async renderChronicMarkers(codes = ['GLU', 'HbA1c'], targetUserId = null) {
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

      const isSinglePoint = data.dates.length === 1;

      const seriesList = data.series.map(s => ({
        name: `${s.name} (${s.code})`,
        type: 'line',
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
          formatter: params => (params.value !== null && params.value !== undefined) ? params.value : ''
        },
        data: s.data
      }));

      const option = {
        title: {
          text: '伴随慢性病与代谢指标动态 (血糖/尿酸/蛋白等)',
          subtext: isSinglePoint ? '💡 当前仅记录了 1 次采样数据（已标明具体测定数值）' : undefined,
          left: 'left',
          textStyle: { fontSize: 15, fontWeight: 600 },
          subtextStyle: { fontSize: 11, color: '#64748b' }
        },
        tooltip: { trigger: 'axis' },
        legend: { top: '30px', type: 'scroll' },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '75px', containLabel: true },
        xAxis: {
          type: 'category',
          boundaryGap: isSinglePoint ? ['25%', '25%'] : false,
          data: data.dates
        },
        yAxis: {
          type: 'value',
          scale: true,
          splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } }
        },
        series: seriesList
      };

      this.chronicChartInstance.setOption(option, true);
    } catch (err) {
      this.chronicChartInstance.hideLoading();
      console.error('Render chronic markers error:', err);
    }
  }
};

window.ChartsModule = ChartsModule;

