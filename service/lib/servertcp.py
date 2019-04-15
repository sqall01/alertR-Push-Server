#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: https://h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

import os
import ssl
import socket
import socketserver
from .server import ClientCommunication


# This class is used for the forked tcp server and extends the constructor
# to pass the global configured data to all threads.
class ForkedTCPServer(socketserver.ForkingMixIn, socketserver.TCPServer):

    def __init__(self, global_data, server_address, request_handler_class):

        # Get reference to global data object.
        self.global_data = global_data

        socketserver.TCPServer.__init__(self, server_address, request_handler_class)


# This class is used for incoming client connections.
class ServerSession(socketserver.BaseRequestHandler):

    def __init__(self, request, client_address, server):

        # File name of this file (used for logging).
        self.file_name = os.path.basename(__file__)

        # ssl socket wrapper.
        self.ssl_socket = None

        # Instance that handles the communication with the client.
        self.client_comm = None

        # Get client ip address and port.
        self.client_addr = client_address[0]  # type: str
        self.client_port = str(client_address[1])  # type: str

        # Get reference to global data object.
        self.global_data = server.global_data
        self.logger = self.global_data.logger

        # Get server certificate/key file.
        self.server_cert_file = self.global_data.server_cert_file
        self.server_key_file = self.global_data.server_key_file

        socketserver.BaseRequestHandler.__init__(self, request, client_address, server)

    def handle(self):

        self.logger.info("[%s]: Client connected (%s:%s)." % (self.file_name, self.client_addr, self.client_port))

        # Try to initiate ssl with client.
        try:
            self.ssl_socket = ssl.wrap_socket(self.request,
                                              server_side=True,
                                              certfile=self.server_cert_file,
                                              keyfile=self.server_key_file,
                                              ssl_version=ssl.PROTOCOL_TLSv1)

        except:
            self.logger.exception("[%s]: Unable to initialize SSL " % self.file_name +
                                  "connection (%s:%s)." % (self.client_addr, self.client_port))
            return

        # Give incoming connection to client communication handler.
        self.client_comm = ClientCommunication(self.ssl_socket, self.client_addr, self.client_port, self.global_data)
        self.client_comm.handle_communication()

        # Close ssl connection gracefully.
        try:
            # self.sslSocket.shutdown(socket.SHUT_RDWR)
            self.ssl_socket.close()
        except:
            self.logger.exception("[%s]: Unable to close SSL " % self.file_name +
                                  "connection gracefully with %s:%s." % (self.client_addr, self.client_port))

        self.logger.info("[%s]: Client disconnected (%s:%s)." % (self.file_name, self.client_addr, self.client_port))

    def close_connection(self):
        self.logger.info("[%s]: Closing connection to " % self.file_name +
                         "client (%s:%s)." % (self.client_addr, self.client_port))
        try:
            self.ssl_socket.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            self.ssl_socket.close()
        except:
            pass
