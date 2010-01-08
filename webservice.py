#!/usr/bin/env python

import os, sys
import re
import logging
from optparse import OptionParser
from datetime import datetime
from itertools import ifilter

DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(os.path.join(DIR_PATH, 'lib'))
import pylast

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template, util
from google.appengine.api.labs import taskqueue

from django.utils import simplejson as json

template.register_template_library('templatefilters')

from api import API
from config import *
from model import User, Album, UserAlbumsOwned, UserAlbumsProcessing

DEFAULT_LIMIT = 10

class MainPage(webapp.RequestHandler):

    def get(self):
        path = os.path.join(TMPL_PATH, 'index.html')
        self.response.out.write(template.render(path, {}))

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

    def get(self, username):
        """Show a user page defaulting to a list of owned albums."""
        user = self.get_user(username)

        # Bang the start processing task on the queue as fetching a
        # users' albums from their library takes a while and we want to
        # display the page immediately.
        # Or maybe leave it to the client instead.
        #start_url = self.request.path + 'albums/start'
        #taskqueue.add(url=start_url)

        # Show the albums we already know the user owns.
        albums_owned = UserAlbumsOwned.all().filter('user', user)

        path = os.path.join(TMPL_PATH, 'user.html')
        user = self.get_user(username)
        values = dict(
            username = username,
            albums   = (a.album for a in albums_owned))
        self.response.out.write(template.render(path, values))

class UserAlbumsPage(BaseUserPage):

    get_actions = [ 'index', 'owned' ]
    default_get_action = 'index'

    post_actions = [ 'start', 'stop', 'processed', 'process' ]
    defautl_get_action = None

    if DEBUG:
        get_actions += post_actions

    def get(self, username, action):
        action = action or self.default_get_action
        if action in self.get_actions:
            output = getattr(self, action)(username)
        else:
            self.error(404)
        if output:
            self.response.out.write(output)

    def post(self, username, action):
        action = action or self.default_post_action
        if action in self.post_actions:
            output = getattr(self, action)(username)
        else:
            self.error(404)
        if output:
            self.response.out.write(output)

    def index(self, username):
        albums = self.api.get_all_albums(username)
        album_list = [ str(a) for a in albums ]
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write(json.dumps(album_list, indent=2))

    def owned(self, username):
        user = self.get_user(username)
        owned_albums = UserAlbumsOwned.all().filter('user', user)
        albums = [ str(a.album) for a in owned_albums ]
        self.response.headers['Content-Type'] = 'text/javascript'
        self.response.out.write(json.dumps(albums, indent=2))

    def start(self, username):
        """Start checking for owned albums."""
        user = self.get_user(username)
        lib_albums = self.api.get_all_albums(username)
        # :TODO: Optimise this so we only pull the data once.
        album_mbids = [ (a,a.get_mbid()) for a in lib_albums ]

        # Don't include the albums we already know the user owns.
        user_albums = UserAlbumsOwned.all().filter('user', user)
        user_album_mbids = set(a.album.mbid for a in user_albums)
        albums = dict((mbid,a) for (a,mbid) in album_mbids
                      if mbid and mbid not in user_album_mbids)

        # Don't re-add any that we are already processing.
        processing = UserAlbumsProcessing.all().filter('user', user)
        for album in (p.album for p in processing):
            del albums[album.mbid]

        # Create processing entries for the rest
        for mbid, album_info in albums.iteritems():
            album = Album.get_or_insert(mbid,
                    mbid   = mbid.encode('utf8'),
                    artist = album_info.artist.name,
                    title  = album_info.title)
            UserAlbumsProcessing(user=user, album=album).put()

        # Add a task to do the work
        task_url = "%s/%s" % (
            os.path.dirname(self.request.path), "process")
        taskqueue.add(url=task_url, method='GET')

    def stop(self, username):
        """Stop processing albums."""
        self.response.headers['Content-Type'] = 'text/plain'
        user = self.get_user(username)
        deleted = 0
        for entry in UserAlbumsProcessing.all().filter('user', user):
            entry.delete()
            deleted += 1
        output = "Stopped processing %d albums for user '%s'" % (
            deleted, username)
        return output

    def process(self, username, limit=DEFAULT_LIMIT):
        # Grab the next item for processing
        user = self.get_user(username)
        q = UserAlbumsProcessing.all()
        q.filter('user', user)
        q.filter('owned', None)
        process_list = q.fetch(limit)

        for entry in process_list:
            album = entry.album

            # Check if the user owns the album
            album_info = self.api.get_album_by_mbid(album.mbid)
            if self.api.find_albums_owned(username, [album_info]):
                entry.owned = True
                logging.info(
                    "Adding owned album '%s' for '%s'" % (album, user))
                user.add_owned_album(album)
            else:
                entry.owned = False
            entry.put()

        # Queue up the next one.
        task_url = "%s/%s" % (
            os.path.dirname(self.request.path), "process")
        taskqueue.add(url=task_url, method='GET')

        values = dict(user=user, process_list=process_list)
        path = os.path.join(TMPL_PATH, 'process.txt')
        return template.render(path, values)

    def processed(self, username, limit=DEFAULT_LIMIT):
        """Fetch newly processed owned albums and purge."""
        user = self.get_user(username)

        # Fetch albums which have been processed.
        q = UserAlbumsProcessing.all()
        q.filter('user', user)
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
        values = { 'albums': owned_albums,
                   'processed': processed_count,
                   'remaining': remaining_count }
        return json.dumps(values, indent=2)

app = webapp.WSGIApplication([
        ('/', MainPage),
        ('/user/(.+)/albums/(.*)', UserAlbumsPage),
        ('/user/?([^/]*)/?', UserPage),
    ],
    debug = DEBUG)

def run_wsgi_app():
    return util.run_wsgi_app(app)
