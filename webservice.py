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

from django.utils import simplejson as json

from api import API
from config import *

class MainPage(webapp.RequestHandler):

    def get(self):
        path = os.path.join(DIR_PATH, 'index.html')
        self.response.out.write(template.render(path, {}))

class BaseUserPage(webapp.RequestHandler):

    @property
    def username(self):
        if getattr(self, '_username', None) is None:
            m = re.match(r'^/user/([^/]*).*', self.request.path)
            if m is None:
                self.error(404)
            self._username = m.group(1)
        return self._username

    @property
    def api(self):
        if getattr(self, '_api', None) is None:
            self._api = API()
        return self._api

class UserPage(BaseUserPage):

    def get(self):
        albums = self.api.get_all_albums(self.username)
        path = os.path.join(DIR_PATH, 'user.html')
        values = dict(username = self.username)
        self.response.out.write(template.render(path, values))

    def post(self):
        self.redirect('/user/%s/' % self.request.get('username'))

class UserAlbumsPage(BaseUserPage):

    def get(self):
        albums = self.api.get_all_albums(self.username)
        album_list = [ str(a) for a in albums ]
        self.response.out.write(json.dumps(album_list))


app = webapp.WSGIApplication([
        ('/', MainPage),
        ('/user/.*/albums/?', UserAlbumsPage),
        ('/user/?.*', UserPage),
    ],
    debug = DEBUG)

def run_wsgi_app():
    return util.run_wsgi_app(app)
