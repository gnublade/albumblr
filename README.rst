==========
 Albumblr
==========

-----------------------------------------------------
 Album suggestions based on Last.fm listening habits
-----------------------------------------------------

:Author: Andy Kilner <gnublade@googlemail.com>
:Website: http://albumblr.appspot.com
:Source: http://github.com/gnublade/albumblr
:License: http://creativecommons.org/licenses/GPL/2.0

About
=====
Albumblr is a Google App Engine project to identify albums listened to
by a Last.fm user and suggest albums that the user might like and which
they don't already own.

It works this out by checking the album's track list against your
library.  If all of the tracks on the album are in your library then
there's a good chance you own the album and have played it all the way
through.

Obviously it's not perfect and if you don't listen to the whole album it
might suggest it to you or if you scrobble from sources such as Spotify
that will fool it too.  If spotify opened up it's data we could check
that for tracks you have played.

Requirements
============
 * PyLast: http://code.google.com/p/pylast/
   A modified version is provided in the lib directory
 * musicbrainz2: http://wiki.musicbrainz.org/PythonMusicBrainz2
   The is an external dependency that needs to be zipped and added to
   the path before uploading to appspot.

Known Bugs
==========
 * Doesn't work from the command line due to dependency on GAE
   datastore.
 * No progress feedback.
 * The matching algorithm is far from perfect.
