"use client";

import { useEffect, useRef, useState } from "react";

export type PetCharacter = "pikachu" | "doraemon" | "armorhero";

export type PetAction =
  | "idle"
  | "thinking"
  | "inputting"
  | "executing"
  | "blocked"
  | "success"
  | "failed"
  | "not_run";

interface PixelPetProps {
  character?: PetCharacter;
  action?: PetAction;
  size?: number;
  onClick?: () => void;
  onCharacterChange?: (character: PetCharacter) => void;
  showSelector?: boolean;
}

const CHARACTER_CONFIG: Record<PetCharacter, { name: string; primary: string; accent: string; folder: string }> = {
  pikachu: { name: "皮卡丘", primary: "#fbbf24", accent: "#f59e0b", folder: "pikachu" },
  doraemon: { name: "多啦A梦", primary: "#3b82f6", accent: "#2563eb", folder: "doraemon" },
  armorhero: { name: "铠甲勇士", primary: "#dc2626", accent: "#b91c1c", folder: "armorhero" },
};

const ACTION_IMAGE_MAP: Record<PetAction, string> = {
  idle: "01_idle.jpg",
  thinking: "02_thinking.jpg",
  inputting: "03_processing.jpg",
  executing: "07_loading.jpg",
  blocked: "08_paused.jpg",
  success: "04_success.jpg",
  failed: "05_fail.jpg",
  not_run: "06_warning.jpg",
};

const ACTION_TEXT: Record<PetAction, string> = {
  idle: "待机中...",
  thinking: "思考中...",
  inputting: "输入中...",
  executing: "执行中...",
  blocked: "阻塞中",
  success: "成功!",
  failed: "失败了",
  not_run: "未运行",
};

const ACTION_COLORS: Record<PetAction, { bg: string; text: string; glow: string }> = {
  idle: { bg: "rgba(156,163,175,0.2)", text: "#6b7280", glow: "rgba(156,163,175,0.3)" },
  thinking: { bg: "rgba(139,92,246,0.15)", text: "#7c3aed", glow: "rgba(139,92,246,0.4)" },
  inputting: { bg: "rgba(59,130,246,0.15)", text: "#2563eb", glow: "rgba(59,130,246,0.4)" },
  executing: { bg: "rgba(245,158,11,0.15)", text: "#d97706", glow: "rgba(245,158,11,0.4)" },
  blocked: { bg: "rgba(239,68,68,0.15)", text: "#dc2626", glow: "rgba(239,68,68,0.4)" },
  success: { bg: "rgba(34,197,94,0.15)", text: "#16a34a", glow: "rgba(34,197,94,0.5)" },
  failed: { bg: "rgba(239,68,68,0.15)", text: "#dc2626", glow: "rgba(239,68,68,0.4)" },
  not_run: { bg: "rgba(156,163,175,0.15)", text: "#9ca3af", glow: "rgba(156,163,175,0.3)" },
};

// 帧动画配置：每个状态对应的图片序列和帧间隔
const FRAME_CONFIG: Record<PetAction, { frames: string[]; frameInterval: number }> = {
  idle: { frames: ["01_idle.jpg", "09_complete.jpg", "01_idle.jpg", "04_success.jpg"], frameInterval: 45 },
  thinking: { frames: ["02_thinking.jpg", "01_idle.jpg", "02_thinking.jpg"], frameInterval: 30 },
  inputting: { frames: ["03_processing.jpg", "07_loading.jpg", "03_processing.jpg"], frameInterval: 25 },
  executing: { frames: ["07_loading.jpg", "03_processing.jpg", "09_complete.jpg", "07_loading.jpg"], frameInterval: 20 },
  blocked: { frames: ["08_paused.jpg", "06_warning.jpg", "08_paused.jpg"], frameInterval: 45 },
  success: { frames: ["04_success.jpg", "09_complete.jpg", "04_success.jpg", "09_complete.jpg"], frameInterval: 15 },
  failed: { frames: ["05_fail.jpg", "06_warning.jpg", "05_fail.jpg", "08_paused.jpg"], frameInterval: 40 },
  not_run: { frames: ["06_warning.jpg", "08_paused.jpg", "06_warning.jpg"], frameInterval: 50 },
};

function getImagePath(char: PetCharacter, filename: string): string {
  return `/static/${CHARACTER_CONFIG[char].folder}/${filename}`;
}

