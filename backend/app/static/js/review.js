// ===== 复习页面 =====
async function loadReviewPage() {
    try {
        const data = await api('GET', `/api/review/${currentUser.id}/due`);
        const el = document.getElementById('review-content');
        if (data.total === 0) {
            el.innerHTML = '<div class="empty-state-enhanced"><div class="icon">✅</div><h3>暂无到期卡片</h3><p>太棒了！所有卡片都已复习完毕</p></div>';
            return;
        }
        const stateColors = { 'new': 'var(--primary)', 'learning': 'var(--warning)', 'review': 'var(--success)', 'relearning': 'var(--danger)' };
        el.innerHTML = `
            <div class="card" style="display:flex;align-items:center;gap:12px">
                <span style="font-size:32px">📋</span>
                <div>
                    <h3 style="margin:0">今日待复习：${data.total} 张卡片</h3>
                    <p style="margin:4px 0 0;color:var(--text-light);font-size:13px">根据FSRS间隔重复算法，以下卡片已到期</p>
                </div>
            </div>
            ${data.cards.map(c => {
                const stateColor = stateColors[c.state] || 'var(--text-light)';
                return `
                <div class="review-card-enhanced">
                    <div class="rc-header">
                        <span class="badge" style="background:${stateColor}22;color:${stateColor};font-weight:700">${c.state}</span>
                        <div class="rc-stats">
                            <div class="rc-stat">稳定性 <span class="rc-stat-val">${c.stability.toFixed(1)}</span></div>
                            <div class="rc-stat">重复 <span class="rc-stat-val">${c.reps}</span></div>
                            <div class="rc-stat">遗忘 <span class="rc-stat-val">${c.lapses}</span></div>
                        </div>
                    </div>
                    <div class="rc-rating-row">
                        <button class="rc-rating-btn rate-again" onclick="submitReview(${c.id}, 1)">
                            <span class="rc-rating-label">重来</span>
                            <span class="rc-rating-hint">完全忘了</span>
                        </button>
                        <button class="rc-rating-btn rate-hard" onclick="submitReview(${c.id}, 2)">
                            <span class="rc-rating-label">困难</span>
                            <span class="rc-rating-hint">想了很久</span>
                        </button>
                        <button class="rc-rating-btn rate-good" onclick="submitReview(${c.id}, 3)">
                            <span class="rc-rating-label">良好</span>
                            <span class="rc-rating-hint">记得不错</span>
                        </button>
                        <button class="rc-rating-btn rate-easy" onclick="submitReview(${c.id}, 4)">
                            <span class="rc-rating-label">简单</span>
                            <span class="rc-rating-hint">毫不费力</span>
                        </button>
                    </div>
                </div>
            `}).join('')}
        `;
    } catch (e) {
        showToast('加载复习卡片失败', 'error');
    }
}

async function submitReview(cardId, rating) {
    try {
        const result = await api('POST', `/api/review/${currentUser.id}/cards/${cardId}`, { rating });
        const ratingNames = { 1: '重来', 2: '困难', 3: '良好', 4: '简单' };
        showToast(`${ratingNames[rating]} → 下次复习：${result.interval} 天后`, 'success');
        loadReviewPage();
    } catch (e) {
        showToast('提交复习失败: ' + e.message, 'error');
    }
}
