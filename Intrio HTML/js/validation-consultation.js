$(document).ready(function(){

    // Remove error class on input/select/textarea focus or change
    $('#interior-estimator-form input, #interior-estimator-form select, #interior-estimator-form textarea').on('click change keyup', function(){
        $(this).removeClass("error_input");
    });

    $('#send_message').click(function(e){

        // Prevent default form submission
        e.preventDefault();

        // Variable declaration
        var error = false;

        var name          = $('input[name="name"]').val();
        var email         = $('input[name="email"]').val();
        var project_type  = $('select[name="project_type"]').val();
        var property_size = $('select[name="property_size"]').val();
        var design_style  = $('select[name="design_style"]').val();
        var timeline      = $('select[name="timeline"]').val();
        var budget_range  = $('select[name="budget_range"]').val();
        var message       = $('textarea[name="message"]').val(); // optional

        // Validation
        if(name.length == 0){
            error = true;
            $('input[name="name"]').addClass("error_input");
        }

        if(email.length == 0 || email.indexOf('@') == -1){
            error = true;
            $('input[name="email"]').addClass("error_input");
        }

        if(project_type.length == 0){
            error = true;
            $('select[name="project_type"]').addClass("error_input");
        }

        if(property_size.length == 0){
            error = true;
            $('select[name="property_size"]').addClass("error_input");
        }

        if(design_style.length == 0){
            error = true;
            $('select[name="design_style"]').addClass("error_input");
        }

        if(timeline.length == 0){
            error = true;
            $('select[name="timeline"]').addClass("error_input");
        }

        if(budget_range.length == 0){
            error = true;
            $('select[name="budget_range"]').addClass("error_input");
        }

        // Proceed if no error
        if(error == false){

            // Disable button and show loading text
            $('#send_message')
                .attr('disabled', true)
                .val('Sending...');

            // Send AJAX request
            $.post(
                "action-consultation.php",
                $("#interior-estimator-form").serialize(),
                function(result){

                    if(result.trim() == 'sent'){

                        // Show success message
                        $('#success_message').fadeIn(500);
                        $('#error_message').hide();

                        // Reset form
                        $('#interior-estimator-form')[0].reset();

                        // Reset button
                        $('#send_message')
                            .removeAttr('disabled')
                            .val('Get Free Estimate');

                    }else{

                        // Show error message
                        $('#error_message').fadeIn(500);
                        $('#success_message').hide();

                        // Re-enable button
                        $('#send_message')
                            .removeAttr('disabled')
                            .val('Get Free Estimate');
                    }

                }
            ).fail(function(){

                // Handle AJAX failure
                $('#error_message').fadeIn(500);
                $('#success_message').hide();

                $('#send_message')
                    .removeAttr('disabled')
                    .val('Get Free Estimate');
            });
        }

    });

});