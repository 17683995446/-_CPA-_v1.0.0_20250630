// ===== 学习页面 =====
let _allStudyKPs = [];
let _studyFilter = 'all';
let _sessionCount = 0;

function filterStudyKPs(subject, btn) {
    _studyFilter = subject;
    document.querySelectorAll('#study-subject-filter .filter-btn').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    renderStudyKPs();
}

function renderStudyKPs() {
    const listEl = document.getElementById('study-kp-list');
    let kps = _allStudyKPs;
    if (_studyFilter !== 'all') {
        kps = kps.filter(kp => kp.subject === _studyFilter);
    }
    if (kps.length === 0) {
        listEl.innerHTML = '<div class="empty-state"><div class="icon">📚</div><h3>暂无知识点</h3><p>请先在知识图谱页面添加知识点</p></div>';
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
            html += `
                <div class="kp-item-enhanced subj-${kp.subject}" onclick="startStudy(${kp.id}, '${kp.code}', '${kp.subject}')" style="margin-bottom:8px">
                    <span class="kp-subj-tag">${kp.code}</span>
                    <div class="kp-body">
                        <div class="kp-title">${kp.name}</div>
                        <div class="kp-desc">${kp.chapter || ''}</div>
                    </div>
                    <span class="kp-diff-stars" style="color:var(--warning)">${stars}</span>
                </div>
            `;
        });
    }
    listEl.innerHTML = html;
}

async function loadStudyPage() {
    try {
        const kps = await api('GET', '/api/knowledge/points');
        _allStudyKPs = kps;
        _studyFilter = 'all';
        document.querySelectorAll('#study-subject-filter .filter-btn').forEach(b => b.classList.remove('active'));
        document.querySelector('#study-subject-filter .filter-btn').classList.add('active');
        renderStudyKPs();
    } catch (e) {
        showToast('加载知识点失败: ' + e.message, 'error');
    }
}

async function startStudy(kpId, kpCode, kpSubject) {
    _sessionCount = 0;
    _sessionCorrect = 0;
    _sessionXp = 0;
    _askedQuestionIds = new Set();
    document.getElementById('session-progress-bar').style.display = 'none';
    try {
        let question = null;
        try {
            const dbQuestions = await api('GET', `/api/questions/by-kp/${kpId}`);
            if (dbQuestions.length > 0) {
                const available = dbQuestions.filter(q => !_askedQuestionIds.has(q.variant_id));
                const pool = available.length > 0 ? available : dbQuestions;
                if (available.length === 0) _askedQuestionIds.clear();
                question = pool[Math.floor(Math.random() * pool.length)];
                question.knowledge_point_code = kpCode;
                question.subject = kpSubject || '';
            }
        } catch {}

        if (!question) {
            // 该知识点暂无题目，用随机题库题目兜底
            try {
                question = await api('GET', '/api/questions/random');
                question.knowledge_point_code = kpCode;
                question.subject = kpSubject || '';
                showToast('该知识点暂无专属题目，已为你随机抽题', 'info');
            } catch (e) {
                throw new Error(e.message || '题库暂时无法访问');
            }
        }

        if (question.variant_id) _askedQuestionIds.add(question.variant_id);
        currentQuestion = { ...question, kp_id: kpId };
        displayQuestion(currentQuestion);
        document.getElementById('study-config').style.display = 'none';
        document.getElementById('study-question').style.display = 'block';

        try {
            const session = await api('POST', `/api/study/sessions?user_id=${currentUser.id}`, { subject: kpSubject || '综合' });
            studySessionId = session.id;
        } catch {}
    } catch (e) {
        showToast('出题失败: ' + e.message, 'error');
    }
}

