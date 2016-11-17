<?php

// written by sqall
// twitter: https://twitter.com/sqall01
// blog: http://blog.h4des.org
// github: https://github.com/sqall01
//
// Licensed under the GNU Public License, version 2.

// Include config data.
require_once("./config/config.php");

// Include output functions.
require_once("./lib/output.php");


function check_password_characteristics($input) {
    if(strlen($input) <= 9) {
        return false;
    }
    $check = preg_match("/[a-z]/", $input);
    if($check != 1) {
        return false;
    }
    $check = preg_match("/[A-Z]/", $input);
    if($check != 1) {
        return false;
    }
    $check = preg_match("/[0-9]/", $input);
    if($check != 1) {
        return false;
    }
    return true;
}


function send_email(
    $to_email,
    $from_email,
    $subject_email,
    $url_prefix,
    $token) {

    // Build registration url.
    $url = $url_prefix . $token;

    $message = "Hello,\r\n"
        . "\r\n"
        . "welcome to your new alertR push notification account.\r\n"
        . "\r\n"
        . "In order to complete the registration you have "
        . "to follow the link below:\r\n"
        . "\r\n"
        . $url
        . "\r\n"
        . "\r\n"
        . "Thank you.\r\n"
        . "\r\n"
        . "If you did not register for the alertR push notification service, "
        . "just ignore this eMail.\r\n";

    $headers = "From: " . $from_email . "\r\n";

    return mail($to_email, $subject_email, $message, $headers);
}


function validate_password_input($input) {
    for($i = 0; $i < strlen($input); $i++) {
        $check = preg_match("/[a-zA-Z0-9\-_,!$?+()\[\]{}%]/", $input[$i]);
        if($check != 1) {
            return false;
        }
    }
    return true;
}


function validate_token_input($input) {
    for($i = 0; $i < strlen($input); $i++) {
        $check = preg_match("/[a-fA-F0-9]/", $input[$i]);
        if($check != 1) {
            return false;
        }
    }
    return true;
}


$mysqli = new mysqli(
    $config_mysql_server,
    $config_mysql_username,
    $config_mysql_password,
    $config_mysql_db,
    $config_mysql_port);

if($mysqli->connect_errno) {
    die("Error: Database connection failed: " . $mysqli->connect_error);
}

$create_users_table = "CREATE TABLE IF NOT EXISTS users ("
    . "id INTEGER PRIMARY KEY AUTO_INCREMENT, "
    . "email VARCHAR(255) NOT NULL UNIQUE, "
    . "active BOOLEAN NOT NULL)";

$create_acl_table = "CREATE TABLE IF NOT EXISTS acl ("
    . "users_id INTEGER NOT NULL, "
    . "acl INTEGER NOT NULL, "
    . "PRIMARY KEY(users_id, acl), "
    . "FOREIGN KEY(users_id) REFERENCES users(id))";

$create_tokens_table = "CREATE TABLE IF NOT EXISTS tokens ("
    . "users_id INTEGER PRIMARY KEY, "
    . "token VARCHAR(255) NOT NULL, "
    . "timestamp INTEGER NOT NULL, "
    . "expiration INTEGER NOT NULL, "
    . "FOREIGN KEY(users_id) REFERENCES users(id))";

$create_passwords_table = "CREATE TABLE IF NOT EXISTS passwords ("
    . "users_id INTEGER PRIMARY KEY, "
    . "password_hash VARCHAR(255) NOT NULL, "
    . "FOREIGN KEY(users_id) REFERENCES users(id))";

$create_bf_info_table = "CREATE TABLE IF NOT EXISTS bruteforce_info ("
    . "id INTEGER PRIMARY KEY AUTO_INCREMENT, "
    . "users_id INTEGER NOT NULL, "
    . "addr VARCHAR(255) NOT NULL, "
    . "counter INTEGER NOT NULL, "
    . "last_attempt INTEGER NOT NULL, "
    . "blocked_until INTEGER NOT NULL, "
    . "FOREIGN KEY(users_id) REFERENCES users(id))";

$create_statistics_send_table = "CREATE TABLE IF NOT EXISTS statistics_send ("
    . "id INTEGER AUTO_INCREMENT, "
    . "users_id INTEGER NOT NULL, "
    . "addr VARCHAR(255) NOT NULL, "
    . "channel VARCHAR(255) NOT NULL, "
    . "timestamp INTEGER NOT NULL, "
    . "PRIMARY KEY(id, users_id, timestamp), "
    . "FOREIGN KEY(users_id) REFERENCES users(id))";

