import pytest

#! Only testing two parameters which should fail, further success and fail parameters tested manually
@pytest.mark.parametrize("refundOrderID, expected_message", [
    (9999999, "Order ID not found."),  #Invalid order
    (2, "Order already refunded."),  #Order which has already been already refunded
])
def test_validate_refund(client, refundOrderID, expected_message):
    response = client.post("refund/validate_refund", json={"refundOrderID": refundOrderID})
    data = response.get_json()

    assert data["message"] == expected_message
