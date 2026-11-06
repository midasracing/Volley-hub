"""Test the maintainer-recommended SeleniumBase CDP configurations on the actual source."""
import argparse
import hashlib
import json
import os
import time
from importlib.metadata import version

import mycdp
import requests
from bs4 import BeautifulSoup
from seleniumbase import SB, sb_cdp

from battery_common import measure, pace, quality, save
from render_probe import snapshot, host_display
from run import HERE, PAGES
from transport_support import challenge
import scraper_incremental as scraper


class Browser:
    def __init__(self,case):
        self.case=case;self.manager=self.owner=self.cdp=None
        self.responses=[]
    def start(self):
        binary=os.getenv('LAB_BROWSER','/usr/bin/google-chrome')
        if self.case=='sb-uc-cdp-solve':
            self.manager=SB(uc=True,headed=True,incognito=True,binary_location=binary)
            self.owner=self.manager.__enter__()
            self.owner.activate_cdp_mode('about:blank')
            self.cdp=self.owner.cdp
        else:
            self.cdp=sb_cdp.Chrome(browser_executable_path=binary,headless=False,sandbox=False)
        async def capture(event,*args):
            if event.type_==mycdp.network.ResourceType.DOCUMENT and event.response.url.startswith('https://pomorskie.volleystation.com/'):
                self.responses.append(event.response)
        self.cdp.add_handler(mycdp.network.ResponseReceived,capture)
        self.cdp.loop.run_until_complete(self.cdp.page.send(mycdp.network.enable()))
    def get(self,url):
        self.responses=[]
        self.cdp.goto(url);self.cdp.sleep(5)
        html=self.cdp.get_page_source(include_shadow_dom=False)
        initial=challenge(html,{})
        attempted=False;helper_error=None
        if initial and self.case.endswith('solve'):
            attempted=True
            try:self.cdp.solve_captcha()
            except Exception as error:helper_error=type(error).__name__+': '+str(error)[:250]
        deadline=time.monotonic()+45
        while challenge(html,{}) and 'attention required' not in self.cdp.get_title().casefold() and time.monotonic()<deadline:
            self.cdp.sleep(1.5);html=self.cdp.get_page_source(include_shadow_dom=False)
        html=self.cdp.get_page_source(include_shadow_dom=False)
        response=self.responses[-1] if self.responses else None
        return {'status':int(response.status) if response else None,'headers':dict(response.headers) if response else {},
                'html':html,'challenge_seen_initially':initial,'helper_attempted':attempted,'helper_error':helper_error,
                'document_responses':len(self.responses)}
    def close(self):
        if self.manager and self.owner:self.manager.__exit__(None,None,None)
        elif self.cdp:self.cdp.quit()
        self.owner=self.manager=self.cdp=None


if __name__=='__main__':
    from community_runner import main
    main(Browser,['sb-cdp-wait','sb-cdp-solve','sb-uc-cdp-solve'],
         {'seleniumbase':'seleniumbase','selenium':'selenium'})
