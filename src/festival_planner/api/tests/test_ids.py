import base64

from festival_planner.api.ids import decode, decode_any, encode


def test_decode_round_trips():
    global_id = encode("Screening", "s-1")
    assert decode(global_id, "Screening") == "s-1"
    assert decode_any(global_id) == ("Screening", "s-1")


def test_decode_rejects_the_wrong_type():
    assert decode(encode("Venue", "v-1"), "Screening") is None


def test_decode_rejects_garbage():
    no_colon = base64.b64encode(b"nocolon").decode()
    for garbage in ("!!", "", no_colon):
        assert decode(garbage, "Screening") is None
        assert decode_any(garbage) is None
