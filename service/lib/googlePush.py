#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: http://blog.h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

import socket
import ssl
import http.client
import json
import os
import requests
from .globalData import ErrorCodes


class GoogleFirebase:

    def __init__(self, global_data, storage, username, client_addr, client_port):
        self.client_addr = client_addr
        self.client_port = client_port
        self.username = username
        self.storage = storage

        # File name of this file (used for logging).
        self.file_name = os.path.basename(__file__)

        # Get global configured data.
        self.global_data = global_data
        self.logger = self.global_data.logger
        self.google_firebase_url = self.global_data.google_firebase_url
        self.google_auth_key = self.global_data.google_auth_key

    def _send_message(self, message):

        # Build message header.
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.google_auth_key
        }

        # Send message to google service.
        r = None
        try:
            r = requests.post(self.google_firebase_url,
                              verify=True,
                              data=json.dumps(message),
                              headers=headers)

        except Exception as e:
            self.logger.exception("[%s]: Sending message to google service " % self.file_name +
                                  "failed (%s:%d)." % (self.client_addr, self.client_port))
            return ErrorCodes.GOOGLE_CONNECTION

        # Check if sending message was successful.
        status = r.status_code
        recv_string = r.text
        if status == 200:
            self.logger.debug("[%s]: Sending message to google service " % self.file_name +
                              "successful (%s:%d)." % (self.client_addr, self.client_port))
            return ErrorCodes.NO_ERROR

        self.logger.error("[%s]: Sending message to google service " % self.file_name +
                          "failed (%s:%d)." % (self.client_addr, self.client_port))

        # Check if we do know the received error.
        if status == 400:
            try:
                recv_data = json.loads(recv_string)
                if recv_data["error"] == "MessageTooBig":
                    return ErrorCodes.GOOGLE_MSG_TOO_LARGE
            except Exception as e:
                pass

        elif status == 401:
            return ErrorCodes.GOOGLE_AUTH

        self.logger.error("[%s]: Returned error unknown: %d %s " % (self.file_name, status, recv_string))
        return ErrorCodes.GOOGLE_UNKNOWN

    # Function that sends the received data directly via Google Firebase.
    def _send_data_direct(self, channel, data):

        # Build message body.
        payload = {"payload": data}

        message = {
            "to": "/topics/" + channel,
            "data": payload,
            "priority": "high"
        }

        self.logger.debug("[%s]: Sending message directly to google service " % self.file_name +
                          "(%s:%d)." % (self.client_addr, self.client_port))

        return self._send_message(message)

    # Function that sends an id via Google Firebase and holds the data in order
    # to have the client fetching the data.
    def _send_data_indirect(self, channel, data):

        data_id, error = self.storage.insert_push_data(self.username, data, self.logger)
        if error != ErrorCodes.NO_ERROR:
            return error

        # Build message body.
        payload = {"payload": "",
                   "data_id": data_id}

        message = {
            "to": "/topics/" + channel,
            "data": payload,
            "priority": "high"
        }

        self.logger.debug("[%s]: Sending message with data id '%s' to google service " % (self.file_name, data_id) +
                          "(%s:%d)." % (self.client_addr, self.client_port))

        return self._send_message(message)

    # Sends push message via Google Firebase.
    def send_notification(self, channel, data):

        # Build message body.
        payload = {"payload": data}

        # Check if message is too large (2039 tested empirically).
        if len(json.dumps(payload)) >= 2039:
            return self._send_data_indirect(channel, data)

        # Payload is small enough to be sent directly via Google Firebase.
        else:
            return self._send_data_direct(channel, data)
