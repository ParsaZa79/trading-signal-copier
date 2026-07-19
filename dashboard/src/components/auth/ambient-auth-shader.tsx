"use client";

import { useEffect, useRef } from "react";

const VERTEX_SHADER = `
  attribute vec2 a_position;

  void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
  }
`;

const FRAGMENT_SHADER = `
  precision highp float;

  uniform vec2 u_resolution;
  uniform float u_time;

  float hash(vec2 p) {
    p = fract(p * vec2(123.34, 345.45));
    p += dot(p, p + 34.345);
    return fract(p.x * p.y);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);

    return mix(
      mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
      mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x),
      f.y
    );
  }

  float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    mat2 rotation = mat2(0.82, -0.57, 0.57, 0.82);

    for (int i = 0; i < 5; i++) {
      value += amplitude * noise(p);
      p = rotation * p * 2.02 + 11.7;
      amplitude *= 0.5;
    }

    return value;
  }

  void main() {
    vec2 uv = gl_FragCoord.xy / max(u_resolution.xy, vec2(1.0));
    float aspect = u_resolution.x / max(u_resolution.y, 1.0);
    float time = u_time * 0.075;

    vec2 flow = vec2(
      fbm(uv * 1.7 + vec2(time * 0.22, -time * 0.13)),
      fbm(uv * 1.9 + vec2(-time * 0.16, time * 0.19) + 7.1)
    );
    flow = (flow - 0.5) * 0.24;

    vec2 primaryCenter = vec2(
      -0.11 + sin(time * 0.71) * 0.035,
      0.62 + cos(time * 0.53) * 0.065
    );
    vec2 secondaryCenter = vec2(
      0.17 + cos(time * 0.43) * 0.05,
      0.41 + sin(time * 0.61) * 0.05
    );

    vec2 primaryDelta = (uv + flow - primaryCenter) * vec2(1.18 * aspect, 1.24);
    vec2 secondaryDelta = (uv - flow * 0.7 - secondaryCenter) * vec2(1.28 * aspect, 1.5);
    float primary = exp(-dot(primaryDelta, primaryDelta) * 5.1);
    float secondary = exp(-dot(secondaryDelta, secondaryDelta) * 7.2);
    float texture = fbm(uv * 2.65 + flow * 1.8 + vec2(time * 0.08, 0.0));
    float field = primary * (0.76 + texture * 0.34) + secondary * 0.38;
    field *= smoothstep(1.08, 0.22, uv.x);

    vec3 base = vec3(0.019, 0.020, 0.024);
    vec3 deepBlue = vec3(0.018, 0.09, 0.32);
    vec3 accentBlue = vec3(0.045, 0.24, 0.76);
    vec3 color = base + deepBlue * field * 0.8 + accentBlue * pow(field, 1.85) * 0.4;

    float vignette = smoothstep(1.18, 0.34, length((uv - 0.49) * vec2(0.84, 1.0)));
    color *= 0.72 + vignette * 0.28;
    gl_FragColor = vec4(color, 1.0);
  }
`;

function createShader(gl: WebGLRenderingContext, type: number, source: string) {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

export function AmbientAuthShader() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl", {
      alpha: false,
      antialias: false,
      depth: false,
      powerPreference: "low-power",
    });
    if (!gl) return;

    const vertexShader = createShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
    const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
    if (!vertexShader || !fragmentShader) return;

    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;

    const buffer = gl.createBuffer();
    const position = gl.getAttribLocation(program, "a_position");
    const resolution = gl.getUniformLocation(program, "u_resolution");
    const time = gl.getUniformLocation(program, "u_time");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let animationFrame = 0;
    let startTime = performance.now();

    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );
    gl.useProgram(program);
    gl.enableVertexAttribArray(position);
    gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      if (bounds.width < 2 || bounds.height < 2) return false;
      const scale = Math.min(window.devicePixelRatio || 1, 1.5);
      const width = Math.max(1, Math.round(bounds.width * scale));
      const height = Math.max(1, Math.round(bounds.height * scale));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
      gl.viewport(0, 0, width, height);
      return true;
    };

    const draw = (now: number) => {
      if (!resize()) return;
      gl.uniform2f(resolution, canvas.width, canvas.height);
      gl.uniform1f(time, (now - startTime) / 1000);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      if (!reducedMotion.matches && !document.hidden) {
        animationFrame = window.requestAnimationFrame(draw);
      }
    };

    const restart = () => {
      window.cancelAnimationFrame(animationFrame);
      startTime = performance.now();
      draw(startTime);
    };

    const resizeObserver = new ResizeObserver(restart);
    resizeObserver.observe(canvas);
    reducedMotion.addEventListener("change", restart);
    document.addEventListener("visibilitychange", restart);
    restart();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      reducedMotion.removeEventListener("change", restart);
      document.removeEventListener("visibilitychange", restart);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      gl.deleteShader(vertexShader);
      gl.deleteShader(fragmentShader);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
    />
  );
}
