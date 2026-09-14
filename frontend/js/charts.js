/**
 * MedTrack-Onco ECharts 肿瘤标志物与慢病指标趋势看板
 */

const ChartsModule = {
  tumorChartInstance: null,
  safetyChartInstance: null,
  chronicChartInstance: null,

  async initAll() {
    await this.renderTumorMarkers(['CEA', 'CA199', 'CA125']);
    await this.renderSafetyMarkers(['WBC', 'PLT', 'ALT', 'Cr']);
    await this.renderChronicMarkers(['GLU', 'HbA1c']);

    window.addEventListener('resize', () => {
      if (this.tumorChartInstance) this.tumorChartInstance.resize();
      if (this.safetyChartInstance) this.safetyChartInstance.resize();
      if (this.chronicChartInstance) this.chronicChartInstance.resize();
    });
  },

  async renderTumorMarkers(codes = ['CEA', 'CA199']) {
    const dom = document.getElementById('chart-tumor-markers');
    if (!dom || typeof echarts === 'undefined') return;

    if (!this.tumorChartInstance) {
      this.tumorChartInstance = echarts.init(dom);
    }

    this.tumorChartInstance.showLoading();

    try {
      const data = await API.getChartSeries(codes.join(','));
      this.tumorChartInstance.hideLoading();

      if (!data.dates || data.dates.length === 0 || !data.series || data.series.length === 0) {
        this.tumorChartInstance.setOption({
          title: { text: '暂无肿瘤标志物时序数据 (请先上传或录入化验单)', left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14 } }
        }, true);
        return;
      }

      const seriesList = data.series.map(s => {
        return {
          name: `${s.name} (${s.code})`,
          type: 'line',
          smooth: true,
          data: s.data,
          symbolSize: 8,
          markLine: s.ref_max ? {
            silent: true,
            symbol: 'none',
            data: [{
              yAxis: s.ref_max,
              name: `${s.name}参考上限`,
              lineStyle: { type: 'dashed', color: '#f59e0b' },
              label: { formatter: `${s.code}上限: {c} ${s.unit || ''}` }
            }]
          } : undefined
        };
      });

      const option = {
        title: { text: '肿瘤标志物动态监控演变趋势', left: 'left', textStyle: { fontSize: 15, fontWeight: 600 } },
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
          boundaryGap: false,
          data: data.dates
        },
        yAxis: {
          type: 'value',
          scale: true
        },
        series: seriesList
      };

      this.tumorChartInstance.setOption(option, true);
    } catch (err) {
      this.tumorChartInstance.hideLoading();
      console.error('Render tumor markers error:', err);
    }
  },

  async renderSafetyMarkers(codes = ['WBC', 'PLT', 'ALT', 'Cr']) {
    const dom = document.getElementById('chart-safety-markers');
    if (!dom || typeof echarts === 'undefined') return;

    if (!this.safetyChartInstance) {
      this.safetyChartInstance = echarts.init(dom);
    }

    this.safetyChartInstance.showLoading();

    try {
      const data = await API.getChartSeries(codes.join(','));
      this.safetyChartInstance.hideLoading();

      if (!data.dates || data.dates.length === 0 || !data.series || data.series.length === 0) {
        this.safetyChartInstance.setOption({
          title: { text: '暂无化疗/靶向毒性监控指标数据', left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14 } }
        }, true);
        return;
      }

      const seriesList = data.series.map(s => ({
        name: `${s.name} (${s.code})`,
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: s.data
      }));

      const option = {
        title: { text: '骨髓抑制与肝肾器官安全性动态监控 (WBC/血小板/转氨酶)', left: 'left', textStyle: { fontSize: 15, fontWeight: 600 } },
        tooltip: { trigger: 'axis' },
        legend: { top: '30px', type: 'scroll' },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '75px', containLabel: true },
        xAxis: { type: 'category', boundaryGap: false, data: data.dates },
        yAxis: { type: 'value', scale: true },
        series: seriesList
      };

      this.safetyChartInstance.setOption(option, true);
    } catch (err) {
      this.safetyChartInstance.hideLoading();
      console.error('Render safety markers error:', err);
    }
  },

  async renderChronicMarkers(codes = ['GLU', 'HbA1c']) {
    const dom = document.getElementById('chart-chronic-markers');
    if (!dom || typeof echarts === 'undefined') return;

    if (!this.chronicChartInstance) {
      this.chronicChartInstance = echarts.init(dom);
    }

    this.chronicChartInstance.showLoading();

    try {
      const data = await API.getChartSeries(codes.join(','));
      this.chronicChartInstance.hideLoading();

      if (!data.dates || data.dates.length === 0 || !data.series || data.series.length === 0) {
        this.chronicChartInstance.setOption({
          title: { text: '暂无慢病代谢指标 (血糖/血脂等)', left: 'center', top: 'middle', textStyle: { color: '#94a3b8', fontSize: 14 } }
        }, true);
        return;
      }

      const seriesList = data.series.map(s => ({
        name: `${s.name} (${s.code})`,
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: s.data
      }));

      const option = {
        title: { text: '伴随慢性病指标动态 (血糖/糖化/代谢)', left: 'left', textStyle: { fontSize: 15, fontWeight: 600 } },
        tooltip: { trigger: 'axis' },
        legend: { top: '30px', type: 'scroll' },
        grid: { left: '3%', right: '4%', bottom: '3%', top: '75px', containLabel: true },
        xAxis: { type: 'category', boundaryGap: false, data: data.dates },
        yAxis: { type: 'value', scale: true },
        series: seriesList
      };

      this.chronicChartInstance.setOption(option, true);
    } catch (err) {
      this.chronicChartInstance.hideLoading();
    }
  }
};

window.ChartsModule = ChartsModule;
