#!/usr/bin/env python

import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from django.utils import simplejson as json

template.register_template_library('templatefilters')

from api import API
from config import *
from model import User, Album, UserAlbums, UserAlbumsProcessing
from util import expose

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

def flattened_user_albums(user_albums):
    for user_album in user_albums:
        value = user_album.album.__json__()
        value.update({
            'num_played_tracks': user_album.num_played_tracks })
        yield value

class UserPage(BaseUserPage):

    def post(self, username):
        """Issue a redirect to the given user page."""
        self.redirect('/user/%s/' % self.request.get('username'))

    @expose('user.html')
    def get(self, username):
        """Show a user page defaulting to a list of owned albums."""
        user = self.api.get_user(username)
        user_details = (user.age, user.gender, user.country)
        wanted_albums = flattened_user_albums(
                self.api.get_user_albums_wanted(user))
        owned_albums = flattened_user_albums(
                self.api.get_user_albums_owned(user))
        return dict(
            username = username,
            avatar_url = user.avatar_url or DEFAULT_AVATAR_URL,
            realname = user.realname,
            gender = user.gender,
            user_details = filter(None, user_details),

            albums = dict(
                wanted = wanted_albums,
                owned  = owned_albums))

class UserAlbumsPage(BaseUserPage):

    def get(self, username, action):
        action = action or 'index'
        func = getattr(self, action, None)
        if 'GET' in getattr(func, 'exposed_methods', []):
            logging.debug("Trying GET action '%s'" % action)
            return func(username)
        else:
            self.error(404)

    def post(self, username, action):
        action = action or None
        func = getattr(self, action, None)
        if 'POST' in getattr(func, 'exposed_methods', []):
            logging.debug("Trying POST action '%s'" % action)
            return func(username)
        else:
            self.error(404)

    @expose(format='json')
    def index(self, username):
        user = self.api.get_user(username)
        self.api.maybe_update_user_albums(user, user.last_updated_to)
        page = self.request.get_range('page', min_value=0)
        user_albums = self.api.get_user_albums(user, page)
        return list(flattened_user_albums(user_albums))

    @expose(format='json')
    def wanted(self, username):
        user = self.api.get_user(username)
        self.api.maybe_update_user_albums(user, user.last_updated_to)
        page = self.request.get_range('page', min_value=0)
        user_albums = self.api.get_user_albums_wanted(user, page)
        return list(flattened_user_albums(user_albums))

    @expose(format='json')
    def owned(self, username):
        user = self.api.get_user(username)
        self.api.maybe_update_user_albums(user, user.last_updated_to)
        page = self.request.get_range('page', min_value=0)
        user_albums = self.api.get_user_albums_owned(user, page)
        return list(flattened_user_albums(user_albums))

app = webapp.WSGIApplication([
        ('/', MainPage),
        ('/user/(.+)/albums/(.*)', UserAlbumsPage),
        ('/user/?([^/]*)/?', UserPage),
    ],
    debug = DEBUG)

def run_wsgi_app():
    from google.appengine.ext.webapp import util
    return util.run_wsgi_app(app)
