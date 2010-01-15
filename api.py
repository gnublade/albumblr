#!/usr/bin/env python

import os, sys
import logging
from datetime import datetime
from itertools import ifilter, ifilterfalse

from google.appengine.ext.db import BadArgumentError
from google.appengine.api.urlfetch import DownloadError

import pylast

from model import Cache, User, Album, UserAlbums
from config import *

class _DatastoreCacheBackend(object):
    """Used as a backend for caching cacheable requests."""
    def __init__(self, *args, **kw):
        pass

    def get_xml(self, key):
        return Cache.get_by_key_name(key).value

    def set_xml(self, key, xml_string):
        item = Cache.get_by_key_name(key)
        if item is None:
            item = Cache(key_name = key, value = xml_string)
        item.value = xml_string
        item.put()

    def has_key(self, key):
        return Cache.get_by_key_name(key) is not None

class API(object):

    def __init__(self, enable_updates=True):
        self.updates_enabled = enable_updates
        self._lastfm = pylast.get_lastfm_network(
                api_key    = API_KEY,
                api_secret = API_SECRET)
        self._lastfm.enable_caching(backend = _DatastoreCacheBackend)

    def get_user(self, username, check_for_update = False):
        user = User.get_by_key_name(username)
        if user is None:
            logging.debug("No user '%s' found, updating." % username)
            user = User(key_name=username, username=username)
            self.update_user(user)
        elif check_for_update:
            self.maybe_update_user(user)
        return user

    def update_user(self, user):
        logging.debug("Updating user '%s'" % user.username)
        lastfm_user = self._lastfm.get_user(user.username)

        user.avatar   = lastfm_user.get_cover_image()
        user.realname = lastfm_user.get_realname()
        user.age      = lastfm_user.get_age()
        user.gender   = lastfm_user.get_gender()
        user.country  = str(lastfm_user.get_country())

        user.last_updated_at = datetime.now()
        user.last_updated_to = 0
        user.put()

    def maybe_update_user(self, user):
        if self.updates_enabled and user.is_update_due():
            self.update_user(user)

    def update_user_albums(self, user, page):
        logging.info("Updating page %d albums for '%s'" % (page, user))
        lastfm_user = self._lastfm.get_user(user.username)
        lastfm_lib = lastfm_user.get_library()
        lastfm_lib_albums = lastfm_lib.get_albums(DEFAULT_LIMIT, page + 1)

        for lastfm_album in pylast.extract_items(lastfm_lib_albums):
            mbid = lastfm_album.get_mbid()
            try:
                album = Album.get_or_insert(mbid,
                    mbid   = mbid,
                    artist = unicode(str(lastfm_album.artist), 'utf8'),
                    title  = lastfm_album.title)
            except BadArgumentError, e:
                logging.debug("Cannot store album '%s'" % lastfm_album)
                continue

            q = UserAlbums.all()
            q.filter('user', user)
            q.filter('album', album)
            user_album = q.get()

            if user_album and user_album.owned:
                continue
            try:
                owned = self._user_owns_album(lastfm_lib, lastfm_album)
            except DownloadError, e:
                logging.debug(str(e))
                owned = None
            if user_album is None:
                user_album = UserAlbums(
                    user  = user,
                    album = album,
                    owned = owned)
            else:
                user_album.owned = owned
            user_album.put()
        user.last_updated_to = page + 1
        user.put()

    def maybe_update_user_albums(self, user, page = 0):
        if self.updates_enabled and (
            user.is_update_due() or user.last_updated_to <= page):
            self.update_user_albums(user, page)

    def get_user_albums(self, user, page):
        q = UserAlbums.all()
        q.filter('user', user)
        return q.fetch(DEFAULT_LIMIT, offset = DEFAULT_LIMIT * page)

    def _user_owns_album(self, lib, album):
        logging.info("Looking for tracks on '%s'" % album)
        album_tracks = album.get_tracks()
        have_tracks  = lib.get_tracks(
                artist = album.artist.name,
                album  = album.title)
        logging.info("    found %d of %d tracks" % (
            len(have_tracks), len(album_tracks)))
        owned = (len(album_tracks) - len(have_tracks)) <= 1
        return owned

    def get_albums_owned(self, user, page=0):
        q = UserAlbums.all()
        q.filter('user', user)
        q.filter('owned', True)
        user_albums = q.fetch(DEFAULT_LIMIT, DEFAULT_LIMIT * page)
        albums = [ a.album for a in user_albums ]
        return albums

    def get_albums_wanted(self, user, page=0):
        q = UserAlbums.all()
        q.filter('user', user)
        q.filter('owned', False)
        user_albums = q.fetch(DEFAULT_LIMIT, DEFAULT_LIMIT * page)
        albums = [ a.album for a in user_albums ]
        return albums

