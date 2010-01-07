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

from api import API
from config import *
from model import User, Album, UserAlbumStatus, UserAlbumsOwned

class MainPage(webapp.RequestHandler):

    def get(self):
        path = os.path.join(DIR_PATH, 'index.html')
        self.response.out.write(template.render(path, {}))

class BaseUserPage(webapp.RequestHandler):

    @property
    def api(self):
        if getattr(self, '_api', None) is None:
            self._api = API()
        return self._api

class UserPage(BaseUserPage):

    def get(self, username):
        start_url = self.request.path + 'albums/start'
        taskqueue.add(url=start_url, method='GET')
        path = os.path.join(DIR_PATH, 'user.html')
        user = User.get_or_insert(username, username = username)
        albums_owned = UserAlbumsOwned.all().filter('user =', user)
        values = dict(
            username = username,
            albums   = (a.album for a in albums_owned))
        self.response.out.write(template.render(path, values))

    def post(self):
        self.redirect('/user/%s/' % self.request.get('username'))

class UserAlbumsPage(BaseUserPage):

    actions = [ 'index', 'status', 'start', 'stop', 'owned' ]
    default_action = 'index'

    def get(self, username, action):
        action = action or self.default_action
        if action in self.actions:
            output = getattr(self, action)(username)
        else:
            self.error(404)

    def index(self, username):
        albums = self.api.get_all_albums(username)
        album_list = [ str(a) for a in albums ]
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write(json.dumps(album_list, indent=2))

    def owned(self, username):
        user = User.get_or_insert(username, username=username)
        owned_albums = UserAlbumsOwned.all().filter('user', user)
        albums = [ str(a.album) for a in owned_albums ]
        self.response.headers['Content-Type'] = 'text/javascript'
        self.response.out.write(json.dumps(albums, indent=2))

    def status(self, username):
        self.response.headers['Content-Type'] = 'text/plain'
        status = UserAlbumStatus.get_by_key_name(username)
        if status:
            output = json.dumps(status.to_dict(), indent=2)
        else:
            output = "No status for user '%s'" % username
        self.response.out.write(output)

    def start(self, username):
        user = User.get_or_insert(username, username=username)
        status = UserAlbumStatus.get_or_insert(username, user=user)
        if status.processed < status.processing:
            return
        user_albums = UserAlbumsOwned.all().filter('user', user)
        user_album_mbids = set(a.album.mbid for a in user_albums)
        lib_albums = self.api.get_all_albums(user.username)
        album_mbids = [ (a,a.get_mbid()) for a in lib_albums ]
        status.owned_count = len(user_album_mbids)
        status.album_count = len(album_mbids)
        albums = [ (a,mbid) for (a,mbid) in album_mbids
                   if mbid and mbid not in user_album_mbids ]
        status.processing = len(albums)
        status.processed = 0
        for album,mbid in albums:
            task_url = "%s/%s/%s" % (
                os.path.dirname(self.request.path), mbid, "process")
            taskqueue.add(url=task_url, method='GET')
        status.put()

    def stop(self, username):
        self.response.headers['Content-Type'] = 'text/plain'
        status = UserAlbumStatus.get_by_key_name(username)
        if status:
            status.delete()
            output = "Deleted status for user '%s'" % username
        else:
            output = "No status for user '%s'" % username
        self.response.out.write(output)

class UserAlbumPage(BaseUserPage):

    actions = [ 'index', 'process', 'status' ]
    default_action = 'index'

    def get(self, username, album_mbid, action):
        assert album_mbid
        output = ""
        action = action or self.default_action
        if action in self.actions:
            output = getattr(self, action)(username, album_mbid)
        else:
            self.error("Unknown action '%s'" % action)
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write(output)

    def index(self, username, album_mbid):
        album = Album.get_by_key_name(album_mbid)
        if album:
            title = str(album)
        else:
            album_info = self.api.get_album_by_mbid(album_mbid)
            title = str(album_info)
        output = "%s\n%s\n" % (title, "=" * len(title))
        return output

    def process(self, username, album_mbid):
        output = "Process\n=======\n"
        album_info = self.api.get_album_by_mbid(album_mbid)
        output += ":User:   %s\n" % username
        output += ":Album:  %s\n" % album_info
        output += ":Status: "
        status = UserAlbumStatus.get_by_key_name(username)
        if self.api.find_albums_owned(username, [album_info]):
            output += "Owned"
            album = Album.get_or_insert(album_mbid,
                    mbid   = album_info.get_mbid().encode('utf8'),
                    artist = album_info.artist.name,
                    title  = album_info.title)
            user = User.get_or_insert(username,
                    username = username)
            logging.info(
                "Adding owned album '%s' for '%s'" % (album, user))
            user.add_owned_album(album)
            if status:
                logging.debug(
                    "Incrementing owned count for '%s'" % username)
                status.owned_count += 1
        else:
            output += "Not owned"
        if status:
            status.processed += 1
            status.last_updated_at = datetime.now()
            status.put()
        return output


app = webapp.WSGIApplication([
        ('/', MainPage),
        ('/user/(.+)/albums/([^/]+)/(.*)', UserAlbumPage),
        ('/user/(.+)/albums/(.*)', UserAlbumsPage),
        ('/user/?([^/]*)/?', UserPage),
    ],
    debug = DEBUG)

def run_wsgi_app():
    return util.run_wsgi_app(app)
