#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: https://h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

import MySQLdb
import os
import time
import datetime
import bcrypt
from .globalData import ErrorCodes


# Class for using mysql as storage backend
class Mysql(object):

    def __init__(self, global_data):

        # File nme of this file (used for logging).
        self.file_name = os.path.basename(__file__)

        self.global_data = global_data
        self.logger = self.global_data.logger
        self.mysql_connection_retries = self.global_data.mysql_connection_retries

        # Needed mysql parameters.
        self.host = self.global_data.mysql_host
        self.port = self.global_data.mysql_port
        self.database = self.global_data.mysql_database
        self.username = self.global_data.mysql_username
        self.password = self.global_data.mysql_password

        # Bruteforce protection parameters.
        self.bf_fail_attempts_count = self.global_data.bf_fail_attempts_count
        self.bf_fail_attempts_timer = self.global_data.bf_fail_attempts_timer
        self.bf_block_time = self.global_data.bf_block_time

        self._cursor = None
        self._conn = None

    # Internal function that connects to the mysql server
    # (needed because direct changes to the database by another program
    # are not seen if the connection to the mysql server is kept alive)
    def _open_connection(self, logger=None):

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        current_try = 0
        while True:
            try:
                self._conn = MySQLdb.connect(host=self.host,
                                             port=self.port,
                                             user=self.username,
                                             passwd=self.password,
                                             db=self.database)

                self._cursor = self._conn.cursor()
                break

            except:

                # Re-throw the exception if we reached our retry limit.
                if current_try >= self.mysql_connection_retries:
                    raise

                current_try += 1
                logger.exception("[%s]: Not able to connect to the MySQL " % self.file_name +
                                 "server. Waiting before retrying (%d/%d)." %
                                 (current_try, self.mysql_connection_retries))

                time.sleep(5)

    # Internal function that closes the connection to the mysql server.
    def _close_connection(self):
        self._cursor.close()
        self._conn.close()
        self._cursor = None
        self._conn = None

    # Function to test the mysql credentials on startup.
    def connection_test(self):
        try:
            self._open_connection()
            self._close_connection()
        except:
            return False
        return True

    def _get_user_id(self, username, logger=None):

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        user_id = None
        try:
            self._cursor.execute("SELECT id FROM users WHERE email = %s AND active = 1", (username, ))

            result = self._cursor.fetchall()

            if len(result) != 1:
                return None, ErrorCodes.NO_ERROR

            user_id = result[0][0]

        except:
            logger.exception("[%s]: Not able to get user id." % self.file_name)

            return None, ErrorCodes.DATABASE_ERROR

        return user_id, ErrorCodes.NO_ERROR

    # Clean up bruteforce information tables.
    def _clean_up_bruteforce_tables(self, logger=None):

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        utc_timestamp = int(time.time())

        try:
            # Reset bruteforce entries that are not blocked anymore.
            self._cursor.execute("UPDATE bruteforce_info SET blocked_until = %s, counter = %s " +
                                 "WHERE blocked_until != 0 AND blocked_until < %s",
                                 (0, 0, utc_timestamp))

            # Reset bruteforce counter if last attempt is older than the given setting.
            self._cursor.execute("UPDATE bruteforce_info SET counter = %s WHERE last_attempt < %s",
                                 (0, utc_timestamp - self.bf_fail_attempts_timer))

            # Commit all changes.
            self._conn.commit()

        except:
            logger.exception("[%s]: Not able to clean up bruteforce tables." % self.file_name)

            return False, ErrorCodes.DATABASE_ERROR

        return True, ErrorCodes.NO_ERROR

    def _check_bruteforce(self, user_id, ip_addr, logger=None):

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        # Clean up bruteforce tables.
        result, error = self._clean_up_bruteforce_tables(logger)
        if not result:
            return result, error

        # Check if user id is blocked from the given ip address.
        try:
            self._cursor.execute("SELECT id FROM bruteforce_info " +
                                 "WHERE users_id = %s AND addr = %s AND blocked_until != 0",
                                 (user_id, ip_addr))

            result = self._cursor.fetchall()

            if len(result) != 0:
                return False, ErrorCodes.NO_ERROR

        except:
            logger.exception("[%s]: Not able to check bruteforce table." % self.file_name)

            return False, ErrorCodes.DATABASE_ERROR

        return True, ErrorCodes.NO_ERROR

    def authenticate_user(self, username, password, ip_addr, logger=None):

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        utc_timestamp = int(time.time())

        # Connect to the database.
        self._open_connection(logger)

        # Get user id for username.
        user_id, error = self._get_user_id(username, logger)
        if not user_id:
            return False, error

        # Check bruteforce protection for user.
        result, error = self._check_bruteforce(user_id, ip_addr, logger)
        if not result:
            logger.info("[%s]: Access denied for %s from %s (bruteforce protection)." %
                        (self.file_name, username, ip_addr))
            return False, error

        # Get password hash from the table.
        password_hash = None
        try:
            self._cursor.execute("SELECT password_hash FROM passwords WHERE users_id = %s", (user_id,))

            result = self._cursor.fetchall()

            if len(result) != 1:
                return False, ErrorCodes.NO_ERROR

            password_hash = result[0][0]

        except:
            logger.exception("[%s]: Not able to get password hash." % self.file_name)

            return False, ErrorCodes.DATABASE_ERROR

        # Check if provided password is correct.
        auth_result = True
        provided_hash = bcrypt.hashpw(password.encode("ascii"), password_hash.encode("ascii"))
        if password_hash.encode("ascii") != provided_hash:
            auth_result = False

            # Increment bruteforce counter in database.
            try:
                self._cursor.execute("SELECT id, counter FROM bruteforce_info WHERE users_id = %s AND addr = %s",
                                     (user_id, ip_addr))

                result = self._cursor.fetchall()

                # Create bruteforce entry if no exist yet.
                if len(result) == 0:
                    self._cursor.execute("INSERT INTO bruteforce_info " +
                                         "(users_id, addr, counter, last_attempt, blocked_until) " +
                                         "VALUES (%s, %s, %s, %s, %s)",
                                         (user_id, ip_addr, 0, utc_timestamp, 0))

                else:
                    bf_id = result[0][0]
                    counter = result[0][1] + 1

                    # Check if username and ip address can still try to log in
                    # => update counter in database.
                    if self.bf_fail_attempts_count > counter:
                        self._cursor.execute("UPDATE bruteforce_info SET counter = %s, last_attempt = %s " +
                                             "WHERE id = %s ",
                                             (counter, utc_timestamp, bf_id))

                    # => block log in attempts.
                    else:
                        utc_block_time = utc_timestamp + self.bf_block_time
                        self._cursor.execute("UPDATE bruteforce_info " +
                                             "SET counter = %s, last_attempt = %s, blocked_until = %s " +
                                             "WHERE id = %s ",
                                             (counter, utc_timestamp, utc_block_time, bf_id))

                        utc_timestr = datetime.datetime.fromtimestamp(utc_block_time).strftime('%Y-%m-%d %H:%M:%S')
                        logger.info("[%s]: Blocking %s from %s until %s (bruteforce protection)." %
                                    (self.file_name, username, ip_addr, utc_timestr))

                # Commit all changes.
                self._conn.commit()

            except:
                logger.exception("[%s]: Not able to update bruteforce data." % self.file_name)

                return False, ErrorCodes.DATABASE_ERROR

        # Close connection to the database.
        self._close_connection()

        return auth_result, ErrorCodes.NO_ERROR

    def add_send_statistic(self, username, ip_addr, channel, logger=None):

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        # Connect to the database.
        self._open_connection(logger)

        # Get user id for username.
        user_id, error = self._get_user_id(username, logger)
        if not user_id:
            return error

        utc_timestamp = int(time.time())

        # Add data to send statistics.
        try:
            self._cursor.execute("INSERT INTO statistics_send " +
                                 "(users_id, addr, channel, timestamp) " +
                                 "VALUES (%s, %s, %s, %s)",
                                 (user_id, ip_addr, channel, utc_timestamp))

        except:
            logger.exception("[%s]: Not able to update send statistics data." % self.file_name)

            return ErrorCodes.DATABASE_ERROR

        # Commit all changes.
        self._conn.commit()

        # Close connection to the database.
        self._close_connection()

        return ErrorCodes.NO_ERROR

    def clean_up_push_data_table(self, push_data_life_span, logger=None):

        # TODO: large messages not yet implemented
        return ErrorCodes.NO_ERROR

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        # Connect to the database.
        self._open_connection(logger)

        utc_timestamp = int(time.time())
        clean_up_time = utc_timestamp - (push_data_life_span * 86400)

        # Delete older push data entries.
        try:
            self._cursor.execute("DELETE FROM push_data " +
                                 "WHERE timestamp < %s",
                                 (clean_up_time,))

        except:
            logger.exception("[%s]: Not able to clean up push data." % self.file_name)

            return ErrorCodes.DATABASE_ERROR

        # Commit all changes.
        self._conn.commit()

        # Close connection to the database.
        self._close_connection()

        return ErrorCodes.NO_ERROR

    def clean_up_statistics_table(self, statistics_life_span, logger=None):

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        # Connect to the database.
        self._open_connection(logger)

        utc_timestamp = int(time.time())
        clean_up_time = utc_timestamp - (statistics_life_span * 86400)

        # Delete older statistics entries.
        try:
            self._cursor.execute("DELETE FROM statistics_send " +
                                 "WHERE timestamp < %s",
                                 (clean_up_time, ))

        except:
            logger.exception("[%s]: Not able to clean up statistics data." % self.file_name)

            return ErrorCodes.DATABASE_ERROR

        # Commit all changes.
        self._conn.commit()

        # Close connection to the database.
        self._close_connection()

        return ErrorCodes.NO_ERROR

    def clean_up_users(self, logger=None):

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        # Connect to the database.
        self._open_connection(logger)

        utc_timestamp = int(time.time())

        # Get expired tokens.
        user_ids = None
        try:
            self._cursor.execute("SELECT users_id FROM tokens WHERE expiration < %s",
                                 (utc_timestamp, ))

            result = self._cursor.fetchall()

            user_ids = map(lambda x: x[0], result)

        except:
            logger.exception("[%s]: Not able to clean up token data." % self.file_name)

            return ErrorCodes.DATABASE_ERROR

        # Delete expired tokens.
        for user_id in user_ids:
            try:
                logger.debug("[%s]: Delete expired token for user id %d." % (self.file_name, user_id))

                self._cursor.execute("DELETE FROM tokens " +
                                     "WHERE users_id = %s",
                                     (user_id, ))

            except:
                logger.exception("[%s]: Not able to clean up tokens." % self.file_name)

                return ErrorCodes.DATABASE_ERROR

        # Get inactive users.
        user_ids = None
        try:
            self._cursor.execute("SELECT id FROM users WHERE active = 0")

            result = self._cursor.fetchall()

            user_ids = map(lambda x: x[0], result)

        except:
            logger.exception("[%s]: Not able to clean up user data." % self.file_name)

            return ErrorCodes.DATABASE_ERROR

        # Delete inactive users which do not have a token.
        for user_id in user_ids:
            try:
                self._cursor.execute("SELECT * FROM tokens WHERE users_id = %s",
                                     (user_id, ))

                result = self._cursor.fetchall()

                # Ignore inactive users that still have a token in the db.
                if len(result) != 0:
                    continue

                logger.debug("[%s]: Delete inactive user with id %d." % (self.file_name, user_id))

                '''
                TODO: large messages not yet implemented
                # Delete push_data of user.
                self._cursor.execute("DELETE FROM push_data " +
                                     "WHERE users_id = %s",
                                     (user_id, ))
                '''

                # Delete bruteforce_info of user.
                self._cursor.execute("DELETE FROM bruteforce_info " +
                                     "WHERE users_id = %s",
                                     (user_id, ))

                # Delete statistics_send of user.
                self._cursor.execute("DELETE FROM statistics_send " +
                                     "WHERE users_id = %s",
                                     (user_id, ))

                # Delete password of user.
                self._cursor.execute("DELETE FROM passwords " +
                                     "WHERE users_id = %s",
                                     (user_id, ))

                # Delete acl of user.
                self._cursor.execute("DELETE FROM acl " +
                                     "WHERE users_id = %s",
                                     (user_id, ))

                # Delete user.
                self._cursor.execute("DELETE FROM users " +
                                     "WHERE id = %s",
                                     (user_id, ))

            except:
                logger.exception("[%s]: Not able to clean up users." % self.file_name)

                return ErrorCodes.DATABASE_ERROR

        # Commit all changes.
        self._conn.commit()

        # Close connection to the database.
        self._close_connection()

        return ErrorCodes.NO_ERROR

    def get_acl(self, username, logger=None):

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        # Connect to the database.
        self._open_connection(logger)

        # Get user id for username.
        user_id, error = self._get_user_id(username, logger)
        if not user_id:
            return [], error

        # Get expired tokens.
        acl = None
        try:
            self._cursor.execute("SELECT acl FROM acl WHERE users_id = %s",
                                 (user_id, ))

            result = self._cursor.fetchall()

            acl = map(lambda x: x[0], result)

        except:
            logger.exception("[%s]: Not able to clean up token data." % self.file_name)

            return [], ErrorCodes.DATABASE_ERROR

        # Close connection to the database.
        self._close_connection()

        return acl, ErrorCodes.NO_ERROR

    def insert_push_data(self, username, data, logger=None):

        # TODO: large messages not yet implemented
        return 0, ErrorCodes.NO_ERROR

        # Set logger instance to use.
        if not logger:
            logger = self.logger

        # Connect to the database.
        self._open_connection(logger)

        # Get user id for username.
        user_id, error = self._get_user_id(username, logger)
        if not user_id:
            return None, error

        # Generate random id for data.
        data_id = None
        allowed_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        len_chars = len(allowed_chars)
        while True:
            data_id = ""
            for i in os.urandom(20):
                data_id += allowed_chars[i % len_chars]
            try:
                self._cursor.execute("SELECT * FROM push_data WHERE id = %s",
                                     (data_id, ))

                result = self._cursor.fetchall()

                if len(result) == 0:
                    break

            except:
                logger.exception("[%s]: Not able to generate data id." % self.file_name)

                return None, ErrorCodes.DATABASE_ERROR

        # Store data in database.
        utc_timestamp = int(time.time())
        try:
            self._cursor.execute("INSERT INTO push_data " +
                                 "(id, users_id, data, timestamp) " +
                                 "VALUES (%s, %s, %s, %s)",
                                 (data_id, user_id, data, utc_timestamp))

        except:
            logger.exception("[%s]: Not able to generate data id." % self.file_name)

            return None, ErrorCodes.DATABASE_ERROR

        # Commit all changes.
        self._conn.commit()

        # Close connection to the database.
        self._close_connection()

        return data_id, ErrorCodes.NO_ERROR
