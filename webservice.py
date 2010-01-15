#!/usr/bin/env python

import os, sys
import re
import logging
from optparse import OptionParser
from datetime import datetime
from functools import wraps

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template, util
from google.appengine.api.labs import taskqueue

from django.utils import simplejson as json

template.register_template_library('templatefilters')

from api import API
from config import *
from model import User, Album, UserAlbums, UserAlbumsProcessing

class ToJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if callable(getattr(obj, '__json__', None)):
            return obj.__json__()
        elif hasattr(obj, '__str__'):
            return obj.__str__()
        else:
            raise TypeError(repr(obj) + " is not JSON serializable")

def dumps(o):
    return json.dumps(o, indent=JSON_INDENT, cls=ToJSONEncoder)

def expose(templatename=None, format=None):
    if templatename:
        path = os.path.join(TMPL_PATH, templatename)
        default_renderer = lambda v: template.render(path, v)
    else:
        default_renderer = lambda v: v
    formats = {
        'json' : ('text/javascript', dumps),
        None   : (None, default_renderer) }
    content_type, renderer = formats.get(format, formats[None])
    def wrapper(func):
        @wraps(func)
        def wrapped(self, *args, **kwargs):
            if content_type:
                self.response.headers['Content-Type'] = content_type
            values = func(self, *args, **kwargs)
            self.response.out.write(renderer(values))
        # :TODO: Restrict the methods.
        wrapped.exposed_methods = [ 'GET', 'POST' ]
        return wrapped
    return wrapper

class MainPage(webapp.RequestHandler):

    @expose('index.html')
    def get(self):
        return {}

class BaseUserPage(webapp.RequestHandler):

    @property
    def api(self):
        if getattr(self, '_api', None) is None:
            update = self.request.get_range('update',
                    min_value=0, max_value=1, default=1)
            self._api = API(enable_updates=update)
        return self._api

class UserPage(BaseUserPage):

    def post(self, username):
        """Issue a redirect to the given user page."""
        self.redirect('/user/%s/' % self.request.get('username'))

    @expose('user.html')
    def get(self, username):
        """Show a user page defaulting to a list of owned albums."""
        user = self.api.get_user(username)

        # Bang the start processing task on the queue as fetching a
        # users' albums from their library takes a while and we want to
        # display the page immediately.
        # Or maybe leave it to the client instead.
        #start_url = self.request.path + 'albums/start'
        #taskqueue.add(url=start_url)

        # Show the albums we already know the user owns.
        stored_albums = UserAlbums.all().filter('user', user)

        user = self.api.get_user(username, check_for_update = True)
        return dict(
            username = username,
            avatar   = user.avatar,
            realname = user.realname,
            age      = user.age,
            gender   = user.gender,
            country  = user.country,

            albums = dict(
                wanted = (a.album for a in stored_albums if a.owned == False),
                owned  = (a.album for a in stored_albums if a.owned)))

class UserAlbumsPage(BaseUserPage):

    def get(self, username, action):
        action = action or 'index'
        func = getattr(self, action)
        logging.debug("Trying GET action '%s'" % action)
        if 'GET' in getattr(func, 'exposed_methods', []):
            return func(username)
        else:
            self.error(404)

    def post(self, username, action):
        action = action or None
        func = getattr(self, action)
        logging.debug("Trying POST action '%s'" % action)
        if 'POST' in getattr(func, 'exposed_methods', []):
            return func(username)
        else:
            self.error(404)

    @expose(format='json')
    def index(self, username):
        user = self.api.get_user(username)
        page = self.request.get_range('page', min_value=0)
        albums = self.api.get_user_albums(user, page)
        return albums

    @expose(format='json')
    def wanted(self, username):
        user = self.api.get_user(username)
        page = self.request.get_range('page', min_value=0)
        albums = self.api.get_albums_wanted(user, page)
        return albums

    @expose(format='json')
    def owned(self, username):
        user = self.api.get_user(username)
        page = self.request.get_range('page', min_value=0)
        albums = self.api.get_albums_owned(user, page)
        return albums

app = webapp.WSGIApplication([
        ('/', MainPage),
        ('/user/(.+)/albums/(.*)', UserAlbumsPage),
        ('/user/?([^/]*)/?', UserPage),
    ],
    debug = DEBUG)

def run_wsgi_app():
    return util.run_wsgi_app(app)
