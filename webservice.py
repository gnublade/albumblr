#!/usr/bin/env python

import os, sys
import re
import logging
from optparse import OptionParser

DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(os.path.join(DIR_PATH, 'lib'))
import pylast

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template, util

from common import get_api, get_all_albums
from config import *

class MainPage(webapp.RequestHandler):

    def get(self):
        path = os.path.join(DIR_PATH, 'index.html')
        self.response.out.write(template.render(path, {}))

class UserPage(webapp.RequestHandler):

    def get(self):
        m = re.match(r'^/user/([^/]*).*', self.request.path)
        if m is None:
            self.error(404)
        username = m.group(1)
        logging.info(username)
        api = get_api()
        user = api.get_user(username)
        albums = get_all_albums(user)
        path = os.path.join(DIR_PATH, 'user.html')
        values = dict(
                albums = list(str(a) for a in albums),
                username = username)
        self.response.out.write(template.render(path, values))

    def post(self):
        self.redirect('/user/' + self.request.get('username'))


app = webapp.WSGIApplication([
        ('/', MainPage),
        ('/user/?.*', UserPage),
    ],
    debug = DEBUG)

def run_wsgi_app():
    return util.run_wsgi_app(app)