function displayQuestion(q) {
    const el = document.getElementById('question-display');
    selectedOption = null;
    isAnswered = false;

    // 隐藏并清空上一题的答题横幅
    const banner = document.getElementById('answer-banner');
    if (banner) { banner.className = 'answer-banner'; banner.innerHTML = ''; }

    // 构建来源标签
    const sourceLabel = q.source === 'past_exam'
        ? '<span class="badge badge-exam">📜 历年真题</span>'
        : '<span class="badge badge-mock">📝 模拟题</span>';
    const yearLabel = q.exam_year
        ? `<span class="badge badge-year">${q.exam_year}年</span>`
        : '';
    const pointLabel = q.exam_point
        ? `<span class="badge badge-point">🎯 ${q.exam_point}</span>`
        : '';
    const diff = q.difficulty || 3;
    const diffStars = '★'.repeat(diff) + '☆'.repeat(5 - diff);

    let html = `
        <div class="question-meta">
            ${sourceLabel}
            ${yearLabel}
            <span class="badge badge-subject">${q.subject || '综合'}</span>
            <span class="badge badge-type">${getTypeName(q.question_type)}</span>
            <span class="badge badge-difficulty">${diffStars} 难度${diff}</span>
            ${pointLabel}
        </div>
        <div class="question-content">${q.content}</div>
    `;
    if (q.options && q.options.length > 0) {
        html += '<div class="options-list">';
        q.options.forEach((opt, i) => {
            html += `
                <div class="option-item" onclick="selectOption(${i})" id="opt-${i}">
                    <div class="option-label">${opt.label}</div>
                    <span>${opt.content}</span>
                </div>
            `;
        });
        html += '</div>';
        html += `
            <div class="explanation-box" id="explanation-box">
                <div id="explanation-text"></div>
            </div>
            <div class="action-bar" id="action-bar">
                <button class="btn btn-primary" onclick="submitAnswer()">提交答案</button>
            </div>
        `;
    } else {
        html += '<div class="empty-state" style="padding:20px;color:var(--text-light)">该题型暂不支持在线作答</div>';
    }
    el.innerHTML = html;
}

function getTypeName(type) {
    const names = {
        single_choice: '单选题', multiple_choice: '多选题',
        judgment: '判断题', tbs: '综合题', journal_entry: '分录题',
    };
    return names[type] || type;
}

function selectOption(index) {
    if (document.querySelector('.option-item.correct')) return;
    document.querySelectorAll('.option-item').forEach(o => o.classList.remove('selected'));
    document.getElementById(`opt-${index}`).classList.add('selected');
    selectedOption = index;
}

async function submitAnswer() {
    if (isAnswered) return;
    if (selectedOption === null) {
        showToast('请选择一个选项', 'error');
        return;
    }
    isAnswered = true;
    const opt = currentQuestion.options[selectedOption];
    // 通过 answer 字段判断正确性，不依赖 is_correct（已从API响应中移除）
    const isCorrect = currentQuestion.question_type === 'judgment'
        ? (opt.content === currentQuestion.answer)
        : (opt.label === currentQuestion.answer);

    currentQuestion.options.forEach((o, i) => {
        const oCorrect = currentQuestion.question_type === 'judgment'
            ? (o.content === currentQuestion.answer)
            : (o.label === currentQuestion.answer);
        if (oCorrect) document.getElementById(`opt-${i}`).classList.add('correct');
        else if (i === selectedOption) document.getElementById(`opt-${i}`).classList.add('wrong');
    });

    // 解析区显示答案标签+内容
    const correctOpt = currentQuestion.options.find(o =>
        currentQuestion.question_type === 'judgment'
            ? (o.content === currentQuestion.answer)
            : (o.label === currentQuestion.answer)
    );
    // 判断题 answer 本身就是"正确"/"错误"，无需再拼接选项内容
    const answerDisplay = currentQuestion.question_type === 'judgment'
        ? currentQuestion.answer
        : (correctOpt ? `${currentQuestion.answer}．${correctOpt.content}` : currentQuestion.answer);
    const explanation = currentQuestion.explanation || '';
    const simpleExpl = currentQuestion.simple_explanation || '';
    const mnemonic = currentQuestion.mnemonic || '';
    const studyTip = currentQuestion.study_tip || '';

    // 构建四个解析卡片
    let explHtml = `<p style="margin-bottom:10px"><strong>✅ 答案：${answerDisplay}</strong></p>`;

    // 模块1：详细解析
    if (explanation) {
        explHtml += `<div class="expl-card expl-detail">
            <div class="expl-card-title">📖 详细解析</div>
            <div class="expl-card-body">${explanation.split('\n').map(l => `<p>${l}</p>`).join('')}</div>
        </div>`;
    }

    // 模块2：通俗易懂简洁解释
    if (simpleExpl) {
        explHtml += `<div class="expl-card expl-simple">
            <div class="expl-card-title">💡 通俗解释</div>
            <div class="expl-card-body">${simpleExpl}</div>
        </div>`;
    }

    // 模块3：记忆口诀
    if (mnemonic) {
        explHtml += `<div class="expl-card expl-mnemonic">
            <div class="expl-card-title">🧠 记忆口诀</div>
            <div class="expl-card-body">${mnemonic}</div>
        </div>`;
    }

    // 模块4：小贴士
    if (studyTip) {
        explHtml += `<div class="expl-card expl-tip">
            <div class="expl-card-title">📌 小贴士</div>
            <div class="expl-card-body">${studyTip}</div>
        </div>`;
    }

    document.getElementById('explanation-text').innerHTML = explHtml;
    document.getElementById('explanation-box').classList.add('show');

    // 答题结果横幅
    const banner = document.getElementById('answer-banner');
    banner.className = 'answer-banner show ' + (isCorrect ? 'correct' : 'wrong');
    banner.innerHTML = isCorrect
        ? '<span style="font-size:22px">✅</span> 答对了！' + (currentQuestion.exam_year ? ` (${currentQuestion.exam_year}年真题)` : '')
        : '<span style="font-size:22px">❌</span> 答错了，再接再厉';

    try {
        const result = await api('POST', `/api/mastery/${currentUser.id}/answer`, {
            knowledge_point_id: currentQuestion.kp_id,
            question_id: currentQuestion.id || null,
            is_correct: isCorrect,
            difficulty: currentQuestion.difficulty || 3,
        });

        await loadUserData();
        updateNavStats();

        if (result && result.xp_earned > 0) {
            _sessionXp += result.xp_earned;
            if (result.is_critical) {
                showCelebration('暴击！', `获得 ${result.xp_earned} XP（3倍暴击）`, '💥');
            } else if (result.level_up) {
                showCelebration('升级！', `恭喜升到 Lv.${result.level_up}`, '⭐');
            } else if (result.should_celebrate) {
                showCelebration('干得漂亮！', `获得 ${result.xp_earned} XP`, '🎉');
            } else {
                showToast(`+${result.xp_earned} XP`, 'success');
            }
        }
        if (isCorrect) _sessionCorrect++;

        document.getElementById('action-bar').innerHTML = `
            <button class="btn btn-primary" onclick="nextQuestion()">下一题</button>
            <button class="btn btn-secondary" onclick="exitStudy()">返回</button>
        `;

        // 更新答题进度
        _sessionCount++;
        const spBar = document.getElementById('session-progress-bar');
        spBar.style.display = 'flex';
        const pct = Math.min(100, _sessionCount * 10);
        document.getElementById('sp-fill').style.width = `${pct}%`;
        document.getElementById('sp-count').textContent = `${_sessionCount} 题`;
    } catch (e) {
        showToast('提交失败: ' + e.message, 'error');
        // API失败时仍允许查看解析和下一题，不重置isAnswered防止重复提交
        document.getElementById('action-bar').innerHTML = `
            <button class="btn btn-primary" onclick="nextQuestion()">下一题</button>
            <button class="btn btn-secondary" onclick="exitStudy()">返回</button>
        `;
    }
}

