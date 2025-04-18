
//On click of remove button
$(document).on('click', '.remove-purchase', function() { //.remove-purchase is attached to the remove button class
    const removePurchase = $(this).data('url'); //Gets URL for Flask route that removes the row
    const pinURL = $(this).data('pin-url'); //Gets URL for Flask route which validates employee pin
    const purchaseId = $(this).data('id'); //Gets purchase ID
    const row = $(`#purchase-${purchaseId}`); //For removing the row visually
    
    //Prompting for PIN input
    const pin = prompt("Enter employee pin:");
    //If no pin is entered or prompt cancelled
    if(!pin)
    {
        alert("Employee pin required to remove purchases.");
        return;
    }

    //AJAX checking the pin is in Employee table
    $.ajax({
        url: pinURL, // Flask route to validate PIN
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ pin: pin }),
        success: function(response) 
        {   
            //If employee pin is valid
            if (response.validPin) 
            {
                //AJAX to remove from db
                $.ajax({
                    url: removePurchase, //Flask route which removes purchase
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({ id: purchaseId }),
                    success: function(response) {
                        if (response.success) {   
                            //Removes row if successful
                            row.remove();       
                            //Updates new total cost
                            $('#total-cost-text').text(`Total Cost: £${response.totalCost}`);    
                        } else {
                            alert("Failed to remove the purchase."); //Alerts user of failure
                        }
                    },
                    error: function() {
                        alert("An error occurred while removing the purchase."); //Alerts user of AJAX failure
                    }
                });
            }
            else
            {
                //If AJAX reponse returns pin as invalid
                alert("PIN invalid.");
            }
        },
        //If error in AJAX response
        error: function() {
            alert("An error occurred while validating the PIN.");
        }
    });
});

//For adding custom dispense with AJAX
//When confirm button is clicked
$(document).on('click', '#confirm-custom-dispense', function() {
    //Flask route to handle adding dispense
    const addCustom = $(this).data('url');
    //Get form inputs
    var rfidUID = $('#customRFIDUID').val();
    var productName = $('#customName').val();
    var productWeight = $('#customWeight').val();
    var productCost = $('#customCost').val();
    //Get date in same format as it is normally recieved by ESP32
    var purchasedAt = new Date().toISOString();

    //Validation for user input
    const nameRegex = /^[A-Za-z\s]+$/; //Only letters
    //If input includes special characters or numbers
    if (!nameRegex.test(productName)) {
        alert("Name must not contain numbers or special characters.");
        return;
    }
    //Check weight and cost is positive float
    if (isNaN(parseFloat(productWeight)) || parseFloat(productWeight) <= 0) {
        alert("Product weight must be a positive number.");
        return;
    }
    if (isNaN(parseFloat(productCost)) || parseFloat(productCost) <= 0) {
        alert("Product cost must be a positive number.");
        return;
    }

    $.ajax({
        url: addCustom, 
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            rfid_uid: parseInt(rfidUID),
            name: productName,
            //Send as float to 2 d.p.
            weight: parseFloat(productWeight).toFixed(2),
            cost: parseFloat(productCost).toFixed(2),
            purchased_at: purchasedAt
        }),
        success: function(response) {
            //Closes modal, clears forms and adds to table
            if (response.success) {
                $('#dispenseModal').modal('hide');
                $('#customName').val('');
                $('#customWeight').val('');
                $('#customCost').val('');
                //Adding row to table
                const customDispenseRow = `
                    <tr id="purchase-${response.purchase_id}">
                        <th scope="row">${productName}</th>
                        <td>${productWeight}g</td>
                        <td>£${parseFloat(productCost).toFixed(2)}</td>
                        <td>${response.formattedDate}</td>
                        <td>
                            <button class="btn btn-danger btn-sm remove-purchase" 
                                    data-id="${response.purchase_id}" 
                                    data-pin-url="${response.pin_url}"
                                    data-url="${response.remove_url}">
                                Remove
                            </button>
                        </td>
                    </tr>
                `;
                $('#purchase-table tbody').append(customDispenseRow);
                //Update total cost
                $('#total-cost-text').text(`Total Cost: £${response.totalCost}`);                    

            } else {
                alert("Error: "+ response.message);
            }
        },
        error: function() {
            alert("Failed to add custom dispense.");
        }
    });
});

