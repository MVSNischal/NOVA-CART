from app.services.orders import ALLOWED

def test_order_state_machine_is_strict():
    assert "PREPARING" in ALLOWED["SHOP_ACCEPTED"]
    assert "DELIVERED" not in ALLOWED["CREATED"]
    assert ALLOWED["DELIVERED"] == set()
