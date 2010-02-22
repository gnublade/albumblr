#!/usr/bin/env python

import os, sys, re
import logging
from datetime import datetime
from itertools import ifilter, ifilterfalse
from math import sqrt

from google.appengine.ext.db import BadArgumentError
from google.appengine.api.urlfetch import DownloadError

import pylast
import musicbrainz2.webservice as ws

from model import Cache, User, Album, Artist, Track, UserAlbums
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

        user.avatar_url = lastfm_user.get_cover_image()
        user.realname   = lastfm_user.get_realname()
        user.age        = lastfm_user.get_age()
        user.gender     = lastfm_user.get_gender()

        country = lastfm_user.get_country().get_name()
        user.country  = str(country) if country else None

        user.last_updated_at = datetime.now()
        user.last_updated_to = 0
        user.put()

    def maybe_update_user(self, user):
        if self.updates_enabled and user.is_update_due():
            self.update_user(user)

    def _find_valid_tracks(self, lastfm_album):
        q = ws.Query()
        mb_incs = ws.ReleaseIncludes(tracks=True, counts=True)
        try:
            mb_album = q.getReleaseById(lastfm_album.get_mbid(), mb_incs)
            logging.debug("Found MB Release: %s" % mb_album)
        except ws.ResourceNotFoundError:
            logging.debug("MusicBrainz couldn't find album: %s" % lastfm_album)
            raise
        p = re.compile("[\W]+")
        def normalise(s):
            return p.sub("", s.lower())
        lastfm_track_map = dict(
            (normalise(t.get_title()), t) for t in lastfm_album.get_tracks())
        tracks = []
        mb_tracks = mb_album.getTracks()
        for mb_track in mb_tracks:
            track_title = mb_track.getTitle()
            lastfm_track = lastfm_track_map.get(normalise(track_title))
            if lastfm_track:
                logging.debug("Matched MusicBrainz track: %s" % track_title)
                tracks.append(lastfm_track)
            else:
                logging.debug("Failed to match track: %s" % track_title)
        return tracks, mb_album.getTracksCount() or len(mb_tracks)

    def update_album(self, album, lastfm_album=None):
        try:
            if lastfm_album is None:
                album_mbid = album.key().name()
                lastfm_album = self._lastfm.get_album_by_mbid(album_mbid)
            else:
                album_mbid = lastfm_album.get_mbid()
            assert album_mbid

            # Every album has an Artist.
            lastfm_artist = lastfm_album.artist
            artist_mbid = lastfm_artist.get_mbid()
            assert artist_mbid
            logging.debug(lastfm_artist.get_name())
            artist_name = lastfm_artist.get_name()
            artist = Artist.get_or_insert(artist_mbid,
                name = unicode(artist_name),
                url  = lastfm_artist.get_url())

            # Get a list of track we think is on the album.
            lastfm_tracks, track_count = self._find_valid_tracks(lastfm_album)

            # Create or update the ablum details.
            album_dict = dict(
                artist = artist,
                title  = lastfm_album.title,
                url    = lastfm_album.get_url(),
                cover_image_url = lastfm_album.get_cover_image(
                    size = pylast.COVER_MEDIUM),
                track_count = track_count)

            album = Album.get_by_key_name(album_mbid)
            if album is None:
                album = Album(key_name = album_mbid, **album_dict)
            else:
                for key, value in album_dict.iteritems():
                    setattr(album, key, value)
            album.put()

            # Create or update the album tracks.
            album_tracks = dict((t.title, t) for t in album.get_tracks())
            for i, lastfm_track in enumerate(lastfm_tracks):
                title = lastfm_track.get_title()
                if title in album_tracks:
                    track = lastfm_track
                    track.position = i
                    track.put()
                else:
                    track = Track(
                        artist = artist,
                        album  = album,
                        title  = title,
                        position = i)

        except BadArgumentError, e:
            logging.debug("Cannot store album '%s'" % lastfm_album)
        except (AssertionError, ws.ResourceNotFoundError), e:
            logging.debug(e)
        return album

    def update_user_albums(self, user, page):
        logging.info("Updating page %d albums for '%s'" % (page, user))
        lastfm_user = self._lastfm.get_user(user.username)
        lastfm_lib = lastfm_user.get_library()
        lastfm_lib_albums = lastfm_lib.get_albums(DEFAULT_LIMIT, page+1)

        for lastfm_album in pylast.extract_items(lastfm_lib_albums):
            album = self.update_album(None, lastfm_album)
            if album is None:
                continue

            q = UserAlbums.all()
            q.filter('user', user)
            q.filter('album', album)
            user_album = q.get()

            if user_album and user_album.owned:
                continue
            try:
                played_tracks = self._find_played_tracks(
                        lastfm_lib, lastfm_album)
                played_count = len(played_tracks)
                owned = played_count / float(album.track_count) > 0.75
            except DownloadError, e:
                logging.debug(str(e))
                owned = None
            if user_album is None:
                user_album = UserAlbums(
                    user  = user,
                    album = album,
                    owned = owned,
                    num_played_tracks = played_count)
            else:
                user_album.owned = owned
            user_album.put()
        user.last_updated_to = page + 1
        user.put()

    def maybe_update_user_albums(self, user, page = 0):
        if self.updates_enabled and (
            user.is_update_due() or user.last_updated_to <= page):
            self.update_user_albums(user, page)

    def get_user_albums(self, user, page=0):
        q = UserAlbums.all()
        q.filter('user', user)
        return q.fetch(DEFAULT_LIMIT, offset = DEFAULT_LIMIT * page)

    def _find_played_tracks(self, lastfm_lib, lastfm_album):
        logging.info("Looking for tracks on '%s'" % lastfm_album)
        album_mbid = lastfm_album.get_mbid()
        album = Album.get_by_key_name(album_mbid)
        tracks = album.get_tracks()
        played_tracks = lastfm_lib.get_tracks(
                artist = lastfm_album.artist.name,
                album  = lastfm_album.title)
        logging.info("    found %d of %d tracks" % (
            len(played_tracks), album.track_count))
        return played_tracks

    def get_user_albums_owned(self, user, page=0):
        q = UserAlbums.all()
        q.filter('user', user)
        q.filter('owned', True)
        user_albums = q.fetch(DEFAULT_LIMIT, DEFAULT_LIMIT * page)
        return user_albums

    def get_user_albums_wanted(self, user, page=0):
        q = UserAlbums.all()
        q.filter('user', user)
        q.filter('owned', False)
        user_albums = q.fetch(DEFAULT_LIMIT, DEFAULT_LIMIT * page)
        return user_albums

