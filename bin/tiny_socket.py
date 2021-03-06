# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import socket
import cPickle
import cStringIO
import sys
import exceptions
import options

DNS_CACHE = {}

# disable Nagle problem.
# -> http://www.cmlenz.net/archives/2008/03/python-httplib-performance-problems
class NoNagleSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        super(NoNagleSocket, self).__init__(*args, **kwargs)
        self.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

socket.socket = NoNagleSocket


class Myexception(Exception):
    def __init__(self, faultCode, faultString):
        self.faultCode = faultCode
        self.faultString = faultString
        self.args = (faultCode, faultString)

# Safety class instance loader for unpickling.
# Inspired by http://nadiana.com/python-pickle-insecure#How_to_Make_Unpickling_Safer
EXCEPTION_CLASSES = [x for x in dir(exceptions) if type(getattr(exceptions,x)) == type]
SAFE_CLASSES = { 'exceptions' : EXCEPTION_CLASSES }
def find_global(module, name):
    if module not in SAFE_CLASSES or name not in SAFE_CLASSES[module]:
        raise cPickle.UnpicklingError('Attempting to unpickle unsafe module %s.%s' % (module,name))
    __import__(module)
    mod = sys.modules[module]
    return getattr(mod, name)

class mysocket:
    def __init__(self, sock=None):
        if sock is None:
            self.sock = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
        self.sock.settimeout(int(options.options['client.timeout']))

    def connect(self, host, port=False):
        if not port:
            protocol, buf = host.split('//')
            host, port = buf.split(':')
        if host in DNS_CACHE:
            host = DNS_CACHE[host]
        self.sock.connect((host, int(port)))
        DNS_CACHE[host], port = self.sock.getpeername()

    def disconnect(self):
        # on Mac, the connection is automatically shutdown when the server disconnect.
        # see http://bugs.python.org/issue4397
        if sys.platform != 'darwin':
            self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()

    def mysend(self, msg, exception=False, traceback=None):
        msg = cPickle.dumps([msg,traceback])
        self.sock.sendall('%8d%s%s' % (len(msg), exception and "1" or "0", msg))

    def myreceive(self):
        def read(socket, size):
            buf=''
            while len(buf) < size:
                chunk = self.sock.recv(size - len(buf))
                if chunk == '':
                    raise RuntimeError, "socket connection broken"
                buf += chunk
            return buf

        size = int(read(self.sock, 8))
        buf = read(self.sock, 1)
        exception = buf != '0' and buf or False
        buf = read(self.sock, size)
        msgio = cStringIO.StringIO(buf)
        unpickler = cPickle.Unpickler(msgio)
        unpickler.find_global = find_global
        res = unpickler.load()

        if isinstance(res[0],Exception):
            if exception:
                raise Myexception(str(res[0]), str(res[1]))
            raise res[0]
        else:
            return res[0]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

