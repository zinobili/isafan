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
