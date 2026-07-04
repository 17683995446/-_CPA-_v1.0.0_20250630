/**
 * AI 学习助手 — LLM 分析前端模块
 *
 * 四个功能 Tab：
 *   1. 学习诊断报告 — 生成/查看个性化诊断
 *   2. 错题归因 — 错误类型分布 + 归因历史
 *   3. 相似题推荐 — 输入题目ID，推荐语义相似题目
 *   4. 深度解析 — LLM 增强单题解析
 */

// ===== Tab 切换 =====
function switchLLMTab(tab) {
    document.querySelectorAll('.llm-tab-content').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.llm-tab').forEach(el => el.classList.remove('active', 'btn-primary'));
    document.getElementById(`llm-tab-${tab}`).style.display = '';
    document.querySelector(`.llm-tab[data-tab="${tab}"]`).classList.add('active', 'btn-primary');

    if (tab === 'error') loadErrorAnalyses();
}

// ===== 页面加载 =====
async function loadLLMPage() {
    await checkLLMStatus();
    await loadLatestReport();
}

// ===== LLM 状态检查 =====
async function checkLLMStatus() {
    try {
        const res = await fetch(`${API_BASE}/api/llm/status`);
        const data = await res.json();
        const dot = document.getElementById('llm-mode-dot');
        const text = document.getElementById('llm-mode-text');

        // API 返回 {"available": true, "mode": "llm"} 或 {"code":200,"data":{...}}
        const info = data.data || data;
        if (info.available) {
            dot.style.background = '#22c55e';
            text.textContent = info.mode === 'llm' ? 'AI 服务已连接（LLM 模式 · Qwen2.5-14B）' : 'AI 服务已连接';
        } else {
            dot.style.background = '#f59e0b';
            text.textContent = 'AI 服务未启用（规则降级模式，配置 API Key 后启用智能分析）';
        }
    } catch (e) {
        document.getElementById('llm-mode-text').textContent = 'AI 服务状态未知';
    }
}

// ===== 学习诊断报告 =====
async function generateReport() {
    const userId = getCurrentUserId();
    if (!userId) { showToast('请先登录'); return; }

    const btn = document.querySelector('#llm-tab-report .btn-primary');
    if (btn) { btn.disabled = true; btn.textContent = '生成中...'; }

    try {
        const res = await fetch(`${API_BASE}/api/llm/report/${userId}?report_type=on_demand`, {
            method: 'POST',
        });
        const data = await res.json();

        if (data.code === 200 && data.data) {
            renderReport(data.data);
            showToast('诊断报告生成成功');
        } else {
            showToast('生成失败，请稍后重试');
        }
    } catch (e) {
        showToast('网络错误');
    } finally {
        btn.disabled = false;
        btn.textContent = '生成诊断报告';
    }
}

async function loadLatestReport() {
    const userId = getCurrentUserId();
    if (!userId) return;

    try {
        const res = await fetch(`${API_BASE}/api/llm/report/${userId}/latest`);
        const data = await res.json();

        if (data.code === 200 && data.data) {
            renderReport(data.data);
        }
    } catch (e) {
        // 静默失败
    }
}

