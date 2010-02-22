
import os, sys

from datetime import datetime, timedelta

from google.appengine.ext import webapp, db

DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
LIB_PATH = os.path.join(DIR_PATH, 'lib')
if LIB_PATH not in sys.path: sys.path.append(LIB_PATH)
import pylast

try:
    import musicbrainz2
except ImportError:
    MB_PATH = os.path.join(LIB_PATH, 'musicbrainz2.zip')
    if MB_PATH not in sys.path: sys.path.insert(0, MB_PATH)

from config import *
from api import API
from model import Artist, Album, UserAlbums, User
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


class DeletePage(webapp.RequestHandler):

    def get(self, user):
        if user:
            self.delete_user(user)
        else:
            self.delete_everything()

    def post(self):
        self.delete_everything()

    @expose()
    def delete_everything(self):
        db.delete(UserAlbums.all(keys_only=True))
        db.delete(Album.all(keys_only=True))
        db.delete(Artist.all(keys_only=True))
        db.delete(User.all(keys_only=True))
        return "Deleted everything.. hope you're happy with yourself!"

    @expose()
    def delete_user(self, username):
        user = User.get_by_key_name(username)
        q = UserAlbums.all(keys_only=True)
        q.filter('user', user)
        db.delete(q)
        user.delete()
        return "Deleted user '%s'" % username

app = webapp.WSGIApplication([
        ('/admin/', AdminPage),
        ('/admin/update/.*', UpdatePage),
        ('/admin/delete/(.*)', DeletePage),
    ],
    debug = DEBUG)

def run_wsgi_app():
    from google.appengine.ext.webapp import util
    util.run_wsgi_app(app)

if __name__ == '__main__':
    run_wsgi_app()