function nextQuestion() {
    if (currentQuestion && currentQuestion.kp_id) {
        const kpCode = currentQuestion.knowledge_point_code;
        const kpSubject = currentQuestion.subject || '';
        // 不重置 _sessionCount，保持累计
        loadNextQuestion(currentQuestion.kp_id, kpCode, kpSubject);
    }
}

async function loadNextQuestion(kpId, kpCode, kpSubject) {
    try {
        let question = null;
        try {
            const dbQuestions = await api('GET', `/api/questions/by-kp/${kpId}`);
            if (dbQuestions.length > 0) {
                const available = dbQuestions.filter(q => !_askedQuestionIds.has(q.variant_id));
                const pool = available.length > 0 ? available : dbQuestions;
                if (available.length === 0) _askedQuestionIds.clear();
                question = pool[Math.floor(Math.random() * pool.length)];
                question.knowledge_point_code = kpCode;
                question.subject = kpSubject || '';
            }
        } catch {}

        if (!question) {
            try {
                question = await api('GET', '/api/questions/random');
                question.knowledge_point_code = kpCode;
                question.subject = kpSubject || '';
            } catch (e) {
                throw new Error(e.message || '题库暂时无法访问');
            }
        }

        if (question.variant_id) _askedQuestionIds.add(question.variant_id);
        currentQuestion = { ...question, kp_id: kpId };
        displayQuestion(currentQuestion);
        document.getElementById('study-config').style.display = 'none';
        document.getElementById('study-question').style.display = 'block';
    } catch (e) {
        showToast('加载题目失败: ' + e.message, 'error');
    }
}

function exitStudy() {
    document.getElementById('study-config').style.display = 'block';
    document.getElementById('study-question').style.display = 'none';
    if (studySessionId) {
        api('PATCH', `/api/study/sessions/${studySessionId}`, {
            questions_answered: _sessionCount || 0,
            correct_count: _sessionCorrect,
            xp_earned: _sessionXp,
        }).catch(() => {});
        studySessionId = null;
    }
    _sessionCount = 0;
    _sessionCorrect = 0;
    _sessionXp = 0;
}
