# alertR Push Server

The push server component of the [alertR alarm and monitoring system](https://github.com/sqall01/alertR). The service can be used by registering an account at [alertr.de](https://alertr.de) and following the setup instructions. If you are searching for a detailed description of the push service design, please read the pages in the official alertR [Github Wiki](https://github.com/sqall01/alertR/wiki/Infrastructure#infrastructure_push).

The directory "service" contains the server part and the directory "website" contains the registration website for the service.

The service needs the following tables in the MySQL database:

```sql
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTO_INCREMENT, 
    email VARCHAR(255) NOT NULL UNIQUE, 
    active BOOLEAN NOT NULL);

CREATE TABLE IF NOT EXISTS acl (
    users_id INTEGER NOT NULL, 
    acl INTEGER NOT NULL, 
    PRIMARY KEY(users_id, acl), 
    FOREIGN KEY(users_id) REFERENCES users(id));

CREATE TABLE IF NOT EXISTS tokens (
    users_id INTEGER PRIMARY KEY, 
    token VARCHAR(255) NOT NULL, 
    timestamp INTEGER NOT NULL, 
    expiration INTEGER NOT NULL, 
    FOREIGN KEY(users_id) REFERENCES users(id));

CREATE TABLE IF NOT EXISTS passwords (
    users_id INTEGER PRIMARY KEY, 
    password_hash VARCHAR(255) NOT NULL, 
    FOREIGN KEY(users_id) REFERENCES users(id));

CREATE TABLE IF NOT EXISTS bruteforce_info (
    id INTEGER PRIMARY KEY AUTO_INCREMENT, 
    users_id INTEGER NOT NULL, 
    addr VARCHAR(255) NOT NULL, 
    counter INTEGER NOT NULL, 
    last_attempt INTEGER NOT NULL, 
    blocked_until INTEGER NOT NULL, 
    FOREIGN KEY(users_id) REFERENCES users(id));

CREATE TABLE IF NOT EXISTS statistics_send (
    id INTEGER AUTO_INCREMENT, 
    users_id INTEGER NOT NULL, 
    addr VARCHAR(255) NOT NULL, 
    channel VARCHAR(255) NOT NULL, 
    timestamp INTEGER NOT NULL, 
    PRIMARY KEY(id, users_id, timestamp), 
    FOREIGN KEY(users_id) REFERENCES users(id));
```