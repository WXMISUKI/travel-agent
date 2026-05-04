// 前端主逻辑 - 修复流式输出 + 耗时展示
const API_BASE =
    window.__API_BASE__ ||
    (window.location.hostname === 'localhost' ? 'http://localhost:8000' : '');
const API_KEY = window.__API_KEY__ || '';

let messages = [];
let isLoading = false;
let abortController = null;
let thinkingLines = [];
let currentAssistantBuffer = '';
let metricsState = null;
let isStreamingContent = false;
let rafPending = false;

async function sendMessage() {
    const inputEl = document.getElementById('userInput');
    const message = inputEl.value.trim();
    if (!message || isLoading) return;
    
    // 添加用户消息
    addMessage('user', message);
    inputEl.value = '';
    setLoading(true);
    
    try {
        await sendStreamRequest(message);
    } catch (error) {
        console.error('Error:', error);
        if (error.name !== 'AbortError') {
            addMessage('assistant', `错误: ${error.message}`);
        }
    }
    
    setLoading(false);
}

async function sendStreamRequest(message) {
    abortController = new AbortController();
    
    const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            ...(API_KEY ? { 'x-api-key': API_KEY } : {})
        },
        body: JSON.stringify({ message: message, history: getHistory() }),
        signal: abortController.signal
    });
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    
    // 创建新消息
    createNewAssistantMessage();
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            if (trimmed.startsWith('data: ')) {
                try {
                    const data = JSON.parse(trimmed.slice(6));
                    handleStreamData(data);
                } catch (e) {
                    console.warn('[SSE] JSON parse error:', e.message, trimmed.slice(0, 120));
                }
            }
        }
    }
}

function handleStreamData(data) {
    switch (data.type) {
        case 'start':
            showThinkingIndicator(true);
            break;
        case 'thinking_delta':
            appendThinkingLine(data.content);
            break;
        case 'content':
            showThinkingIndicator(false);
            isStreamingContent = true;
            appendContent(data.content);
            break;
        case 'done':
            showThinkingIndicator(false);
            finishMessage();
            break;
        case 'error':
            showThinkingIndicator(false);
            appendContent(data.content);
            break;
        case 'fallback':
            handleFallbackMessage(data);
            break;
        case 'step_status':
            handleStepStatus(data);
            break;
        case 'metric':
            handleMetric(data);
            break;
        case 'plan':
            handlePlanMessage(data);
            break;
        case 'todo':
            handleTodoMessage(data);
            break;
    }
}

// 处理降级消息
function handleFallbackMessage(data) {
    if (!window.currentThinking) return;
    
    const msg = data.message || '';
    const icon = data.status === 'success' ? '✅' : '🔄';
    
    const fallbackEl = document.createElement('div');
    fallbackEl.className = 'fallback-message';
    fallbackEl.innerHTML = `<span class="fallback-icon">${icon}</span> ${msg}`;
    
    window.currentThinking.appendChild(fallbackEl);
    scrollToBottom();
}

// 处理步骤状态消息
function handleStepStatus(data) {
    if (!window.currentThinking) return;
    
    const statusIcon = {
        'running': '🔄',
        'completed': '✅',
        'failed': '❌',
        'fallback_success': '✅',
        'error': '❌'
    }[data.status] || '⬜';
    
    const stepEl = document.createElement('div');
    stepEl.className = `step-status step-${data.status}`;
    stepEl.innerHTML = `<span class="step-icon">${statusIcon}</span> 步骤${data.step_id}: ${data.status}`;
    
    window.currentThinking.appendChild(stepEl);
    scrollToBottom();
}

// 处理执行计划消息
function handlePlanMessage(data) {
    if (!window.currentThinking) return;
    
    const planEl = document.createElement('div');
    planEl.className = 'plan-message';
    
    let stepsHtml = '';
    if (data.plan && data.plan.steps) {
        stepsHtml = data.plan.steps.map(s => 
            `<div class="plan-step">⏳ [${s.id}] ${s.tool}: ${s.purpose}</div>`
        ).join('');
    }
    
    planEl.innerHTML = `<div class="plan-header">📋 执行计划</div>${stepsHtml}`;
    window.currentThinking.appendChild(planEl);
    scrollToBottom();
}

// 处理TODO列表消息
function handleTodoMessage(data) {
    if (!window.currentThinking) return;
    
    const todoEl = document.createElement('div');
    todoEl.className = 'todo-list';
    
    let itemsHtml = '';
    if (data.items) {
        itemsHtml = data.items.map(item => 
            `<div class="todo-item">${item}</div>`
        ).join('');
    }
    
    todoEl.innerHTML = `<div class="todo-header">📝 待办事项</div>${itemsHtml}`;
    window.currentThinking.appendChild(todoEl);
    scrollToBottom();
}

