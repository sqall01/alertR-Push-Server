#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: http://blog.h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

from lib import ServerSession, ForkedTCPServer
from lib import GlobalData
from lib import Mysql
from lib import DatabaseCleaner
import time
import xml.etree.ElementTree
import os
import sys
import logging
import signal
import _thread

# alertR Push Notification Server needs the following additional python3 packages:
# - bcrypt
# - mysqlclient
#
# In order to install them on a Debian like machine please execute the following commands:
#
# apt-get install libmysqlclient-dev
# pip3 install bcrypt mysqlclient

# Global instances used to access it via terminate signal handler.
server = None
db_cleaner = None


# Function creates a path location for the given user input.
def make_path(input_location):
    # Do nothing if the given location is an absolute path.
    if input_location[0] == "/":
        return input_location
    # Replace ~ with the home directory.
    elif input_location[0] == "~":
        return os.environ["HOME"] + input_location[1:]
    # Assume we have a given relative path.
    return os.path.dirname(os.path.abspath(__file__)) + "/" + input_location


# Shutdown server gracefully.
def shutdown_server(server_obj):
    server_obj.shutdown()


# Signal handler to gracefully shutdown the server.
def sigterm_handler(signum, frame):
    if server:
        # Shutdown has to be done via another thread. Otherwise a
        # deadlock will occur.
        _thread.start_new_thread(shutdown_server, (server,))

    if db_cleaner:
        db_cleaner.shutdown()

if __name__ == "__main__":

    # Register sigterm handler to gracefully shutdown the server.
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Generate object of the global needed data.
    global_data = GlobalData()

    file_name = os.path.basename(__file__)

    # Parse config file, get logfile configurations
    # and initialize logging
    try:
        configRoot = xml.etree.ElementTree.parse(global_data.config_file).getroot()

        global_data.logdir = make_path(str(configRoot.find("general").find("log").attrib["dir"]))

        # parse chosen log level
        temp_loglevel = str(configRoot.find("general").find("log").attrib["level"])
        temp_loglevel = temp_loglevel.upper()
        if temp_loglevel == "DEBUG":
            global_data.loglevel = logging.DEBUG
        elif temp_loglevel == "INFO":
            global_data.loglevel = logging.INFO
        elif temp_loglevel == "WARNING":
            global_data.loglevel = logging.WARNING
        elif temp_loglevel == "ERROR":
            global_data.loglevel = logging.ERROR
        elif temp_loglevel == "CRITICAL":
            global_data.loglevel = logging.CRITICAL
        else:
            raise ValueError("No valid log level in config file.")

        # initialize logging
        logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s",
                            datefmt="%m/%d/%Y %H:%M:%S",
                            filename=global_data.logdir + "/all.log",
                            level=global_data.loglevel)

        global_data.logger = logging.getLogger("server")
        fh = logging.FileHandler(global_data.logdir + "/server.log")
        fh.setLevel(global_data.loglevel)
        log_format = logging.Formatter("%(asctime)s %(levelname)s: %(message)s",
                                       "%m/%d/%Y %H:%M:%S")
        fh.setFormatter(log_format)
        global_data.logger.addHandler(fh)

    except Exception as e:
        print("Config could not be parsed.")
        print(e)
        sys.exit(1)

    # Parse the rest of the config with initialized logging.
    try:

        # Check if config and client version are compatible.
        version = float(configRoot.attrib["version"])
        if version != global_data.version:
            raise ValueError("Config version '%.3f' not " % version +
                             "compatible with client version '%.3f'." % global_data.version)

        # Get server configurations
        global_data.logger.debug("[%s]: Parsing server configuration." % file_name)
        global_data.server_cert_file = make_path(str(configRoot.find("general").find("server").attrib["certFile"]))
        global_data.server_key_file = make_path(str(configRoot.find("general").find("server").attrib["keyFile"]))
        port = int(configRoot.find("general").find("server").attrib["port"])

        if (not os.path.exists(global_data.server_cert_file) or
           not os.path.exists(global_data.server_key_file)):
            raise ValueError("Server certificate or key does not exist.")

        # Get bruteforce protection configuration.
        global_data.bf_fail_attempts_count = \
                        int(configRoot.find("general").find("server").attrib["bruteforceLoginAttempts"])
        global_data.bf_block_time = int(configRoot.find("general").find("server").attrib["bruteforceBlockTime"])

        # Get statistics configuration.
        global_data.statistics_life_span = int(configRoot.find("general").find("server").attrib["statisticsLifeSpan"])

        if global_data.statistics_life_span < 0:
            raise ValueError("Statistics life span is not valid.")

        # Get google firebase configuration.
        global_data.logger.debug("[%s]: Parsing google firebase configuration." % file_name)
        global_data.google_cert_file = make_path(str(configRoot.find("general").find("google").attrib["certFile"]))
        global_data.google_auth_key = str(configRoot.find("general").find("google").attrib["authKey"])

        if not os.path.exists(global_data.google_cert_file):
            raise ValueError("Google server certificate does not exist.")

        # Get mysql server configuration.
        global_data.logger.debug("[%s]: Parsing database configuration." % file_name)
        global_data.mysql_host = str(configRoot.find("storage").find("mysql").attrib["server"])
        global_data.mysql_port = int(configRoot.find("storage").find("mysql").attrib["port"])
        global_data.mysql_database = str(configRoot.find("storage").find("mysql").attrib["database"])
        global_data.mysql_username = str(configRoot.find("storage").find("mysql").attrib["username"])
        global_data.mysql_password = str(configRoot.find("storage").find("mysql").attrib["password"])
        global_data.mysql_connection_retries = int(configRoot.find("storage").find("mysql").attrib["connectionRetries"])

        global_data.logger.info("[%s]: Testing database configuration." % file_name)
        storage_test = Mysql(global_data)
        if not storage_test.connection_test():
            raise ValueError("Database settings test failed.")

    except:
        global_data.logger.exception("[%s]: Could not parse config." % file_name)
        sys.exit(1)

    # Start database cleaning thread.
    global_data.logger.info("[%s]: Starting database cleaning thread." % file_name)
    db_cleaner = DatabaseCleaner(global_data)
    db_cleaner.daemon = True
    db_cleaner.start()

    # Start server process.
    global_data.logger.info("[%s]: Starting server process." % file_name)
    while True:
        try:
            server = ForkedTCPServer(global_data, ("0.0.0.0", port), ServerSession)
            break
        except:
            global_data.logger.exception("[%s]: Starting server failed. " % file_name +
                                         "Try again in 5 seconds.")
            time.sleep(5)
    global_data.logger.info("[%s] Server started." % file_name)
    server.serve_forever()
    server.server_close()
    global_data.logger.info("[%s] Server stopped." % file_name)

    # Wait to ensure that every thread is stopped gracefully.
    time.sleep(5)
