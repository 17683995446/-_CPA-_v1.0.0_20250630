// ===== 知识图谱页面 =====
let _allKnowledgeKPs = [];
let _knowledgeFilter = 'all';
let _knowledgeSearch = '';

function filterKnowledgePage(subject, btn) {
    _knowledgeFilter = subject;
    document.querySelectorAll('#kp-subject-filter .filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    renderKnowledgeKPs();
}

function filterKnowledgeBySearch() {
    _knowledgeSearch = document.getElementById('kp-search').value.trim().toLowerCase();
    renderKnowledgeKPs();
}

function renderKnowledgeKPs() {
    const listEl = document.getElementById('kp-list-display');
    let kps = _allKnowledgeKPs;
    if (_knowledgeFilter !== 'all') {
        kps = kps.filter(kp => kp.subject === _knowledgeFilter);
    }
    if (_knowledgeSearch) {
        kps = kps.filter(kp =>
            (kp.name || '').toLowerCase().includes(_knowledgeSearch) ||
            (kp.code || '').toLowerCase().includes(_knowledgeSearch) ||
            (kp.chapter || '').toLowerCase().includes(_knowledgeSearch) ||
            (kp.description || '').toLowerCase().includes(_knowledgeSearch)
        );
    }
    if (kps.length === 0) {
        listEl.innerHTML = '<div class="empty-state"><div class="icon">🔍</div><h3>未找到匹配的知识点</h3><p>尝试更换关键词或筛选条件</p></div>';
        return;
    }
    // 按科目分组
    const subjects = {};
    kps.forEach(kp => {
        if (!subjects[kp.subject]) subjects[kp.subject] = [];
        subjects[kp.subject].push(kp);
    });
    let html = '';
    for (const [subject, kpList] of Object.entries(subjects)) {
        html += `<div class="kp-group-header subj-${subject}"><span>${subject}</span><span class="kp-group-count">${kpList.length} 个知识点</span></div>`;
        kpList.forEach(kp => {
            const stars = '★'.repeat(kp.difficulty) + '☆'.repeat(5 - kp.difficulty);
            const desc = kp.description || kp.chapter || '';
            html += `
                <div class="kp-item-enhanced subj-${kp.subject}" onclick="startStudyFromKnowledge(${kp.id}, '${kp.code}', '${kp.subject}')" style="margin-bottom:8px">
                    <span class="kp-subj-tag">${kp.code}</span>
                    <div class="kp-body">
                        <div class="kp-title">${kp.name}</div>
                        <div class="kp-desc">${desc}</div>
                    </div>
                    <span class="kp-diff-stars" style="color:var(--warning)">${stars}</span>
                </div>
            `;
        });
    }
    listEl.innerHTML = html;
}

function startStudyFromKnowledge(kpId, kpCode, kpSubject) {
    showPage('study');
    setTimeout(() => startStudy(kpId, kpCode, kpSubject), 200);
}

async function loadKnowledgePage() {
    try {
        const kps = await api('GET', '/api/knowledge/points');
        _allKnowledgeKPs = kps;
        _knowledgeFilter = 'all';
        _knowledgeSearch = '';
        document.getElementById('kp-search').value = '';
        document.querySelectorAll('#kp-subject-filter .filter-btn').forEach(b => b.classList.remove('active'));
        document.querySelector('#kp-subject-filter .filter-btn').classList.add('active');
        renderKnowledgeKPs();
        // 渲染知识图谱图表
        renderKnowledgeCharts(kps);
    } catch (e) {
        showToast('加载知识点失败', 'error');
    }
}

async function addKnowledgePoint() {
    const code = document.getElementById('kp-code').value.trim();
    const name = document.getElementById('kp-name').value.trim();
    const subject = document.getElementById('kp-subject').value;
    const chapter = document.getElementById('kp-chapter').value.trim();

    if (!code || !name || !chapter) {
        showToast('请填写所有字段', 'error');
        return;
    }

    try {
        await api('POST', '/api/knowledge/points', { code, name, subject, chapter, difficulty: 3 });
        showToast('知识点添加成功', 'success');
        document.getElementById('kp-code').value = '';
        document.getElementById('kp-name').value = '';
        document.getElementById('kp-chapter').value = '';
        loadKnowledgePage();
    } catch (e) {
        showToast('添加失败: ' + e.message, 'error');
    }
}

// ===== 知识可视化页面 =====
let _vizChart = null;
let _vizGraphData = null;      // {nodes, edges} from API
let _vizMasteryMap = null;     // {kp_id: masteryItem}
let _vizKpMap = null;          // {kp_id: node}
let _vizSubjectFilter = 'all';
let _vizLayout = 'force';
const _vizSubjectColors = {
    '会计': '#6366f1',
    '审计': '#ec4899',
    '财务成本管理': '#10b981',
    '公司战略与风险管理': '#f59e0b',
    '经济法': '#3b82f6',
    '税法': '#8b5cf6',
};
const _vizMasteryColors = {
    'unknown': '#94a3b8',
    'learning': '#f59e0b',
    'mastering': '#3b82f6',
    'mastered': '#10b981',
};

function vizFilterSubject(subject, btn) {
    _vizSubjectFilter = subject;
    document.querySelectorAll('.viz-toolbar .viz-layout-btn').forEach(b => {
        if (b.textContent === '全部' || b.textContent === '会计' || b.textContent === '审计' ||
            b.textContent === '财管' || b.textContent === '战略' || b.textContent === '经济法' || b.textContent === '税法') {
            b.classList.remove('active');
        }
    });
    if (btn) btn.classList.add('active');
    renderVizGraph();
}

function vizSetLayout(layout, btn) {
    _vizLayout = layout;
    document.querySelectorAll('.viz-toolbar .viz-layout-btn').forEach(b => {
        if (b.textContent === '力导向' || b.textContent === '环形' || b.textContent === '树形') {
            b.classList.remove('active');
        }
    });
    if (btn) btn.classList.add('active');
    renderVizGraph();
}

function closeVizDetail() {
    document.getElementById('viz-detail-panel').classList.remove('show');
}

async function loadKnowledgeVizPage() {
    if (!currentUser) return;
    try {
        // 并发获取图谱数据和掌握度数据
        const [graphData, masteryData] = await Promise.all([
            api('GET', '/api/knowledge/graph'),
            api('GET', `/api/mastery/${currentUser.id}/all`),
        ]);

        _vizGraphData = graphData;
        _vizMasteryMap = {};
        masteryData.items.forEach(item => {
            _vizMasteryMap[item.knowledge_point_id] = item;
        });
        _vizKpMap = {};
        graphData.nodes.forEach(n => { _vizKpMap[n.id] = n; });

        // 更新统计卡片
        document.getElementById('viz-total-kps').textContent = graphData.nodes.length;
        document.getElementById('viz-total-edges').textContent = graphData.edges.length;
        document.getElementById('viz-answered-kps').textContent = masteryData.answered_kps;
        const avgMastery = masteryData.items.length > 0
            ? Math.round(masteryData.items.reduce((s, i) => s + i.p_known, 0) / masteryData.items.length * 100)
            : 0;
        document.getElementById('viz-avg-mastery').textContent = avgMastery + '%';

        renderVizGraph();
    } catch (e) {
        showToast('加载知识可视化失败: ' + e.message, 'error');
    }
}

function renderVizGraph() {
    if (!_vizGraphData) return;

    const chartDom = document.getElementById('viz-canvas');
    if (_vizChart) { _vizChart.dispose(); _vizChart = null; }
    _vizChart = echarts.init(chartDom);

    // 筛选节点和边
    let nodes = _vizGraphData.nodes;
    let edges = _vizGraphData.edges;
    if (_vizSubjectFilter !== 'all') {
        const filteredIds = new Set(nodes.filter(n => n.subject === _vizSubjectFilter).map(n => n.id));
        nodes = nodes.filter(n => filteredIds.has(n.id));
        edges = edges.filter(e => filteredIds.has(e.source) && filteredIds.has(e.target));
    }

    // 数据验证：过滤掉引用不存在节点的边（防止 ECharts 内部错误）
    const nodeIdSet = new Set(nodes.map(n => String(n.id)));
    edges = edges.filter(e => nodeIdSet.has(String(e.source)) && nodeIdSet.has(String(e.target)));

    // 构造 ECharts 节点
    const echartsNodes = nodes.map(n => {
        const mastery = _vizMasteryMap[n.id] || {};
        const pKnown = mastery.p_known ?? 0.1;
        const level = mastery.mastery_level || 'unknown';
        const subjColor = _vizSubjectColors[n.subject] || '#64748b';
        const masteryColor = _vizMasteryColors[level] || '#94a3b8';
        const symbolSize = 25 + (n.difficulty || 3) * 6; // 难度越大节点越大

        return {
            id: String(n.id),
            name: n.label || n.name || n.code,
            symbolSize: symbolSize,
            category: n.subject,
            itemStyle: {
                color: subjColor,
                borderColor: masteryColor,
                borderWidth: 3,
                shadowBlur: 10,
                shadowColor: masteryColor + '66',
            },
            label: {
                show: true,
                position: 'bottom',
                fontSize: 11,
                color: '#475569',
                formatter: () => {
                    const name = n.name || n.label || n.code;
                    return name.length > 8 ? name.slice(0, 7) + '…' : name;
                },
            },
            _kpData: n,
            _mastery: mastery,
            _pKnown: pKnown,
            _level: level,
        };
    });

    // 构造 ECharts 边
    const echartsEdges = edges.map(e => ({
        source: String(e.source),
        target: String(e.target),
        lineStyle: {
            color: '#cbd5e1',
            width: 1.5,
            curveness: 0.15,
            opacity: 0.6,
        },
        symbol: ['none', 'arrow'],
        symbolSize: 8,
    }));

    // 布局配置
    let layoutConfig;
    if (_vizLayout === 'force') {
        layoutConfig = 'force';
    } else if (_vizLayout === 'circular') {
        layoutConfig = 'circular';
    } else {
        layoutConfig = 'none';
    }

    // 科目分类
    const categories = Object.keys(_vizSubjectColors).map(s => ({ name: s }));

    const option = {
        tooltip: {
            formatter: function(params) {
                if (params.dataType === 'node') {
                    const d = params.data._kpData;
                    const m = params.data._mastery;
                    const pKnown = params.data._pKnown;
                    const level = params.data._level;
                    const levelLabel = { unknown: '未学习', learning: '学习中', mastering: '较熟练', mastered: '已掌握' };
                    return `<div style="font-weight:700;font-size:13px;margin-bottom:4px">${d.name || d.label}</div>
                        <div style="font-size:12px;color:#64748b">${d.code} | ${d.subject} | ${d.chapter || ''}</div>
                        <div style="font-size:12px;margin-top:4px">难度: ${'★'.repeat(d.difficulty||3)}${'☆'.repeat(5-(d.difficulty||3))}</div>
                        <div style="font-size:12px;color:${_vizMasteryColors[level]}">掌握度: ${Math.round(pKnown*100)}% (${levelLabel[level]})</div>
                        ${m.total_answers ? `<div style="font-size:12px">答题: ${m.correct_answers}/${m.total_answers}</div>` : ''}`;
                } else if (params.dataType === 'edge') {
                    return '前置依赖';
                }
            },
        },
        series: [{
            type: 'graph',
            layout: layoutConfig,
            data: echartsNodes,
            links: echartsEdges,
            categories: categories,
            roam: true,
            draggable: true,
            label: { show: true },
            lineStyle: { color: 'source' },
            emphasis: {
                focus: 'adjacency',
                lineStyle: { width: 3, opacity: 1, color: '#6366f1' },
                itemStyle: { shadowBlur: 20 },
            },
            force: _vizLayout === 'force' ? {
                repulsion: 200,
                edgeLength: [80, 160],
                gravity: 0.08,
            } : undefined,
        }],
    };

    // 树形布局：用力导向布局模拟层级结构（高重力+长边）
    if (_vizLayout === 'tree') {
        option.series[0].layout = 'force';
        option.series[0].force = {
            repulsion: 300,
            edgeLength: [120, 250],
            gravity: 0.15,
            layoutAnimation: true,
        };
    }

    try {
        _vizChart.setOption(option);
    } catch (chartErr) {
        console.error('ECharts渲染错误:', chartErr);
        // 降级：使用最简配置重试
        try {
            _vizChart.dispose();
            _vizChart = echarts.init(chartDom);
            _vizChart.setOption({
                series: [{
                    type: 'graph',
                    layout: 'force',
                    data: echartsNodes.map(n => ({ id: n.id, name: n.name, symbolSize: 30 })),
                    links: echartsEdges.map(e => ({ source: e.source, target: e.target })),
                    roam: true,
                    label: { show: true },
                    force: { repulsion: 200, edgeLength: 100 },
                }],
            });
        } catch (fallbackErr) {
            console.error('降级渲染也失败:', fallbackErr);
            throw new Error('图谱渲染失败: ' + chartErr.message);
        }
    }

    // 响应式
    if (!_vizChart._resizeBound) {
        window.addEventListener('resize', () => { if (_vizChart) _vizChart.resize(); });
        _vizChart._resizeBound = true;
    }

    // 点击节点：弹出详情面板
    _vizChart.off('click');
    _vizChart.on('click', async function(params) {
        if (params.dataType === 'node') {
            const kpData = params.data._kpData;
            const mastery = params.data._mastery;
            await showVizDetail(kpData, mastery);
        }
    });

    // 右键节点：直接打开思维导图
    _vizChart.off('contextmenu');
    _vizChart.on('contextmenu', function(params) {
        if (params.dataType === 'node') {
            params.event.event.preventDefault();
            openMindMap(params.data._kpData.id);
        }
    });

    // 双击节点：跳转学习页
    _vizChart.off('dblclick');
    _vizChart.on('dblclick', function(params) {
        if (params.dataType === 'node') {
            const kp = params.data._kpData;
            closeVizDetail();
            showPage('study');
            setTimeout(() => startStudy(kp.id, kp.code, kp.subject), 300);
        }
    });
}

async function showVizDetail(kpData, mastery) {
    const panel = document.getElementById('viz-detail-panel');
    const content = document.getElementById('viz-detail-content');
    const subjColor = _vizSubjectColors[kpData.subject] || '#64748b';
    const pKnown = mastery.p_known ?? 0.1;
    const level = mastery.mastery_level || 'unknown';
    const levelLabel = { unknown: '未学习', learning: '学习中', mastering: '较熟练', mastered: '已掌握' };
    const masteryColor = _vizMasteryColors[level];
    const stars = '★'.repeat(kpData.difficulty || 3) + '☆'.repeat(5 - (kpData.difficulty || 3));
    const accuracy = mastery.total_answers > 0
        ? Math.round(mastery.correct_answers / mastery.total_answers * 100)
        : 0;

    // 获取前置依赖
    let prereqHtml = '';
    try {
        const pathData = await api('GET', `/api/knowledge/graph/learning-path/${kpData.id}`);
        if (pathData.path && pathData.path.length > 1) {
            prereqHtml = `
                <div class="vdp-prereq">
                    <div class="vdp-prereq-title">📚 学习路径（${pathData.path.length - 1} 个前置知识点）</div>
                    ${pathData.path.slice(0, -1).map(p => `
                        <div class="vdp-prereq-item" onclick="vizJumpToKp(${p.id})">
                            <span style="font-size:11px;color:${_vizSubjectColors[p.subject]||'#64748b'};font-weight:700;width:60px;flex-shrink:0">${p.code}</span>
                            <span>${p.name}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        }
    } catch {}

    content.innerHTML = `
        <span class="vdp-subj-tag" style="color:${subjColor};background:${subjColor}22">${kpData.subject}</span>
        <div class="vdp-title">${kpData.name || kpData.label}</div>
        <div class="vdp-code">${kpData.code} | ${kpData.chapter || ''} | 难度 ${stars}</div>

        <div class="vdp-mastery-bar">
            <div class="vmb-label">
                <span>掌握度</span>
                <span style="color:${masteryColor}">${Math.round(pKnown * 100)}% · ${levelLabel[level]}</span>
            </div>
            <div class="progress-bar"><div class="progress-fill" style="width:${pKnown * 100}%;background:${masteryColor}"></div></div>
        </div>

        <div class="vdp-stats">
            <div class="vdp-stat">
                <div class="vs-num">${mastery.total_answers || 0}</div>
                <div class="vs-label">累计答题</div>
            </div>
            <div class="vdp-stat">
                <div class="vs-num">${accuracy}%</div>
                <div class="vs-label">正确率</div>
            </div>
        </div>

        ${prereqHtml}

        <div class="vdp-actions">
            <button class="btn btn-primary" style="width:auto;padding:10px 20px" onclick="vizStartStudy(${kpData.id}, '${kpData.code}', '${kpData.subject}')">📚 开始学习</button>
            <button class="btn btn-secondary" style="width:auto;padding:10px 20px" onclick="openMindMap(${kpData.id})">🧠 知识图谱</button>
            <button class="btn btn-secondary" style="width:auto;padding:10px 20px" onclick="closeVizDetail()">关闭</button>
        </div>
    `;

    panel.classList.add('show');
}

function vizStartStudy(kpId, kpCode, kpSubject) {
    closeVizDetail();
    showPage('study');
    setTimeout(() => startStudy(kpId, kpCode, kpSubject), 300);
}

async function vizJumpToKp(kpId) {
    const kp = _vizKpMap[kpId];
    if (!kp) return;
    const mastery = _vizMasteryMap[kpId] || {};
    await showVizDetail(kp, mastery);
    // 高亮对应节点
    if (_vizChart) {
        _vizChart.dispatchAction({
            type: 'highlight',
            seriesIndex: 0,
            name: String(kpId),
        });
    }
}