// 处理图片：去除背景阴影和灰色区域
async function processImage(src: string): Promise<ImageBitmap | null> {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d", { willReadFrequently: true });
      if (!ctx) { resolve(null); return; }

      ctx.drawImage(img, 0, 0);
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;
      const w = canvas.width;
      const h = canvas.height;

      // 采样边缘像素确定背景色
      const samples: number[][] = [];
      for (let x = 0; x < w; x += Math.max(1, Math.floor(w / 20))) {
        samples.push([x, 0], [x, h - 1]);
      }
      for (let y = 0; y < h; y += Math.max(1, Math.floor(h / 20))) {
        samples.push([0, y], [w - 1, y]);
      }

      let bgR = 0, bgG = 0, bgB = 0;
      for (const [sx, sy] of samples) {
        const idx = (sy * w + sx) * 4;
        bgR += data[idx]; bgG += data[idx + 1]; bgB += data[idx + 2];
      }
      bgR = Math.round(bgR / samples.length);
      bgG = Math.round(bgG / samples.length);
      bgB = Math.round(bgB / samples.length);

      // 判断是否为背景色（包括灰白棋盘格）
      const isBg = (r: number, g: number, b: number) => {
        const avg = (r + g + b) / 3;
        const dist = Math.sqrt((r - bgR) ** 2 + (g - bgG) ** 2 + (b - bgB) ** 2);
        return dist < 50 || (Math.abs(r - avg) < 20 && Math.abs(g - avg) < 20 && Math.abs(b - avg) < 20 && avg > 200);
      };

      // 判断是否为阴影（底部较暗区域）
      const isShadow = (r: number, g: number, b: number, y: number) => {
        const avg = (r + g + b) / 3;
        return y > h * 0.82 && avg < 140 && avg > 40;
      };

      // 判断是否为边框线（深灰色线条）
      const isBorder = (r: number, g: number, b: number) => {
        const avg = (r + g + b) / 3;
        return avg < 100 && avg > 40 && Math.abs(r - g) < 15 && Math.abs(g - b) < 15;
      };

      for (let i = 0; i < data.length; i += 4) {
        const x = (i / 4) % w;
        const y = Math.floor((i / 4) / w);
        const r = data[i], g = data[i + 1], b = data[i + 2];

        if (isBg(r, g, b) || isShadow(r, g, b, y) || isBorder(r, g, b)) {
          data[i + 3] = 0;
        }
      }

      ctx.putImageData(imageData, 0, 0);
      canvas.toBlob((blob) => {
        if (blob) createImageBitmap(blob).then(resolve).catch(() => resolve(null));
        else resolve(null);
      });
    };
    img.onerror = () => resolve(null);
    img.src = src;
  });
}