// 创建新消息容器
function createNewAssistantMessage() {
    const messagesEl = document.getElementById('messages');

    const msgEl = document.createElement('div');
    msgEl.className = 'message assistant';

    // 头像
    const avatar = document.createElement('div');
    avatar.className = 'avatar';
    avatar.textContent = '✈️';

    // 内容区域
    const contentWrap = document.createElement('div');
    contentWrap.className = 'content-wrapper';

    // 思考容器
    const thinkingEl = document.createElement('div');
    thinkingEl.className = 'thinking-container';

    const thinkingHeader = document.createElement('div');
    thinkingHeader.className = 'thinking-header';
    thinkingHeader.innerHTML = '🔍 思考过程 <span class="toggle-icon">▼</span>';
    thinkingHeader.onclick = () => toggleThinking(thinkingEl);

    const thinkingContent = document.createElement('div');
    thinkingContent.className = 'thinking-content active';

    const thinkingIndicator = document.createElement('div');
    thinkingIndicator.className = 'thinking-indicator';
    thinkingIndicator.innerHTML = `
        <span class="thinking-spinner"></span>
        <span class="thinking-text">正在分析</span>
        <span class="thinking-dots"><i></i><i></i><i></i></span>
    `;
    thinkingContent.appendChild(thinkingIndicator);

    const metricsPanel = document.createElement('div');
    metricsPanel.className = 'metrics-panel';
    metricsPanel.innerHTML = `
        <div class="metrics-title">⏱️ 耗时明细</div>
        <div class="metrics-summary">
            <span data-metric="plan_ms">Plan: --</span>
            <span data-metric="llm_ms">LLM: --</span>
            <span data-metric="total_ms">Total: --</span>
        </div>
        <div class="metrics-tools" data-metric-tools></div>
    `;
    thinkingContent.appendChild(metricsPanel);

    thinkingEl.appendChild(thinkingHeader);
    thinkingEl.appendChild(thinkingContent);

    // 耗时摘要条（显示在内容区域上方）
    const timingBar = document.createElement('div');
    timingBar.className = 'timing-bar';
    timingBar.innerHTML = '<span class="timing-bar-text">⏱️ 处理中...</span>';

    // 回复内容
    const contentEl = document.createElement('div');
    contentEl.className = 'content markdown-body';

    contentWrap.appendChild(thinkingEl);
    contentWrap.appendChild(timingBar);
    contentWrap.appendChild(contentEl);

    msgEl.appendChild(avatar);
    msgEl.appendChild(contentWrap);

    messagesEl.appendChild(msgEl);

    // 保存引用用于更新
    window.currentThinking = thinkingContent;
    window.currentContent = contentEl;
    window.currentTimingBar = timingBar;
    thinkingLines = [];
    currentAssistantBuffer = '';
    metricsState = { plan_ms: null, llm_ms: null, total_ms: null, tools: {} };
    isStreamingContent = false;
    rafPending = false;

    messages.push({ role: 'assistant', content: '' });
    scrollToBottom();
}

function appendThinkingLine(line) {
    if (!window.currentThinking || !line) return;
    showThinkingIndicator(false);
    thinkingLines.push(line);
    const row = document.createElement('div');
    row.className = 'thinking-step';
    row.textContent = line;
    window.currentThinking.appendChild(row);
    scrollToBottom();
}

function showThinkingIndicator(show) {
    if (!window.currentThinking) return;
    let indicator = window.currentThinking.querySelector('.thinking-indicator');
    if (!indicator && show) {
        indicator = document.createElement('div');
        indicator.className = 'thinking-indicator';
        indicator.innerHTML = `
            <span class="thinking-spinner"></span>
            <span class="thinking-text">正在分析</span>
            <span class="thinking-dots"><i></i><i></i><i></i></span>
        `;
        window.currentThinking.prepend(indicator);
    }
    if (indicator) {
        indicator.style.display = show ? 'flex' : 'none';
    }
}

function appendContent(text) {
    if (!window.currentContent) return;

    currentAssistantBuffer += text || '';

    // 更新历史
    if (messages.length > 0) {
        messages[messages.length - 1].content = currentAssistantBuffer;
    }

    if (!rafPending) {
        rafPending = true;
        requestAnimationFrame(() => {
            rafPending = false;
            if (!window.currentContent || !isStreamingContent) return;
            window.currentContent.style.whiteSpace = 'pre-wrap';
            window.currentContent.textContent = currentAssistantBuffer;
            scrollToBottom();
        });
    }
}

function toggleThinking(container) {
    const content = container.querySelector('.thinking-content');
    const icon = container.querySelector('.toggle-icon');
    content.classList.toggle('active');
    icon.textContent = content.classList.contains('active') ? '▲' : '▼';
}

