/**
 * Live2DModel - 简化的 Live2D 模型包装类
 *
 * 将 Cubism SDK 的复杂架构精简为一个类，提供简洁的 API：
 * - initialize(): 加载模型并开始渲染
 * - setParameter() / setParameters(): 控制模型参数
 * - setDrag(): 控制头部/眼球方向
 * - setVisible(): 暂停/恢复渲染
 * - destroy(): 完全清理
 */

import { CubismDefaultParameterId } from './Framework/src/cubismdefaultparameterid';
import { CubismModelSettingJson } from './Framework/src/cubismmodelsettingjson';
import {
  BreathParameterData,
  CubismBreath
} from './Framework/src/effect/cubismbreath';
import { CubismEyeBlink } from './Framework/src/effect/cubismeyeblink';
import { ICubismModelSetting } from './Framework/src/icubismmodelsetting';
import { CubismIdHandle } from './Framework/src/id/cubismid';
import { CubismFramework, Option as CubismOption } from './Framework/src/live2dcubismframework';
import { CubismMatrix44 } from './Framework/src/math/cubismmatrix44';
import { CubismModelMatrix } from './Framework/src/math/cubismmodelmatrix';
import { CubismMoc } from './Framework/src/model/cubismmoc';
import { CubismModel } from './Framework/src/model/cubismmodel';
import { CubismPhysics } from './Framework/src/physics/cubismphysics';
import { CubismRenderer_WebGL } from './Framework/src/rendering/cubismrenderer_webgl';
import { csmVector } from './Framework/src/type/csmvector';

/**
 * 纹理信息
 */
interface TextureInfo {
  id: WebGLTexture;
  width: number;
  height: number;
}

/**
 * 简化版 Live2D 模型控制类
 */
export class Live2DModel {
  // ---- 私有成员 ----
  private _canvas: HTMLCanvasElement | null = null;
  private _gl: WebGL2RenderingContext | null = null;
  private _container: HTMLElement | null = null;

  private _modelSetting: ICubismModelSetting | null = null;
  private _model: CubismModel | null = null;
  private _renderer: CubismRenderer_WebGL | null = null;
  private _modelMatrix: CubismModelMatrix | null = null;

  private _breath: CubismBreath | null = null;
  private _eyeBlink: CubismEyeBlink | null = null;
  private _physics: CubismPhysics | null = null;

  private _projection: CubismMatrix44 = new CubismMatrix44();

  // 拖拽状态
  private _dragX = 0;
  private _dragY = 0;
  private _dragManager = { x: 0, y: 0 };

  // 用户自定义参数
  private _userParams: Map<string, number> = new Map();

  // 渲染循环
  private _visible = true;
  private _modelScale = 1.0; // 模型缩放（1.0=100%, 0.6=60%, 值越小模型越小）
  private _animationId: number | null = null;
  private _resizeObserver: ResizeObserver | null = null;
  private _lastTime = 0;

  // 参数 ID 缓存
  private _idParamAngleX!: CubismIdHandle;
  private _idParamAngleY!: CubismIdHandle;
  private _idParamAngleZ!: CubismIdHandle;
  private _idParamEyeBallX!: CubismIdHandle;
  private _idParamEyeBallY!: CubismIdHandle;
  private _idParamBodyAngleX!: CubismIdHandle;

  // 指针事件绑定
  private _boundOnPointerDown: (e: PointerEvent) => void;
  private _boundOnPointerMove: (e: PointerEvent) => void;
  private _boundOnPointerUp: (e: PointerEvent) => void;
  private _boundOnPointerLeave: (e: PointerEvent) => void;
  private _isPointerDown = false;
  private _lastPointerX = 0;
  private _lastPointerY = 0;

  constructor() {
    // 绑定指针事件处理函数以便后续移除
    this._boundOnPointerDown = this._onPointerDown.bind(this);
    this._boundOnPointerMove = this._onPointerMove.bind(this);
    this._boundOnPointerUp = this._onPointerUp.bind(this);
    this._boundOnPointerLeave = this._onPointerLeave.bind(this);
  }

  // ==================== 公开 API ====================

