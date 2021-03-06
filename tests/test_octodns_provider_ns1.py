#
#
#

from __future__ import absolute_import, division, print_function, \
    unicode_literals

from mock import Mock, call, patch
from nsone.rest.errors import AuthException, ResourceException
from unittest import TestCase

from octodns.record import Delete, Record, Update
from octodns.provider.ns1 import Ns1Provider
from octodns.zone import Zone


class DummyZone(object):

    def __init__(self, records):
        self.data = {
            'records': records
        }


class TestNs1Provider(TestCase):
    zone = Zone('unit.tests.', [])
    expected = set()
    expected.add(Record.new(zone, '', {
        'ttl': 32,
        'type': 'A',
        'value': '1.2.3.4',
    }))
    expected.add(Record.new(zone, 'foo', {
        'ttl': 33,
        'type': 'A',
        'values': ['1.2.3.4', '1.2.3.5'],
    }))
    expected.add(Record.new(zone, 'cname', {
        'ttl': 34,
        'type': 'CNAME',
        'value': 'foo.unit.tests.',
    }))
    expected.add(Record.new(zone, '', {
        'ttl': 35,
        'type': 'MX',
        'values': [{
            'preference': 10,
            'exchange': 'mx1.unit.tests.',
        }, {
            'preference': 20,
            'exchange': 'mx2.unit.tests.',
        }]
    }))
    expected.add(Record.new(zone, 'naptr', {
        'ttl': 36,
        'type': 'NAPTR',
        'values': [{
            'flags': 'U',
            'order': 100,
            'preference': 100,
            'regexp': '!^.*$!sip:info@bar.example.com!',
            'replacement': '.',
            'service': 'SIP+D2U',
        }, {
            'flags': 'S',
            'order': 10,
            'preference': 100,
            'regexp': '!^.*$!sip:info@bar.example.com!',
            'replacement': '.',
            'service': 'SIP+D2U',
        }]
    }))
    expected.add(Record.new(zone, '', {
        'ttl': 37,
        'type': 'NS',
        'values': ['ns1.unit.tests.', 'ns2.unit.tests.'],
    }))
    expected.add(Record.new(zone, '_srv._tcp', {
        'ttl': 38,
        'type': 'SRV',
        'values': [{
            'priority': 10,
            'weight': 20,
            'port': 30,
            'target': 'foo-1.unit.tests.',
        }, {
            'priority': 12,
            'weight': 30,
            'port': 30,
            'target': 'foo-2.unit.tests.',
        }]
    }))
    expected.add(Record.new(zone, 'sub', {
        'ttl': 39,
        'type': 'NS',
        'values': ['ns3.unit.tests.', 'ns4.unit.tests.'],
    }))

    nsone_records = [{
        'type': 'A',
        'ttl': 32,
        'short_answers': ['1.2.3.4'],
        'domain': 'unit.tests.',
    }, {
        'type': 'A',
        'ttl': 33,
        'short_answers': ['1.2.3.4', '1.2.3.5'],
        'domain': 'foo.unit.tests.',
    }, {
        'type': 'CNAME',
        'ttl': 34,
        'short_answers': ['foo.unit.tests.'],
        'domain': 'cname.unit.tests.',
    }, {
        'type': 'MX',
        'ttl': 35,
        'short_answers': ['10 mx1.unit.tests.', '20 mx2.unit.tests.'],
        'domain': 'unit.tests.',
    }, {
        'type': 'NAPTR',
        'ttl': 36,
        'short_answers': [
            '10 100 S SIP+D2U !^.*$!sip:info@bar.example.com! .',
            '100 100 U SIP+D2U !^.*$!sip:info@bar.example.com! .'
        ],
        'domain': 'naptr.unit.tests.',
    }, {
        'type': 'NS',
        'ttl': 37,
        'short_answers': ['ns1.unit.tests.', 'ns2.unit.tests.'],
        'domain': 'unit.tests.',
    }, {
        'type': 'SRV',
        'ttl': 38,
        'short_answers': ['12 30 30 foo-2.unit.tests.',
                          '10 20 30 foo-1.unit.tests.'],
        'domain': '_srv._tcp.unit.tests.',
    }, {
        'type': 'NS',
        'ttl': 39,
        'short_answers': ['ns3.unit.tests.', 'ns4.unit.tests.'],
        'domain': 'sub.unit.tests.',
    }]

    @patch('nsone.NSONE.loadZone')
    def test_populate(self, load_mock):
        provider = Ns1Provider('test', 'api-key')

        # Bad auth
        load_mock.side_effect = AuthException('unauthorized')
        zone = Zone('unit.tests.', [])
        with self.assertRaises(AuthException) as ctx:
            provider.populate(zone)
        self.assertEquals(load_mock.side_effect, ctx.exception)

        # General error
        load_mock.reset_mock()
        load_mock.side_effect = ResourceException('boom')
        zone = Zone('unit.tests.', [])
        with self.assertRaises(ResourceException) as ctx:
            provider.populate(zone)
        self.assertEquals(load_mock.side_effect, ctx.exception)
        self.assertEquals(('unit.tests',), load_mock.call_args[0])

        # Non-existant zone doesn't populate anything
        load_mock.reset_mock()
        load_mock.side_effect = \
            ResourceException('server error: zone not found')
        zone = Zone('unit.tests.', [])
        provider.populate(zone)
        self.assertEquals(set(), zone.records)
        self.assertEquals(('unit.tests',), load_mock.call_args[0])

        # Existing zone w/o records
        load_mock.reset_mock()
        nsone_zone = DummyZone([])
        load_mock.side_effect = [nsone_zone]
        zone = Zone('unit.tests.', [])
        provider.populate(zone)
        self.assertEquals(set(), zone.records)
        self.assertEquals(('unit.tests',), load_mock.call_args[0])

        # Existing zone w/records
        load_mock.reset_mock()
        nsone_zone = DummyZone(self.nsone_records)
        load_mock.side_effect = [nsone_zone]
        zone = Zone('unit.tests.', [])
        provider.populate(zone)
        self.assertEquals(self.expected, zone.records)
        self.assertEquals(('unit.tests',), load_mock.call_args[0])

    @patch('nsone.NSONE.createZone')
    @patch('nsone.NSONE.loadZone')
    def test_sync(self, load_mock, create_mock):
        provider = Ns1Provider('test', 'api-key')

        desired = Zone('unit.tests.', [])
        desired.records.update(self.expected)

        plan = provider.plan(desired)
        # everything except the root NS
        expected_n = len(self.expected) - 1
        self.assertEquals(expected_n, len(plan.changes))

        # Fails, general error
        load_mock.reset_mock()
        create_mock.reset_mock()
        load_mock.side_effect = ResourceException('boom')
        with self.assertRaises(ResourceException) as ctx:
            provider.apply(plan)
        self.assertEquals(load_mock.side_effect, ctx.exception)

        # Fails, bad auth
        load_mock.reset_mock()
        create_mock.reset_mock()
        load_mock.side_effect = \
            ResourceException('server error: zone not found')
        create_mock.side_effect = AuthException('unauthorized')
        with self.assertRaises(AuthException) as ctx:
            provider.apply(plan)
        self.assertEquals(create_mock.side_effect, ctx.exception)

        # non-existant zone, create
        load_mock.reset_mock()
        create_mock.reset_mock()
        load_mock.side_effect = \
            ResourceException('server error: zone not found')
        create_mock.side_effect = None
        got_n = provider.apply(plan)
        self.assertEquals(expected_n, got_n)

        # Update & delete
        load_mock.reset_mock()
        create_mock.reset_mock()
        nsone_zone = DummyZone(self.nsone_records + [{
            'type': 'A',
            'ttl': 42,
            'short_answers': ['9.9.9.9'],
            'domain': 'delete-me.unit.tests.',
        }])
        nsone_zone.data['records'][0]['short_answers'][0] = '2.2.2.2'
        nsone_zone.loadRecord = Mock()
        load_mock.side_effect = [nsone_zone, nsone_zone]
        plan = provider.plan(desired)
        self.assertEquals(2, len(plan.changes))
        self.assertIsInstance(plan.changes[0], Update)
        self.assertIsInstance(plan.changes[1], Delete)

        got_n = provider.apply(plan)
        self.assertEquals(2, got_n)
        nsone_zone.loadRecord.assert_has_calls([
            call('unit.tests', u'A'),
            call().update(answers=[u'1.2.3.4'], ttl=32),
            call('delete-me', u'A'),
            call().delete()
        ])
