<?php
$subject = 'New Contact Message';
$to = 'contact@designesia.com';

$name  = isset($_POST['name']) ? trim($_POST['name']) : '';
$email = isset($_POST['email']) ? trim($_POST['email']) : '';
$phone = isset($_POST['phone']) ? trim($_POST['phone']) : '';
$msg   = isset($_POST['message']) ? trim($_POST['message']) : '';

$message  = "Name : " . $name . "\n";
$message .= "Email : " . $email . "\n";
$message .= "Phone : " . $phone . "\n";
$message .= "Message : " . $msg . "\n";

// Lebih aman: From pakai email domain sendiri
$headers  = "MIME-Version: 1.0\r\n";
$headers .= "Content-Type: text/plain; charset=UTF-8\r\n";
$headers .= "From: Designesia <contact@designesia.com>\r\n";
$headers .= "Reply-To: " . $name . " <" . $email . ">\r\n";
$headers .= "Return-Path: contact@designesia.com\r\n";

if (mail($to, $subject, $message, $headers)) {
    echo 'sent';
} else {
    echo 'failed';
}
?>