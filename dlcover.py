#!/usr/bin/env python
#
# Copyright (c) 2008 Sebastian Noack
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#

from optparse import OptionParser

import os
import re
from optparse import OptionParser
from functools import wraps, partial
import urllib2

import magic
import tagpy
import musicbrainz; locals().update((k, v) for k, v in musicbrainz.__dict__.iteritems() if k.startswith('MB'))

AMAZON_URL = 'http://images.amazon.com/images/P/%s.01.%s.jpg'
AMAZON_PICTURE_SIZES = (
	('thumbnail', 'THUMBZZZ'),
	('small', 'TZZZZZZZ'),
	('medium', 'MZZZZZZZ'),
	('large', 'LZZZZZZZ'),
)
IMAGE_MIME_TYPES = (
	'image/jpeg',
	'image/png',
	'image/gif',
	'image/bmp',
)

def memoize(func, cache, key=lambda x: x[:]):
    def wrapper(*args):
        mem_args = key(args)
        if mem_args in cache:
            return cache[mem_args]
        result = func(*args)
        cache[mem_args] = result
        return result
    return wraps(func)(wrapper)

def normalize(obj):
	if isinstance(obj, basestring):
		return re.sub(r'[^a-z0-9]', '', obj.lower())
	if isinstance(obj, (list, tuple)):
		return obj.__class__(normalize(x) for x in obj)
	return obj

@partial(memoize, cache={}, key=normalize)
def get_mb_for_artist(artist):
	mb = musicbrainz.mb()
	mb.SetDepth(4)
	mb.QueryWithArgs(MBQ_FindArtistByName, [artist])
	return mb

@partial(memoize, cache={}, key=normalize)
def get_ASIN(artist, album):
	mb = get_mb_for_artist(artist)
	mb.Select(MBS_Rewind)

	for idx_artist in xrange(1, mb.GetResultInt(MBE_GetNumArtists) + 1):
		mb.Select1(MBS_SelectArtist, idx_artist)
		for idx_album in xrange(1, mb.GetResultInt(MBE_GetNumAlbums) + 1):
			mb.Select1(MBS_SelectAlbum, idx_album)
			if normalize(mb.GetResultData(MBE_AlbumGetAlbumName)) == normalize(album):
				try:
					return mb.GetResultData(MBE_AlbumGetAmazonAsin)
				except musicbrainz.MusicBrainzError:
					pass
			mb.Select(MBS_Back)
		mb.Select(MBS_Back)

def download_cover(dirname, asin, verbose=False, size='medium'):
	url = AMAZON_URL % (str(asin), dict(AMAZON_PICTURE_SIZES)[size])
	filename = os.path.join(dirname, url.split('/')[-1])

	response = urllib2.urlopen(url)
	fd = open(filename, 'wb')
	fd.write(response.read())
	response.close()
	fd.close()

	if verbose:
		print "Downloaded '%s' and saved as '%s'." % (url, filename)

def process_collection(directory, verbose=False, size='medium'):
	# Initialize libmagic for mime type lookup.
	m = magic.open(magic.MAGIC_MIME)
	m.load()

	for dirpath, dirnames, filenames in os.walk(directory):
		# Skip directories which contains already an image.
		if any(m.file(os.path.join(dirpath, f)) in IMAGE_MIME_TYPES for f in filenames):
			continue

		for filename in filenames:
			try:
				t = tagpy.FileRef(os.path.join(dirpath, filename)).tag()
			except ValueError:
				# Try the next file if this file isn't readable by taglib.
				continue

			# If artist and album is given, get the ASIN from musicbrainz and
			# download the cover from Amazon. 
			if t.artist and t.album:
				asin = get_ASIN(t.artist, t.album)
				if asin is not None:
					download_cover(dirpath, asin, verbose, size)
					break

	# Close libmagic.
	m.close()

if __name__ == '__main__':
	usage = 'Usage: %prog <directory>'
	parser = OptionParser(usage)
	parser.add_option('-q', '--quiet', action='store_false', dest='verbose',
		default=True, help="Don't print status messages.") 
	parser.add_option('-s', '--size', type='choice', dest='size',
		choices=[x[0] for x in AMAZON_PICTURE_SIZES], default='medium',
		help='The size of the downloaded cover images.')

	options, args = parser.parse_args()
	if len(args) != 1:
		parser.error('incorrect number of arguments')

	process_collection(args[0], options.verbose, options.size)