  /**
   * 初始化 Cubism Framework，在指定容器内创建 WebGL2 canvas，加载模型。
   *
   * @param container 放置 canvas 的 DOM 容器元素
   * @param modelPath 模型文件目录路径 (e.g. '/Resources/Remielle_DanV3/')
   * @param modelJson 模型 json 文件名 (e.g. 'Remielle_DanV3.model3.json')
   * @returns 加载成功返回 true
   */
  async initialize(
    container: HTMLElement,
    modelPath: string,
    modelJson: string
  ): Promise<boolean> {
    this._container = container;

    try {
      // 1. 创建 canvas
      this._canvas = document.createElement('canvas');
      this._canvas.style.width = '100%';
      this._canvas.style.height = '100%';
      this._canvas.style.display = 'block';
      this._canvas.style.cursor = 'grab';
      this._canvas.setAttribute('touch-action', 'none');
      container.appendChild(this._canvas);

      // 2. 获取 WebGL2 context
      this._gl = this._canvas.getContext('webgl2', {
        premultipliedAlpha: true,
        alpha: true
      }) as WebGL2RenderingContext | null;

      if (!this._gl) {
        console.error('[Live2DModel] WebGL2 is not available.');
        return false;
      }

      // 3. 初始化 Cubism Framework
      CubismFramework.startUp(new CubismOption());
      CubismFramework.initialize();

      // 4. 缓存参数 ID
      const idManager = CubismFramework.getIdManager();
      this._idParamAngleX = idManager.getId(CubismDefaultParameterId.ParamAngleX);
      this._idParamAngleY = idManager.getId(CubismDefaultParameterId.ParamAngleY);
      this._idParamAngleZ = idManager.getId(CubismDefaultParameterId.ParamAngleZ);
      this._idParamEyeBallX = idManager.getId(CubismDefaultParameterId.ParamEyeBallX);
      this._idParamEyeBallY = idManager.getId(CubismDefaultParameterId.ParamEyeBallY);
      this._idParamBodyAngleX = idManager.getId(CubismDefaultParameterId.ParamBodyAngleX);

      // 5. 加载 model3.json
      const modelHomeDir = modelPath;
      const settingResponse = await fetch(`${modelHomeDir}${modelJson}`);
      if (!settingResponse.ok) {
        console.error(`[Live2DModel] Failed to load ${modelJson}`);
        return false;
      }
      const settingBuffer = await settingResponse.arrayBuffer();
      this._modelSetting = new CubismModelSettingJson(settingBuffer, settingBuffer.byteLength);

      // 6. 加载 .moc3
      const mocFileName = this._modelSetting.getModelFileName();
      const mocResponse = await fetch(`${modelHomeDir}${mocFileName}`);
      if (!mocResponse.ok) {
        console.error(`[Live2DModel] Failed to load ${mocFileName}`);
        return false;
      }
      const mocBuffer = await mocResponse.arrayBuffer();
      const moc = CubismMoc.create(mocBuffer);
      if (!moc) {
        console.error('[Live2DModel] Failed to create CubismMoc.');
        return false;
      }
      this._model = moc.createModel();
      if (!this._model) {
        console.error('[Live2DModel] Failed to create CubismModel.');
        return false;
      }
      this._model.saveParameters();

      // 7. 设置 model matrix
      this._modelMatrix = new CubismModelMatrix(
        this._model.getCanvasWidth(),
        this._model.getCanvasHeight()
      );

      // 8. 加载物理
      const physicsFileName = this._modelSetting.getPhysicsFileName();
      if (physicsFileName) {
        const physicsResponse = await fetch(`${modelHomeDir}${physicsFileName}`);
        if (physicsResponse.ok) {
          const physicsBuffer = await physicsResponse.arrayBuffer();
          this._physics = CubismPhysics.create(physicsBuffer, physicsBuffer.byteLength);
          console.log('[Live2DModel] Physics loaded.');
        }
      }

      // 9. 设置呼吸
      this._setupBreath();

      // 10. 设置眨眼（如果模型有定义眨眼参数）
      this._setupEyeBlink();

      // 11. 创建渲染器
      this._renderer = new CubismRenderer_WebGL();
      this._renderer.initialize(this._model);
      this._renderer.startUp(this._gl!);

      // 12. 加载纹理
      await this._loadTextures(modelHomeDir);

      // 13. 设置 premultiplied alpha
      this._renderer.setIsPremultipliedAlpha(true);

      // 14. 设置 WebGL 状态
      this._gl.enable(this._gl.BLEND);
      this._gl.blendFunc(this._gl.SRC_ALPHA, this._gl.ONE_MINUS_SRC_ALPHA);

      // 15. 重设 canvas 大小
      this._resizeCanvas();

      // 16. 绑定指针事件（只绑定在 canvas 上）
      this._canvas.addEventListener('pointerdown', this._boundOnPointerDown);
      this._canvas.addEventListener('pointermove', this._boundOnPointerMove);
      this._canvas.addEventListener('pointerup', this._boundOnPointerUp);
      this._canvas.addEventListener('pointerleave', this._boundOnPointerLeave);

      // 17. 启动渲染循环
      this._lastTime = performance.now();
      this._startRenderLoop();

      // 18. 监听容器大小变化，自动同步 canvas 分辨率
      this._resizeObserver = new ResizeObserver(() => {
        this._resizeCanvas();
      });
      this._resizeObserver.observe(container);

      console.log('[Live2DModel] Initialization complete.');
      return true;
    } catch (error) {
      console.error('[Live2DModel] Initialization failed:', error);
      return false;
    }
  }

