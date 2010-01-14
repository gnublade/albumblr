#!/usr/bin/env python

import os, sys
import logging
from datetime import datetime
from itertools import ifilter, ifilterfalse

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

    def __init__(self):
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

        user.last_update_at = datetime.now()
        user.last_update_to = 0
        user.put()

    def maybe_update_user(self, user):
        if user.is_update_due():
            self.update_user(user)

    def update_user_albums(self, user, page):
        logging.debug("Updating page %d albums for '%s'" % (page, user))
        lastfm_user = self._lastfm.get_user(user.username)
        lastfm_lib = lastfm_user.get_library()
        lastfm_lib_albums = lastfm_lib.get_albums(DEFAULT_LIMIT, page)

        for lastfm_album in pylast.extract_items(lastfm_lib_albums):
            mbid = lastfm_album.get_mbid()
            album = Album.get_or_insert(mbid,
                mbid   = mbid,
                artist = str(lastfm_album.artist),
                title  = lastfm_album.title)

            q = UserAlbums.all()
            q.filter('user', user)
            q.filter('album', album)
            user_album = q.get()

            if user_album and user_album.owned:
                continue
            owned = self._user_owns_album(lastfm_lib, lastfm_album)
            if user_album is None:
                user_album = UserAlbums(
                    user  = user,
                    album = album,
                    owned = owned)
            else:
                user_album.owned = owned
            user_album.put()

    def maybe_update_user_albums(self, user, page = 0):
        if user.is_update_due() or user.last_update_to <= page:
            self.update_user_albums(user, page)

    def get_user_albums(self, user):
        self.maybe_update_user_albums(user)
        q = UserAlbums.all()
        q.filter('user', user)
        return q.fetch(DEFAULT_LIMIT)

    def _user_owns_album(self, lib, album):
        logging.info("Looking for tracks on '%s'" % album)
        album_tracks = album.get_tracks()
        have_tracks  = lib.get_tracks(
                artist = album.artist.name,
                album  = album.title)
        logging.info("    found %d of %d tracks" % (
            len(have_tracks), len(album_tracks)))
        owned = (len(album_tracks) - len(have_tracks)) > 1
        return owned

    ####

    def get_top_track_albums(self, username):
        user = self._lastfm.get_user(username)
        albums = set()
        for top_track in user.get_top_tracks():
            track = top_track.item
            album = track.get_album()
            logging.debug("Adding top track '%s' album '%s'" % (track, album))
            if album:
                key = album.get_mbid() or str(album)
                if key not in albums:
                    yield album
                    albums.add(key)
            else:
                logging.info("No album for track '%s'" % track)

    def _is_album_owned(self, username):
        """Coroutine to test whether album is owned by a given user."""
        user = self._lastfm.get_user(username)
        lib = user.get_library()
        album = yield
        while 1:
            logging.info("Looking for tracks on '%s'" % album)
            album_tracks = album.get_tracks()
            have_tracks  = lib.get_tracks(
                    artist = album.artist.name,
                    album  = album.title)
            logging.info("    found %d of %d tracks" % (
                len(have_tracks), len(album_tracks)))
            owned = (len(album_tracks) - len(have_tracks)) > 1
            album = yield (album, owned)

    def find_albums_owned(self, username, albums, **params):
        """Return all of the given albums which the user owns."""
        pred = self._is_album_owned(username).send
        return ifilter(pred, albums)

    def find_albums_wanted(self, username, albums, **params):
        """Return all of the given albums which the user doesn't own."""
        pred = self._is_album_owned(username).send
        yielded = pred(None)
        logging.debug(yielded)
        return ifilterfalse(pred, albums)


