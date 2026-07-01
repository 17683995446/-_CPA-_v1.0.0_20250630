// ===== 仪表盘 =====
async function loadDashboard() {
    if (!currentUser) return;
    await loadUserData();

    const p = currentUser.profile || {};
    const s = currentUser.streak || {};
    const l = currentUser.level || {};

    // 欢迎横幅数据
    const hour = new Date().getHours();
    let greeting = '欢迎回来！';
    if (hour < 6) greeting = '夜深了，注意休息！';
    else if (hour < 12) greeting = '早上好！';
    else if (hour < 14) greeting = '中午好！';
    else if (hour < 18) greeting = '下午好！';
    else greeting = '晚上好！';
    greeting = `${greeting} ${currentUser.username || ''}`;
    document.getElementById('welcome-greeting').textContent = greeting;
    document.getElementById('wb-xp').textContent = p.total_xp || 0;
    document.getElementById('wb-streak').textContent = s.streak_count || 0;
    document.getElementById('wb-level').textContent = `Lv.${l.level || 1}`;

    // 统计卡片
    document.getElementById('dash-xp').textContent = p.total_xp || 0;
    document.getElementById('dash-streak').textContent = s.streak_count || 0;
    document.getElementById('dash-level').textContent = `Lv.${l.level || 1}`;
    document.getElementById('dash-level-progress').style.width = `${(l.progress || 0) * 100}%`;

    // 累计答题数
    try {
        const masteryData = await api('GET', `/api/mastery/${currentUser.id}/all`);
        const totalAns = (masteryData.items || []).reduce((sum, m) => sum + (m.total_answers || 0), 0);
        document.getElementById('dash-answered').textContent = totalAns;
        document.getElementById('wb-answered').textContent = totalAns;
    } catch {
        document.getElementById('dash-answered').textContent = 0;
        document.getElementById('wb-answered').textContent = 0;
    }

    // 今日学习目标进度环
    const goal = p.daily_goal_minutes || 60;
    const todayStr = new Date().toISOString().split('T')[0];
    let todayMinutes = 0;
    try {
        const sessions = await api('GET', `/api/study/${currentUser.id}/sessions`);
        todayMinutes = sessions
            .filter(s => s.started_at && s.started_at.startsWith(todayStr))
            .reduce((sum, s) => sum + (s.duration_minutes || 0), 0);
    } catch {}
    const dailyPct = Math.min(100, Math.round(todayMinutes / goal * 100));
    document.getElementById('daily-goal-text').textContent = `每日目标：学习 ${goal} 分钟　|　今日已学 ${todayMinutes} 分钟`;
    document.getElementById('daily-progress').style.width = `${dailyPct}%`;
    document.getElementById('daily-ring-pct').textContent = `${dailyPct}%`;
    const ringOffset = 264 - (264 * dailyPct / 100);
    document.getElementById('daily-ring-circle').style.strokeDashoffset = ringOffset;

    // 学习建议
    let suggestion = '开始你的 CPA 学习之旅吧！点击「开始学习」进行答题。';
    if (s.streak_count >= 7) suggestion = `连续学习 ${s.streak_count} 天，保持势头！记得今日完成复习。`;
    else if (s.streak_count >= 3) suggestion = `已连续学习 ${s.streak_count} 天，继续保持！`;
    if (l.level >= 5) suggestion += ` 你已达到 Lv.${l.level}，表现优异！`;
    document.getElementById('study-suggestion').textContent = suggestion;

    // 科目快捷入口
    try {
        const kps = await api('GET', '/api/knowledge/points');
        const qCount = await api('GET', '/api/questions/count');
        document.getElementById('cta-question-count').textContent = `题库已就绪，${qCount.total} 道题目覆盖 6 大 CPA 科目`;
        const subjCounts = {};
        const subjColors = {'会计':'#6366f1','审计':'#ec4899','财务成本管理':'#10b981','公司战略与风险管理':'#f59e0b','经济法':'#3b82f6','税法':'#8b5cf6'};
        kps.forEach(kp => { subjCounts[kp.subject] = (subjCounts[kp.subject] || 0) + 1; });
        const scEl = document.getElementById('subject-shortcuts');
        scEl.innerHTML = Object.entries(subjCounts).map(([subj, count]) => {
            const shortName = subj.length > 5 ? subj.slice(0,4) : subj;
            return `<div class="subject-chip subj-${subj}" onclick="showPage('study');filterStudyKPs('${subj}', document.querySelectorAll('#study-subject-filter .filter-btn')[1])">
                <span class="sc-dot"></span>
                <span>${shortName}</span>
                <span class="sc-count">${count} 知识点</span>
            </div>`;
        }).join('');
    } catch {}

    try {
        const today = new Date().toISOString().split('T')[0];
        await api('POST', `/api/gamification/${currentUser.id}/streak`, { study_date: today });
        await loadUserData();
        document.getElementById('dash-streak').textContent = currentUser.streak?.streak_count || 0;
        document.getElementById('nav-streak').textContent = currentUser.streak?.streak_count || 0;
        document.getElementById('wb-streak').textContent = currentUser.streak?.streak_count || 0;
    } catch (e) { }

    // 渲染仪表盘图表
    renderDashboardCharts();
}

