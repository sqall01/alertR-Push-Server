<?php

// written by sqall
// twitter: https://twitter.com/sqall01
// blog: https://h4des.org
// github: https://github.com/sqall01
//
// Licensed under the GNU Public License, version 2.

// Include config data.
require_once("../config/config.php");
require_once("./objects.php");

// Open connection to local unix socket server of push service.
@$fd = stream_socket_client("unix://" . $config_push_socket,
                            $errno,
                            $errstr,
                            5);

// Check if connection could be established.
if ($errno != 0) {
    $result = array();
    $result["code"] = ErrorCodes::WEB_BRIDGE_ERROR;
    $result["reason"] = $errstr;
    die(json_encode($result));
}

// Just transmit received data to unix socket server.
if(isset($_POST["data"])) {
    $data = $_POST["data"];
    fwrite($fd, $data);

    $result = fread($fd, 4096);
    echo $result;
}

// If no data is given, post an error.
else {
    fclose($fd);
    $result = array();
    $result["code"] = ErrorCodes::WEB_BRIDGE_ERROR;
    $result["reason"] = "POST variable data not set.";
    die(json_encode($result));
}

?>