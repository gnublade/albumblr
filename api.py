#!/usr/bin/env python

import os, sys
import logging

DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(os.path.join(DIR_PATH, 'lib'))
import pylast

from config import *

class API(object):

    def __init__(self):
        self._lastfm = pylast.get_lastfm_network(
                api_key    = API_KEY,
                api_secret = API_SECRET)

    def get_all_albums(self, username):
        user = self._lastfm.get_user(username)
        lib = user.get_library()
        for album in lib.get_albums():
            yield album.item

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

    def find_albums_owned(self, username, albums):
        user = self._lastfm.get_user(username)
        lib = user.get_library()
        for album in albums:
            logging.info("Looking for tracks on '%s'" % album)
            album_tracks = album.get_tracks()
            have_tracks  = lib.get_tracks(
                    artist = album.artist.name,
                    album  = album.title)
            album_len, have_len = len(album_tracks), len(have_tracks)
            logging.info("    found %d of %d tracks" % (have_len, album_len))
            if (album_len - have_len) > 1:
                logging.debug("Removing album '%s'" % album)
            else:
                yield album

