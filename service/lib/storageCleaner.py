#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: http://blog.h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.


import os
import time
import threading
from .storage import Mysql


class DatabaseCleaner(threading.Thread):

    def __init__(self, global_data):
        threading.Thread.__init__(self)

        # File name of this file (used for logging).
        self.file_name = os.path.basename(__file__)

        # Get global configured data.
        self.global_data = global_data
        self.logger = self.global_data.logger
        self.db_cleaner_sleep_timer = self.global_data.db_cleaner_sleep_timer
        self.statistics_life_span = self.global_data.statistics_life_span
        self.push_data_life_span = self.global_data.push_data_life_span

        self.storage = Mysql(self.global_data)

        # Flag that indicates that the thread should be terminated.
        self.running = True

    def run(self):

        # Clean up statistics table one time during start up directly.
        self.storage.clean_up_statistics_table(self.statistics_life_span)

        # Clean up push data table one time during start up directly.
        self.storage.clean_up_push_data_table(self.push_data_life_span)

        # Clean up users and tokens table.
        self.storage.clean_up_users()

        while True:

            self.logger.debug("[%s]: Cleaning up database." % self.file_name)

            # Clean up statistics table.
            if self.statistics_life_span != 0:
                self.storage.clean_up_statistics_table(self.statistics_life_span)

            # Clean up push data table.
            if self.push_data_life_span != 0:
                self.storage.clean_up_push_data_table(self.push_data_life_span)

            # Clean up users.
            self.storage.clean_up_users()

            # Sleep until next run.
            counter = 0
            while counter < self.db_cleaner_sleep_timer:
                time.sleep(1)
                if not self.running:
                    self.logger.info("[%s]: Database cleaning thread stopped." % self.file_name)
                    return
                counter += 1

    def shutdown(self):
        self.running = False
