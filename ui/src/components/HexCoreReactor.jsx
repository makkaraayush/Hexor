import React, { useEffect, useRef } from 'react';

export default function HexCoreReactor({ 
  isSpeaking, 
  isListening, 
  statusText = "HEXOR ONLINE",
  telemetry = {} 
}) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;
    let angle = 0;
    let pulse = 0;

    const resize = () => {
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const particles = Array.from({ length: 48 }, () => ({
      x: (Math.random() - 0.5) * 200,
      y: (Math.random() - 0.5) * 200,
      radius: Math.random() * 2 + 1,
      speed: Math.random() * 0.02 + 0.01,
      angle: Math.random() * Math.PI * 2,
      dist: Math.random() * 80 + 30
    }));

    const drawHexagon = (x, y, radius, rot, color, lineWidth = 1.5, fill = false) => {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(rot);
      ctx.beginPath();
      for (let i = 0; i < 6; i++) {
        const a = (i * Math.PI) / 3;
        const hx = radius * Math.cos(a);
        const hy = radius * Math.sin(a);
        if (i === 0) ctx.moveTo(hx, hy);
        else ctx.lineTo(hx, hy);
      }
      ctx.closePath();
      if (fill) {
        ctx.fillStyle = color;
        ctx.fill();
      } else {
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.stroke();
      }
      ctx.restore();
    };

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;
      
      ctx.clearRect(0, 0, w, h);

      const pulseSpeed = isSpeaking ? 0.08 : (isListening ? 0.05 : 0.02);
      pulse += pulseSpeed;
      const pulseScale = 1 + Math.sin(pulse) * (isSpeaking ? 0.12 : 0.04);
      angle += isSpeaking ? 0.03 : 0.01;

      const primaryColor = isSpeaking ? '#00f0ff' : (isListening ? '#10b981' : '#00f0ff');
      const glowColor = isSpeaking ? 'rgba(0, 240, 255, 0.4)' : (isListening ? 'rgba(16, 185, 129, 0.4)' : 'rgba(0, 240, 255, 0.2)');

      const grad = ctx.createRadialGradient(cx, cy, 10, cx, cy, 180 * pulseScale);
      grad.addColorStop(0, glowColor);
      grad.addColorStop(0.5, 'rgba(0, 240, 255, 0.05)');
      grad.addColorStop(1, 'transparent');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);

      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(angle * 0.4);
      ctx.strokeStyle = 'rgba(0, 240, 255, 0.25)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(0, 0, 140, 0, Math.PI * 2);
      ctx.stroke();

      for (let i = 0; i < 36; i++) {
        const a = (i * Math.PI * 2) / 36;
        const tickLen = i % 3 === 0 ? 8 : 4;
        ctx.beginPath();
        ctx.moveTo(Math.cos(a) * 135, Math.sin(a) * 135);
        ctx.lineTo(Math.cos(a) * (135 + tickLen), Math.sin(a) * (135 + tickLen));
        ctx.strokeStyle = i % 6 === 0 ? primaryColor : 'rgba(0, 240, 255, 0.3)';
        ctx.stroke();
      }
      ctx.restore();

      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(-angle * 0.6);
      ctx.strokeStyle = 'rgba(0, 240, 255, 0.4)';
      ctx.lineWidth = 2;
      for (let seg = 0; seg < 4; seg++) {
        ctx.beginPath();
        ctx.arc(0, 0, 115 * pulseScale, seg * Math.PI / 2 + 0.1, (seg + 1) * Math.PI / 2 - 0.2);
        ctx.stroke();
      }
      ctx.restore();

      drawHexagon(cx, cy, 90 * pulseScale, angle, 'rgba(0, 240, 255, 0.3)', 1.5);
      drawHexagon(cx, cy, 70 * pulseScale, -angle * 1.5, primaryColor, 2);
      drawHexagon(cx, cy, 48 * pulseScale, angle * 2, 'rgba(255, 255, 255, 0.7)', 1.5);

      const coreGrad = ctx.createRadialGradient(cx, cy, 2, cx, cy, 28 * pulseScale);
      coreGrad.addColorStop(0, '#ffffff');
      coreGrad.addColorStop(0.4, primaryColor);
      coreGrad.addColorStop(1, 'transparent');
      drawHexagon(cx, cy, 26 * pulseScale, -angle, coreGrad, 1, true);

      particles.forEach((p, idx) => {
        p.angle += p.speed * (isSpeaking ? 2.5 : 1);
        const px = cx + Math.cos(p.angle) * (p.dist * pulseScale);
        const py = cy + Math.sin(p.angle) * (p.dist * pulseScale);

        ctx.fillStyle = idx % 2 === 0 ? primaryColor : '#ffffff';
        ctx.beginPath();
        ctx.arc(px, py, p.radius, 0, Math.PI * 2);
        ctx.fill();

        if (idx % 4 === 0) {
          ctx.strokeStyle = 'rgba(0, 240, 255, 0.15)';
          ctx.lineWidth = 0.5;
          ctx.beginPath();
          ctx.moveTo(cx, cy);
          ctx.lineTo(px, py);
          ctx.stroke();
        }
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [isSpeaking, isListening]);

  return (
    <div className="relative w-full h-full flex flex-col items-center justify-center select-none">
      <canvas ref={canvasRef} className="absolute inset-0 w-full h-full z-0" />
      
      <div className="relative z-10 flex flex-col items-center pointer-events-none mt-48">
        <div className="px-3 py-1 bg-cyan-950/70 border border-cyan-500/40 rounded-full backdrop-blur-md flex items-center space-x-2">
          <span className={`w-2 h-2 rounded-full ${isSpeaking ? 'bg-cyan-400 animate-ping' : (isListening ? 'bg-emerald-400 animate-pulse' : 'bg-cyan-500')}`} />
          <span className="font-orbitron text-xs tracking-widest text-cyan-300 font-semibold uppercase">
            {isSpeaking ? "SYNTHESIZING SPEECH" : (isListening ? "AUDIO SENSORS ACTIVE" : statusText)}
          </span>
        </div>
        <div className="font-mono-tech text-[10px] text-cyan-500/80 mt-1 tracking-wider">
          FREQ: 432.8 MHZ // ARCH: QUANTUM REACT
        </div>
      </div>
    </div>
  );
}