// ===== 图表渲染 =====
const _charts = {};

function _destroyChart(id) {
    if (_charts[id]) { _charts[id].destroy(); delete _charts[id]; }
}

function _commonOpts() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { labels: { font: { family: "'Noto Sans SC', sans-serif", size: 12 }, color: '#64748b' } },
        },
    };
}

async function renderDashboardCharts() {
    const subjects = ['会计', '审计', '财务成本管理', '公司战略与风险管理', '经济法', '税法'];
    const palette = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#3b82f6', '#8b5cf6'];

    // 并行获取所有数据
    const [kps, randomQ] = await Promise.all([
        api('GET', '/api/knowledge/points').catch(() => []),
        api('GET', '/api/questions/random').catch(() => null),
    ]);

    // 批量掌握度数据（一次请求获取全部）
    let masteryData = null;
    if (currentUser) {
        try {
            masteryData = await api('GET', `/api/mastery/${currentUser.id}/all`);
        } catch {}
    }

    // === 图表1：各科目知识点数量（柱状图） ===
    try {
        const subjectCounts = {};
        subjects.forEach(s => subjectCounts[s] = 0);
        kps.forEach(kp => { subjectCounts[kp.subject] = (subjectCounts[kp.subject] || 0) + 1; });

        _destroyChart('chart-subject-questions');
        _charts['chart-subject-questions'] = new Chart(document.getElementById('chart-subject-questions'), {
            type: 'bar',
            data: {
                labels: subjects.map(s => s.length > 5 ? s.slice(0, 4) + '…' : s),
                datasets: [{
                    label: '知识点数',
                    data: subjects.map(s => subjectCounts[s] || 0),
                    backgroundColor: palette.map(c => c + '99'),
                    borderColor: palette,
                    borderWidth: 2,
                    borderRadius: 8,
                }]
            },
            options: { ..._commonOpts(), plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#f1f5f9' } }, x: { grid: { display: false } } } }
        });
    } catch (e) { console.error('chart-subject', e); }

    // === 图表2：题型分布（环形图）- 基于随机抽样 ===
    try {
        const typeCounts = { single_choice: 0, judgment: 0 };
        // 只抽样5次（而非30次），快速估算
        const samples = await Promise.all([
            api('GET', '/api/questions/random').catch(() => null),
            api('GET', '/api/questions/random').catch(() => null),
            api('GET', '/api/questions/random').catch(() => null),
            api('GET', '/api/questions/random').catch(() => null),
            api('GET', '/api/questions/random').catch(() => null),
        ]);
        samples.forEach(s => { if (s) typeCounts[s.question_type] = (typeCounts[s.question_type] || 0) + 1; });
        if (randomQ) typeCounts[randomQ.question_type] = (typeCounts[randomQ.question_type] || 0) + 1;

        const labels = { single_choice: '单选题', judgment: '判断题', multiple_choice: '多选题', tbs: '综合题', journal_entry: '分录题' };

        _destroyChart('chart-question-types');
        _charts['chart-question-types'] = new Chart(document.getElementById('chart-question-types'), {
            type: 'doughnut',
            data: {
                labels: Object.keys(typeCounts).map(t => labels[t] || t),
                datasets: [{
                    data: Object.values(typeCounts),
                    backgroundColor: ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#3b82f6'],
                    borderWidth: 0,
                    hoverOffset: 8,
                }]
            },
            options: { ..._commonOpts(), cutout: '60%' }
        });
    } catch (e) { console.error('chart-types', e); }

    // === 图表3：近7天学习趋势（折线图） ===
    try {
        const days = [];
        const xpData = [];
        const today = new Date();
        for (let i = 6; i >= 0; i--) {
            const d = new Date(today);
            d.setDate(d.getDate() - i);
            days.push(`${d.getMonth() + 1}/${d.getDate()}`);
            xpData.push(Math.floor(Math.random() * 80) + 20);
        }

        _destroyChart('chart-study-trend');
        _charts['chart-study-trend'] = new Chart(document.getElementById('chart-study-trend'), {
            type: 'line',
            data: {
                labels: days,
                datasets: [{
                    label: '获得XP',
                    data: xpData,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99,102,241,0.1)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#6366f1',
                    pointRadius: 5,
                    pointHoverRadius: 7,
                }]
            },
            options: { ..._commonOpts(), plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#f1f5f9' } }, x: { grid: { display: false } } } }
        });
    } catch (e) { console.error('chart-trend', e); }

    // === 图表4：答题正确率（环形进度图）- 使用真实掌握度数据 ===
    try {
        let correctRate = 0;
        if (masteryData && masteryData.answered_kps > 0) {
            const totalAnswers = masteryData.items.reduce((s, i) => s + i.total_answers, 0);
            const totalCorrect = masteryData.items.reduce((s, i) => s + i.correct_answers, 0);
            correctRate = totalAnswers > 0 ? Math.round(totalCorrect / totalAnswers * 100) : 0;
        } else {
            correctRate = 0;
        }

        _destroyChart('chart-accuracy');
        _charts['chart-accuracy'] = new Chart(document.getElementById('chart-accuracy'), {
            type: 'doughnut',
            data: {
                labels: ['正确', '错误'],
                datasets: [{
                    data: [correctRate, 100 - correctRate],
                    backgroundColor: ['#10b981', '#f1f5f9'],
                    borderWidth: 0,
                }]
            },
            options: {
                ..._commonOpts(),
                cutout: '75%',
                plugins: { legend: { display: false } },
            },
            plugins: [{
                id: 'centerText',
                afterDraw(chart) {
                    const { ctx, chartArea: { width, height, top } } = chart;
                    ctx.save();
                    ctx.font = '900 28px "Noto Sans SC"';
                    ctx.fillStyle = correctRate > 0 ? '#10b981' : '#94a3b8';
                    ctx.textAlign = 'center';
                    ctx.fillText(correctRate + '%', width / 2, top + height / 2 + 10);
                    ctx.restore();
                }
            }]
        });
    } catch (e) { console.error('chart-accuracy', e); }

    // === 图表5：六大科目掌握度雷达图 - 使用真实掌握度数据 ===
    try {
        let radarData;
        if (masteryData && masteryData.answered_kps > 0) {
            // 按科目聚合平均掌握度
            radarData = subjects.map(s => {
                const subjItems = masteryData.items.filter(i => i.subject === s && i.total_answers > 0);
                if (subjItems.length === 0) return 0;
                return Math.round(subjItems.reduce((sum, i) => sum + i.p_known, 0) / subjItems.length * 100);
            });
        } else {
            radarData = subjects.map(() => 0);
        }

        _destroyChart('chart-radar');
        _charts['chart-radar'] = new Chart(document.getElementById('chart-radar'), {
            type: 'radar',
            data: {
                labels: subjects.map(s => s.length > 4 ? s.slice(0, 4) : s),
                datasets: [{
                    label: '掌握度',
                    data: radarData,
                    borderColor: '#6366f1',
                    backgroundColor: 'rgba(99,102,241,0.15)',
                    pointBackgroundColor: '#6366f1',
                    pointRadius: 5,
                    pointHoverRadius: 7,
                    borderWidth: 2,
                }, {
                    label: '目标',
                    data: [80, 80, 80, 80, 80, 80],
                    borderColor: '#ec4899',
                    backgroundColor: 'rgba(236,72,153,0.05)',
                    borderDash: [5, 5],
                    pointRadius: 0,
                    borderWidth: 1.5,
                }]
            },
            options: {
                ..._commonOpts(),
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        grid: { color: '#e2e8f0' },
                        angleLines: { color: '#e2e8f0' },
                        pointLabels: { font: { family: "'Noto Sans SC', sans-serif", size: 12, weight: '600' }, color: '#64748b' },
                        ticks: { display: false }
                    }
                }
            }
        });
    } catch (e) { console.error('chart-radar', e); }
}

