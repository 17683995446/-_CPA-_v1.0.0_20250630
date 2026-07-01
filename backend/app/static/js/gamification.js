// ===== 成就页面 =====
async function loadAchievementsPage() {
    try {
        const achievements = await api('GET', `/api/gamification/${currentUser.id}/achievements`);
        const el = document.getElementById('achievements-display');
        if (achievements.length === 0) {
            el.innerHTML = '<div class="empty-state-enhanced" style="grid-column:1/-1"><div class="icon">🏆</div><h3>暂无成就</h3><p>持续学习解锁更多成就</p></div>';
            return;
        }
        const icons = { study: '📚', streak: '🔥', xp: '⚡', mastery: '🎓' };
        const unlockedCount = achievements.filter(a => a.unlocked).length;
        el.innerHTML = `
            <div class="card" style="display:flex;align-items:center;gap:12px;margin-bottom:20px;grid-column:1/-1">
                <span style="font-size:32px">🏆</span>
                <div>
                    <h3 style="margin:0">成就进度：${unlockedCount} / ${achievements.length}</h3>
                    <div class="progress-bar" style="margin-top:8px"><div class="progress-fill" style="width:${unlockedCount*100/achievements.length}%"></div></div>
                </div>
            </div>
        ` + achievements.map(a => `
            <div class="achievement-card-enhanced ${a.unlocked ? 'unlocked' : 'locked'}">
                ${a.unlocked ? '' : '<div class="ach-lock">🔒</div>'}
                <div class="ach-icon">${icons[a.category] || '🏆'}</div>
                <div class="ach-name">${a.name}</div>
                <div class="ach-desc">${a.description}</div>
                <div class="ach-xp">+${a.xp_reward} XP</div>
                ${a.unlocked ? '<div style="color:var(--success);font-size:12px;margin-top:8px;font-weight:700">✓ 已解锁</div>' : ''}
            </div>
        `).join('');
    } catch (e) {
        showToast('加载成就失败', 'error');
    }
}
