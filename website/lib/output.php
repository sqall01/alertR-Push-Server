<?php

// written by sqall
// twitter: https://twitter.com/sqall01
// blog: http://blog.h4des.org
// github: https://github.com/sqall01
//
// Licensed under the GNU Public License, version 2.

function output_account_activated($email) {
    echo '<p>Account <b>'
        . $email
        . '</b> registered successfully.</p>';
}


function output_password_form($token) {

    echo '<p>Please enter a password for your account.<br />';
    echo 'The password has the following requirements:</p>';
    echo '<p>Minimum length: 10 characters'
        . '<br />'
        . 'At least: 1 number'
        . '<br />'
        . 'At least: 1 upper letter'
        . '<br />'
        . 'At least: 1 lower letter'
        . '</p>';
    echo '<p>Allowed special characters: '
        . '- _ , ! $ ? + ( ) [ ] { } %'
        . '</p>';
    echo '<form action="index.php?reg_token='
        . $token
        . '" method="POST">';
    echo 'Password: ';
    echo '<input type="password" name="password" />';
    echo '<br />';
    echo 'Password repeated: ';
    echo '<input type="password" name="password_repeat" />';
    echo '<br />';
    echo '<input type="submit" value="Set Password" />';
    echo '</form>';
}


function output_register_form() {
    echo '<form action="index.php" method="POST">';
    echo 'eMail address: ';
    echo '<input type="text" name="email" />';
    echo '<input type="submit" value="Register" />';
    echo '</form>';
}


function output_token_resend($diff_time, $email) {
    echo '<p>Token sent to <b>'
        . htmlentities($email, ENT_QUOTES)
        . '</b> '
        . intval($diff_time / 60)
        . ' minutes ago.</p>';

    echo '<form action="index.php" method="POST">';
    echo '<input type="hidden" name="email" value="'
        . $email
        . '" />';
    echo '<input type="hidden" name="token_resend" value="1" />';
    echo '<input type="submit" value="Resend Token" />';
    echo '</form>';
}


function output_token_resend_forbidden(
    $diff_time,
    $config_token_resend_time,
    $email) {

    echo '<p>Token sent to <b>'
        . htmlentities($email, ENT_QUOTES)
        . '</b> '
        . intval($diff_time / 60)
        . ' minutes ago.</p>';
    echo '<p>Allowed to resent token after '
        . $config_token_resend_time
        . ' minutes.</p>';

}


function output_waiting_activation($email) {
    echo '<p>Activation eMail was sent to <b>'
        . $email
        . '</b>.</p>';
    echo '<p>You have to follow the instructions '
        . 'in the eMail before the registration is complete.</p>';
}

?>