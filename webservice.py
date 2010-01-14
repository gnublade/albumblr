#!/usr/bin/env python

import os, sys
import re
import logging
from optparse import OptionParser
from datetime import datetime
from functools import wraps

DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
TMPL_PATH = os.path.join(DIR_PATH, 'templates')

sys.path.append(os.path.join(DIR_PATH, 'lib'))
import pylast

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template, util
from google.appengine.api.labs import taskqueue

from django.utils import simplejson as json

template.register_template_library('templatefilters')

from api import API
from config import *
from model import User, Album, UserAlbums, UserAlbumsProcessing

DEFAULT_LIMIT = 10
JSON_INDENT   = 2

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
            self._api = API()
        return self._api

    def get_user(self, username):
        return User.get_or_insert(username, username=username)

class UserPage(BaseUserPage):

    def post(self, username):
        """Issue a redirect to the given user page."""
        self.redirect('/user/%s/' % self.request.get('username'))

    @expose('user.html')
    def get(self, username):
        """Show a user page defaulting to a list of owned albums."""
        db_user = self.get_user(username)

        # Bang the start processing task on the queue as fetching a
        # users' albums from their library takes a while and we want to
        # display the page immediately.
        # Or maybe leave it to the client instead.
        #start_url = self.request.path + 'albums/start'
        #taskqueue.add(url=start_url)

        # Show the albums we already know the user owns.
        cached_albums = UserAlbums.all().filter('user', db_user)

        api_user = self.api.get_user(username)
        return dict(
            username = username,
            avatar   = api_user.get_cover_image(),
            realname = api_user.get_realname(),
            age      = api_user.get_age(),
            gender   = api_user.get_gender(),
            country  = api_user.get_country(),

            wanted_albums = (a.album for a in cached_albums if not a.owned),
            owned_albums  = (a.album for a in cached_albums if a.owned))

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
        albums = self.api.get_all_albums(username)
        album_list = [ str(a) for a in albums ]
        return album_list

    @expose(format='json')
    def wanted(self, username):
        params = { 'limit': 10 }
        page_index = self.request.get('page')
        if page_index:
            params['page'] = page_index
        albums = self.api.get_all_albums(username)
        wanted_albums = self.api.find_albums_wanted(username, albums, **params)
        return list(wanted_albums)

    @expose(format='json')
    def owned(self, username):
        db_user = self.get_user(username)
        cached_albums = UserAlbums.all().filter('user', db_user)
        return cached_albums

    @expose()
    def start(self, username):
        """Start checking for owned albums."""
        db_user = self.get_user(username)
        lib_albums = self.api.get_all_albums(username)
        # :TODO: Optimise this so we only pull the data once.
        album_mbids = [ (a,a.get_mbid()) for a in lib_albums ]

        # Don't include the albums we already know the user owns.
        cached_albums_owned = UserAlbums.all().filter('user', db_user)
        cached_album_mbids = set(a.album.mbid for a in cached_albums_owned)
        albums = dict((mbid,a) for (a,mbid) in album_mbids
                      if mbid and mbid not in cached_album_mbids)

        # Don't re-add any that we are already processing.
        processing = UserAlbumsProcessing.all().filter('user', db_user)
        for album in (p.album for p in processing):
            del albums[album.mbid]

        # Create processing entries for the rest
        for mbid, album_info in albums.iteritems():
            album = Album.get_or_insert(mbid,
                    mbid   = mbid.encode('utf8'),
                    artist = album_info.artist.name,
                    title  = album_info.title)
            UserAlbumsProcessing(user=db_user, album=album).put()

        # Add a task to do the work
        task_url = "%s/%s" % (
            os.path.dirname(self.request.path), "process")
        taskqueue.add(url=task_url, method='GET')

    @expose(format='plain')
    def stop(self, username):
        """Stop processing albums."""
        db_user = self.get_user(username)
        deleted = 0
        for entry in UserAlbumsProcessing.all().filter('user', db_user):
            entry.delete()
            deleted += 1
        output = "Stopped processing %d albums for user '%s'" % (
            deleted, username)
        return output

    @expose('process.txt')
    def process(self, username, limit=DEFAULT_LIMIT):
        # Grab the next item for processing
        db_user = self.get_user(username)
        q = UserAlbumsProcessing.all()
        q.filter('user', db_user)
        q.filter('owned', None)
        process_list = q.fetch(limit)

        for entry in process_list:
            album = entry.album

            # Check if the user owns the album
            album_info = self.api.get_album_by_mbid(album.mbid)
            if self.api.find_albums_owned(username, [album_info]):
                entry.owned = True
                logging.info(
                    "Adding owned album '%s' for '%s'" % (album, db_user))
                db_user.add_owned_album(album)
            else:
                entry.owned = False
            entry.put()

        # Queue up the next one.
        task_url = "%s/%s" % (
            os.path.dirname(self.request.path), "process")
        taskqueue.add(url=task_url, method='GET')

        return dict(user=db_user, process_list=process_list)

    @expose(format='json')
    def processed(self, username, limit=DEFAULT_LIMIT):
        """Fetch newly processed owned albums and purge."""
        db_user = self.get_user(username)

        # Fetch albums which have been processed.
        q = UserAlbumsProcessing.all()
        q.filter('user', db_user)
        remaining_count = q.count()
        q.filter('owned !=', None)
        processing = q.fetch(limit)
        processed_count = len(processing)

        # Collect the owned albums and purge all afterwards
        owned_albums = []
        for p in processing:
            if p.owned:
                owned_albums.append(str(p.album))
            p.delete()
        return { 'albums': owned_albums,
                 'processed': processed_count,
                 'remaining': remaining_count }

app = webapp.WSGIApplication([
        ('/', MainPage),
        ('/user/(.+)/albums/(.*)', UserAlbumsPage),
        ('/user/?([^/]*)/?', UserPage),
    ],
    debug = DEBUG)

def run_wsgi_app():
    return util.run_wsgi_app(app)
