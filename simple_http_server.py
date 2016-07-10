"""Simple HTTP Server.

This module builds on BaseHTTPServer by implementing the standard GET
and HEAD requests in a fairly straightforward manner.
http://opensource.apple.com//source/python/python-3/python/Lib/SimpleHTTPServer.py?txt
"""


import os
import posixpath
import BaseHTTPServer
import urllib
import cgi
import shutil
import mimetypes
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
import base64
import time
import re
import uuid
import hashlib
import sys
import threading

import logging as log

__version__ = "0.6"
__author__ = "apple"
__contributor__ = "bones7456" # Post Uploads
__contributor__ = "wonjohnchoi" # Adding Basic Auth
__contributor__ = "zph" # Rebasing script from Apple, merging Post and Basic Auth, +self-destruct, +auto-gen passwords


__all__ = ["SimpleHTTPRequestHandler"]

class HTTPConfig():
    def __init__(self):
        self.host = '127.0.0.1'
        self.base_url = os.getenv('BASE_URL', 'public/')
        self.port = int(os.getenv('PORT', '5000'))
        self.username = os.getenv('BASIC_AUTH_USER', 'admin')
        self.password = os.getenv('BASIC_AUTH_PASSWORD', os.urandom(20).encode('hex'))
        self.self_destruct_delay = os.getenv('SELF_DESTRUCT_DELAY', 600)

config = HTTPConfig()

class SimpleHTTPRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """Simple HTTP request handler with GET and HEAD commands.

    This serves files from the current directory and any of its
    subdirectories.  It assumes that all files are plain text files
    unless they have the extension ".html" in which case it assumes
    they are HTML files.

    The GET and HEAD requests are identical except that the HEAD
    request omits the actual contents of the file.

    """

    server_version = "SimpleHTTP/" + __version__

    extensions_map = mimetypes.types_map.copy()
    extensions_map.update({
        '': 'application/octet-stream', # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        })

    def auth_header(self):
        return self.headers.getheader('Authorization')

    def decode_auth_header(self):
        auth_header = self.auth_header()
        if auth_header:
            px = re.split('\s+', auth_header)
            return base64.b64decode(px[1])
        else:
            return ''

    def auth_to_base64(self, u, p):
        return base64.b64encode('{}:{}'.format(u, p))

    def is_authenticated(self):
        h = self.auth_header()
        expected = 'Basic ' + self.auth_to_base64(config.username, config.password)
        return h and h == expected

    def authenticate(self):
        if self.is_authenticated():
            return True
        else:
            log.info('Auth failure: "{}"'.format(self.decode_auth_header()))
            time.sleep(2)
            self.do_AUTHHEAD()
            return False

    def send_head(self):
        """Common code for GET and HEAD commands.

        This sends the response code and MIME headers.

        Return value is either a file object (which has to be copied
        to the outputfile by the caller unless the command was HEAD,
        and must be closed by the caller under all circumstances), or
        None, in which case the caller has nothing further to do.

        """
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                return self.list_directory(path)
        ctype = self.guess_type(path)
        if ctype.startswith('text/'):
            mode = 'r'
        else:
            mode = 'rb'
        try:
            f = open(path, mode)
        except IOError:
            self.send_error(404, "File not found")
            return None
        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.end_headers()
        return f

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html).

        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().

        """

        try:
            list = os.listdir(os.path.join(path, config.base_url))
        except os.error:
            self.send_error(404, "No permission to list directory")
            return None
        list.sort(lambda a, b: cmp(a.lower(), b.lower()))
        f = StringIO()
        header = """
        <title>Directory listing for {path}</title>
        <h2>Directory listing for {path}</h2>
        <li><a href="{usage_route}">{usage}</a>
        <hr>\n<ul>
        """.format(**{'path': self.path,
                      'usage_route': "/usage.txt",
                      'usage': 'Usage Instructions'})
        body = ""
        for name in list:
            fullname = os.path.join(path, config.base_url, name)
            displayname = linkname = name = cgi.escape(name)
            # Append / for directories or @ for symbolic links
            if os.path.isdir(fullname):
                displayname = name + "/"
                linkname = name + "/"
            if os.path.islink(fullname):
                displayname = name + "@"
                # Note: a link to a directory displays with @ and links with /
            body += '<li><a href="{}">{}</a>'.format(linkname, displayname)
        closing = "</ul><hr>"
        f.writelines((header, body, closing))
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        return f

    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax.

        Components that mean special things to the local file system
        (e.g. drive or directory names) are ignored.  (XXX They should
        probably be diagnosed.)

        """
        path = posixpath.normpath(urllib.unquote(path))
        words = path.split('/')
        words = filter(None, words)
        if path == "/":
            path = os.getcwd()
        else:
            path = os.path.join(os.getcwd(), config.base_url)

        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir): continue
            path = os.path.join(path, word)
        return path

    def copyfile(self, source, outputfile):
        """Copy all data between two file objects.

        The SOURCE argument is a file object open for reading
        (or anything with a read() method) and the DESTINATION
        argument is a file object open for writing (or
        anything with a write() method).

        The only reason for overriding this would be to change
        the block size or perhaps to replace newlines by CRLF
        -- note however that this the default server uses this
        to copy binary data as well.

        """
        shutil.copyfileobj(source, outputfile)

    def guess_type(self, path):
        """Guess the type of a file.

        Argument is a PATH (a filename).

        Return value is a string of the form type/subtype,
        usable for a MIME Content-type header.

        The default implementation looks the file's extension
        up in the table self.extensions_map, using text/plain
        as a default; however it would be permissible (if
        slow) to look inside the data to make a better guess.

        """

        base, ext = posixpath.splitext(path)
        if self.extensions_map.has_key(ext):
            return self.extensions_map[ext]
        ext = ext.lower()
        if self.extensions_map.has_key(ext):
            return self.extensions_map[ext]
        else:
            return self.extensions_map['']

    def bool_to_human(self, b):
        if b:
            'Success'
        else:
            'Failure'

    def deal_post_data(self):
        boundary = self.headers.plisttext.split("=")[1]
        remainbytes = int(self.headers['content-length'])
        line = self.rfile.readline()
        remainbytes -= len(line)
        if not boundary in line:
            return (False, "Content does NOT begin with boundary", {})
        line = self.rfile.readline()
        remainbytes -= len(line)
        fn = re.findall(r'Content-Disposition.*name="file"; filename="(.*)"', line)
        if not fn:
            fn = (uuid.uuid4())
        path = self.translate_path(self.path)
        original_filename = fn[0]
        fn = os.path.join(path, config.base_url, fn[0])
        try:
            out = open(fn, 'wb')
        except IOError:
            return (False, "Can't create file to write, do you have permission to write?", {})
        line = self.rfile.readline()
        remainbytes -= len(line)
        line = self.rfile.readline()
        remainbytes -= len(line)

        preline = self.rfile.readline()
        remainbytes -= len(preline)
        while remainbytes > 0:
            line = self.rfile.readline()
            remainbytes -= len(line)
            if boundary in line:
                preline = preline[0:-1]
                if preline.endswith('\r'):
                    preline = preline[0:-1]
                out.write(preline)
                out.close()
                # DO MD5
                md5 = md5Checksum(fn)
                meta = {'filename': original_filename,
                        'md5': md5,
                        'path': fn}
                msg = "File '{filename}' with MD5 {md5} uploaded!".format(**meta)
                log.info(msg)
                return (True,
                        msg,
                        meta)

            else:
                out.write(preline)
                preline = line
        return (False, "Unexpected end of data.")

    def do_AUTHHEAD(self):
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"Test\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        """Serve a GET request."""
        if not self.authenticate():
            return
        f = self.send_head()
        if f:
            self.copyfile(f, self.wfile)
            f.close()

    def do_HEAD(self):
        """Serve a HEAD request."""
        if not self.authenticate():
            return
        f = self.send_head()
        if f:
            f.close()

    def do_POST(self):
        if not self.authenticate():
            return
        """Serve a POST request."""
        r, info, meta = self.deal_post_data()
        res = 'Success' if r else 'Failure'
        log.info("Upload {} {} by: {}".format(res, info, self.client_address))
        f = StringIO()
        ref = self.headers.get('referer', 'None')

        response = {'result': res,
                    'referer': ref,
                    'info': info}
        result = """
        <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
        <html><title>Upload Result Page</title>
        <body><h2>Upload Result Page</h2>
        <hr>
        <strong>{result}:</strong>
        {info}
        <br><a href="{referer}">back</a>"
        </body></html>
        """
        f.write(result.format(**response))
        length = f.tell()
        f.seek(0)
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        if f:
            self.copyfile(f, self.wfile)
            f.close()


def md5Checksum(filePath):
    # CREDIT: http://joelverhagen.com/blog/2011/02/md5-hash-of-file-in-python/
    with open(filePath, 'rb') as f:
        m = hashlib.md5()
        while True:
            data = f.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


class ErrorMissingOutputDir(Exception):
    def __init__(self, out=''):
        self.out = out
        self.msg = "Error: unable to find {}. Terminating server.".format(out)

def self_destruct(shutdown):
    log.fatal("Time ran out for server. Killing process for security.")
    shutdown()

def ensure_output_path(c):
    output_dir = os.path.join(os.getcwd(), c.base_url)
    try:
        if not os.path.exists(output_dir):
            raise ErrorMissingOutputDir(output_dir)
    except ErrorMissingOutputDir as e:
        log.fatal(e.msg)
        sys.exit(1)

def main(HandlerClass=SimpleHTTPRequestHandler,
         ServerClass=BaseHTTPServer.HTTPServer):

    log.basicConfig(format='%(asctime)s %(message)s', level=log.DEBUG)

    c = config
    log.info('listening on {}:{}'.format(c.host, c.port))
    log.info("Auth {}:{}".format(c.username, c.password))
    log.info("Server will shutdown in {} seconds(s)".format(c.self_destruct_delay))
    log.info('Starting server, use <Ctrl-C> to stop')

    ensure_output_path(c)
    server = ServerClass((c.host, c.port), HandlerClass)

    threading.Timer(c.self_destruct_delay, self_destruct, [server.shutdown]).start()
    server.serve_forever()


if __name__ == '__main__':
    main()
