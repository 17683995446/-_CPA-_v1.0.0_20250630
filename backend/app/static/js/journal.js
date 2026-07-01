// ===== 分录练习页面 =====
async function loadJournalPage() {
    try {
        const accounts = await api('GET', '/api/journal/accounts');
        const datalist = document.getElementById('account-list');
        datalist.innerHTML = Object.keys(accounts).map(a => `<option value="${a}">`).join('');
    } catch {}
}

function addJournalLine() {
    const container = document.getElementById('journal-lines');
    const line = document.createElement('div');
    line.className = 'journal-line';
    line.innerHTML = `
        <input type="text" class="jl-account" placeholder="科目（如：银行存款）" list="account-list">
        <select class="jl-direction"><option value="借">借</option><option value="贷">贷</option></select>
        <input type="number" class="jl-amount" placeholder="金额" step="0.01" oninput="updateBalanceIndicator()">
        <button class="btn-remove-line" onclick="removeJournalLine(this); updateBalanceIndicator()">×</button>
    `;
    container.appendChild(line);
}

function removeJournalLine(btn) {
    const lines = document.querySelectorAll('.journal-line');
    if (lines.length > 1) btn.parentElement.remove();
}

function clearJournalLines() {
    const container = document.getElementById('journal-lines');
    container.innerHTML = `
        <div class="journal-line">
            <input type="text" class="jl-account" placeholder="科目（如：银行存款）" list="account-list">
            <select class="jl-direction"><option value="借">借</option><option value="贷">贷</option></select>
            <input type="number" class="jl-amount" placeholder="金额" step="0.01" oninput="updateBalanceIndicator()">
            <button class="btn-remove-line" onclick="removeJournalLine(this); updateBalanceIndicator()">×</button>
        </div>
    `;
    document.getElementById('balance-indicator').style.display = 'none';
    document.getElementById('journal-result').className = 'journal-result';
    document.getElementById('journal-result').innerHTML = '';
}

function loadJournalExample() {
    const container = document.getElementById('journal-lines');
    const example = [
        { account: '银行存款', direction: '借', amount: 10000 },
        { account: '实收资本', direction: '贷', amount: 10000 },
    ];
    container.innerHTML = example.map(e => `
        <div class="journal-line">
            <input type="text" class="jl-account" value="${e.account}" list="account-list">
            <select class="jl-direction"><option value="借" ${e.direction==='借'?'selected':''}>借</option><option value="贷" ${e.direction==='贷'?'selected':''}>贷</option></select>
            <input type="number" class="jl-amount" value="${e.amount}" step="0.01" oninput="updateBalanceIndicator()">
            <button class="btn-remove-line" onclick="removeJournalLine(this); updateBalanceIndicator()">×</button>
        </div>
    `).join('');
    updateBalanceIndicator();
}

function updateBalanceIndicator() {
    const lines = document.querySelectorAll('.journal-line');
    let debit = 0, credit = 0;
    lines.forEach(line => {
        const dir = line.querySelector('.jl-direction').value;
        const amt = parseFloat(line.querySelector('.jl-amount').value) || 0;
        if (dir === '借') debit += amt;
        else credit += amt;
    });
    const el = document.getElementById('balance-indicator');
    if (debit === 0 && credit === 0) {
        el.style.display = 'none';
        return;
    }
    el.style.display = 'flex';
    if (debit === credit) {
        el.className = 'balance-indicator balanced';
        el.innerHTML = `<span>✅</span> 借贷平衡：借方 ${debit.toFixed(2)} = 贷方 ${credit.toFixed(2)}`;
    } else {
        el.className = 'balance-indicator unbalanced';
        el.innerHTML = `<span>❌</span> 借贷不平衡：借方 ${debit.toFixed(2)} ≠ 贷方 ${credit.toFixed(2)}（差额 ${Math.abs(debit-credit).toFixed(2)}）`;
    }
}

async function validateJournal() {
    const lines = document.querySelectorAll('.journal-line');
    const journalLines = [];
    lines.forEach(line => {
        const account = line.querySelector('.jl-account').value.trim();
        const direction = line.querySelector('.jl-direction').value;
        const amount = parseFloat(line.querySelector('.jl-amount').value);
        if (account && !isNaN(amount)) {
            journalLines.push({ account, direction, amount });
        }
    });

    if (journalLines.length === 0) {
        showToast('请至少填写一行完整的分录', 'error');
        return;
    }

    try {
        const result = await api('POST', '/api/journal/validate', { lines: journalLines });
        const el = document.getElementById('journal-result');
        el.className = 'journal-result show ' + (result.is_valid ? 'valid' : 'invalid');

        let html = '';
        if (result.is_valid) {
            html = `<h4 style="color:var(--success)">✅ 分录正确！</h4>`;
        } else {
            html = `<h4 style="color:var(--danger)">❌ 分录有误</h4>`;
            html += '<div class="error-list">';
            result.errors.forEach(e => {
                html += `<div class="error-item"><strong>${e.error_type}</strong>: ${e.message}</div>`;
            });
            html += '</div>';
        }

        html += `<div style="margin-top:12px;font-size:13px;color:var(--text-light)">
            借方合计: ${result.total_debit} | 贷方合计: ${result.total_credit} | 差额: ${result.balance_diff}
        </div>`;

        if (result.corrections && result.corrections.length > 0) {
            html += '<div style="margin-top:8px"><strong>修正建议：</strong></div><div class="error-list">';
            result.corrections.forEach(c => {
                html += `<div class="correction-item">💡 ${c.suggestion}</div>`;
            });
            html += '</div>';
        }

        if (result.explanation) {
            html += `<div style="margin-top:12px;padding:12px;background:rgba(99,102,241,0.05);border-radius:8px;font-size:13px"><strong>分录解释：</strong><br>${result.explanation}</div>`;
        }

        el.innerHTML = html;
    } catch (e) {
        showToast('验证失败: ' + e.message, 'error');
    }
}
