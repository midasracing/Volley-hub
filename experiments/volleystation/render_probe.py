"""Measure browser-visible properties; never infer identity from launch options alone."""
import hashlib
import ctypes
import json
import re
import subprocess

PROBE_JS = r'''(() => {
  let c=window.__volleyProbeCanvas;
  if(!c){c=document.createElement('canvas');c.width=240;c.height=90;
    const x=c.getContext('2d');x.fillStyle='#f4d35e';x.fillRect(0,0,240,90);
    x.font='20px Arial';x.fillStyle='#123456';x.fillText('Volley probe: Zażółć 2026',8,42);
    x.beginPath();x.arc(188,48,24,0,Math.PI*2);x.fillStyle='rgba(40,80,160,.55)';x.fill();
    window.__volleyProbeCanvas=c;}
  const x=c.getContext('2d');
  const fonts={};for(const name of ['Arial','Liberation Sans','DejaVu Sans','monospace']){
    x.font='16px "'+name+'"';fonts[name]=x.measureText('mmmmmmmmlliZażółć').width;}
  let g=window.__volleyProbeGL;
  if(!g){const gc=document.createElement('canvas');gc.width=16;gc.height=16;
    g=gc.getContext('webgl');window.__volleyProbeGL=g;}
  let gl={available:!!g};let pixels=[];
  if(g){try {const e=g.getExtension('WEBGL_debug_renderer_info');
    gl={available:true,vendor:g.getParameter(g.VENDOR),renderer:g.getParameter(g.RENDERER),
      unmaskedVendor:e?g.getParameter(e.UNMASKED_VENDOR_WEBGL):null,
      unmaskedRenderer:e?g.getParameter(e.UNMASKED_RENDERER_WEBGL):null,
      maxTextureSize:g.getParameter(g.MAX_TEXTURE_SIZE),version:g.getParameter(g.VERSION)};
    g.clearColor(.125,.25,.5,1);g.clear(g.COLOR_BUFFER_BIT);
    const p=new Uint8Array(16*16*4);g.readPixels(0,0,16,16,g.RGBA,g.UNSIGNED_BYTE,p);pixels=Array.from(p);
  }catch(e){gl.error=e.name;}}
  return {core:{userAgent:navigator.userAgent,platform:navigator.platform,languages:Array.from(navigator.languages),
    hardwareConcurrency:navigator.hardwareConcurrency,deviceMemory:navigator.deviceMemory??null,
    webdriver:navigator.webdriver,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone,
    screen:{width:screen.width,height:screen.height,availWidth:screen.availWidth,availHeight:screen.availHeight,
      colorDepth:screen.colorDepth,pixelDepth:screen.pixelDepth},
    window:{outerWidth,outerHeight,innerWidth,innerHeight,devicePixelRatio},fontWidths:fonts,webgl:gl},
    canvasRGBA:Array.from(x.getImageData(0,0,c.width,c.height).data),canvasPNG:c.toDataURL(),webglPixels:pixels,
    serverSawCookie:document.documentElement.dataset.probeCookie==='true'?true:
      document.documentElement.dataset.probeCookie==='false'?false:null};
})()'''


def snapshot(evaluate):
    data = evaluate(PROBE_JS)
    if isinstance(data, str):
        data = json.loads(data)
    core = data['core']
    identity = {k:v for k,v in core.items() if k!='window'}
    return {'core':core,'core_sha256':hashlib.sha256(json.dumps(core,sort_keys=True).encode()).hexdigest(),
            'identity_sha256':hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest(),
            'canvas_pixels_sha256':hashlib.sha256(bytes(data['canvasRGBA'])).hexdigest(),
            'canvas_png_sha256':hashlib.sha256(data['canvasPNG'].encode()).hexdigest(),
            'webgl_pixels_sha256':hashlib.sha256(bytes(data['webglPixels'])).hexdigest() if data['webglPixels'] else None,
            'server_saw_persistent_cookie':data.get('serverSawCookie')}


def host_display():
    try:
        out=subprocess.check_output(['xdpyinfo'],text=True,stderr=subprocess.DEVNULL)
        match=re.search(r'dimensions:\s+(\d+)x(\d+) pixels',out)
        return {'width':int(match[1]),'height':int(match[2])} if match else None
    except Exception:
        try:
            lib=ctypes.CDLL('libX11.so.6')
            lib.XOpenDisplay.argtypes=[ctypes.c_char_p];lib.XOpenDisplay.restype=ctypes.c_void_p
            display=lib.XOpenDisplay(None)
            if not display:return None
            try:
                lib.XDefaultScreen.argtypes=[ctypes.c_void_p]
                screen=lib.XDefaultScreen(display)
                for name in ['XDisplayWidth','XDisplayHeight']:
                    getattr(lib,name).argtypes=[ctypes.c_void_p,ctypes.c_int]
                return {'width':lib.XDisplayWidth(display,screen),'height':lib.XDisplayHeight(display,screen)}
            finally:
                lib.XCloseDisplay.argtypes=[ctypes.c_void_p];lib.XCloseDisplay(display)
        except Exception:return None
