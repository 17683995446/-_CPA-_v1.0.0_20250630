// charts.js — 创新点可行性-新颖度矩阵 + Mermaid 初始化
(function () {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // ---- Mermaid 初始化 ----
  if (window.mermaid) {
    mermaid.initialize({
      startOnLoad: true,
      theme: 'neutral',
      securityLevel: 'loose',
      flowchart: { useMaxWidth: true, htmlLabels: true, curve: 'basis' }
    });
  }

  // ---- 创新点可行性-新颖度矩阵（散点/气泡图）----
  var chartEl = document.getElementById('chart-matrix');
  if (chartEl && window.echarts) {
    var chart = echarts.init(chartEl, null, { renderer: 'svg' });

    // 数据：[可行性(x), 新颖度(y), 优先级(气泡大小), 名称, 是否重点]
    // 重点创新点(1-4) 用 accent2 色，其余用 accent 色
    var data = [
      { value: [8.5, 9, 9], name: '① 知识追踪掌握度画像', star: true },
      { value: [9, 9, 9], name: '② AI出题+FSRS闭环', star: true },
      { value: [7, 9.5, 8], name: '③ 分录判错/审计模拟', star: true },
      { value: [8.5, 8.5, 8], name: '④ 疲劳感知调度', star: true },
      { value: [8, 7.5, 7], name: '⑤ 跨科知识图谱联动', star: false },
      { value: [8.5, 7.5, 7], name: '⑥ 考纲变动追踪', star: false },
      { value: [8, 6.5, 6.5], name: '⑦ 情境化命题生成', star: false },
      { value: [6.5, 7.5, 6.5], name: '⑧ 预测分', star: false },
      { value: [8.5, 6, 6], name: '⑨ 苏格拉底追问辅导', star: false },
      { value: [9, 5.5, 5.5], name: '⑩ 离线TTS听课', star: false },
      { value: [6, 8.5, 7], name: '⑪ TBS自动评分', star: false },
      { value: [8.5, 6, 6], name: '⑫ 错题变式题生成', star: false }
    ];

    var starData = data.filter(function (d) { return d.star; });
    var normalData = data.filter(function (d) { return !d.star; });

    chart.setOption({
      animation: false,
      backgroundColor: 'transparent',
      grid: { left: 70, right: 40, top: 50, bottom: 70 },
      tooltip: {
        appendToBody: true,
        formatter: function (p) {
          var d = p.data;
          return '<b>' + d.name + '</b><br/>可行性: ' + d.value[0] + ' / 10<br/>新颖度: ' + d.value[1] + ' / 10';
        }
      },
      xAxis: {
        type: 'value',
        name: '可行性（越靠右越高）→',
        nameLocation: 'middle',
        nameGap: 38,
        nameTextStyle: { color: muted, fontSize: 12, fontWeight: 600 },
        min: 5,
        max: 10,
        splitLine: { show: true, lineStyle: { color: rule, type: 'dashed' } },
        axisLine: { lineStyle: { color: rule } },
        axisLabel: { color: muted, fontSize: 11 }
      },
      yAxis: {
        type: 'value',
        name: '↑ 新颖度（越靠上越高）',
        nameLocation: 'middle',
        nameGap: 50,
        nameTextStyle: { color: muted, fontSize: 12, fontWeight: 600 },
        min: 4,
        max: 10,
        splitLine: { show: true, lineStyle: { color: rule, type: 'dashed' } },
        axisLine: { lineStyle: { color: rule } },
        axisLabel: { color: muted, fontSize: 11 }
      },
      series: [
        {
          name: '重点创新',
          type: 'scatter',
          symbolSize: function (d) { return d[2] * 10; },
          data: starData,
          itemStyle: {
            color: accent2,
            opacity: 0.82,
            borderColor: accent2,
            borderWidth: 2,
            shadowBlur: 8,
            shadowColor: 'rgba(180,83,9,0.3)'
          },
          label: {
            show: true,
            formatter: function (p) { return p.data.name; },
            position: 'top',
            color: ink,
            fontSize: 11,
            fontWeight: 700,
            distance: 8,
            width: 140,
            overflow: 'break',
            lineHeight: 13
          }
        },
        {
          name: '其他创新',
          type: 'scatter',
          symbolSize: function (d) { return d[2] * 9; },
          data: normalData,
          itemStyle: {
            color: accent,
            opacity: 0.6,
            borderColor: accent,
            borderWidth: 1.2
          },
          label: {
            show: true,
            formatter: function (p) { return p.data.name; },
            position: 'top',
            color: muted,
            fontSize: 10,
            fontWeight: 600,
            distance: 8,
            width: 130,
            overflow: 'break',
            lineHeight: 12
          }
        }
      ],
      graphic: [
        {
          type: 'text',
          right: 80,
          top: 68,
          z: 100,
          style: {
            text: '高可行 · 高新颖\n（优先切入）',
            fill: accent2,
            fontSize: 11,
            fontWeight: 700,
            textAlign: 'center',
            lineHeight: 14
          }
        }
      ]
    });

    window.addEventListener('resize', function () { chart.resize(); });
  }
})();
