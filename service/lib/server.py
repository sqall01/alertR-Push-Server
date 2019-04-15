#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: https://h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

import os
import json
from .storage import Mysql
from .globalData import ErrorCodes, AclCodes
from .googlePush import GoogleFirebase

BUFSIZE = 4096


# This class handles the communication with the incoming client connection.
class ClientCommunication:

    def __init__(self, socket, client_addr, client_port, global_data):
        self.socket = socket
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
            self.socket.send(json.dumps(message).encode('ascii'))
        except:
            pass

    def handle_communication(self):

        self.socket.settimeout(self.server_receive_timeout)

        # Get message from client.
        message = {}
        data = None
        try:
            data = self.socket.recv(BUFSIZE)
            message = json.loads(data.decode("ascii"))
        except:
            self.logger.exception("[%s]: Receiving data " % self.file_name +
                                  "failed (%s:%s)." % (self.client_addr, self.client_port))
            if data is not None:
                self.logger.debug("[%s]: Received data: %s" % (self.file_name, data.decode("ascii")))
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
                              "and server has '%.3f' (%s:%s)" %
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

        self.logger.info("[%s]: Successfully authenticated %s (%s:%s)." %
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
        firebase = GoogleFirebase(self.global_data, self.storage, username, self.client_addr, self.client_port)
        error = firebase.send_notification(channel, notification_data)
        if error != ErrorCodes.NO_ERROR:
            self._send_error(error)
            return

        # Add data to the statistics table.
        if self.statistics_life_span != 0:
            error = self.storage.add_send_statistic(username, self.client_addr, channel)
            if error != ErrorCodes.NO_ERROR:
                self.logger.error("[%s]: Not able to add send statistics data (%s:%s)." %
                                  (self.file_name, self.client_addr, self.client_port))

        # Send success back.
        try:
            message = {"Code": ErrorCodes.NO_ERROR}
            self.socket.send(json.dumps(message).encode('ascii'))
        except:
            pass
