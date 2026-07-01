// ===== 登录/注册 =====
function switchAuthTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    // tab 可以是字符串 'login'/'register'（程序化调用），也可以是事件对象（点击调用）
    const tabName = typeof tab === 'string' ? tab : (tab && tab.target ? tab.target.dataset.tab : null);
    if (!tabName) return;
    const activeTab = document.querySelector(`.auth-tab[data-tab="${tabName}"]`);
    if (activeTab) activeTab.classList.add('active');
    document.getElementById('login-form').style.display = tabName === 'login' ? 'block' : 'none';
    document.getElementById('register-form').style.display = tabName === 'register' ? 'block' : 'none';
}

async function doRegister() {
    const username = document.getElementById('reg-username').value.trim();
    const email = document.getElementById('reg-email').value.trim();
    const password = document.getElementById('reg-password').value;
    const examDate = document.getElementById('reg-exam-date').value;
    const dailyGoal = parseInt(document.getElementById('reg-daily-goal').value) || 60;
    const errEl = document.getElementById('reg-error');
    errEl.textContent = '';

    if (!username || !email || !password) {
        errEl.textContent = '请填写所有必填字段';
        return;
    }
    if (password.length < 6) {
        errEl.textContent = '密码至少6位';
        return;
    }

    try {
        await api('POST', '/api/users', {
            username, email, password,
            target_exam_date: examDate || null,
            daily_goal_minutes: dailyGoal,
        });
        showToast('注册成功，请登录', 'success');
        switchAuthTab('login');
        document.getElementById('login-username').value = username;
    } catch (e) {
        errEl.textContent = e.message;
    }
}

async function doLogin() {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    const errEl = document.getElementById('login-error');
    errEl.textContent = '';

    if (!username || !password) {
        errEl.textContent = '请输入用户名和密码';
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/api/users?username=${encodeURIComponent(username)}`);
        if (!res.ok) throw new Error('用户不存在');
        const users = await res.json();
        const user = users.find(u => u.username === username);
        if (!user) throw new Error('用户不存在');

        currentUser = user;
        localStorage.setItem('cpa_user_id', user.id);
        localStorage.setItem('cpa_username', user.username);
        await loadUserData();
        showApp();
    } catch (e) {
        errEl.textContent = e.message;
    }
}

function logout() {
    currentUser = null;
    localStorage.removeItem('cpa_user_id');
    localStorage.removeItem('cpa_username');
    document.getElementById('auth-page').style.display = 'flex';
    document.getElementById('app').classList.remove('active');
}

async function loadUserData() {
    try {
        const profile = await api('GET', `/api/users/${currentUser.id}/profile`);
        currentUser.profile = profile;
        try {
            const streak = await api('GET', `/api/gamification/${currentUser.id}/streak`);
            currentUser.streak = streak;
        } catch { currentUser.streak = { streak_count: 0, max_streak: 0, protections: 0 }; }
        try {
            const level = await api('GET', `/api/gamification/${currentUser.id}/level`);
            currentUser.level = level;
        } catch { currentUser.level = { level: 1, current_level_xp: 0, next_level_xp: 100, progress: 0 }; }
        updateNavStats();
    } catch (e) {
        console.error('加载用户数据失败:', e);
    }
}

function updateNavStats() {
    const p = currentUser.profile || {};
    const s = currentUser.streak || {};
    const l = currentUser.level || {};
    document.getElementById('nav-username').textContent = currentUser.username;
    document.getElementById('nav-xp').textContent = p.total_xp || 0;
    document.getElementById('nav-streak').textContent = s.streak_count || 0;
    document.getElementById('nav-level').textContent = `Lv.${l.level || 1}`;
    // 头像首字母
    const avatarEl = document.getElementById('nav-avatar');
    if (avatarEl) avatarEl.textContent = (currentUser.username || 'U').charAt(0).toUpperCase();
}

function showApp() {
    document.getElementById('auth-page').style.display = 'none';
    document.getElementById('app').classList.add('active');
    showPage('dashboard');
    loadDashboard();
}
