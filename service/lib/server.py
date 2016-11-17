#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: http://blog.h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Public License, version 2.

import ssl
import socket
import socketserver
import os
import json
from .storage import Mysql
from .globalData import ErrorCodes, AclCodes
from .googlePush import GoogleFirebase

BUFSIZE = 4096


# This class handles the communication with the incoming client connection.
class ClientCommunication:

    def __init__(self, ssl_socket, client_addr, client_port, global_data):
        self.ssl_socket = ssl_socket
        self.client_addr = client_addr
        self.client_port = client_port

        # File name of this file (used for logging).
        self.file_name = os.path.basename(__file__)

        # Get global configured data.
        self.global_data = global_data
        self.logger = self.global_data.logger
        self.server_receive_timeout = self.global_data.server_receive_timeout
        self.statistics_life_span = self.global_data.statistics_life_span
        self.server_version = self.global_data.version
        self.notification_channel = self.global_data.notification_channel

        # Set up storage interface.
        self.storage = Mysql(self.global_data)

    def _check_message_sanity(self, message):

        # Check if message has all needed fields.
        fields = ["username", "password", "channel", "data", "version"]
        for field in fields:
            if field not in message.keys():
                return ErrorCodes.ILLEGAL_MSG_ERROR

        # Check all string fields have the correct type.
        fields_str = ["username", "password", "channel", "data"]
        for field in fields_str:
            if not isinstance(message[field], str):
                return ErrorCodes.ILLEGAL_MSG_ERROR

        # Check all float fields have the correct type.
        fields_float = ["version"]
        for field in fields_float:
            if not isinstance(message[field], float):
                return ErrorCodes.ILLEGAL_MSG_ERROR

        return ErrorCodes.NO_ERROR

    # Send back the occured error code.
    def _send_error(self, error_code):
        try:
            message = {"Code": error_code}
            if error_code == ErrorCodes.VERSION_MISSMATCH:
                message["version"] = self.server_version
            self.ssl_socket.send(json.dumps(message).encode('ascii'))
        except Exception as e:
            pass

    def handle_communication(self):

        self.ssl_socket.settimeout(self.server_receive_timeout)

        # Get message from client.
        message = {}
        try:
            data = self.ssl_socket.recv(BUFSIZE)
            message = json.loads(data.decode("ascii"))
        except Exception as e:
            self.logger.exception("[%s]: Receiving data " % self.file_name +
                                  "failed (%s:%d)." % (self.client_addr, self.client_port))
            return

        # Check the sanity of the message.
        error = self._check_message_sanity(message)
        if error != ErrorCodes.NO_ERROR:
            self._send_error(error)
            return

        # Verify protocol version of client.
        client_version = message["version"]
        if int(self.server_version * 10) != int(client_version * 10):
            self.logger.error("[%s]: Protocol version not compatible. " % self.file_name +
                              "Client has protocol version: '%.3f' " % client_version +
					          "and server has '%.3f' (%s:%d)" %
                              (self.server_version, self.client_addr, self.client_port))
            self._send_error(ErrorCodes.VERSION_MISSMATCH)
            return

        # Authenticate the user.
        username = message["username"]
        password = message["password"]
        result, error = self.storage.authenticate_user(username, password, self.client_addr)

        # If an error occured, send an error message back to the client.
        if error != ErrorCodes.NO_ERROR:
            self._send_error(error)
            return

        # Also regard a failed authentication as an error.
        elif not result:
            self._send_error(ErrorCodes.AUTH_ERROR)
            return

        self.logger.info("[%s]: Successfully authenticated %s (%s:%d)." %
                         (self.file_name, username, self.client_addr, self.client_port))

        # Get acl of user.
        acl, error = self.storage.get_acl(username)
        if error != ErrorCodes.NO_ERROR:
            self._send_error(error)
            return

        # Check if channel is the notification channel.
        # Only uses with the correct permission are allowed to send to this channel.
        channel = message["channel"]
        if channel.lower() == self.notification_channel.lower():
            if not AclCodes.NOTIFICATION_CHANNEL in acl:
                self._send_error(ErrorCodes.NO_NOTIFICATION_PERMISSION)
                return
            channel = self.notification_channel

        # Send push notification to google service.
        notification_data = message["data"]
        firebase = GoogleFirebase(self.global_data, self.client_addr, self.client_port)
        error = firebase.send_notification(channel, notification_data)
        if error != ErrorCodes.NO_ERROR:
            self._send_error(error)
            return

        # Add data to the statistics table.
        if self.statistics_life_span != 0:
            error = self.storage.add_send_statistic(username, self.client_addr, channel)
            if error != ErrorCodes.NO_ERROR:
                self.logger.error("[%s]: Not able to add send statistics data (%s:%d)." %
                                  (self.file_name, self.client_addr, self.client_port))

        # Send success back.
        try:
            message = {"Code": ErrorCodes.NO_ERROR}
            self.ssl_socket.send(json.dumps(message).encode('ascii'))
        except Exception as e:
            pass


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
        self.client_addr = client_address[0]
        self.client_port = client_address[1]

        # Get reference to global data object.
        self.global_data = server.global_data
        self.logger = self.global_data.logger

        # Get server certificate/key file.
        self.server_cert_file = self.global_data.server_cert_file
        self.server_key_file = self.global_data.server_key_file

        socketserver.BaseRequestHandler.__init__(self, request, client_address, server)

    def handle(self):

        self.logger.info("[%s]: Client connected (%s:%d)." % (self.file_name, self.client_addr, self.client_port))

        # Try to initiate ssl with client.
        try:
            self.ssl_socket = ssl.wrap_socket(self.request,
                                              server_side=True,
                                              certfile=self.server_cert_file,
                                              keyfile=self.server_key_file,
                                              ssl_version=ssl.PROTOCOL_TLSv1)

        except Exception as e:
            self.logger.exception("[%s]: Unable to initialize SSL " % self.file_name +
                                  "connection (%s:%d)." % (self.client_addr, self.client_port))
            return

        # Give incoming connection to client communication handler.
        self.client_comm = ClientCommunication(self.ssl_socket, self.client_addr, self.client_port, self.global_data)
        self.client_comm.handle_communication()

        # Close ssl connection gracefully.
        try:
            # self.sslSocket.shutdown(socket.SHUT_RDWR)
            self.ssl_socket.close()
        except Exception as e:
            self.logger.exception("[%s]: Unable to close SSL " % self.file_name +
                                  "connection gracefully with %s:%d." % (self.client_addr, self.client_port))

        self.logger.info("[%s]: Client disconnected (%s:%d)." % (self.file_name, self.client_addr, self.client_port))

    def close_connection(self):
        self.logger.info("[%s]: Closing connection to " % self.file_name +
                         "client (%s:%d)." % (self.client_addr, self.client_port))
        try:
            self.ssl_socket.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            self.ssl_socket.close()
        except:
            pass
