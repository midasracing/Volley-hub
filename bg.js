/* Animowane tło sekcji głównej — port komponentu Velaris (WebGL) na czysty JavaScript.
   Wstrzymuje się poza ekranem i przy ukrytej karcie, a przy „Ogranicz ruch" rysuje jedną klatkę. */
(function () {
  var cv = document.getElementById("hero-bg");
  if (!cv) return;
  var box = cv.parentElement;
  var fullScreen = cv.classList.contains("hero-bg");
  var CFG = { bg: "#02060f", colors: ["#2f7bf0", "#0a60d6", "#08306b", "#02060f"], speed: 1.2, grain: 0.25 };

  var gl = cv.getContext("webgl", { antialias: false, powerPreference: "low-power" });
  if (!gl) { box.classList.add("no-gl"); return; }

  var VS = "attribute vec2 position;varying vec2 vUv;void main(){vUv=position*0.5+0.5;gl_Position=vec4(position,0.0,1.0);}";
  var FS = [
    "#ifdef GL_FRAGMENT_PRECISION_HIGH", "precision highp float;", "#else", "precision mediump float;", "#endif",
    "varying vec2 vUv;uniform vec2 u_resolution;uniform float u_time;uniform float u_grain;uniform vec3 u_colors[4];uniform vec3 u_bg;",
    "vec3 permute(vec3 x){return mod(((x*34.0)+1.0)*x,289.0);}",
    "float snoise(vec2 v){const vec4 C=vec4(0.211324865405187,0.366025403784439,-0.577350269189626,0.024390243902439);",
    "vec2 i=floor(v+dot(v,C.yy));vec2 x0=v-i+dot(i,C.xx);vec2 i1=(x0.x>x0.y)?vec2(1.0,0.0):vec2(0.0,1.0);",
    "vec4 x12=x0.xyxy+C.xxzz;x12.xy-=i1;i=mod(i,289.0);",
    "vec3 p=permute(permute(i.y+vec3(0.0,i1.y,1.0))+i.x+vec3(0.0,i1.x,1.0));",
    "vec3 m=max(0.5-vec3(dot(x0,x0),dot(x12.xy,x12.xy),dot(x12.zw,x12.zw)),0.0);m=m*m;m=m*m;",
    "vec3 x=2.0*fract(p*C.www)-1.0;vec3 h=abs(x)-0.5;vec3 ox=floor(x+0.5);vec3 a0=x-ox;",
    "m*=1.79284291400159-0.85373472095314*(a0*a0+h*h);",
    "vec3 g;g.x=a0.x*x0.x+h.x*x0.y;g.yz=a0.yz*x12.xz+h.yz*x12.yw;return 130.0*dot(m,g);}",
    "void main(){vec2 uv=vUv;float ratio=u_resolution.x/u_resolution.y;vec2 p=uv-0.5;p.x*=ratio;float t=u_time*0.1;",
    "float n1=snoise(p*0.4+vec2(t*0.2,-t*0.3));",
    "float n2=snoise(p*0.55+vec2(-t*0.15,t*0.25)+n1*0.25);",
    "float n3=snoise(p*0.75+vec2(t*0.1,-t*0.2)+n2*0.2);",
    "vec3 col=u_bg;float dist=length(p)*1.5;float vignette=1.0-smoothstep(0.3,1.2,dist);",
    "col=mix(col,u_colors[0],smoothstep(-0.2,0.5,n1)*0.85);",
    "col=mix(col,u_colors[1],smoothstep(-0.1,0.6,n2)*0.7);",
    "col=mix(col,u_colors[2],smoothstep(-0.3,0.4,n3)*0.6);",
    "col=mix(col,u_colors[3],smoothstep(0.0,0.7,n1*n2)*0.5);",
    "float glow=smoothstep(0.8,0.0,dist)*0.3;col+=u_colors[1]*glow;col=mix(col*0.2,col,vignette);",
    "float grain=fract(sin(dot(uv,vec2(12.9898,78.233))*1.0)*43758.5453+u_time);col+=(grain-0.5)*u_grain*0.1;",
    "gl_FragColor=vec4(col,1.0);}"
  ].join("\n");

  function shader(type, src) {
    var s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return gl.getShaderParameter(s, gl.COMPILE_STATUS) ? s : null;
  }
  var vs = shader(gl.VERTEX_SHADER, VS), fs = shader(gl.FRAGMENT_SHADER, FS);
  var prog = gl.createProgram();
  if (!vs || !fs) { box.classList.add("no-gl"); return; }
  gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { box.classList.add("no-gl"); return; }
  gl.useProgram(prog);

  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  var pos = gl.getAttribLocation(prog, "position");
  gl.enableVertexAttribArray(pos);
  gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);

  function rgb(hex) {
    var h = hex.replace("#", "");
    return [0, 2, 4].map(function (i) { return parseInt(h.slice(i, i + 2), 16) / 255; });
  }
  var uRes = gl.getUniformLocation(prog, "u_resolution"), uTime = gl.getUniformLocation(prog, "u_time");
  gl.uniform1f(gl.getUniformLocation(prog, "u_grain"), CFG.grain);
  gl.uniform3fv(gl.getUniformLocation(prog, "u_colors"), new Float32Array(CFG.colors.reduce(function (a, c) { return a.concat(rgb(c)); }, [])));
  var b = rgb(CFG.bg); gl.uniform3f(gl.getUniformLocation(prog, "u_bg"), b[0], b[1], b[2]);

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var raf = 0, visible = true, last = 8000;

  function draw(ms) {
    if (!cv.width || !cv.height) return;
    last = ms;
    gl.uniform1f(uTime, ms * 0.001 * CFG.speed);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }
  function frame(ms) { draw(ms); raf = requestAnimationFrame(frame); }
  function start() { if (!raf && visible && !document.hidden && !reduce.matches) raf = requestAnimationFrame(frame); }
  function stop() { cancelAnimationFrame(raf); raf = 0; }

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    var width = fullScreen ? window.innerWidth : box.clientWidth;
    var height = fullScreen ? window.innerHeight : box.clientHeight;
    cv.width = Math.round(width * dpr);
    cv.height = Math.round(height * dpr);
    if (fullScreen) { cv.style.width = width + "px"; cv.style.height = height + "px"; }
    gl.viewport(0, 0, cv.width, cv.height);
    gl.uniform2f(uRes, cv.width, cv.height);
    draw(last);
  }

  new ResizeObserver(resize).observe(box);
  window.addEventListener("resize", resize, { passive: true });
  new IntersectionObserver(function (e) { visible = e[0].isIntersecting; visible ? start() : stop(); }).observe(box);
  document.addEventListener("visibilitychange", function () { document.hidden ? stop() : start(); });
  reduce.addEventListener && reduce.addEventListener("change", function () { reduce.matches ? stop() : start(); });
  resize();
  start();
})();
