// 前端主逻辑
const API_BASE = 'http://localhost:8000';

class TravelChat {
    constructor() {
        this.messages = [];
        this.isLoading = false;
        
        this.init();
    }
    
    init() {
        // 获取DOM元素
        this.messagesEl = document.getElementById('messages');
        this.inputEl = document.getElementById('userInput');
        this.sendBtn = document.getElementById('sendBtn');
        
        // 绑定事件
        this.bindEvents();
    }
    
    bindEvents() {
        // 发送按钮点击
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        // 输入框回车
        this.inputEl.addEventListener('keyup', (e) => {
            if (e.key === 'Enter') {
                this.sendMessage();
            }
        });
    }
    
    async sendMessage() {
        const message = this.inputEl.value.trim();
        if (!message || this.isLoading) return;
        
        // 添加用户消息
        this.addMessage('user', message);
        this.inputEl.value = '';
        
        // 设置加载状态
        this.setLoading(true);
        
        try {
            // 构建请求数据
            const requestData = {
                message: message,
                history: this.getHistory() || []
            };
            
            console.log('发送请求:', requestData);
            
            // 调用API
            const response = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            console.log('响应状态:', response.status);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('响应数据:', data);
            
            // 处理响应
            if (data.error) {
                this.addMessage('assistant', `抱歉，发生了错误：${data.error}`);
            } else if (!data.response) {
                this.addMessage('assistant', '抱歉，未收到有效响应，请稍后重试。');
            } else {
                this.addMessage('assistant', data.response);
            }
            
        } catch (error) {
            console.error('Error:', error);
            this.addMessage('assistant', `抱歉，无法连接到服务器：${error.message}`);
        }
        
        this.setLoading(false);
    }
    
    addMessage(role, content) {
        if (!content) return; // 防御：空内容不添加
        
        const messageEl = document.createElement('div');
        messageEl.className = `message ${role}`;
        
        const avatar = role === 'user' ? '👤' : '✈️';
        
        // 处理换行
        const formattedContent = String(content).replace(/\n/g, '<br>');
        
        messageEl.innerHTML = `
            <div class="avatar">${avatar}</div>
            <div class="content">${formattedContent}</div>
        `;
        
        this.messagesEl.appendChild(messageEl);
        
        // 滚动到底部
        this.scrollToBottom();
        
        // 保存到历史
        this.messages.push({ role, content });
    }
    
    getHistory() {
        // 返回最近6条消息作为上下文，确保返回数组
        const history = this.messages.slice(-12).map(m => ({
            role: m.role,
            content: m.content
        }));
        return history;
    }
    
    scrollToBottom() {
        this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
    }
    
    setLoading(loading) {
        this.isLoading = loading;
        this.inputEl.disabled = loading;
        this.sendBtn.disabled = loading;
        this.sendBtn.textContent = loading ? '发送中...' : '发送';
        
        if (loading) {
            // 添加加载指示器
            const loadingEl = document.createElement('div');
            loadingEl.className = 'message assistant';
            loadingEl.id = 'loading';
            loadingEl.innerHTML = `
                <div class="avatar">✈️</div>
                <div class="content">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            `;
            this.messagesEl.appendChild(loadingEl);
            this.scrollToBottom();
        } else {
            // 移除加载指示器
            const loadingEl = document.getElementById('loading');
            if (loadingEl) {
                loadingEl.remove();
            }
        }
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    new TravelChat();
});