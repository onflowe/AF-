/**
 * main.ts - 应用入口
 *
 * 启动聊天 UI 和 Live2D 模型，将它们连接在一起。
 */

import { initChat, onAiResponse } from './chat';
import { Live2DModel } from './model-wrapper';

// 将 Live2D 实例暴露到 window，方便调试
declare global {
  interface Window {
    live2d: Live2DModel | null;
  }
}

window.addEventListener('load', async () => {
  // ---- 1. 初始化聊天 UI ----
  initChat();

  // ---- 2. 初始化 Live2D 模型 ----
  const container = document.getElementById('live2d-container');
  if (!container) {
    console.error('[Main] #live2d-container not found.');
    return;
  }

  const live2d = new Live2DModel();
  const success = await live2d.initialize(
    container,
    '/Resources/Remielle_DanV3/',
    'Remielle_DanV3.model3.json'
  );

  if (!success) {
    console.error('[Main] Live2D model initialization failed.');
    // 即使模型加载失败，聊天仍可用
    window.live2d = null;
    return;
  }

  // 暴露到 window 供调试
  window.live2d = live2d;

  // ---- 3. 连接 AI 回复与 Live2D 表情 ----
  onAiResponse((responseText) => {
    // 简单的情感→表情映射
    const lower = responseText.toLowerCase();

    // 检测开心
    if (/[😊😂🤣😄😆😁😃]/.test(responseText) || /\b(ha|he|hi){2,}\b/i.test(lower) ||
        /开心|哈哈|太好|棒|不错|喜欢/.test(responseText)) {
      live2d.setParameters({
        'ParamEyeLSmile': 0.7,
        'ParamEyeRSmile': 0.7,
        'ParamMouthForm': 0.5,
        'ParamCheek': 0.4
      });
      // 2 秒后恢复
      setTimeout(() => {
        live2d.setParameters({
          'ParamEyeLSmile': 0,
          'ParamEyeRSmile': 0,
          'ParamMouthForm': 0,
          'ParamCheek': 0
        });
      }, 2000);
    }

    // 检测惊讶
    if (/[😲😯😮]/.test(responseText) || /天哪|居然|真的吗|哇|什么/.test(responseText)) {
      live2d.setParameters({
        'ParamEyeLOpen': 0.9,
        'ParamBrowLY': 0.7,
        'ParamBrowRY': 0.7,
        'ParamMouthOpenY': 0.4
      });
      setTimeout(() => {
        live2d.setParameters({
          'ParamEyeLOpen': 0,
          'ParamBrowLY': 0,
          'ParamBrowRY': 0,
          'ParamMouthOpenY': 0
        });
      }, 1500);
    }

    // 模拟说话（嘴巴动画）
    let talkPhase = 0;
    const talkInterval = setInterval(() => {
      const mouthOpen = 0.15 + Math.sin(talkPhase) * 0.15;
      live2d.setParameter('ParamMouthOpenY', mouthOpen);
      talkPhase += 0.4;
    }, 60);

    // 根据回复长度决定"说话"时长
    const talkDuration = Math.min(responseText.length * 50, 4000);
    setTimeout(() => {
      clearInterval(talkInterval);
      live2d.setParameter('ParamMouthOpenY', 0);
    }, talkDuration);
  });

  console.log('[Main] Application ready. Access `window.live2d` to control the model.');
});
