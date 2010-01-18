import os
DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
TMPL_PATH = os.path.join(DIR_PATH, 'templates')

API_KEY    = "..."
API_SECRET = "..."

DEBUG = True

DEFAULT_LIMIT = 10
JSON_INDENT   = 2

DEFAULT_AVATAR_URL = "http://cdn.last.fm/flatness/catalogue/noimage/2/default_user_large.png"