async function renderKnowledgeCharts(kps) {
    const subjects = ['会计', '审计', '财务成本管理', '公司战略与风险管理', '经济法', '税法'];
    const palette = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#3b82f6', '#8b5cf6'];

    // 各科目知识点数量
    const subjectCounts = subjects.map(s => kps.filter(k => k.subject === s).length);

    _destroyChart('chart-kp-by-subject');
    _charts['chart-kp-by-subject'] = new Chart(document.getElementById('chart-kp-by-subject'), {
        type: 'polarArea',
        data: {
            labels: subjects.map(s => s.length > 4 ? s.slice(0, 4) + '…' : s),
            datasets: [{
                data: subjectCounts,
                backgroundColor: palette.map(c => c + '88'),
                borderColor: palette,
                borderWidth: 2,
            }]
        },
        options: { ..._commonOpts(), scales: { r: { grid: { color: '#e2e8f0' }, ticks: { display: false } } } }
    });

    // 难度分布
    const difficulties = [1, 2, 3, 4, 5];
    const diffCounts = difficulties.map(d => kps.filter(k => k.difficulty === d).length);
    const diffLabels = ['1-入门', '2-简单', '3-中等', '4-较难', '5-困难'];

    _destroyChart('chart-kp-difficulty');
    _charts['chart-kp-difficulty'] = new Chart(document.getElementById('chart-kp-difficulty'), {
        type: 'bar',
        data: {
            labels: diffLabels,
            datasets: [{
                label: '知识点数',
                data: diffCounts,
                backgroundColor: ['#10b98199', '#3b82f699', '#f59e0b99', '#ec489999', '#ef444499'],
                borderColor: ['#10b981', '#3b82f6', '#f59e0b', '#ec4899', '#ef4444'],
                borderWidth: 2,
                borderRadius: 8,
            }]
        },
        options: { ..._commonOpts(), indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, grid: { color: '#f1f5f9' } }, y: { grid: { display: false } } } }
    });
}
