<?php

$subject = 'New Consultation Request';
$to = 'contact@designesia.com';

// Get form data
$name          = $_POST['name'] ?? '';
$email         = $_POST['email'] ?? '';
$project_type  = $_POST['project_type'] ?? '';
$property_size = $_POST['property_size'] ?? '';
$design_style  = $_POST['design_style'] ?? '';
$timeline      = $_POST['timeline'] ?? '';
$budget_range  = $_POST['budget_range'] ?? '';
$msg           = $_POST['message'] ?? '';

// Get checkbox values
$services = isset($_POST['services']) && is_array($_POST['services'])
    ? implode(', ', $_POST['services'])
    : 'None';

// Set email headers
$headers  = "From: ".$name." <".$email.">\r\n";
$headers .= "Reply-To: ".$email."\r\n";
$headers .= "Content-Type: text/plain; charset=UTF-8\r\n";

// Build plain text message
$message  = "New Consultation Request\n";
$message .= "-----------------------------------\n";
$message .= "Name: $name\n";
$message .= "Email: $email\n";
$message .= "Project Type: $project_type\n";
$message .= "Property Size: $property_size\n";
$message .= "Design Style: $design_style\n";
$message .= "Project Timeline: $timeline\n";
$message .= "Additional Services: $services\n";
$message .= "Estimated Budget Range: $budget_range\n";
$message .= "Project Details:\n$msg\n";

// Send email
if(mail($to, $subject, $message, $headers)){
    echo 'sent';
} else {
    echo 'failed';
}

?>