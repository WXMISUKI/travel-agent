// 前端主逻辑 - 修复多次对话问题
const API_BASE = 'http://localhost:8000';

let messages = [];
let isLoading = false;
let abortController = null;

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
        headers: { 'Content-Type': 'application/json' },
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
            if (line.startsWith('data: ')) {
                try {
                    const data = JSON.parse(line.slice(6));
                    handleStreamData(data);
                } catch (e) {}
            }
        }
    }
}

function handleStreamData(data) {
    switch (data.type) {
        case 'thinking':
            updateThinking(data.content);
            break;
        case 'content':
            appendContent(data.content);
            break;
        case 'done':
            finishMessage();
            break;
        case 'error':
            appendContent(data.content);
            break;
        case 'fallback':
            // 处理降级流程消息
            handleFallbackMessage(data);
            break;
        case 'step_status':
            // 处理步骤状态消息
            handleStepStatus(data);
            break;
        case 'plan':
            // 处理执行计划消息
            handlePlanMessage(data);
            break;
        case 'todo':
            // 处理TODO列表消息
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
    thinkingContent.className = 'thinking-content';
    thinkingContent.id = 'thinking-' + Date.now(); // 唯一ID
    
    thinkingEl.appendChild(thinkingHeader);
    thinkingEl.appendChild(thinkingContent);
    
    // 回复内容
    const contentEl = document.createElement('div');
    contentEl.className = 'content markdown-body';
    contentEl.id = 'content-' + Date.now(); // 唯一ID
    
    contentWrap.appendChild(thinkingEl);
    contentWrap.appendChild(contentEl);
    
    msgEl.appendChild(avatar);
    msgEl.appendChild(contentWrap);
    
    messagesEl.appendChild(msgEl);
    
    // 保存引用用于更新
    window.currentThinking = thinkingContent;
    window.currentContent = contentEl;
    
    messages.push({ role: 'assistant', content: '' });
    scrollToBottom();
}

function updateThinking(steps) {
    if (!window.currentThinking) return;
    
    const content = Array.isArray(steps) ? steps.join('\n') : steps;
    window.currentThinking.innerHTML = content.split('\n').map(s => `<div>${s}</div>`).join('');
    scrollToBottom();
}

function appendContent(text) {
    if (!window.currentContent) return;
    
    if (typeof marked !== 'undefined') {
        window.currentContent.innerHTML = marked.parse(text);
    } else {
        window.currentContent.innerHTML = text.replace(/\n/g, '<br>');
    }
    
    // 更新历史
    if (messages.length > 0) {
        messages[messages.length - 1].content += text;
    }
    
    scrollToBottom();
}

function toggleThinking(container) {
    const content = container.querySelector('.thinking-content');
    const icon = container.querySelector('.toggle-icon');
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '▲';
    } else {
        content.style.display = 'none';
        icon.textContent = '▼';
    }
}

function finishMessage() {
    // 可以收起思考过程
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