if($mysqli->query($create_users_table) !== TRUE
    || $mysqli->query($create_acl_table) !== TRUE
    || $mysqli->query($create_tokens_table) !== TRUE
    || $mysqli->query($create_passwords_table) !== TRUE
    || $mysqli->query($create_bf_info_table) !== TRUE
    || $mysqli->query($create_statistics_send_table) !== TRUE) {
    die("Error: Database table check.");
}

date_default_timezone_set("UTC");

if(!isset($_GET["reg_token"])
    && !isset($_POST["email"])) {
    output_register_form();
}


// User requested to resend a token.
else if(isset($_POST["email"])
    && isset($_POST["token_resend"])) {

    $email = $_POST["email"];
    if(!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        die("Error: email address invalid.");
    }

    // Check if user already exists in database.
    $select_email = "SELECT * FROM users WHERE email='"
        . $mysqli->real_escape_string($email)
        . "'";

    $result = $mysqli->query($select_email);
    if(!$result) {
        die("Error: Getting email from db: " . $mysqli->error);
    }

    $row = $result->fetch_assoc();

    // User does not exist in database.
    if(!$row) {
        die("Error: Account does not exist.");
    }

    // Do not continue if the account is already active.
    if($row["active"] == 1) {
        die("Error: Account already active.");
    }

    // Get token for account.
    $select_token = "SELECT * FROM tokens WHERE users_id="
        . $row["id"];

    $result = $mysqli->query($select_token);
    if(!$result) {
        die("Error: Getting token from db: " . $mysqli->error);
    }

    $row = $result->fetch_assoc();

    if (count($row) == 0) {
        die("Error: Token for account does not exist.");
    }

    // Check if allowed to resend a token.
    $current_time = time();
    $time_sent = $row["timestamp"];
    $diff_time = $current_time - $time_sent;
    if($diff_time < ($config_token_resend_time * 60)) {
        die("Error: Not allowed to resend token yet.");
    }

    $email_id = $row["users_id"];

    // Delete old token.
    $delete_token = "DELETE FROM tokens WHERE users_id = "
        . intval($email_id);

    if(!$mysqli->query($delete_token)) {
        die("Error: Deleting token from db: " . $mysqli->error);
    }

    $token_raw = openssl_random_pseudo_bytes(32);
    if(!$token_raw) {
        die("Error: Generating token failed.");
    }
    $token = bin2hex($token_raw);

    // Insert token into the database.
    $insert_token = "INSERT INTO tokens "
        . "(users_id, token, timestamp, expiration) "
        . "VALUES ( "
        . intval($email_id)
        . ", '"
        . $token
        . "', "
        . time()
        . ", "
        . (time() + $config_token_expiration_time)
        . ")";

    if(!$mysqli->query($insert_token)) {
        die("Error: Inserting token in db: " . $mysqli->error);
    }

    // Send eMail for account activation.
    if(!send_email(
        $email,
        $config_email_from,
        $config_email_subject,
        $config_email_url,
        $token)) {

        die("Error: Not able to send eMail.");
    }

    output_waiting_activation($email);

}

// User provided email address for registration.
else if(isset($_POST["email"])) {

    $email = $_POST["email"];
    if(!filter_var($email, FILTER_VALIDATE_EMAIL)) {
        die("Error: email address invalid.");
    }

    // Check if user already exists in database.
    $select_email = "SELECT * FROM users WHERE email='"
        . $mysqli->real_escape_string($email)
        . "'";

    $result = $mysqli->query($select_email);
    if(!$result) {
        die("Error: Getting email from db: " . $mysqli->error);
    }

    $row = $result->fetch_assoc();

    // User already exists in database.
    if($row) {

        // Do not continue if the account is already active.
        if($row["active"] == 1) {
            die("Error: Account already active.");
        }

        // Get token for account.
        $select_token = "SELECT * FROM tokens WHERE users_id="
            . $row["id"];

        $result = $mysqli->query($select_token);
        if(!$result) {
            die("Error: Getting token from db: " . $mysqli->error);
        }

        $row = $result->fetch_assoc();

        if (count($row) == 0) {
            die("Error: Token for account does not exist.");
        }

        // Check if allowed to resend a token.
        $current_time = time();
        $time_sent = $row["timestamp"];
        $diff_time = $current_time - $time_sent;
        if($diff_time >= ($config_token_resend_time * 60)) {
            output_token_resend($diff_time, $email);
        }

        // Not allowed to resend token yet.
        else {
            output_token_resend_forbidden(
                $diff_time,
                $config_token_resend_time,
                $email);
        }
    }

    // User does not exist in database.
    else {

        // Insert email into the database (as not active).
        $insert_email = "INSERT INTO users (email, active) "
            . "VALUES ( '"
            . $mysqli->real_escape_string($email)
            . "', 0)";

        if(!$mysqli->query($insert_email)) {
            die("Error: Inserting email in db: " . $mysqli->error);
        }

        $email_id = $mysqli->insert_id;

        $token_raw = openssl_random_pseudo_bytes(32);
        if(!$token_raw) {
            die("Error: Generating token failed.");
        }
        $token = bin2hex($token_raw);

        // Insert token into the database.
        $insert_token = "INSERT INTO tokens "
            . "(users_id, token, timestamp, expiration) "
            . "VALUES ( "
            . intval($email_id)
            . ", '"
            . $token
            . "', "
            . time()
            . ", "
            . (time() + $config_token_expiration_time)
            . ")";

        if(!$mysqli->query($insert_token)) {
            die("Error: Inserting token in db: " . $mysqli->error);
        }

        // Send eMail for account activation.
        if(!send_email(
            $email,
            $config_email_from,
            $config_email_subject,
            $config_email_url,
            $token)) {

            die("Error: Not able to send eMail.");
        }

        output_waiting_activation($email);

    }

}

