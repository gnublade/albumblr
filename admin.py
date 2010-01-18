
import os, sys

from datetime import datetime, timedelta

from google.appengine.ext import webapp

DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(os.path.join(DIR_PATH, 'lib'))
import pylast

from config import *
from api import API
from model import Artist, Album, UserAlbums
from util import expose

UPDATE_FREQ = timedelta(0, 60)

class AdminPage(webapp.RequestHandler):

    @expose('admin.html')
    def get(self):
        return dict()

class UpdatePage(webapp.RequestHandler):

    def get(self):
        self.update_albums()

    def post(self):
        self.update_albums()

    @expose()
    def update_albums(self):
        api = API()
        when = datetime.now() - UPDATE_FREQ
        i = 0
        albums = Album.gql("WHERE last_updated_at < :1", when)
        for i, album in enumerate(albums):
            api.update_album(album)
        return "Update %d Albums" % i

app = webapp.WSGIApplication([
        ('/admin/', AdminPage),
        ('/admin/update/.*', UpdatePage),
    ],
    debug = DEBUG)

def run_wsgi_app():
    from google.appengine.ext.webapp import util
    util.run_wsgi_app(app)

if __name__ == '__main__':
    run_wsgi_app()
