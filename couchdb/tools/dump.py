#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2007-2009 Christopher Lenz
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

"""Utility for dumping a snapshot of a CouchDB database to a multipart MIME
file.
"""

from __future__ import print_function
from base64 import b64decode
from optparse import OptionParser
import sys

from couchdb import __version__ as VERSION
from couchdb import json
from couchdb.client import Database
from couchdb.multipart import write_multipart

BULK_SIZE = 1000

def dump_docs(envelope, db, docs):
    for doc in docs:

        print('Dumping document %r' % doc.id, file=sys.stderr)
        attachments = doc.pop('_attachments', {})
        jsondoc = json.encode(doc)

        if attachments:
            open_envelope = False
            for name, info in attachments.items():

                content_type = info.get('content_type')
                if content_type is None: # CouchDB < 0.8
                    content_type = info.get('content-type')

                if 'data' not in info:
                    attachment = db.get_attachment(doc, name)
                    # In case the attachment is not in the db
                    if attachment is None:
                        data = {}
                        print('Missing attachment')
                    else:
                        data = attachment.read()
                else:
                    try:
                        data = b64decode(info['data'])
                    except TypeError as e:
                        print('Could not decode attachment')
                        data = {}

                if data and content_type:
                    if not open_envelope:
                        parts = envelope.open({
                            'Content-ID': doc.id,
                            'ETag': '"%s"' % doc.rev
                        })
                        parts.add('application/json', jsondoc)
                        open_envelope = True
                    parts.add(content_type, data, {'Content-ID': name})

            parts.close()

        else:
            envelope.add('application/json', jsondoc, {
                'Content-ID': doc.id,
                'ETag': '"%s"' % doc.rev
            })

def dump_db(dburl, username=None, password=None, boundary=None,
            output=None, bulk_size=BULK_SIZE):

    if output is None:
        output = sys.stdout if sys.version_info[0] < 3 else sys.stdout.buffer

    db = Database(dburl)
    if username is not None and password is not None:
        db.resource.credentials = username, password

    envelope = write_multipart(output, boundary=boundary)
    start, num = 0, db.info()['doc_count']
    while start < num:
        opts = {'limit': bulk_size, 'skip': start, 'include_docs': True}
        docs = (row.doc for row in db.view('_all_docs', **opts))
        dump_docs(envelope, db, docs)
        start += bulk_size

    envelope.close()


def main():
    parser = OptionParser(usage='%prog [options] dburl', version=VERSION)
    parser.add_option('--json-module', action='store', dest='json_module',
                      help='the JSON module to use ("simplejson", "cjson", '
                            'or "json" are supported)')
    parser.add_option('-u', '--username', action='store', dest='username',
                      help='the username to use for authentication')
    parser.add_option('-p', '--password', action='store', dest='password',
                      help='the password to use for authentication')
    parser.add_option('-b', '--bulk-size', action='store', dest='bulk_size',
                      type='int', default=BULK_SIZE,
                      help='number of docs retrieved from database')
    parser.set_defaults()
    options, args = parser.parse_args()

    if len(args) != 1:
        return parser.error('incorrect number of arguments')

    if options.json_module:
        json.use(options.json_module)

    dump_db(args[0], username=options.username, password=options.password,
            bulk_size=options.bulk_size)


if __name__ == '__main__':
    main()