function renderReport(report) {
    const container = document.getElementById('report-display');
    container.classList.remove('empty-state');

    const content = report.content || {};
    const snapshot = content.data_snapshot || {};
    const weakPoints = content.weak_points || [];

    let weakHTML = '';
    if (weakPoints.length > 0) {
        weakHTML = weakPoints.map((wp, i) => `
            <div style="padding:10px 12px;background:var(--bg-secondary);border-radius:6px;margin-top:6px;border-left:3px solid #ef4444">
                <div style="font-weight:600;font-size:13px">薄弱点 ${i + 1}</div>
                <div style="font-size:13px;color:var(--text-muted);margin-top:4px">${escapeHtml(wp.description || wp.kp_name || '')}</div>
            </div>
        `).join('');
    }

    let masteryHTML = '';
    if (snapshot.subject_mastery) {
        masteryHTML = Object.entries(snapshot.subject_mastery).map(([subj, val]) => {
            const pct = Math.round(val * 100);
            const color = pct >= 70 ? '#22c55e' : pct >= 40 ? '#f59e0b' : '#ef4444';
            return `
                <div style="display:flex;align-items:center;gap:8px;margin-top:4px">
                    <span style="font-size:12px;width:60px">${escapeHtml(subj)}</span>
                    <div style="flex:1;height:6px;background:var(--bg-secondary);border-radius:3px;overflow:hidden">
                        <div style="width:${pct}%;height:100%;background:${color}"></div>
                    </div>
                    <span style="font-size:12px;width:36px;text-align:right">${pct}%</span>
                </div>
            `;
        }).join('');
    }

    container.innerHTML = `
        <div style="background:var(--bg-card);border-radius:12px;padding:20px;border:1px solid var(--border-color)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <h3 style="margin:0">📋 学习诊断报告</h3>
                <span style="font-size:12px;color:var(--text-muted)">${report.created_at ? escapeHtml(new Date(report.created_at).toLocaleString('zh-CN')) : ''}</span>
            </div>

            <div style="font-size:14px;color:var(--text-muted);margin-bottom:16px">${escapeHtml(report.summary || '')}</div>

            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px">
                <div style="text-align:center;padding:12px;background:var(--bg-secondary);border-radius:8px">
                    <div style="font-size:24px;font-weight:700">${report.total_questions || 0}</div>
                    <div style="font-size:11px;color:var(--text-muted)">总答题数</div>
                </div>
                <div style="text-align:center;padding:12px;background:var(--bg-secondary);border-radius:8px">
                    <div style="font-size:24px;font-weight:700">${Math.round((report.accuracy_rate || 0) * 100)}%</div>
                    <div style="font-size:11px;color:var(--text-muted)">正确率</div>
                </div>
                <div style="text-align:center;padding:12px;background:var(--bg-secondary);border-radius:8px">
                    <div style="font-size:24px;font-weight:700">${report.weak_points_count || 0}</div>
                    <div style="font-size:11px;color:var(--text-muted)">薄弱知识点</div>
                </div>
            </div>

            ${masteryHTML ? `<div style="margin-bottom:16px"><div style="font-size:12px;font-weight:600;margin-bottom:4px">各科目掌握度</div>${masteryHTML}</div>` : ''}

            ${content.overall_assessment ? `<div style="margin-bottom:16px"><div style="font-size:12px;font-weight:600;margin-bottom:4px">总体评价</div><div style="font-size:13px;line-height:1.6">${escapeHtml(content.overall_assessment)}</div></div>` : ''}

            ${weakHTML ? `<div style="margin-bottom:16px"><div style="font-size:12px;font-weight:600;margin-bottom:4px">薄弱点分析</div>${weakHTML}</div>` : ''}

            ${content.study_plan ? `<div style="margin-bottom:16px"><div style="font-size:12px;font-weight:600;margin-bottom:4px">学习建议</div><div style="font-size:13px;line-height:1.6;padding:10px 12px;background:var(--bg-secondary);border-radius:6px;border-left:3px solid var(--accent)">${escapeHtml(content.study_plan)}</div></div>` : ''}

            ${content.encouragement ? `<div style="text-align:center;font-size:14px;color:var(--accent);margin-top:8px">${escapeHtml(content.encouragement)}</div>` : ''}
        </div>
    `;
}

// ===== 错题归因 =====
async function loadErrorAnalyses() {
    const userId = getCurrentUserId();
    if (!userId) return;

    try {
        // 加载归因历史
        const res = await fetch(`${API_BASE}/api/llm/error-analysis/${userId}?limit=20`);
        const data = await res.json();

        if (data.code === 200 && data.data && data.data.length > 0) {
            renderErrorList(data.data);
        }

        // 加载错误类型统计
        const statsRes = await fetch(`${API_BASE}/api/llm/error-analysis/${userId}/stats`);
        const statsData = await statsRes.json();

        if (statsData.code === 200 && statsData.data) {
            renderErrorStats(statsData.data);
        }
    } catch (e) {
        // 静默失败
    }
}

