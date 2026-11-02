import ipaddress

from server import net


def test_usable_only_private_ipv4():
    assert net._usable("192.168.1.20")
    assert net._usable("10.4.4.4")
    assert net._usable("172.16.0.9")
    assert not net._usable("127.0.0.1")       # loopback
    assert not net._usable("169.254.1.1")     # link-local
    assert not net._usable("8.8.8.8")         # public
    assert not net._usable("not-an-ip")


def test_rank_prefers_home_lan_over_vpn_range():
    assert net._rank("192.168.0.1") < net._rank("172.16.0.1") < net._rank("10.8.0.1")


def test_lan_ips_returns_private_addresses_only():
    for ip in net.lan_ips():
        addr = ipaddress.ip_address(ip)
        assert addr.version == 4 and addr.is_private and not addr.is_loopback


# --- client_ip (X-Forwarded-For hop walking) ---------------------------------

from starlette.datastructures import Headers

PEER = "10.0.0.1"  # the TCP peer — on Render, its edge proxy


def _xff(*values: str) -> Headers:
    return Headers(raw=[(b"x-forwarded-for", v.encode()) for v in values])


def test_zero_hops_returns_peer_and_ignores_header():
    assert net.client_ip(_xff("203.0.113.7"), PEER, 0) == PEER
    assert net.client_ip(_xff("203.0.113.7"), PEER, -3) == PEER


def test_no_peer_and_no_header():
    assert net.client_ip(Headers(), None, 0) == "?"
    assert net.client_ip(Headers(), None, 1) == "?"


def test_one_hop_takes_rightmost_entry():
    assert net.client_ip(_xff("203.0.113.7"), PEER, 1) == "203.0.113.7"
    assert net.client_ip(_xff("1.1.1.1, 203.0.113.7"), PEER, 1) == "203.0.113.7"


def test_n_hops_take_nth_from_right():
    h = _xff("198.51.100.1, 203.0.113.7, 172.70.1.1")
    assert net.client_ip(h, PEER, 2) == "203.0.113.7"
    assert net.client_ip(h, PEER, 3) == "198.51.100.1"


def test_header_shorter_than_hops_yields_leftmost():
    assert net.client_ip(_xff("203.0.113.7"), PEER, 3) == "203.0.113.7"


def test_missing_or_empty_header_falls_back_to_peer():
    assert net.client_ip(Headers(), PEER, 1) == PEER
    assert net.client_ip(_xff(""), PEER, 1) == PEER
    assert net.client_ip(_xff(" , ,"), PEER, 1) == PEER


def test_spoofed_leftmost_entry_is_ignored():
    # client sends its own XFF; the one trusted proxy appends the real address
    h = _xff("6.6.6.6, 203.0.113.7")
    assert net.client_ip(h, PEER, 1) == "203.0.113.7"


def test_multiple_header_lines_are_joined_in_order():
    h = _xff("6.6.6.6", "203.0.113.7")
    assert net.client_ip(h, PEER, 1) == "203.0.113.7"


def test_garbage_entries_stop_the_walk():
    assert net.client_ip(_xff("not-an-ip"), PEER, 1) == PEER
    assert net.client_ip(_xff("203.0.113.7, garbage"), PEER, 2) == PEER
    # a bad entry beyond a good trusted one keeps the good one
    assert net.client_ip(_xff("garbage, 203.0.113.7"), PEER, 2) == "203.0.113.7"
    assert net.client_ip(_xff("1.2.3.4.5"), PEER, 1) == PEER
    assert net.client_ip(_xff("[::1"), PEER, 1) == PEER


def test_ports_and_ipv6_are_normalised():
    assert net.client_ip(_xff("203.0.113.7:51234"), PEER, 1) == "203.0.113.7"
    assert net.client_ip(_xff("[2001:DB8::1]:443"), PEER, 1) == "2001:db8::1"
    assert net.client_ip(_xff("2001:DB8:0::1"), PEER, 1) == "2001:db8::1"


def test_plain_mapping_headers_work():
    assert net.client_ip({"x-forwarded-for": "203.0.113.7"}, PEER, 1) == "203.0.113.7"