  /**
   * 设置单个模型参数值。
   * @param paramId 参数 ID，如 'ParamMouthOpenY', 'ParamEyeLOpen'
   * @param value 参数值 (0.0 - 1.0)
   */
  setParameter(paramId: string, value: number): void {
    this._userParams.set(paramId, Math.max(0, Math.min(1, value)));
  }

  /**
   * 获取模型参数当前值。
   * @param paramId 参数 ID
   * @returns 参数值 (0.0 - 1.0)
   */
  getParameter(paramId: string): number {
    if (!this._model) return 0;
    const id = CubismFramework.getIdManager().getId(paramId);
    return this._model.getParameterValueById(id);
  }

  /**
   * 批量设置模型参数（如用于表情控制）。
   * @param params 参数名到值的映射
   */
  setParameters(params: Record<string, number>): void {
    for (const [id, value] of Object.entries(params)) {
      this._userParams.set(id, Math.max(0, Math.min(1, value)));
    }
  }

  /**
   * 控制头部/眼球追踪方向。
   * @param x 水平方向 (-1.0 左 到 1.0 右)
   * @param y 垂直方向 (-1.0 下 到 1.0 上)
   */
  setDrag(x: number, y: number): void {
    this._dragX = Math.max(-1, Math.min(1, x));
    this._dragY = Math.max(-1, Math.min(1, y));
  }

  /**
   * 设置模型缩放比例。
   *
   * 原理：投影矩阵 scale 越大 → 更多世界坐标压入屏幕 → 模型越小。
   * 所以内部用 scaleRelative(1/s, 1/s) 来保证语义直观。
   *
   * @param scale 模型可见大小 (0.3 ~ 1.5, 默认 0.6)
   *              0.6 = 屏幕占比 60%（较小）
   *              1.0 = 100% 原始大小
   *              1.5 = 150%（放大）
   */
  setScale(scale: number): void {
    this._modelScale = Math.max(0.2, Math.min(2.0, scale));
  }

  /**
   * 暂停/恢复渲染。
   * @param visible 是否可见
   */
  setVisible(visible: boolean): void {
    this._visible = visible;
    if (this._canvas) {
      this._canvas.style.display = visible ? 'block' : 'none';
    }
  }

  /**
   * 获取内部的 canvas 元素。
   */
  getCanvas(): HTMLCanvasElement | null {
    return this._canvas;
  }

  /**
   * 完全清理：停止渲染循环，释放 WebGL 资源，移除 DOM 元素。
   */
  destroy(): void {
    // 停止渲染循环
    if (this._animationId !== null) {
      cancelAnimationFrame(this._animationId);
      this._animationId = null;
    }

    // 断开 ResizeObserver
    if (this._resizeObserver) {
      this._resizeObserver.disconnect();
      this._resizeObserver = null;
    }

    // 移除事件监听
    if (this._canvas) {
      this._canvas.removeEventListener('pointerdown', this._boundOnPointerDown);
      this._canvas.removeEventListener('pointermove', this._boundOnPointerMove);
      this._canvas.removeEventListener('pointerup', this._boundOnPointerUp);
      this._canvas.removeEventListener('pointerleave', this._boundOnPointerLeave);
    }

    // 释放渲染器
    if (this._renderer) {
      this._renderer.release();
      this._renderer = null;
    }

    // 释放模型
    if (this._model) {
      this._model = null;
    }

    // 移除 canvas
    if (this._canvas && this._canvas.parentElement) {
      this._canvas.parentElement.removeChild(this._canvas);
    }

    this._canvas = null;
    this._gl = null;
    this._modelSetting = null;
    this._physics = null;
    this._breath = null;
    this._eyeBlink = null;
    this._userParams.clear();

    console.log('[Live2DModel] Destroyed.');
  }

