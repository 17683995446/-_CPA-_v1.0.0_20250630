// ===== 单知识点知识图谱（多视图） =====
let _mmChart = null;
let _mmCurrentData = null;
let _mmCurrentView = 'mindmap';

async function openMindMap(kpId) {
    const overlay = document.getElementById('viz-mindmap-overlay');
    overlay.classList.add('show');

    try {
        const data = await api('GET', `/api/knowledge/graph/neighbors/${kpId}`);
        _mmCurrentData = data;
        _mmCurrentView = 'mindmap';
        // 重置标签状态
        document.querySelectorAll('.mmh-tab').forEach(t => t.classList.remove('active'));
        document.querySelector('.mmh-tab[data-view="mindmap"]')?.classList.add('active');
        // 等待 DOM 渲染完成后再初始化 ECharts
        await new Promise(r => setTimeout(r, 100));
        renderMmView(data, _mmCurrentView);
    } catch (e) {
        showToast('加载知识图谱失败: ' + e.message, 'error');
        closeMindMap();
    }
}

function switchMmView(view) {
    if (!_mmCurrentData || view === _mmCurrentView) return;
    _mmCurrentView = view;
    document.querySelectorAll('.mmh-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.mmh-tab[data-view="${view}"]`)?.classList.add('active');
    renderMmView(_mmCurrentData, view);
}

function closeMindMap() {
    const overlay = document.getElementById('viz-mindmap-overlay');
    overlay.classList.remove('show');
    if (_mmChart) { _mmChart.dispose(); _mmChart = null; }
    _mmCurrentData = null;
}

// 统一渲染入口
function renderMmView(data, view) {
    const centerNode = data.nodes.find(n => n.role === 'center');
    if (!centerNode) return;

    const subjColor = _vizSubjectColors[centerNode.subject] || '#64748b';
    document.getElementById('mm-title-text').textContent = centerNode.name;
    const subjTag = document.getElementById('mm-subj-tag');
    subjTag.textContent = centerNode.subject;
    subjTag.style.color = subjColor;
    subjTag.style.background = subjColor + '22';

    renderMindMapSidebar(data, centerNode);

    const canvas = document.getElementById('mm-canvas');
    if (_mmChart) { _mmChart.dispose(); _mmChart = null; }
    _mmChart = echarts.init(canvas);

    const roleConfig = {
        center:       { color: subjColor, size: 60, label: '当前知识点' },
        prerequisite: { color: '#3b82f6', size: 40, label: '前置依赖' },
        dependent:    { color: '#10b981', size: 40, label: '后续应用' },
        related:      { color: '#f59e0b', size: 36, label: '关联知识' },
    };

    // 安全过滤：移除引用不存在节点的边（防止 ECharts __original 崩溃）
    const validNodeIds = new Set(data.nodes.map(n => String(n.id)));
    const safeData = {
        ...data,
        edges: data.edges.filter(e =>
            validNodeIds.has(String(e.source)) && validNodeIds.has(String(e.target))
        ),
    };

    let option;
    try {
        switch (view) {
            case 'concept':  option = buildConceptMapOption(safeData, roleConfig, subjColor); break;
            case 'causal':   option = buildCausalDiagramOption(safeData, roleConfig, subjColor); break;
            case 'relation': option = buildRelationGraphOption(safeData, roleConfig, subjColor); break;
            case 'flow':     option = buildFlowChartOption(safeData, roleConfig, subjColor); break;
            default:         option = buildMindMapOption(safeData, roleConfig, subjColor); break;
        }
        _mmChart.setOption(option, true);
    } catch (e) {
        console.error('知识图谱渲染错误:', e);
        // 降级渲染：仅显示节点，不显示边
        try {
            const fallbackNodes = safeData.nodes.map(n => {
                const cfg = roleConfig[n.role] || roleConfig.related;
                return { id: String(n.id), name: n.name, symbolSize: cfg.size, itemStyle: { color: cfg.color }, label: { show: true }, _kpData: n };
            });
            _mmChart.setOption({ series: [{ type: 'graph', layout: 'force', data: fallbackNodes, links: [], roam: true }] }, true);
        } catch (e2) { console.error('降级渲染也失败:', e2); }
    }

    if (!_mmChart._resizeBound) {
        window.addEventListener('resize', () => { if (_mmChart) _mmChart.resize(); });
        _mmChart._resizeBound = true;
    }

    // 通用交互
    _mmChart.off('click');
    _mmChart.on('click', function(params) {
        if (params.dataType === 'node' && params.data._kpData && params.data._kpData.role !== 'center') {
            openMindMap(params.data._kpData.id);
        }
    });
    _mmChart.off('dblclick');
    _mmChart.on('dblclick', function(params) {
        if (params.dataType === 'node' && params.data._kpData) {
            const kp = params.data._kpData;
            closeMindMap();
            closeVizDetail();
            showPage('study');
            setTimeout(() => startStudy(kp.id, kp.code, kp.subject), 300);
        }
    });
}

// 通用 tooltip
function mmTooltip() {
    return {
        formatter: function(params) {
            if (params.dataType === 'node' && params.data._kpData) {
                const d = params.data._kpData;
                const mastery = _vizMasteryMap[d.id] || {};
                const level = mastery.mastery_level || 'unknown';
                const levelLabel = { unknown: '未学习', learning: '学习中', mastering: '较熟练', mastered: '已掌握' };
                const stars = '★'.repeat(d.difficulty || 3) + '☆'.repeat(5 - (d.difficulty || 3));
                return `<div style="font-weight:700;font-size:13px">${d.name}</div>
                    <div style="font-size:11px;color:#64748b">${d.code} | ${d.subject}</div>
                    <div style="font-size:11px;margin-top:2px">难度: ${stars}</div>
                    <div style="font-size:11px;color:${_vizMasteryColors[level]}">掌握度: ${levelLabel[level]}</div>`;
            }
        },
    };
}

// 通用 legend
function mmLegend(roleConfig) {
    return {
        data: Object.values(roleConfig).map(c => c.label),
        bottom: 10,
        textStyle: { fontSize: 11 },
    };
}

// 构建节点公共属性
function buildMmNode(n, roleConfig) {
    const cfg = roleConfig[n.role] || roleConfig.related;
    const mastery = _vizMasteryMap[n.id] || {};
    const level = mastery.mastery_level || 'unknown';
    const masteryColor = _vizMasteryColors[level] || '#94a3b8';
    return {
        id: String(n.id),
        name: n.name,
        symbolSize: cfg.size,
        itemStyle: {
            color: cfg.color,
            borderColor: n.role === 'center' ? masteryColor : cfg.color,
            borderWidth: n.role === 'center' ? 4 : 2,
            shadowBlur: 12,
            shadowColor: cfg.color + '44',
        },
        label: {
            show: true,
            position: n.role === 'center' ? 'inside' : 'bottom',
            fontSize: n.role === 'center' ? 14 : 11,
            fontWeight: n.role === 'center' ? 700 : 500,
            color: n.role === 'center' ? '#fff' : '#475569',
            formatter: () => {
                const name = n.name || n.code;
                return name.length > 10 ? name.slice(0, 9) + '…' : name;
            },
        },
        category: cfg.label,
        _kpData: n,
    };
}

// 构建边公共属性
function buildMmEdge(e, directed) {
    const isPrereq = e.label === '前置依赖';
    return {
        source: String(e.source),
        target: String(e.target),
        label: {
            show: true,
            formatter: e.label,
            fontSize: 10,
            color: '#94a3b8',
            backgroundColor: 'rgba(255,255,255,0.8)',
            padding: [2, 6],
            borderRadius: 4,
        },
        lineStyle: {
            color: isPrereq ? '#3b82f6' : (e.label === '后续应用' ? '#10b981' : '#f59e0b'),
            width: 2,
            curveness: 0.2,
            opacity: 0.7,
        },
        symbol: directed ? ['none', 'arrow'] : ['none', 'none'],
        symbolSize: 7,
    };
}

// ===== 1. 思维导图（放射状） =====
function buildMindMapOption(data, roleConfig, subjColor) {
    const centerX = 360, centerY = 200;
    const prerequisites = data.nodes.filter(n => n.role === 'prerequisite');
    const dependents = data.nodes.filter(n => n.role === 'dependent');
    const related = data.nodes.filter(n => n.role === 'related');

    data.nodes.forEach(n => {
        if (n.role === 'center') { n._mmX = centerX; n._mmY = centerY; }
    });
    prerequisites.forEach((n, i) => {
        const angle = Math.PI + (Math.PI / Math.max(prerequisites.length, 1)) * (i + 0.5);
        n._mmX = centerX + Math.cos(angle) * 180;
        n._mmY = centerY + Math.sin(angle) * 130;
    });
    dependents.forEach((n, i) => {
        const angle = (Math.PI / Math.max(dependents.length, 1)) * (i + 0.5);
        n._mmX = centerX + Math.cos(angle) * 180;
        n._mmY = centerY + Math.sin(angle) * 130;
    });
    related.forEach((n, i) => {
        const angle = -Math.PI / 2 + ((Math.PI / 2) / Math.max(related.length, 1)) * (i + 0.5) - Math.PI / 4;
        n._mmX = centerX + Math.cos(angle) * 160;
        n._mmY = centerY + Math.sin(angle) * 120;
    });

    const nodes = data.nodes.map(n => { const nd = buildMmNode(n, roleConfig); nd.x = n._mmX; nd.y = n._mmY; return nd; });
    const links = data.edges.map(e => buildMmEdge(e, true));
    const categories = Object.entries(roleConfig).map(([, cfg]) => ({ name: cfg.label }));

    return {
        tooltip: mmTooltip(),
        legend: mmLegend(roleConfig),
        series: [{
            type: 'graph', layout: 'none', data: nodes, links: links,
            categories: categories, roam: true, draggable: true,
            emphasis: { focus: 'adjacency', lineStyle: { width: 3, opacity: 1 } },
        }],
    };
}

// ===== 2. 概念图（层级树形） =====
function buildConceptMapOption(data, roleConfig, subjColor) {
    const prerequisites = data.nodes.filter(n => n.role === 'prerequisite');
    const dependents = data.nodes.filter(n => n.role === 'dependent');
    const related = data.nodes.filter(n => n.role === 'related');
    const centerNode = data.nodes.find(n => n.role === 'center');

    // 构建 ECharts tree 数据结构
    // 中心节点作为根，前置在上层，后续在下层，关联并排
    const childNodes = [
        ...dependents.map(n => ({
            name: n.name,
            value: n,
            itemStyle: { color: roleConfig.dependent.color, borderColor: roleConfig.dependent.color },
            label: { fontSize: 11, color: '#475569' },
            children: [],
        })),
        ...related.map(n => ({
            name: n.name,
            value: n,
            itemStyle: { color: roleConfig.related.color, borderColor: roleConfig.related.color },
            label: { fontSize: 11, color: '#475569' },
            children: [],
        })),
    ];

    const rootData = [{
        name: centerNode.name,
        value: centerNode,
        itemStyle: { color: subjColor, borderColor: _vizMasteryColors[(_vizMasteryMap[centerNode.id]||{}).mastery_level || 'unknown'] || '#94a3b8', borderWidth: 4 },
        label: { fontSize: 14, fontWeight: 700, color: '#fff' },
        children: childNodes,
    }];

    // 如果有前置依赖，作为上层父节点
    if (prerequisites.length > 0) {
        rootData[0] = {
            name: prerequisites.length === 1 ? prerequisites[0].name : '前置知识群',
            value: prerequisites[0],
            itemStyle: { color: roleConfig.prerequisite.color, borderColor: roleConfig.prerequisite.color },
            label: { fontSize: 12, color: '#fff' },
            children: [
                ...(prerequisites.length > 1 ? prerequisites.map(n => ({
                    name: n.name, value: n,
                    itemStyle: { color: roleConfig.prerequisite.color },
                    label: { fontSize: 11, color: '#475569' },
                    children: [],
                })) : []),
                rootData[0],
            ],
        };
    }

    return {
        tooltip: {
            formatter: function(params) {
                const d = params.data.value;
                if (d && d.id) {
                    const mastery = _vizMasteryMap[d.id] || {};
                    const level = mastery.mastery_level || 'unknown';
                    const levelLabel = { unknown: '未学习', learning: '学习中', mastering: '较熟练', mastered: '已掌握' };
                    const stars = '★'.repeat(d.difficulty || 3) + '☆'.repeat(5 - (d.difficulty || 3));
                    return `<div style="font-weight:700;font-size:13px">${d.name}</div>
                        <div style="font-size:11px;color:#64748b">${d.code} | ${d.subject}</div>
                        <div style="font-size:11px;margin-top:2px">难度: ${stars}</div>
                        <div style="font-size:11px;color:${_vizMasteryColors[level]}">掌握度: ${levelLabel[level]}</div>`;
                }
                return params.name;
            },
        },
        legend: { bottom: 10, textStyle: { fontSize: 11 }, data: Object.values(roleConfig).map(c => c.label) },
        series: [{
            type: 'tree',
            data: rootData,
            top: '5%',
            left: '10%',
            bottom: '15%',
            right: '20%',
            symbolSize: 12,
            orient: 'TB',
            initialTreeDepth: -1,
            label: { position: 'top', verticalAlign: 'middle', align: 'center', fontSize: 11 },
            leaves: { label: { position: 'bottom', verticalAlign: 'middle', align: 'center' } },
            emphasis: { focus: 'descendant' },
            expandAndCollapse: true,
            animationDuration: 550,
            animationDurationUpdate: 750,
            lineStyle: { color: '#cbd5e1', width: 2 },
            roam: true,
        }],
    };
}

// ===== 3. 因果图（因果链，左→右方向） =====
function buildCausalDiagramOption(data, roleConfig, subjColor) {
    const prerequisites = data.nodes.filter(n => n.role === 'prerequisite');
    const dependents = data.nodes.filter(n => n.role === 'dependent');
    const related = data.nodes.filter(n => n.role === 'related');
    const centerNode = data.nodes.find(n => n.role === 'center');

    const canvasW = 720, canvasH = 473;
    const colX = { left: 120, center: 360, right: 600 };
    const centerY = canvasH / 2;

    // 前置在左列，中心在中列，后续在右列，关联在中列上下
    data.nodes.forEach(n => {
        if (n.role === 'center') { n._mmX = colX.center; n._mmY = centerY; }
    });
    prerequisites.forEach((n, i) => {
        const total = prerequisites.length;
        n._mmX = colX.left;
        n._mmY = centerY - (total - 1) * 35 + i * 70;
    });
    dependents.forEach((n, i) => {
        const total = dependents.length;
        n._mmX = colX.right;
        n._mmY = centerY - (total - 1) * 35 + i * 70;
    });
    related.forEach((n, i) => {
        const total = related.length;
        n._mmX = colX.center;
        n._mmY = 40 + i * 35;
    });

    const nodes = data.nodes.map(n => {
        const nd = buildMmNode(n, roleConfig);
        nd.x = n._mmX; nd.y = n._mmY;
        // 因果图中使用矩形节点
        if (n.role === 'center') {
            nd.symbol = 'roundRect';
            nd.symbolSize = [120, 50];
            nd.label.position = 'inside';
        } else if (n.role === 'prerequisite' || n.role === 'dependent') {
            nd.symbol = 'roundRect';
            nd.symbolSize = [100, 36];
        }
        return nd;
    });

    // 因果边：所有边都有方向箭头，强调因果
    const links = data.edges.map(e => {
        const edge = buildMmEdge(e, true);
        edge.lineStyle.curveness = 0.15;
        edge.lineStyle.width = 2.5;
        // 因果关系标注
        const causalLabel = e.label === '前置依赖' ? '导致' : (e.label === '后续应用' ? '引发' : '影响');
        edge.label.formatter = causalLabel;
        edge.label.fontWeight = 600;
        return edge;
    });

    const categories = Object.entries(roleConfig).map(([, cfg]) => ({ name: cfg.label }));

    return {
        tooltip: mmTooltip(),
        legend: mmLegend(roleConfig),
        series: [{
            type: 'graph', layout: 'none', data: nodes, links: links,
            categories: categories, roam: true, draggable: true,
            emphasis: { focus: 'adjacency', lineStyle: { width: 3, opacity: 1 } },
        }],
        graphic: [
            { type: 'text', left: colX.left - 30, top: 10, style: { text: '原因 / 前置', fontSize: 11, fill: '#3b82f6', fontWeight: 600 } },
            { type: 'text', left: colX.center - 25, top: 10, style: { text: '核心概念', fontSize: 11, fill: subjColor, fontWeight: 600 } },
            { type: 'text', left: colX.right - 30, top: 10, style: { text: '结果 / 后续', fontSize: 11, fill: '#10b981', fontWeight: 600 } },
        ],
    };
}

// ===== 4. 关系图（无向力导向网络） =====
function buildRelationGraphOption(data, roleConfig, subjColor) {
    const nodes = data.nodes.map(n => {
        const nd = buildMmNode(n, roleConfig);
        // 关系图用圆形节点，稍大
        nd.symbolSize = n.role === 'center' ? 55 : 38;
        nd.label.position = 'bottom';
        if (n.role === 'center') {
            nd.label.position = 'inside';
            nd.label.color = '#fff';
        }
        return nd;
    });

    // 无向边：去掉箭头
    const links = data.edges.map(e => {
        const edge = buildMmEdge(e, false);
        edge.lineStyle.curveness = 0.3;
        edge.lineStyle.width = 2;
        edge.lineStyle.opacity = 0.5;
        edge.label.show = false; // 关系图隐藏边标签，减少视觉干扰
        return edge;
    });

    const categories = Object.entries(roleConfig).map(([, cfg]) => ({ name: cfg.label }));

    return {
        tooltip: mmTooltip(),
        legend: mmLegend(roleConfig),
        series: [{
            type: 'graph', layout: 'force', data: nodes, links: links,
            categories: categories, roam: true, draggable: true,
            emphasis: { focus: 'adjacency', lineStyle: { width: 4, opacity: 1 }, label: { show: true } },
            force: { repulsion: 350, edgeLength: [80, 160], gravity: 0.08, layoutAnimation: true },
            label: { show: true },
        }],
    };
}

// ===== 5. 流程图（学习路径，顺序步骤） =====
function buildFlowChartOption(data, roleConfig, subjColor) {
    const prerequisites = data.nodes.filter(n => n.role === 'prerequisite');
    const dependents = data.nodes.filter(n => n.role === 'dependent');
    const related = data.nodes.filter(n => n.role === 'related');
    const centerNode = data.nodes.find(n => n.role === 'center');

    // 构建学习路径：前置1 → 前置2 → ... → 中心 → 后续1 → 后续2 → ...
    const pathNodes = [...prerequisites, centerNode, ...dependents];
    const canvasW = 720, canvasH = 473;
    const cols = pathNodes.length;
    const colWidth = Math.min(160, (canvasW - 80) / Math.max(cols, 1));

    const nodes = pathNodes.map((n, i) => {
        const cfg = roleConfig[n.role] || roleConfig.center;
        const mastery = _vizMasteryMap[n.id] || {};
        const level = mastery.mastery_level || 'unknown';
        const masteryColor = _vizMasteryColors[level] || '#94a3b8';
        const isCenter = n.role === 'center';
        return {
            id: String(n.id),
            name: n.name,
            symbol: 'roundRect',
            symbolSize: isCenter ? [130, 55] : [110, 42],
            x: 60 + i * colWidth + (isCenter ? 65 : 55),
            y: canvasH / 2,
            itemStyle: {
                color: cfg.color,
                borderColor: isCenter ? masteryColor : cfg.color,
                borderWidth: isCenter ? 4 : 2,
                shadowBlur: 10,
                shadowColor: cfg.color + '44',
                borderRadius: 8,
            },
            label: {
                show: true,
                position: 'inside',
                fontSize: isCenter ? 13 : 11,
                fontWeight: isCenter ? 700 : 500,
                color: '#fff',
                formatter: () => {
                    const name = n.name || n.code;
                    return name.length > 8 ? name.slice(0, 7) + '…' : name;
                },
            },
            category: cfg.label,
            _kpData: n,
        };
    });

    // 流程箭头：顺序连接
    const links = [];
    for (let i = 0; i < pathNodes.length - 1; i++) {
        const from = pathNodes[i];
        const to = pathNodes[i + 1];
        const isEnteringCenter = to.role === 'center';
        const isLeavingCenter = from.role === 'center';
        links.push({
            source: String(from.id),
            target: String(to.id),
            label: {
                show: true,
                formatter: isEnteringCenter ? '先学' : (isLeavingCenter ? '再学' : '→'),
                fontSize: 10,
                color: '#64748b',
                backgroundColor: 'rgba(255,255,255,0.9)',
                padding: [2, 6],
                borderRadius: 4,
            },
            lineStyle: {
                color: isEnteringCenter ? '#3b82f6' : (isLeavingCenter ? '#10b981' : '#94a3b8'),
                width: 2.5,
                curveness: 0,
                opacity: 0.8,
                type: 'solid',
            },
            symbol: ['none', 'arrow'],
            symbolSize: 10,
        });
    }

    // 关联知识点放在上下方，用虚线连接
    related.forEach((n, i) => {
        const cfg = roleConfig.related;
        nodes.push({
            id: String(n.id),
            name: n.name,
            symbol: 'circle',
            symbolSize: 30,
            x: 200 + i * 120,
            y: 60,
            itemStyle: { color: cfg.color, shadowBlur: 8, shadowColor: cfg.color + '44' },
            label: { show: true, position: 'bottom', fontSize: 10, color: '#475569',
                formatter: () => { const name = n.name || n.code; return name.length > 8 ? name.slice(0, 7) + '…' : name; } },
            category: cfg.label,
            _kpData: n,
        });
        links.push({
            source: String(n.id),
            target: String(centerNode.id),
            label: { show: false },
            lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed', curveness: 0.3, opacity: 0.5 },
            symbol: ['none', 'none'],
        });
    });

    const categories = Object.entries(roleConfig).map(([, cfg]) => ({ name: cfg.label }));

    return {
        tooltip: mmTooltip(),
        legend: mmLegend(roleConfig),
        series: [{
            type: 'graph', layout: 'none', data: nodes, links: links,
            categories: categories, roam: true, draggable: true,
            emphasis: { focus: 'adjacency', lineStyle: { width: 3, opacity: 1 } },
        }],
        graphic: [
            { type: 'text', left: 20, top: canvasH / 2 - 50, style: { text: '📖 学习路径', fontSize: 12, fill: '#64748b', fontWeight: 600 } },
            ...(related.length > 0 ? [{ type: 'text', left: 20, top: 35, style: { text: '💡 拓展关联', fontSize: 11, fill: '#f59e0b', fontWeight: 600 } }] : []),
        ],
    };
}

function renderMindMapSidebar(data, centerNode) {
    const sidebar = document.getElementById('mm-sidebar');
    const subjColor = _vizSubjectColors[centerNode.subject] || '#64748b';
    const mastery = _vizMasteryMap[centerNode.id] || {};
    const level = mastery.mastery_level || 'unknown';
    const levelLabel = { unknown: '未学习', learning: '学习中', mastering: '较熟练', mastered: '已掌握' };
    const stars = '★'.repeat(centerNode.difficulty || 3) + '☆'.repeat(5 - (centerNode.difficulty || 3));

    const prerequisites = data.nodes.filter(n => n.role === 'prerequisite');
    const dependents = data.nodes.filter(n => n.role === 'dependent');
    const related = data.nodes.filter(n => n.role === 'related');

    function sectionHtml(title, icon, items, relColor) {
        if (items.length === 0) {
            return `<div class="mm-sidebar-section">
                <div class="mm-sidebar-title">${icon} ${title}</div>
                <div class="mm-empty">暂无</div>
            </div>`;
        }
        return `<div class="mm-sidebar-section">
            <div class="mm-sidebar-title">${icon} ${title}（${items.length}）</div>
            ${items.map(n => `
                <div class="mm-kp-item" onclick="openMindMap(${n.id})">
                    <span class="mm-kp-code" style="color:${_vizSubjectColors[n.subject]||'#64748b'}">${n.code}</span>
                    <span class="mm-kp-name">${n.name}</span>
                </div>
            `).join('')}
        </div>`;
    }

    sidebar.innerHTML = `
        <div class="mm-info-card">
            <div style="font-size:14px;font-weight:700;color:${subjColor}">${centerNode.name}</div>
            <div style="font-size:11px;color:var(--text-lighter);margin-top:2px">${centerNode.code} | ${centerNode.chapter || ''}</div>
            ${centerNode.description ? `<div class="mm-info-desc">${centerNode.description}</div>` : ''}
            <div class="mm-info-diff">难度: ${stars} | 掌握度: <span style="color:${_vizMasteryColors[level]}">${levelLabel[level]}</span></div>
        </div>
        ${sectionHtml('前置依赖', '📘', prerequisites, '#3b82f6')}
        ${sectionHtml('后续应用', '📗', dependents, '#10b981')}
        ${sectionHtml('关联知识', '📙', related, '#f59e0b')}
        <div style="margin-top:16px;padding-top:12px;border-top:1px solid var(--border)">
            <div style="font-size:11px;color:var(--text-lighter);line-height:1.6">
                💡 <b>单击</b>节点切换图谱<br>
                💡 <b>双击</b>节点跳转学习<br>
                💡 可拖拽、缩放图谱<br>
                💡 顶部切换5种视图模式
            </div>
        </div>
    `;
}