// 缓动函数：easeInOutQuad
function easeInOutQuad(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

// 缓动函数：easeOutBounce
function easeOutBounce(t: number): number {
  const n1 = 7.5625;
  const d1 = 2.75;
  if (t < 1 / d1) {
    return n1 * t * t;
  } else if (t < 2 / d1) {
    return n1 * (t -= 1.5 / d1) * t + 0.75;
  } else if (t < 2.5 / d1) {
    return n1 * (t -= 2.25 / d1) * t + 0.9375;
  } else {
    return n1 * (t -= 2.625 / d1) * t + 0.984375;
  }
}

export function PixelPet({
  character = "pikachu",
  action = "idle",
  size = 140,
  onClick,
  onCharacterChange,
  showSelector = false,
}: PixelPetProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef(0);
  const animFrameRef = useRef<number>(0);
  const currentCharRef = useRef(character);
  const currentActionRef = useRef(action);
  const imagesRef = useRef<ImageBitmap[]>([]);
  const [isHovered, setIsHovered] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  // 加载当前角色的所有状态图片
  useEffect(() => {
    currentCharRef.current = character;
    currentActionRef.current = action;
    setIsLoaded(false);
    imagesRef.current = [];

    const config = FRAME_CONFIG[action];
    const promises = config.frames.map((f) => processImage(getImagePath(character, f)));

    Promise.all(promises).then((bitmaps) => {
      const valid = bitmaps.filter((b): b is ImageBitmap => b !== null);
      if (valid.length > 0) {
        imagesRef.current = valid;
        setIsLoaded(true);
      }
    });
  }, [character, action]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const animate = () => {
      ctx.clearRect(0, 0, 128, 128);
      frameRef.current++;

      const currentAction = currentActionRef.current;
      const currentChar = currentCharRef.current;
      const colors = ACTION_COLORS[currentAction];
      const images = imagesRef.current;
      const config = FRAME_CONFIG[currentAction];

      // 帧动画：根据动作切换不同的图片
      const frameIndex = Math.floor(frameRef.current / config.frameInterval) % images.length;

      // 计算动画变换
      let bounceY = 0;
      let rotate = 0;
      let scaleX = 1;
      let scaleY = 1;
      let blinkScaleY = 1;

      const t = frameRef.current;

      switch (currentAction) {
        case "success": {
          // 开心跳跃：使用弹跳缓动
          const jumpCycle = (t % 30) / 30;
          bounceY = -easeOutBounce(jumpCycle) * 15;
          rotate = Math.sin(t * 0.15) * 8;
          scaleX = 1 + Math.sin(t * 0.2) * 0.08;
          scaleY = 1 - Math.sin(t * 0.2) * 0.04;
          break;
        }
        case "executing": {
          // 执行中：快速摆动
          bounceY = Math.abs(Math.sin(t * 0.25)) * 6;
          rotate = Math.sin(t * 0.15) * 5;
          scaleX = 1 + Math.sin(t * 0.2) * 0.05;
          break;
        }
        case "thinking": {
          // 思考中：缓慢摇摆
          bounceY = Math.sin(t * 0.1) * 4;
          rotate = Math.sin(t * 0.06) * 5;
          // 偶尔点头
          if (t % 120 < 20) {
            const nodProgress = (t % 120) / 20;
            rotate += Math.sin(nodProgress * Math.PI) * 3;
          }
          break;
        }
        case "inputting": {
          // 输入中：轻微抖动
          bounceY = Math.sin(t * 0.15) * 3;
          scaleX = 1 + Math.sin(t * 0.1) * 0.03;
          // 快速眨眼
          if (t % 60 < 4) {
            const blinkProgress = (t % 60) / 4;
            blinkScaleY = 1 - easeInOutQuad(blinkProgress) * 0.2;
          }
          break;
        }
        case "idle": {
          // 待机：呼吸 + 眨眼 + 轻微摇摆
          const breathCycle = (t % 120) / 120;
          const breath = Math.sin(breathCycle * Math.PI * 2);
          scaleX = 1 + breath * 0.03;
          scaleY = 1 + breath * 0.04;
          
          // 轻微左右摇摆
          rotate = Math.sin(t * 0.03) * 3;
          
          // 缓慢上下浮动
          bounceY = Math.sin(t * 0.025) * 2;
          
          // 眨眼效果：每180帧一次，使用easeInOut
          const blinkInterval = 180;
          const blinkPhase = t % blinkInterval;
          const blinkDuration = 6;
          if (blinkPhase < blinkDuration) {
            const blinkProgress = blinkPhase / blinkDuration;
            blinkScaleY = 1 - easeInOutQuad(blinkProgress) * 0.25;
          }
          
          // 偶尔的小动作：每300帧
          const twitchInterval = 300;
          const twitchPhase = t % twitchInterval;
          if (twitchPhase > twitchInterval - 12) {
            const twitchProgress = (twitchPhase - (twitchInterval - 12)) / 12;
            const twitch = Math.sin(twitchProgress * Math.PI);
            rotate += twitch * 2;
            bounceY += twitch * 1.5;
          }
          break;
        }
        case "blocked": {
          // 阻塞：缓慢抖动
          rotate = Math.sin(t * 0.04) * 3;
          bounceY = Math.sin(t * 0.06) * 1;
          // 偶尔叹气（缩放）
          if (t % 150 < 20) {
            const sighProgress = (t % 150) / 20;
            scaleY = 1 - Math.sin(sighProgress * Math.PI) * 0.05;
          }
          break;
        }
        case "failed": {
          // 失败：沮丧抖动
          bounceY = Math.sin(t * 0.04) * 1;
          rotate = Math.sin(t * 0.05) * 3;
          // 偶尔摇头
          if (t % 100 < 15) {
            const shakeProgress = (t % 100) / 15;
            rotate += Math.sin(shakeProgress * Math.PI * 3) * 2;
          }
          break;
        }
        case "not_run": {
          // 未运行：轻微浮动
          bounceY = Math.sin(t * 0.03) * 1;
          rotate = Math.sin(t * 0.02) * 2;
          break;
        }
      }

      // 绘制阴影（只在有图片时绘制）
      if (images.length > 0 && isLoaded) {
        const shadowScale = 1 - Math.abs(bounceY) * 0.02;
        ctx.fillStyle = "rgba(0,0,0,0.06)";
        ctx.beginPath();
        ctx.ellipse(64, 108, 22 * shadowScale, 3 * shadowScale, 0, 0, Math.PI * 2);
        ctx.fill();
      }

      // 绘制图片
      if (images.length > 0 && isLoaded) {
        const img = images[frameIndex];
        const imgSize = 85;

        ctx.save();
        ctx.translate(64, 64 + bounceY);
        ctx.rotate((rotate * Math.PI) / 180);
        ctx.scale(scaleX, scaleY * blinkScaleY);

        // 成功状态时添加发光效果
        if (currentAction === "success") {
          ctx.shadowColor = colors.glow;
          ctx.shadowBlur = 12 + Math.sin(t * 0.1) * 6;
        } else if (currentAction === "failed" || currentAction === "blocked") {
          ctx.shadowColor = colors.glow;
          ctx.shadowBlur = 5;
        }

        ctx.drawImage(img, -imgSize / 2, -imgSize / 2, imgSize, imgSize);
        ctx.restore();
      } else {
        // 加载中显示占位动画
        const config = CHARACTER_CONFIG[currentChar];
        const pulse = Math.sin(t * 0.1) * 5;
        ctx.fillStyle = config.primary + "30";
        ctx.fillRect(24 + pulse, 34 + pulse, 80 - pulse * 2, 80 - pulse * 2);
        ctx.fillStyle = config.primary;
        ctx.font = "10px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("加载中...", 64, 78);
      }

      // 绘制气泡文字
      if (t % 180 < 90) {
        drawSpeechBubble(ctx, ACTION_TEXT[currentAction], currentAction);
      }

      animFrameRef.current = requestAnimationFrame(animate);
    };

    animFrameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [isLoaded]);

  const drawSpeechBubble = (ctx: CanvasRenderingContext2D, text: string, act: PetAction) => {
    const colors = ACTION_COLORS[act];
    ctx.font = "bold 11px sans-serif";
    const textWidth = ctx.measureText(text).width;
    const padding = 8;
    const bubbleWidth = textWidth + padding * 2;
    const bubbleHeight = 22;
    const bubbleX = 64 - bubbleWidth / 2;
    const bubbleY = 2;

    ctx.fillStyle = colors.bg;
    ctx.strokeStyle = colors.text;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.roundRect(bubbleX, bubbleY, bubbleWidth, bubbleHeight, 6);
    ctx.fill();
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(bubbleX + bubbleWidth / 2 - 4, bubbleY + bubbleHeight);
    ctx.lineTo(bubbleX + bubbleWidth / 2, bubbleY + bubbleHeight + 5);
    ctx.lineTo(bubbleX + bubbleWidth / 2 + 4, bubbleY + bubbleHeight);
    ctx.closePath();
    ctx.fillStyle = colors.bg;
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = colors.text;
    ctx.textAlign = "center";
    ctx.fillText(text, 64, bubbleY + 15);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <div
        style={{
          position: "relative",
          width: size,
          height: size,
          cursor: onClick ? "pointer" : "default",
          transition: "transform 0.2s",
          transform: isHovered ? "scale(1.05)" : "scale(1)",
        }}
        onClick={() => {
          if (showSelector) setShowDropdown(!showDropdown);
          onClick?.();
        }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        <canvas
          ref={canvasRef}
          width={128}
          height={128}
          style={{ width: "100%", height: "100%", imageRendering: "pixelated" }}
        />

        {showSelector && showDropdown && (
          <div
            style={{
              position: "absolute",
              top: "100%",
              left: "50%",
              transform: "translateX(-50%)",
              marginTop: 8,
              backgroundColor: "#ffffff",
              border: "1px solid #e5e5e5",
              borderRadius: 12,
              boxShadow: "0 4px 20px rgba(0,0,0,0.15)",
              padding: 8,
              zIndex: 100,
              minWidth: 120,
            }}
          >
            {(Object.keys(CHARACTER_CONFIG) as PetCharacter[]).map((char) => (
              <button
                key={char}
                onClick={(e) => {
                  e.stopPropagation();
                  onCharacterChange?.(char);
                  setShowDropdown(false);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  width: "100%",
                  padding: "8px 12px",
                  border: "none",
                  borderRadius: 8,
                  backgroundColor: char === character ? CHARACTER_CONFIG[char].primary + "20" : "transparent",
                  color: "#1a1a1a",
                  fontSize: 13,
                  cursor: "pointer",
                  textAlign: "left",
                  fontWeight: char === character ? 600 : 400,
                }}
              >
                <div
                  style={{
                    width: 16,
                    height: 16,
                    borderRadius: 4,
                    backgroundColor: CHARACTER_CONFIG[char].primary,
                    border: "1px solid " + CHARACTER_CONFIG[char].accent,
                  }}
                />
                {CHARACTER_CONFIG[char].name}
              </button>
            ))}
          </div>
        )}
      </div>

      {showSelector && (
        <div style={{ fontSize: 12, color: "#999999", fontWeight: 500 }}>
          {CHARACTER_CONFIG[character].name}
        </div>
      )}
    </div>
  );
}