  // ==================== 私有方法 ====================

  /**
   * 设置呼吸动画参数
   */
  private _setupBreath(): void {
    this._breath = CubismBreath.create();

    const breathParameters = new csmVector<BreathParameterData>();
    breathParameters.pushBack(
      new BreathParameterData(this._idParamAngleX, 0.0, 15.0, 6.5345, 0.5)
    );
    breathParameters.pushBack(
      new BreathParameterData(this._idParamAngleY, 0.0, 8.0, 3.5345, 0.5)
    );
    breathParameters.pushBack(
      new BreathParameterData(this._idParamAngleZ, 0.0, 10.0, 5.5345, 0.5)
    );
    breathParameters.pushBack(
      new BreathParameterData(this._idParamBodyAngleX, 0.0, 4.0, 15.5345, 0.5)
    );
    breathParameters.pushBack(
      new BreathParameterData(
        CubismFramework.getIdManager().getId(CubismDefaultParameterId.ParamBreath),
        0.5,
        0.5,
        3.2345,
        1
      )
    );

    this._breath.setParameters(breathParameters);
  }

  /**
   * 设置眨眼
   */
  private _setupEyeBlink(): void {
    if (this._modelSetting && this._modelSetting.getEyeBlinkParameterCount() > 0) {
      this._eyeBlink = CubismEyeBlink.create(this._modelSetting);
    }
  }

  /**
   * 加载纹理
   */
  private async _loadTextures(modelHomeDir: string): Promise<void> {
    if (!this._modelSetting || !this._renderer) return;

    const textureCount = this._modelSetting.getTextureCount();

    for (let i = 0; i < textureCount; i++) {
      const textureFileName = this._modelSetting.getTextureFileName(i);
      if (!textureFileName) continue;

      const texturePath = modelHomeDir + textureFileName;
      const textureInfo = await this._loadTextureFromPng(texturePath);
      if (textureInfo) {
        this._renderer.bindTexture(i, textureInfo.id);
      }
    }
  }

