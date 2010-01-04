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
        api = get_api()
        user = api.get_user(username)
        albums = get_all_albums(user)
        path = os.path.join(DIR_PATH, 'user.html')
        values = dict(username = username)
        self.response.out.write(template.render(path, values))

    def post(self):
        self.redirect('/user/' + self.request.get('username'))

class UserAlbumsPage(webapp.RequestHandler):

    @property
    def user(self):
        if getattr(self, '_user', None) is None:
            m = re.match(r'^/user/([^/]*).*', self.request.path)
            if m is None:
                self.error(404)
            username = m.group(1)
            api = get_api()
            user = api.get_user(username)
            self._user = user
        return self._user

    def get(self):
        albums = get_all_albums(self.user)
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
