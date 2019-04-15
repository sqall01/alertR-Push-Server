#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: https://h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

import os
import threading
import socketserver
from .server import ClientCommunication


# This class is used for the forked tcp server and extends the constructor
# to pass the global configured data to all threads.
class ForkedUnixServer(socketserver.ForkingMixIn, socketserver.UnixStreamServer):

    def __init__(self, global_data, server_address, request_handler_class):

        # Get reference to global data object.
        self.global_data = global_data

        socketserver.UnixStreamServer.__init__(self, server_address, request_handler_class)


# This class is used for incoming client connections.
class ServerSessionNoTLS(socketserver.BaseRequestHandler):

    def __init__(self, request, client_address, server):

        # File name of this file (used for logging).
        self.file_name = os.path.basename(__file__)

        # socket
        self.socket = request

        # Instance that handles the communication with the client.
        self.client_comm = None

        # Get client ip address and port.
        self.client_addr = "127.0.0.1"
        self.client_port = "unixsock"

        # Get reference to global data object.
        self.global_data = server.global_data
        self.logger = self.global_data.logger

        socketserver.BaseRequestHandler.__init__(self, request, client_address, server)

    def handle(self):

        self.logger.info("[%s]: Client connected (%s:%s)." % (self.file_name, self.client_addr, self.client_port))

        # Give incoming connection to client communication handler.
        self.client_comm = ClientCommunication(self.socket, self.client_addr, self.client_port, self.global_data)
        self.client_comm.handle_communication()

        # Close connection gracefully.
        try:
            self.socket.close()
        except:
            self.logger.exception("[%s]: Unable to close " % self.file_name +
                                  "connection gracefully with %s:%s." % (self.client_addr, self.client_port))

        self.logger.info("[%s]: Client disconnected (%s:%s)." % (self.file_name, self.client_addr, self.client_port))

    def close_connection(self):
        self.logger.info("[%s]: Closing connection to " % self.file_name +
                         "client (%s:%s)." % (self.client_addr, self.client_port))
        try:
            self.socket.close()
        except:
            pass


class UnixServerWrapper(threading.Thread):

    def __init__(self, unixserver, logger):
        threading.Thread.__init__(self)

        # File name of this file (used for logging).
        self.file_name = os.path.basename(__file__)

        self.unixserver = unixserver
        self.logger = logger

    def run(self):
        self.logger.info("[%s] Unix socket server started." % self.file_name)
        self.unixserver.serve_forever()
        self.unixserver.server_close()
        self.logger.info("[%s] Unix socket server stopped." % self.file_name)
