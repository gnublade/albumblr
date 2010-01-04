#!/usr/bin/env python

import os, sys
import logging

DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(os.path.join(DIR_PATH, 'lib'))
import pylast

from config import *

def get_api():
    api = pylast.get_lastfm_network(
            api_key    = API_KEY,
            api_secret = API_SECRET)
    return api

def get_all_albums(user):
    lib = user.get_library()
    for album in lib.get_albums():
        yield album.item

def get_top_track_albums(user):
    albums = {}
    for track in user.get_top_tracks():
        album = track.item.get_album()
        logging.debug("Adding top track '%s' album '%s'" % (track.item, album))
        if album:
            albums[album.get_mbid()] = album
        else:
            logging.info("No album for track '%s'" % track.item)
    return albums.values()

def find_albums_owned(user, albums):
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

