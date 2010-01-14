from datetime import datetime

from google.appengine.ext import db

SECONDS_PER_DAY = 24 * 3600
UPDATE_INTERVAL = 1 * SECONDS_PER_DAY

class Cache(db.Model):
    value = db.TextProperty()

class Album(db.Model):
    mbid   = db.StringProperty()
    title  = db.StringProperty()
    artist = db.StringProperty()

    def __str__(self):
        return "%s - %s" % (self.artist, self.title) or self.mbid

class User(db.Model):
    username = db.StringProperty(required=True)
    avatar   = db.StringProperty()
    realname = db.StringProperty()
    age      = db.IntegerProperty()
    gender   = db.StringProperty(choices=["Male", "Female"])
    country  = db.StringProperty()

    last_update_at = db.DateTimeProperty()
    last_update_to = db.IntegerProperty()

    def __str__(self):
        return self.username

    def add_owned_album(self, album):
        q = UserAlbumsOwned.all()
        q.filter('user', self)
        q.filter('album', album)
        owned_album = q.get()
        if owned_album is None:
            owned_album = UserAlbumsOwned(user=self, album=album)
            owned_album.put()
        return owned_album

    def is_update_due(self):
        if self.last_update_at:
            td = datetime.now() - self.last_update_at
            seconds_since = td.days * SECONDS_PER_DAY + td.seconds
            update_due = seconds_since >= UPDATE_INTERVAL
        else:
            update_due = True # Never been updated
        return update_due

class UserAlbums(db.Model):
    user  = db.ReferenceProperty(User, required=True)
    album = db.ReferenceProperty(Album, required=True)
    owned = db.BooleanProperty(default=True)

    def __str__(self):
        return "%s [%s Owned]" % (self.album, ("Not ", "")[self.owned])

class UserAlbumsProcessing(db.Model):
    user  = db.ReferenceProperty(User, required=True)
    album = db.ReferenceProperty(Album, required=True)
    owned = db.BooleanProperty()
