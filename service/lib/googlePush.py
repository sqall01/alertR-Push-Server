#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: http://blog.h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Public License, version 2.

import socket
import ssl
import http.client
import json
import os
from .globalData import ErrorCodes


# HTTPSConnection like class that verifies server certificates.
class VerifiedHTTPSConnection(http.client.HTTPSConnection):
    # needs socket and ssl lib
    def __init__(self, host, port=None, servercert_file=None,
                 key_file=None, cert_file=None, strict=None,
                 timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
        http.client.HTTPSConnection.__init__(self,
                                             host,
                                             port,
                                             key_file,
                                             cert_file,
                                             strict,
                                             timeout)
        self.servercert_file = servercert_file

    # overwrites the original version of httplib (python 2.6)
    def connect(self):
        """Connect to a host on a given (SSL) port."""

        sock = socket.create_connection((self.host, self.port), self.timeout)
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()

        # the only thing that has to be changed in the original function from
        # httplib (tell ssl.wrap_socket to verify server certificate)
        self.sock = ssl.wrap_socket(sock,
                                    self.key_file,
                                    self.cert_file,
                                    cert_reqs=ssl.CERT_REQUIRED,
                                    ca_certs=self.servercert_file)


class GoogleFirebase:

    def __init__(self, global_data, client_addr, client_port):
        self.client_addr = client_addr
        self.client_port = client_port

        # File name of this file (used for logging).
        self.file_name = os.path.basename(__file__)

        # Get global configured data.
        self.global_data = global_data
        self.logger = self.global_data.logger
        self.google_cert_file = self.global_data.google_cert_file
        self.google_auth_key = self.global_data.google_auth_key

    def send_notification(self, channel, data):

        # Build message header.
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.google_auth_key
        }

        # Build message body.
        payload = {"payload": data}

        # Check if message is too large (2039 tested empirically).
        if len(json.dumps(payload)) >= 2039:
            self.logger.error("[%s]: Sending message to google service " % self.file_name +
                              "failed (%s:%d)." % (self.client_addr, self.client_port))
            return ErrorCodes.GOOGLE_MSG_TOO_LARGE

        message = {
            "to": "/topics/" + channel,
            "data": payload,
            "priority": "high"
        }

        # Send message to google service.
        response = None
        try:
            conn = VerifiedHTTPSConnection("fcm.googleapis.com", 443, self.google_cert_file)
            conn.request("POST", "/fcm/send", json.dumps(message), headers)
            response = conn.getresponse()
        except Exception as e:
            self.logger.exception("[%s]: Sending message to google service " % self.file_name +
                                  "failed (%s:%d)." % (self.client_addr, self.client_port))
            return ErrorCodes.GOOGLE_CONNECTION

        # Check if sending message was successful.
        status = response.status
        recv_string = response.read()
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