function renderErrorList(analyses) {
    const container = document.getElementById('error-analysis-list');
    container.classList.remove('empty-state');

    const typeLabels = {
        concept_confusion: { label: '概念混淆', color: '#ef4444' },
        calculation_error: { label: '计算失误', color: '#f59e0b' },
        misreading: { label: '审题不清', color: '#8b5cf6' },
        memory_decay: { label: '记忆遗忘', color: '#06b6d4' },
        method_wrong: { label: '方法错误', color: '#ec4899' },
    };

    container.innerHTML = analyses.map(a => {
        const info = typeLabels[a.error_type] || { label: escapeHtml(a.error_type), color: '#6b7280' };
        return `
            <div style="padding:12px;background:var(--bg-card);border-radius:8px;margin-top:8px;border:1px solid var(--border-color);border-left:3px solid ${info.color}">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-size:13px;font-weight:600;color:${info.color}">${escapeHtml(info.label)}</span>
                    <span style="font-size:11px;color:var(--text-muted)">${a.created_at ? escapeHtml(new Date(a.created_at).toLocaleDateString('zh-CN')) : ''}</span>
                </div>
                <div style="font-size:13px;margin-top:6px;color:var(--text-muted)">题目ID: ${escapeHtml(String(a.question_id))} | 你的答案: ${escapeHtml(a.user_answer)}</div>
                <div style="font-size:13px;margin-top:4px">${escapeHtml(a.suggestion)}</div>
                ${a.related_concept ? `<div style="font-size:12px;margin-top:4px;color:var(--accent)">关联: ${escapeHtml(a.related_concept)}</div>` : ''}
            </div>
        `;
    }).join('');
}

