/* Fluid Glass adaptation for Volley Hub.
   Technique adapted from React Bits Fluid Glass: GPU shader, SDF-like capsule,
   Fresnel edge lighting and subtle chromatic dispersion. Vanilla JS/WebGL2; no React dependency. */
(function(){
  "use strict";
  if(window.__vhFluidGlass) return;
  window.__vhFluidGlass=true;
  const VERT=`#version 300 es
  const vec2 P[3]=vec2[3](vec2(-1.,-1.),vec2(3.,-1.),vec2(-1.,3.));
  void main(){gl_Position=vec4(P[gl_VertexID],0.,1.);}`;
  const FRAG=`#version 300 es
  precision highp float;
  uniform vec2 uSize;
  uniform float uTime;
  uniform float uDark;
  out vec4 outColor;
  float roundedBox(vec2 p, vec2 b, float r){
    vec2 q=abs(p)-b+vec2(r);
    return length(max(q,0.))+min(max(q.x,q.y),0.)-r;
  }
  void main(){
    vec2 uv=gl_FragCoord.xy/uSize;
    vec2 p=(uv-.5)*vec2(uSize.x/uSize.y,1.);
    float aspect=uSize.x/uSize.y;
    float radius=min(.47, .47/aspect);
    float d=roundedBox(p,vec2(max(.0,aspect*.5-.035),.465),radius);
    float aa=max(fwidth(d)*1.6,.0015);
    float inside=1.-smoothstep(-aa,aa,d);
    float edge=1.-smoothstep(.0,.095,abs(d));
    float rim=exp(-abs(d)*28.);
    float topLight=exp(-pow((uv.y-.91)*8.,2.))*smoothstep(.0,.16,uv.y);
    float sideLight=exp(-pow((uv.x-.06)*15.,2.))+exp(-pow((uv.x-.94)*15.,2.));
    float sweep=exp(-pow((uv.x-(.2+.6*(.5+.5*sin(uTime*.42))))*10.,2.))*exp(-pow((uv.y-.78)*5.,2.));
    float chroma=sin((uv.x*2.3+uv.y*1.4+uTime*.12)*6.283)*.5+.5;
    vec3 col=mix(vec3(.68,.82,1.),vec3(1.),topLight*.7);
    col+=vec3(.12,.32,.8)*rim*.45;
    col+=vec3(.65,.86,1.)*sideLight*.08;
    col+=vec3(.2,.55,1.)*sweep*.15;
    col+=vec3(.8,.35,.95)*edge*chroma*.045;
    float alpha=inside*(.035+topLight*.11+sideLight*.035+sweep*.035)+rim*(.28+uDark*.08)+edge*.035;
    alpha*=smoothstep(.0,.02,uv.x)*smoothstep(.0,.02,1.-uv.x);
    outColor=vec4(col,clamp(alpha,0.,.58));
  }`;
  function shader(gl,type,src){
    const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);
    if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){console.warn("Fluid Glass shader:",gl.getShaderInfoLog(s));gl.deleteShader(s);return null;}
    return s;
  }
  function mount(host){
    if(!host||host.querySelector(":scope > .fluid-glass-canvas"))return;
    const canvas=document.createElement("canvas");
    canvas.className="fluid-glass-canvas";canvas.setAttribute("aria-hidden","true");
    host.appendChild(canvas);
    const gl=canvas.getContext("webgl2",{alpha:true,antialias:true,powerPreference:"low-power"});
    if(!gl){host.classList.add("fluid-glass-fallback");canvas.remove();return;}
    const vs=shader(gl,gl.VERTEX_SHADER,VERT),fs=shader(gl,gl.FRAGMENT_SHADER,FRAG);
    if(!vs||!fs){canvas.remove();host.classList.add("fluid-glass-fallback");return;}
    const program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.linkProgram(program);
    if(!gl.getProgramParameter(program,gl.LINK_STATUS)){canvas.remove();host.classList.add("fluid-glass-fallback");return;}
    gl.useProgram(program);
    const sizeLoc=gl.getUniformLocation(program,"uSize"),timeLoc=gl.getUniformLocation(program,"uTime"),darkLoc=gl.getUniformLocation(program,"uDark");
    gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE_MINUS_SRC_ALPHA);
    let w=0,h=0,raf=0,start=performance.now(),visible=true;
    const resize=()=>{
      const r=host.getBoundingClientRect(),dpr=Math.min(window.devicePixelRatio||1,1.5);
      const nw=Math.max(1,Math.round(r.width*dpr)),nh=Math.max(1,Math.round(r.height*dpr));
      if(nw!==w||nh!==h){w=nw;h=nh;canvas.width=w;canvas.height=h;gl.viewport(0,0,w,h);}
    };
    const draw=now=>{
      if(!visible){raf=0;return;}
      resize();gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform2f(sizeLoc,w,h);gl.uniform1f(timeLoc,(now-start)/1000);
      gl.uniform1f(darkLoc,matchMedia("(prefers-color-scheme: dark)").matches?1:0);
      gl.drawArrays(gl.TRIANGLES,0,3);raf=requestAnimationFrame(draw);
    };
    const io=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;if(visible&&!raf)raf=requestAnimationFrame(draw);});
    io.observe(host);
    const ro=new ResizeObserver(resize);ro.observe(host);
    raf=requestAnimationFrame(draw);
    host.__fluidGlassCleanup=()=>{cancelAnimationFrame(raf);io.disconnect();ro.disconnect();gl.getExtension("WEBGL_lose_context")?.loseContext();canvas.remove();};
  }
  function update(){
    const active=document.querySelector(".bottom .nav.active");
    document.querySelectorAll(".bottom .nav").forEach(n=>{
      if(n!==active&&n.querySelector(":scope > .fluid-glass-canvas"))n.__fluidGlassCleanup?.();
    });
    if(active)mount(active);
    const marker=document.querySelector("#ios-matches .im-selection-glass");
    if(marker)mount(marker);
  }
  const start=()=>{update();new MutationObserver(update).observe(document.body,{subtree:true,attributes:true,attributeFilter:["class"]});};
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start,{once:true});else start();
  window.addEventListener("resize",update,{passive:true});
})();