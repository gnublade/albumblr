import logging
from datetime import datetime

from google.appengine.ext import db

SECONDS_PER_DAY = 24 * 3600
UPDATE_INTERVAL = 1 * SECONDS_PER_DAY

class Cache(db.Model):
    value = db.TextProperty()

class Artist(db.Model):

    name = db.StringProperty(required=True)
    url  = db.StringProperty()

    def __str__(self):
        return str(self.name)

class Album(db.Model):
    title           = db.StringProperty()
    artist          = db.ReferenceProperty(Artist, required=True)
    url             = db.StringProperty()
    cover_image_url = db.StringProperty()
    track_count     = db.IntegerProperty()

    last_updated_at = db.DateTimeProperty(auto_now=True)

    def __str__(self):
        return "%s - %s" % (self.artist, self.title) or self.mbid

    def __json__(self):
        return dict((k,getattr(self, k)) for k in self.properties())

    def get_tracks(self):
        q = Track.all()
        q.filter('album', self)
        return q.fetch(self.track_count)

class Track(db.Model):
    artist = db.ReferenceProperty(Artist, required=True)
    album  = db.ReferenceProperty(Album, required=True)
    title  = db.StringProperty(required=True)
    position = db.IntegerProperty()

class User(db.Model):
    username = db.StringProperty(required=True)
    realname = db.StringProperty()
    age      = db.IntegerProperty()
    gender   = db.StringProperty(choices=["Male", "Female"])
    country  = db.StringProperty()

    avatar_url = db.StringProperty()

    last_updated_at = db.DateTimeProperty()
    last_updated_to = db.IntegerProperty()

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
        if self.last_updated_at:
            td = datetime.now() - self.last_updated_at
            seconds_since = td.days * SECONDS_PER_DAY + td.seconds
            update_due = seconds_since >= UPDATE_INTERVAL
            logging.debug("td:%s, %s, %s" % (str(td), seconds_since, update_due))
        else:
            update_due = True # Never been updated
        return update_due

class UserAlbums(db.Model):
    user  = db.ReferenceProperty(User, required=True)
    album = db.ReferenceProperty(Album, required=True)
    owned = db.BooleanProperty(default=True)

    num_played_tracks = db.IntegerProperty()

    def __str__(self):
        return "%s [%sOwned]" % (self.album, ("Not ", "")[self.owned])

class UserAlbumsProcessing(db.Model):
    user  = db.ReferenceProperty(User, required=True)
    album = db.ReferenceProperty(Album, required=True)
    owned = db.BooleanProperty()
