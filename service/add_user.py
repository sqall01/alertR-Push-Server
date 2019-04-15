#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: https://h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

from lib import GlobalData
import xml.etree.ElementTree
import MySQLdb
import bcrypt
import sys

new_username = "MyEmailAccount@alertr.de"
new_password = "MyAlertrDePassword"

global_data = GlobalData()

try:
    configRoot = xml.etree.ElementTree.parse(global_data.config_file).getroot()

    global_data.mysql_host = str(configRoot.find("storage").find("mysql").attrib["server"])
    global_data.mysql_port = int(configRoot.find("storage").find("mysql").attrib["port"])
    global_data.mysql_database = str(configRoot.find("storage").find("mysql").attrib["database"])
    global_data.mysql_username = str(configRoot.find("storage").find("mysql").attrib["username"])
    global_data.mysql_password = str(configRoot.find("storage").find("mysql").attrib["password"])

except Exception as e:
    print("Config could not be parsed.")
    print(e)
    sys.exit(1)

conn = MySQLdb.connect(host=global_data.mysql_host,
                       port=global_data.mysql_port,
                       user=global_data.mysql_username,
                       passwd=global_data.mysql_password,
                       db=global_data.mysql_database)
cursor = conn.cursor()

cursor.execute("INSERT INTO users (email, active) VALUES (%s, 1)",
               (new_username, ))

bcrypt_hash = bcrypt.hashpw(new_password.encode("ascii"), bcrypt.gensalt())
user_id = cursor.lastrowid

cursor.execute("INSERT INTO passwords (users_id, password_hash) VALUES (%s, %s)",
               (user_id, bcrypt_hash))

conn.commit()
cursor.close()
conn.close()
