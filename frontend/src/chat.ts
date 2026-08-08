/**
 * chat.ts - AI 聊天模块
 *
 * 负责聊天 UI 的消息发送/接收，通过 POST /api/chat/record 连接 FastAPI 后端。
 */

const API_URL = '/api/chat/record';

// AI 回复回调列表
type AiResponseCallback = (response: string) => void;
const _aiResponseCallbacks: AiResponseCallback[] = [];

/**
 * 初始化聊天 UI：绑定 DOM 事件
 */
export function initChat(): void {
  const chatMessages = document.getElementById('chatMessages');
  const userInput = document.getElementById('userInput') as HTMLInputElement;
  const submitBtn = document.getElementById('submitBtn') as HTMLButtonElement;

  if (!chatMessages || !userInput || !submitBtn) {
    console.error('[Chat] Required DOM elements not found.');
    return;
  }

  // 发送按钮点击
  submitBtn.addEventListener('click', () => sendMessage());

  // 回车键发送
  userInput.addEventListener('keypress', (e: KeyboardEvent) => {
    if (e.key === 'Enter') {
      sendMessage();
    }
  });
}

/**
 * 注册 AI 回复回调（每次 AI 回复时触发）
 * @param callback 回调函数，参数为 AI 回复文本
 */
export function onAiResponse(callback: AiResponseCallback): void {
  _aiResponseCallbacks.push(callback);
}

/**
 * 发送消息
 */
async function sendMessage(): Promise<void> {
  const chatMessages = document.getElementById('chatMessages');
  const userInput = document.getElementById('userInput') as HTMLInputElement;
  const submitBtn = document.getElementById('submitBtn') as HTMLButtonElement;

  if (!chatMessages || !userInput || !submitBtn) return;

  const message = userInput.value.trim();
  if (!message) return;

  // 显示用户消息
  addMessage(chatMessages, message, 'user');
  userInput.value = '';
  submitBtn.disabled = true;

  // 显示加载中
  const loadingMsg = addMessage(chatMessages, '正在思考...', 'loading');

  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        Human_content: message,
        session_id: 's001',
        user_id: 'u001'
      })
    });

    loadingMsg.remove();

    if (!response.ok) {
      throw new Error('请求失败: ' + response.status);
    }

    const data = await response.json();
    console.log('[Chat] 后端返回:', data);

    const aiText = data.response || data.message || data.result || '(无回复)';
    addMessage(chatMessages, aiText, 'ai');

    // 触发 AI 回复回调
    for (const cb of _aiResponseCallbacks) {
      try {
        cb(aiText);
      } catch (err) {
        console.error('[Chat] AI response callback error:', err);
      }
    }
  } catch (error) {
    loadingMsg.remove();
    const errMsg = '抱歉，出错了：' + (error instanceof Error ? error.message : '未知错误');
    addMessage(chatMessages, errMsg, 'ai');
    console.error('[Chat] 发送消息失败:', error);
  } finally {
    submitBtn.disabled = false;
    userInput.focus();
  }
}

/**
 * 添加消息到聊天区域
 */
function addMessage(
  container: HTMLElement,
  text: string,
  type: 'user' | 'ai' | 'loading'
): HTMLElement {
  const msgDiv = document.createElement('div');
  msgDiv.className = 'message ' + type;
  msgDiv.textContent = text;
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
  return msgDiv;
}