// Token and passwords for the registration are given.
else if(isset($_GET["reg_token"])
    && isset($_POST["password"])
    && isset($_POST["password_repeat"])) {

    $token = $_GET["reg_token"];
    if(!validate_token_input($token)) {
        die("Error: Token invalid.");
    }

    $password_1 = $_POST["password"];
    if(!validate_password_input($password_1)) {
        die("Error: Password invalid.");
    }

    $password_2 = $_POST["password_repeat"];
    if(!validate_password_input($password_2)) {
        die("Error: Password invalid.");
    }

    if(!check_password_characteristics($password_1)) {
        die("Error: Password too weak.");
    }

    if(strcmp($password_1, $password_2) != 0) {
        die("Error: Passwords different.");
    }

    // Get token for account.
    $select_token = "SELECT * FROM tokens WHERE token='"
        . $mysqli->real_escape_string($token)
        . "'";

    $result = $mysqli->query($select_token);
    if(!$result) {
        die("Error: Getting token from db: " . $mysqli->error);
    }

    $row = $result->fetch_assoc();

    if (count($row) == 0) {
        die("Error: Token does not exist.");
    }

    // Check if token is expired.
    if($row["expiration"] <= time()) {
        die("Error: Token is expired.");
    }

    $email_id = $row["users_id"];

    // Get email from database.
    $select_email = "SELECT * FROM users WHERE id="
        . intval($email_id);

    $result = $mysqli->query($select_email);
    if(!$result) {
        die("Error: Getting email from db: " . $mysqli->error);
    }

    $row = $result->fetch_assoc();

    if (count($row) == 0) {
        die("Error: Account does not exist.");
    }

    $email = $row["email"];

    $password_hash = password_hash($password_1, PASSWORD_BCRYPT);

    // Insert password into the database.
    $insert_password = "INSERT INTO passwords (users_id, password_hash) "
        . "VALUES ( "
        . intval($email_id)
        . ", '"
        . $password_hash
        . "')";

    if(!$mysqli->query($insert_password)) {
        die("Error: Inserting password in db: " . $mysqli->error);
    }

    // Delete old token.
    $delete_token = "DELETE FROM tokens WHERE users_id = "
        . intval($email_id);

    if(!$mysqli->query($delete_token)) {
        die("Error: Deleting token from db: " . $mysqli->error);
    }

    // Activate user account.
    $update_users = "UPDATE users SET "
        . "active = 1 "
        . "WHERE id = "
        . intval($email_id);

    if(!$mysqli->query($update_users)) {
        die("Error: Activating account in db: " . $mysqli->error);
    }

    output_account_activated($email);

}

// Token for the registration is given.
else if(isset($_GET["reg_token"])) {

    $token = $_GET["reg_token"];
    if(!validate_token_input($token)) {
        die("Error: Token invalid.");
    }

    // Get token for account.
    $select_token = "SELECT * FROM tokens WHERE token='"
        . $mysqli->real_escape_string($token)
        . "'";

    $result = $mysqli->query($select_token);
    if(!$result) {
        die("Error: Getting token from db: " . $mysqli->error);
    }

    $row = $result->fetch_assoc();

    if (count($row) == 0) {
        die("Error: Token does not exist.");
    }

    // Check if token is expired.
    if($row["expiration"] <= time()) {
        die("Error: Token is expired.");
    }

    output_password_form($token);

}

// Unknown input.
else {
    die("Error: Invalid action.");
}

?>