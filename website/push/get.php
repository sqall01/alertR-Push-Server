<?php

// written by sqall
// twitter: https://twitter.com/sqall01
// blog: https://h4des.org
// github: https://github.com/sqall01
//
// Licensed under the GNU Public License, version 2.

// Include config data.
require_once("../config/config.php");

abstract class ErrorCodes {
	const NO_ERROR = 0; // No error.
	const DATABASE_ERROR = 1; // Database problems.
	const NO_DATA = 2; // Data does not exist.
    const ILLEGAL_ID = 3; // Malformed id.
	const DATA_NOT_ON_SERVER = 4; // Placeholder for HA.
}


function validate_id_input($input) {
    for($i = 0; $i < strlen($input); $i++) {
        $check = preg_match("/[a-fA-F0-9]/", $input[$i]);
        if($check != 1) {
            return false;
        }
    }
    return true;
}

header('Content-type: application/json');

// Validate given id.
$result = array();
if(!isset($_GET["id"])) {
    $result["error"] = ErrorCodes::ILLEGAL_ID;
    die(json_encode($result));
}
if(!validate_id_input($_GET["id"]) || strlen($_GET["id"]) !== 20) {
    $result["error"] = ErrorCodes::ILLEGAL_ID;
    die(json_encode($result));
}

// Connect to database.
$mysqli = new mysqli(
    $config_mysql_server,
    $config_mysql_username,
    $config_mysql_password,
    $config_mysql_db,
    $config_mysql_port);
if($mysqli->connect_errno) {
    $result["error"] = ErrorCodes::DATABASE_ERROR;
    $result["msg"] = $mysqli->connect_error;
    die(json_encode($result));
}

// Get data from database.
$get_data_query = "SELECT data, timestamp FROM push_data WHERE id=" .
         $mysqli->real_escape_string($_GET["id"]);
$result_query = $mysqli->query($get_data_query);
if(!$result_query) {
    $result["error"] = ErrorCodes::DATABASE_ERROR;
    $result["msg"] = $mysqli->error;
    die(json_encode($result));
}
$row = $result_query->fetch_assoc();
if(count($row) === 0) {
    $result["error"] = ErrorCodes::NO_DATA;
    die(json_encode($result));
}

// Return data.
$result["error"] = ErrorCodes::NO_ERROR;
$result["data"] = $row["data"];
$result["timestamp"] = $row["timestamp"];
echo json_encode($result)
?>