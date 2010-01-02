#!/usr/bin/env python

import os, sys
import logging
from optparse import OptionParser

DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(os.path.join(DIR_PATH, 'lib'))
import pylast

from config import *

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

def main(username, all_albums=False):
    api = pylast.get_lastfm_network(
            api_key    = API_KEY,
            api_secret = API_SECRET)
    user = api.get_user(username)
    albums = get_all_albums(user) if all_albums else get_top_track_albums(user)
    for album in find_albums_owned(user, albums):
        print album

def add_options(parser):
    parser.add_option('-a', '--all',
            action = 'store_true')
    parser.add_option('-d', '--debug',
            action = 'store_true')
    parser.add_option('-v', '--verbose',
            action = 'store_true')

    def post_func(opts, args):
        if len(args) != 1:
            parser.error("No username given")

def init_logging(opts):
    if opts.debug:
        log_level = logging.DEBUG
    elif opts.verbose:
        log_level = logging.INFO
    else:
        log_level = logging.WARN
    logging.basicConfig(level=log_level)

def run_cgi():
    from google.appengine.ext import webapp
    from google.appengine.ext.webapp import template
    from google.appengine.ext.webapp.util import run_wsgi_app

    class MainPage(webapp.RequestHandler):

        def get(self):
            path = os.path.join(DIR_PATH, 'index.html')
            self.response.out.write(template.render(path, {}))

    app = webapp.WSGIApplication([('/', MainPage)], debug=DEBUG)
    run_wsgi_app(app)

def run_cli():
    usage = "usage: %prog [options] USERNAME"
    parser = OptionParser(usage)
    post_func = add_options(parser)
    opts, args = parser.parse_args()
    if post_func: post_func(opts, args)
    init_logging(opts)

    main(*args, all_albums=opts.all)

if __name__ == '__main__':
    run_cgi() if 'GATEWAY_INTERFACE' in os.environ else run_cli()