function finishMessage() {
    showThinkingIndicator(false);
    isStreamingContent = false;
    if (window.currentContent && currentAssistantBuffer) {
        try {
            if (typeof marked !== 'undefined') {
                window.currentContent.style.whiteSpace = '';
                window.currentContent.innerHTML = marked.parse(currentAssistantBuffer);
            } else {
                window.currentContent.style.whiteSpace = 'pre-wrap';
                window.currentContent.textContent = currentAssistantBuffer;
            }
        } catch (e) {
            window.currentContent.style.whiteSpace = 'pre-wrap';
            window.currentContent.textContent = currentAssistantBuffer;
        }
    }
    currentAssistantBuffer = '';
}

function handleMetric(data) {
    if (!data || !data.name) return;
    if (!metricsState) metricsState = { plan_ms: null, llm_ms: null, total_ms: null, tools: {} };

    if (data.name === 'tool_ms') {
        const key = `${data.step_id || '?'}-${data.tool || 'tool'}`;
        metricsState.tools[key] = {
            stepId: data.step_id || '?',
            tool: data.tool || 'tool',
            value: Number(data.value || 0)
        };
    } else if (Object.prototype.hasOwnProperty.call(metricsState, data.name)) {
        metricsState[data.name] = Number(data.value || 0);
    }

    renderMetricsPanel();
    renderTimingBar();
}

function renderMetricsPanel() {
    if (!window.currentThinking) return;
    const panel = window.currentThinking.querySelector('.metrics-panel');
    if (!panel) return;

    const formatMs = (v) => (typeof v === 'number' && !Number.isNaN(v) ? `${v.toFixed(0)}ms` : '--');

    const planEl = panel.querySelector('[data-metric="plan_ms"]');
    const llmEl = panel.querySelector('[data-metric="llm_ms"]');
    const totalEl = panel.querySelector('[data-metric="total_ms"]');
    if (planEl) planEl.textContent = `Plan: ${formatMs(metricsState?.plan_ms)}`;
    if (llmEl) llmEl.textContent = `LLM: ${formatMs(metricsState?.llm_ms)}`;
    if (totalEl) totalEl.textContent = `Total: ${formatMs(metricsState?.total_ms)}`;

    const toolsWrap = panel.querySelector('[data-metric-tools]');
    if (!toolsWrap) return;
    const tools = Object.values(metricsState?.tools || {}).sort((a, b) => Number(a.stepId) - Number(b.stepId));
    if (!tools.length) {
        toolsWrap.innerHTML = '<div class="metric-tool-item metric-empty">暂无工具步骤耗时</div>';
        return;
    }
    toolsWrap.innerHTML = tools
        .map(t => `<div class="metric-tool-item">步骤${t.stepId} ${t.tool}: ${formatMs(t.value)}</div>`)
        .join('');
}

function renderTimingBar() {
    if (!window.currentTimingBar || !metricsState) return;
    const fmt = (v) => (typeof v === 'number' && !Number.isNaN(v) ? `${v.toFixed(0)}ms` : null);

    const parts = [];
    const plan = fmt(metricsState.plan_ms);
    if (plan) parts.push(`计划 ${plan}`);

    const tools = Object.values(metricsState.tools || {});
    for (const t of tools.sort((a, b) => Number(a.stepId) - Number(b.stepId))) {
        parts.push(`${t.tool} ${fmt(t.value)}`);
    }

    const llm = fmt(metricsState.llm_ms);
    if (llm) parts.push(`生成 ${llm}`);

    const total = fmt(metricsState.total_ms);
    if (total) parts.push(`总计 ${total}`);

    if (parts.length) {
        window.currentTimingBar.innerHTML = `<span class="timing-bar-text">⏱️ ${parts.join(' · ')}</span>`;
        window.currentTimingBar.style.display = 'block';
    }
}

function addMessage(role, content) {
    if (!content) return;
    
    const messagesEl = document.getElementById('messages');
    const msgEl = document.createElement('div');
    msgEl.className = `message ${role}`;
    
    const avatar = role === 'user' ? '👤' : '✈️';
    let html;
    if (role === 'assistant' && typeof marked !== 'undefined') {
        html = marked.parse(content);
    } else {
        html = String(content).replace(/\n/g, '<br>');
    }
    
    msgEl.innerHTML = `<div class="avatar">${avatar}</div><div class="content">${html}</div>`;
    messagesEl.appendChild(msgEl);
    
    scrollToBottom();
    messages.push({ role, content });
}

function getHistory() {
    return messages.slice(-10).map(m => ({ role: m.role, content: m.content }));
}

function scrollToBottom() {
    document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
}

function setLoading(loading) {
    isLoading = loading;
    document.getElementById('userInput').disabled = loading;
    document.getElementById('sendBtn').disabled = loading;
    document.getElementById('sendBtn').style.display = loading ? 'none' : 'inline-block';
    document.getElementById('stopBtn').style.display = loading ? 'inline-block' : 'none';
}

function stopGenerating() {
    if (abortController) abortController.abort();
    addMessage('assistant', '<br>[已停止]');
    setLoading(false);
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('userInput').addEventListener('keyup', e => {
        if (e.key === 'Enter') sendMessage();
    });
});