//For adding item with AJAX
//When confirm button is clicked
$(document).on('click', '#confirm-item', function() {
    //Flask route to handle adding item
    const addItem = $(this).data('url');
    //Get RFID UID to add item to
    var rfidUID = $('#itemRFIDUID').val();
    //Get input from dropdown
    const dropdown = document.getElementById('itemDropdown');
    const selectedItem = dropdown.value;
    
    //Check an item has been selected
    if (!selectedItem) {
        alert("Please select an item from the dropdown.");
        return;
    }
    //Get item name and cost as separate values
    const [itemName, itemCost] = selectedItem.split(',');
    //Get date in same format as it is normally recieved by ESP32
    var purchasedAt = new Date().toISOString();

    $.ajax({
        url: addItem, 
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            rfid_uid: parseInt(rfidUID),
            name: itemName,
            cost: parseFloat(itemCost).toFixed(2),
            purchased_at: purchasedAt
        }),
        success: function(response) {
            //Closes modal, clears forms and adds to table
            if (response.success) {
                $('#itemModal').modal('hide');
                
                //Adding row to table
                const customDispenseRow = `
                    <tr id="purchase-${response.purchase_id}">
                        <th scope="row">${itemName}</th>
                        <td>0.0g</td>
                        <td>£${parseFloat(itemCost).toFixed(2)}</td>
                        <td>${response.formattedDate}</td>
                        <td>
                            <button class="btn btn-danger btn-sm remove-purchase" 
                                    data-id="${response.purchase_id}"
                                    data-pin-url="${response.pin_url}"
                                    data-url="${response.remove_url}">
                                Remove
                            </button>
                        </td>
                    </tr>
                `;
                $('#purchase-table tbody').append(customDispenseRow);
                //Update total cost
                $('#total-cost-text').text(`Total Cost: £${response.totalCost}`);   
                
                //Set dropdown back to default
                dropdown.selectedIndex = 0;

            } else {
                alert("Error: " + response.message);
            }
        },
        error: function() {
            alert("Failed to add item.");
        }
    });
});

//Confirm payment is clicked
$(document).on('click', '#confirm-payment', function() {
    //Gets if user decided to use points, will need to pass this after payment to deduct used points from user
    const usingPoints = $('#using-points').is(':checked');
    $('#using-points-hidden').val(usingPoints);
    
    //Submit to redirect user
    $('#payment-form').submit();
});

//Cancel order is clicked
$(document).on('click', '#cancel-order', function() {
    const pinURL = $(this).data('pin-url'); //Gets URL for Flask route which validates employee pin
    //Prompting for PIN input
    const pin = prompt("Enter employee pin:");
    if(!pin)
    {
        alert("Employee pin required to cancel order.");
        return;
    }

    //AJAX checking the pin is in Employee table
    $.ajax({
        url: pinURL, // Flask route to validate PIN
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ pin: pin }),
        success: function(response) 
        {   
            //If employee pin is valid
            if (response.validPin) 
            {
                //Submit cancel order button
                $('#cancel-order-form').submit();
            }
            else
            {
                //If AJAX reponse returns pin as invalid
                alert("PIN invalid.");
            }
        },
        //If error in AJAX response
        error: function() 
        {
            alert("An error occurred while validating the PIN.");
        }
    });
});

//Request refund is clicked
$(document).on('click', '#request-refund-button', function() {
    const validationURL =  $(this).data('url'); //Gets URL for Flask route which validates the refund request
    const refundURL = $(this).data('refund-url'); //Gets URL for Flask route which starts the refund session

    var refundOrderID = $('#refundOrderID').val();

    if (isNaN(refundOrderID) || refundOrderID <= 0) {
        alert("Order ID must be a positive number and not empty.");
        return;
    }

    refundOrderID = parseInt(refundOrderID);

    const pinURL = $(this).data('pin-url'); //Gets URL for Flask route which validates employee pin
    //Prompting for PIN input
    const pin = prompt("Enter employee pin:");
    if(!pin)
    {
        alert("Employee pin required to request refund.");
        return;
    }

    //AJAX checking the pin is in Employee table
    $.ajax({
        url: pinURL, // Flask route to validate PIN
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ pin: pin }),
        success: function(response) 
        {   
            //If employee pin is valid
            if (response.validPin) 
            {
                //AJAX to validate the refund request
                $.ajax({
                    url: validationURL, //Flask route which validates refund request
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify
                    ({ refundOrderID: refundOrderID }),
                    success: function(response)
                    {
                        if (response.success) 
                        {   
                            refundAmount = parseFloat(response.refundAmount)
                            refundPoints = parseInt(response.refundPoints)
                            //If success start refund session with stripe
                            $.ajax({
                                url: refundURL, //Flask route which validates sends refund request
                                type: 'POST',
                                contentType: 'application/json',
                                data: JSON.stringify
                                ({ 
                                    refundOrderID: refundOrderID,
                                    refundAmount: refundAmount,
                                    refundPoints: refundPoints
                                }),
                                success: function(response) {
                                    if (response.success) {   
                                        window.location.replace("/home/scanrfid")
                                    } 
                                    else 
                                    {
                                        alert("Error: " + response.message); //Alerts user of failure
                                    }
                                },
                                error: function() 
                                {
                                    alert("An unexpected error occurred while starting the refund session."); //Alerts user of AJAX failure
                                }
                            });
                        } 
                        else 
                        {
                            alert("Error: " + response.message); //Alerts user of failure
                        }
                    },
                    error: function() 
                    {
                        alert("An unexpected error occurred while validating the refund."); //Alerts user of AJAX failure
                    }
                });
            }
            else
            {
                //If AJAX reponse returns pin as invalid
                alert("PIN invalid.");
            }
        },
        //If error in AJAX response
        error: function() 
        {
            alert("An error occurred while validating the PIN.");
        }
    });
});

