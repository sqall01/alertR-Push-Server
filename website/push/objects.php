<?php

// written by sqall
// twitter: https://twitter.com/sqall01
// blog: https://h4des.org
// github: https://github.com/sqall01
// 
// Licensed under the GNU Public License, version 2.

abstract class ErrorCodes {
    const NO_ERROR = 0;
    const DATABASE_ERROR = 1;
    const AUTH_ERROR = 2;
    const ILLEGAL_MSG_ERROR = 3;
    const GOOGLE_MSG_TOO_LARGE = 4;
    const GOOGLE_CONNECTION = 5;
    const GOOGLE_UNKNOWN = 6;
    const GOOGLE_AUTH = 7;
    const VERSION_MISSMATCH = 8;
    const NO_NOTIFICATION_PERMISSION = 9;
    const PHP_BRIDGE_ERROR = 10;
}

?>