  /**
   * 从 PNG 文件加载纹理到 WebGL
   */
  private _loadTextureFromPng(path: string): Promise<TextureInfo | null> {
    return new Promise(resolve => {
      const img = new Image();
      img.onload = () => {
        if (!this._gl) {
          resolve(null);
          return;
        }

        const gl = this._gl;
        const texture = gl.createTexture();
        if (!texture) {
          resolve(null);
          return;
        }

        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 1);
        gl.texImage2D(
          gl.TEXTURE_2D,
          0,
          gl.RGBA,
          gl.RGBA,
          gl.UNSIGNED_BYTE,
          img
        );
        gl.generateMipmap(gl.TEXTURE_2D);

        resolve({
          id: texture,
          width: img.width,
          height: img.height
        });
      };
      img.onerror = () => {
        console.error(`[Live2DModel] Failed to load texture: ${path}`);
        resolve(null);
      };
      img.src = path;
    });
  }

  /**
   * 重设 canvas 大小（基于容器尺寸和高 DPI）
   */
  private _resizeCanvas(): void {
    if (!this._canvas || !this._container) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = this._container.getBoundingClientRect();
    this._canvas.width = rect.width * dpr;
    this._canvas.height = rect.height * dpr;
  }

  /**
   * 启动渲染循环
   */
  private _startRenderLoop(): void {
    const loop = (): void => {
      if (!this._gl || !this._model || !this._renderer || !this._canvas) return;

      if (this._visible) {
        this._renderFrame();
      }

      this._animationId = requestAnimationFrame(loop);
    };
    this._animationId = requestAnimationFrame(loop);
  }

  /**
   * 渲染一帧
   */
  private _renderFrame(): void {
    if (!this._gl || !this._model || !this._renderer || !this._canvas || !this._modelMatrix) return;

    const gl = this._gl;
    const now = performance.now();
    const deltaTimeSeconds = Math.min((now - this._lastTime) / 1000, 0.5); // 防止大帧间隔
    this._lastTime = now;

    // 1. 清除 canvas（透明背景）
    gl.viewport(0, 0, this._canvas.width, this._canvas.height);
    gl.clearColor(0.0, 0.0, 0.0, 0.0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    // 2. 加载上一帧保存的参数基准状态
    this._model.loadParameters();

    // 3. 保存基准状态（拖拽/呼吸/物理在此基础上叠加，下帧恢复时不累积）
    this._model.saveParameters();

    // 4. 应用拖拽效果（每帧从基准状态叠加，不累积）
    this._model.addParameterValueById(this._idParamAngleX, this._dragX * 30);
    this._model.addParameterValueById(this._idParamAngleY, this._dragY * 30);
    this._model.addParameterValueById(this._idParamAngleZ, this._dragX * this._dragY * -30);
    this._model.addParameterValueById(this._idParamBodyAngleX, this._dragX * 10);
    this._model.addParameterValueById(this._idParamEyeBallX, this._dragX);
    this._model.addParameterValueById(this._idParamEyeBallY, this._dragY);

    // 5. 应用呼吸动画
    if (this._breath) {
      this._breath.updateParameters(this._model, deltaTimeSeconds);
    }

    // 6. 应用眨眼
    if (this._eyeBlink) {
      this._eyeBlink.updateParameters(this._model, deltaTimeSeconds);
    }

    // 7. 应用物理模拟
    if (this._physics) {
      this._physics.evaluate(this._model, deltaTimeSeconds);
    }

    // 8. 应用用户自定义参数
    const idManager = CubismFramework.getIdManager();
    this._userParams.forEach((value, paramId) => {
      const id = idManager.getId(paramId);
      this._model!.addParameterValueById(id, value);
    });

    // 9. 更新模型（提交所有参数变更）
    this._model.update();

    // 10. 计算投影矩阵
    this._updateProjection();

    // 11. 设置 MVP 矩阵并绘制
    this._projection.multiplyByMatrix(this._modelMatrix);
    this._renderer.setMvpMatrix(this._projection);
    this._renderer.setRenderState(null, [0, 0, this._canvas.width, this._canvas.height]);
    this._renderer.drawModel();
  }

  /**
   * 更新投影矩阵，适配画布宽高比。
   * 沿用 frontend1 LAppLive2DManager.onUpdate() 的 scale 方式，
   * 并叠加用户自定义的模型缩放。
   */
  private _updateProjection(): void {
    if (!this._canvas || !this._model || !this._modelMatrix) return;

    const width = this._canvas.width;
    const height = this._canvas.height;

    if (width === 0 || height === 0) return;

    this._projection.loadIdentity();

    if (this._model.getCanvasWidth() > 1.0 && width < height) {
      // 横长模型在竖长窗口：以模型宽度为基准
      this._modelMatrix.setWidth(2.0);
      this._projection.scale(1.0, width / height);
    } else {
      this._projection.scale(height / width, 1.0);
    }

    // 叠加用户自定义缩放：projection scale 越大 → 模型越小，
    // 所以用 scaleRelative(1/s, 1/s) 保证 s=0.6 时模型占屏幕 60%
    if (this._modelScale !== 1.0) {
      this._projection.scaleRelative(1.0 / this._modelScale, 1.0 / this._modelScale);
    }
  }

  // ==================== 指针事件处理 ====================

  private _onPointerDown(e: PointerEvent): void {
    this._isPointerDown = true;
    this._lastPointerX = e.clientX;
    this._lastPointerY = e.clientY;

    if (this._canvas) {
      this._canvas.style.cursor = 'grabbing';
      this._canvas.setPointerCapture(e.pointerId);
    }
  }

  private _onPointerMove(e: PointerEvent): void {
    if (!this._isPointerDown || !this._canvas) return;

    const dx = e.clientX - this._lastPointerX;
    const dy = e.clientY - this._lastPointerY;
    this._lastPointerX = e.clientX;
    this._lastPointerY = e.clientY;

    // 将像素位移转换为 -1 到 1 的范围
    const sensitivity = 0.005;
    this._dragX = Math.max(-1, Math.min(1, this._dragX + dx * sensitivity));
    this._dragY = Math.max(-1, Math.min(1, this._dragY + dy * sensitivity));
  }

  private _onPointerUp(_e: PointerEvent): void {
    this._isPointerDown = false;
    if (this._canvas) {
      this._canvas.style.cursor = 'grab';
    }
  }

  private _onPointerLeave(_e: PointerEvent): void {
    this._isPointerDown = false;
    if (this._canvas) {
      this._canvas.style.cursor = 'grab';
    }
  }
}
