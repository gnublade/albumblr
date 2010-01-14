from google.appengine.ext import db

class Album(db.Model):
    mbid   = db.StringProperty()
    title  = db.StringProperty()
    artist = db.StringProperty()

    def __str__(self):
        return "%s - %s" % (self.artist, self.title) or self.mbid

class User(db.Model):
    username = db.StringProperty(required=True)

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

class UserAlbums(db.Model):
    user  = db.ReferenceProperty(User, required=True)
    album = db.ReferenceProperty(Album, required=True)
    owned = db.BooleanProperty(default=True)

class UserAlbumsProcessing(db.Model):
    user  = db.ReferenceProperty(User, required=True)
    album = db.ReferenceProperty(Album, required=True)
    owned = db.BooleanProperty()
