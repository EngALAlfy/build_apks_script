import socket
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from server.discovery import Discovery, discover_addresses, normalize_name, usable_ipv4

class DiscoveryTests(unittest.TestCase):
    def adapter(self,name,address,index):
        return SimpleNamespace(name=name,nice_name=name,index=index,ips=[SimpleNamespace(ip=address)])

    def test_normalize_stable_names(self):
        self.assertEqual(normalize_name('APK-Builder'),'apk-builder.local.')
        self.assertEqual(normalize_name('apk-builder.local.'),'apk-builder.local.')
        for invalid in ('','-bad','bad-','bad name','bad.example.com','x'*64,'http://name.local'):
            with self.assertRaises(ValueError,msg=invalid):normalize_name(invalid)

    def test_only_usable_ipv4_is_advertised(self):
        self.assertTrue(usable_ipv4('192.168.1.8'))
        for invalid in ('127.0.0.1','169.254.1.2','224.0.0.251','0.0.0.0','::1',('fe80::1',0,3),'not-an-address'):
            self.assertFalse(usable_ipv4(invalid))

    def test_physical_lan_is_preferred_over_virtual_and_vpn_adapters(self):
        adapters=[self.adapter('Intel Ethernet','192.168.1.8',3),self.adapter('Hyper-V Virtual Ethernet Adapter','172.29.0.1',4),self.adapter('VPN Adapter','10.0.0.5',5)]
        with patch('server.discovery.ifaddr.get_adapters',return_value=adapters),patch('server.discovery.preferred_address',return_value='10.0.0.5'):
            self.assertEqual(discover_addresses(),['192.168.1.8'])
            self.assertEqual(discover_addresses('4'),['172.29.0.1'])
            self.assertEqual(discover_addresses('Intel Ethernet'),['192.168.1.8'])
            self.assertEqual(discover_addresses('missing'),[])

    def test_waits_for_lan_instead_of_publishing_wsl_only(self):
        with patch('server.discovery.ifaddr.get_adapters',return_value=[self.adapter('vEthernet WSL','172.29.0.1',4)]):
            self.assertEqual(discover_addresses(),[])

    def test_explicit_bind_and_loopback(self):
        self.assertEqual(discover_addresses(bind_address='192.168.1.8'),['192.168.1.8'])
        self.assertEqual(discover_addresses(bind_address='127.0.0.1'),[])

    def test_service_has_real_hostname_and_no_private_configuration(self):
        zc=Mock()
        d=Discovery('apk-builder',8080)
        try:
            with patch('server.discovery.discover_addresses',return_value=['192.168.1.8']),patch('server.discovery.Zeroconf',return_value=zc):
                d.refresh()
            info=zc.register_service.call_args.args[0]
            self.assertEqual(info.server,'apk-builder.local.')
            self.assertEqual(info.port,8080)
            self.assertEqual(info.addresses,[socket.inet_aton('192.168.1.8')])
            self.assertEqual(info.properties,{b'path':b'/',b'title':b'APK Builder'})
            self.assertEqual(d.status()['url'],'http://apk-builder.local:8080')
            self.assertEqual(d.status()['status'],'advertised')
        finally:d.close()
        zc.unregister_service.assert_called_once()

    def test_ip_change_rebinds_and_reannounces_the_same_name(self):
        first,second=Mock(),Mock()
        d=Discovery()
        try:
            with patch('server.discovery.discover_addresses',side_effect=[['192.168.1.8'],['192.168.1.9'],['192.168.1.9']]),patch('server.discovery.Zeroconf',side_effect=[first,second]) as create:
                d.refresh();d.refresh();d.refresh()
            self.assertEqual(create.call_count,2)
            first.close.assert_called_once()
            self.assertEqual(second.register_service.call_args.args[0].server,'apk-builder.local.')
            self.assertEqual(d.status()['addresses'],['192.168.1.9'])
        finally:d.close()

    def test_no_interface_is_nonfatal(self):
        d=Discovery()
        with patch('server.discovery.discover_addresses',return_value=[]),patch('server.discovery.Zeroconf') as create:
            d.refresh()
        self.assertEqual(d.status()['status'],'unavailable')
        create.assert_not_called()

    def test_failed_registration_does_not_withdraw_someone_elses_record(self):
        zc=Mock();zc.register_service.side_effect=OSError('name conflict')
        d=Discovery()
        with patch('server.discovery.discover_addresses',return_value=['192.168.1.8']),patch('server.discovery.Zeroconf',return_value=zc):
            with self.assertRaises(OSError):d.refresh()
        d.close()
        zc.unregister_service.assert_not_called()
        zc.close.assert_called_once()

    def test_disabled_mode_does_not_open_multicast_sockets(self):
        d=Discovery(enabled=False)
        with patch('server.discovery.Zeroconf') as create:d.start();d.close()
        self.assertEqual(d.status()['status'],'disabled')
        create.assert_not_called()

if __name__=='__main__':unittest.main()