function renderErrorStats(stats) {
    const container = document.getElementById('error-stats-chart');
    if (!container) return;

    const labels = Object.keys(stats);
    const values = Object.values(stats);

    if (labels.length === 0) {
        container.innerHTML = '<div style="text-align:center;color:var(--text-muted);font-size:13px;padding:40px">暂无错误数据</div>';
        return;
    }

    const colors = ['#ef4444', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899'];

    // 用简单的柱状图
    container.innerHTML = values.map((v, i) => {
        const maxVal = Math.max(...values);
        const pct = maxVal > 0 ? (v / maxVal) * 100 : 0;
        return `
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                <span style="font-size:12px;width:70px;text-align:right">${labels[i]}</span>
                <div style="flex:1;height:18px;background:var(--bg-secondary);border-radius:4px;overflow:hidden">
                    <div style="width:${pct}%;height:100%;background:${colors[i % colors.length]};display:flex;align-items:center;justify-content:flex-end;padding-right:6px;font-size:11px;color:white;font-weight:600">${v}</div>
                </div>
            </div>
        `;
    }).join('');
}

// ===== 相似题推荐 =====
async function findSimilar() {
    const qid = document.getElementById('similar-qid').value;
    if (!qid) { showToast('请输入题目ID'); return; }

    const btn = document.querySelector('#llm-tab-similar .btn-primary');
    if (btn) { btn.disabled = true; btn.textContent = '搜索中...'; }

    try {
        const res = await fetch(`${API_BASE}/api/llm/similarity/${qid}?top_k=5`);
        const data = await res.json();

        if (data.code === 200 && data.data) {
            renderSimilarResults(data.data, qid);
        } else {
            showToast('未找到相似题');
        }
    } catch (e) {
        showToast('网络错误');
    } finally {
        btn.disabled = false;
        btn.textContent = '推荐相似题';
    }
}

function renderSimilarResults(results, baseQid) {
    const container = document.getElementById('similar-results');

    if (!results || results.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="icon">🔗</div><h3>未找到相似题</h3></div>';
        return;
    }

    container.innerHTML = `
        <div style="font-size:13px;color:var(--text-muted);margin-bottom:8px">基于题目 Q${escapeHtml(String(baseQid))} 的语义相似推荐：</div>
        ${results.map((r, i) => `
            <div style="padding:12px;background:var(--bg-card);border-radius:8px;margin-top:8px;border:1px solid var(--border-color)">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
                    <span style="font-size:13px;font-weight:600">Q${escapeHtml(String(r.question_id))}</span>
                    <span style="font-size:12px;padding:2px 8px;border-radius:4px;background:var(--bg-secondary)">${(r.similarity * 100).toFixed(1)}% 相似</span>
                </div>
                <div style="font-size:13px;color:var(--text-muted)">${escapeHtml(r.content)}</div>
                ${r.kp_code ? `<div style="font-size:11px;margin-top:4px;color:var(--accent)">${escapeHtml(r.kp_code)} ${escapeHtml(r.kp_name || '')}</div>` : ''}
            </div>
        `).join('')}
    `;
}

// ===== 深度解析 =====
async function enhanceExplanation() {
    const qid = document.getElementById('explain-qid').value;
    if (!qid) { showToast('请输入题目ID'); return; }

    const btn = document.querySelector('#llm-tab-explain .btn-primary');
    if (btn) { btn.disabled = true; btn.textContent = '生成中...'; }

    try {
        const res = await fetch(`${API_BASE}/api/llm/explanation/${qid}`, { method: 'POST' });
        const data = await res.json();

        if (data.code === 200 && data.data) {
            renderExplanation(data.data);
        } else {
            showToast('题目不存在或生成失败');
        }
    } catch (e) {
        showToast('网络错误');
    } finally {
        btn.disabled = false;
        btn.textContent = '生成深度解析';
    }
}

function renderExplanation(data) {
    const container = document.getElementById('explain-results');
    const badge = data.llm_enhanced
        ? '<span style="font-size:11px;padding:2px 8px;border-radius:4px;background:#22c55e20;color:#22c55e">AI 增强</span>'
        : '<span style="font-size:11px;padding:2px 8px;border-radius:4px;background:var(--bg-secondary);color:var(--text-muted)">原始解析</span>';

    container.innerHTML = `
        <div style="background:var(--bg-card);border-radius:12px;padding:20px;border:1px solid var(--border-color)">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <h3 style="margin:0">💡 深度解析</h3>
                ${badge}
            </div>

            ${data.explanation ? `<div style="margin-bottom:16px"><div style="font-size:12px;font-weight:600;margin-bottom:4px">详细解析</div><div style="font-size:13px;line-height:1.7;white-space:pre-wrap">${escapeHtml(data.explanation)}</div></div>` : ''}

            ${data.simple_explanation ? `<div style="margin-bottom:12px;padding:10px 12px;background:var(--bg-secondary);border-radius:6px;border-left:3px solid #06b6d4"><div style="font-size:12px;font-weight:600;margin-bottom:2px">通俗解释</div><div style="font-size:13px">${escapeHtml(data.simple_explanation)}</div></div>` : ''}

            ${data.mnemonic ? `<div style="margin-bottom:12px;padding:10px 12px;background:var(--bg-secondary);border-radius:6px;border-left:3px solid #8b5cf6"><div style="font-size:12px;font-weight:600;margin-bottom:2px">记忆口诀</div><div style="font-size:13px">${escapeHtml(data.mnemonic)}</div></div>` : ''}

            ${data.study_tip ? `<div style="margin-bottom:12px;padding:10px 12px;background:var(--bg-secondary);border-radius:6px;border-left:3px solid #22c55e"><div style="font-size:12px;font-weight:600;margin-bottom:2px">学习建议</div><div style="font-size:13px">${escapeHtml(data.study_tip)}</div></div>` : ''}
        </div>
    `;
}

// ===== 工具函数 =====
function getCurrentUserId() {
    return localStorage.getItem('cpa_user_id') || (typeof currentUser !== 'undefined' ? currentUser?.id : null);
}
