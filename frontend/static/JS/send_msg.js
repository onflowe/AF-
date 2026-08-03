// 获取DOM元素
        const API_URL = "/api/chat/record"
        const chatMessages = document.getElementById('chatMessages');
        const userInput = document.getElementById('userInput');
        const submitBtn = document.getElementById('submitBtn');
         // 按回车键发送
        userInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });

        // 发送消息函数
        async function sendMessage() {
            const message = userInput.value.trim();//==================================================================

            // 空消息不发送
            if (!message) return;

            // 显示用户消息
            addMessage(message, 'user');

            // 清空输入框
            userInput.value = '';

            // 禁用按钮，防止重复发送
            submitBtn.disabled = true;

            // 显示加载中
            const loadingMsg = addMessage('正在思考...', 'loading');

            try {
                // 调用后端API ===========================================================================================
                const response = await fetch(API_URL, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        Human_content: message,
                        session_id: "s001",
                        user_id: "u001"
                        // 如果需要传用户ID、会话ID等，在这里加
                        // user_id: 'user_001',
                        // conversation_id: 'conv_001'
                    })
                });

                if (!response.ok) {
                    throw new Error('请求失败: ' + response.status);
                }

                const data = await response.json();
                console.log('后端返回的数据:', data);
                // 移除加载消息
                loadingMsg.remove();

                // 显示AI回复
                // 假设后端返回格式：{ "response": "AI的回答内容" }

                addMessage(data.response || data.message || data.result, 'ai');

            } catch (error) {
                // 移除加载消息
                loadingMsg.remove();

                // 显示错误信息
                addMessage('抱歉，出错了：' + error.message, 'ai');
                console.error('发送消息失败:', error);
            } finally {
                // 重新启用按钮
                submitBtn.disabled = false;
                // 输入框重新聚焦
                userInput.focus();
            }
        }

        // 添加消息到聊天区域
        function addMessage(text, type) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + type;
            messageDiv.textContent = text;
            chatMessages.appendChild(messageDiv);

            // 自动滚动到底部
            chatMessages.scrollTop = chatMessages.scrollHeight;

            return messageDiv;
        }