"""Rendering variants, with the same bounded import protocol as CDP trials."""
import os
import shutil
import tempfile
from pathlib import Path

from camoufox import DefaultAddons
from camoufox.fingerprints import Screen, generate_fingerprint
from camoufox.sync_api import Camoufox

from battery_common import read_page

CASES = ['cam-render-default', 'cam-render-clean', 'cam-render-software']


def fingerprint():
    return generate_fingerprint(os='linux', window=(1366, 768),
        screen=Screen(min_width=1920, max_width=1920, min_height=1080, max_height=1080))


class Browser:
    def __init__(self, case):
        self.case=case;self.manager=self.context=self.page=None
        self.root=Path(tempfile.mkdtemp(prefix='volley-render-'))
        self.cdp=self

    def start(self):
        options={'headless':False,'persistent_context':True,
                 'user_data_dir':str(self.root),'fingerprint':fingerprint()}
        if self.case!='cam-render-default':options['exclude_addons']=[DefaultAddons.UBO]
        if self.case=='cam-render-software':
            os.environ.update(LIBGL_ALWAYS_SOFTWARE='1',GALLIUM_DRIVER='llvmpipe')
            options['firefox_user_prefs']={'webgl.disabled':False,'webgl.force-enabled':True}
        self.manager=Camoufox(**options);self.context=self.manager.__enter__()
        self.page=self.context.pages[0] if self.context.pages else self.context.new_page()

    def evaluate(self, expression):return self.page.evaluate(expression)

    def get(self,url):
        result=read_page(self.page,url,wait_seconds=45)
        result.update(helper_attempted=False,helper_error=None,document_responses=None)
        return result

    def close(self):
        if self.manager and self.context:self.manager.__exit__(None,None,None)
        self.manager=self.context=self.page=None
        shutil.rmtree(self.root,ignore_errors=True)


if __name__=='__main__':
    from community_runner import main
    main(Browser,CASES,{'camoufox':'camoufox'})
