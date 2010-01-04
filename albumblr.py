#!/usr/bin/env python

import os, sys
import re
import logging
from optparse import OptionParser

DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(os.path.join(DIR_PATH, 'lib'))
import pylast

from config import *
from common import (
    get_api, get_all_albums, get_top_track_albums, find_albums_owned)

def main(username, all_albums=False):
    api = get_api()
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
    from webservice import run_wsgi_app
    run_wsgi_app()

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
