"""Offline restart checks at a stable localhost origin; no source requests."""
import copy
import hashlib
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from camoufox.sync_api import Camoufox
from camoufox.utils import launch_options
from playwright.sync_api import sync_playwright

from community_cam import fingerprint
from render_probe import host_display, snapshot
from run import HERE


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        present='volley_restart=1' in self.headers.get('Cookie','')
        body=('<!doctype html><title>Local restart probe</title><script>'
              'window.__serverSawCookie='+json.dumps(present)+'</script>').encode()
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Set-Cookie','volley_restart=1; Path=/; Max-Age=3600; SameSite=Lax')
        self.end_headers();self.wfile.write(body)
    def log_message(self,*args):pass


def main():
    output=HERE/'outputs'/'community'/'fingerprint-restarts';output.mkdir(parents=True,exist_ok=True)
    report={'run_id':os.getenv('GITHUB_RUN_ID'),'display':host_display(),'source_requests':0,'modes':{}}
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}/'
    try:
        with tempfile.TemporaryDirectory(prefix='volley-fingerprint-') as root:
            for mode in ['frozen-options','saved-fingerprint','stock-firefox']:
                entries=[];item={'starts':entries};report['modes'][mode]=item
                profile=str(Path(root)/mode);fp=fingerprint()
                options=launch_options(headless=False,user_data_dir=profile,fingerprint=fp)
                try:
                    for index in range(3):
                        if mode=='stock-firefox':
                            manager=sync_playwright();playwright=manager.__enter__()
                            context=playwright.firefox.launch_persistent_context(profile,headless=False)
                        else:
                            manager=Camoufox(from_options=copy.deepcopy(options),persistent_context=True) if mode=='frozen-options' else Camoufox(
                                fingerprint=fp,user_data_dir=profile,persistent_context=True,headless=False)
                            context=manager.__enter__()
                        try:
                            page=context.pages[0] if context.pages else context.new_page()
                            page.goto(url);page.wait_for_timeout(250)
                            a=snapshot(page.evaluate);b=snapshot(page.evaluate)
                            entries.append({'start':index+1,'first':a,'second':b})
                            item['browser_version']=context.browser.version
                        finally:
                            context.close();manager.__exit__(None,None,None)
                    keys=['core_sha256','canvas_pixels_sha256','canvas_png_sha256','webgl_pixels_sha256']
                    item['stable_across_restarts']={k:len({e['first'][k] for e in entries})==1 for k in keys}
                    item['stable_within_process']={k:all(e['first'][k]==e['second'][k] for e in entries) for k in keys}
                    item['cookie_continuity']=all(e['first']['server_saw_persistent_cookie'] for e in entries[1:])
                except Exception as error:item['error']=type(error).__name__+': '+str(error)[:800]
    finally:
        server.shutdown()
        (output/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
