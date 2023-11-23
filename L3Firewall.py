from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *
from pox.lib.util import dpidToStr
from pox.lib.addresses import EthAddr
from collections import namedtuple
import os
''' New imports here ... '''
import csv
import argparse
from pox.lib.packet.ethernet import ethernet, ETHER_BROADCAST
from pox.lib.addresses import IPAddr
import pox.lib.packet as pkt
from pox.lib.packet.arp import arp
from pox.lib.packet.ipv4 import ipv4
from pox.lib.packet.icmp import icmp
from collections import defaultdict

log = core.getLogger()
priority = 50000

l2config = "l2firewall.config"
l3config = "l3firewall.config"


class Firewall(EventMixin):

    def __init__(self, l2config, l3config):
        self.listenTo(core.openflow)
        self.disbaled_MAC_pair = []  # Shore a tuple of MAC pair which will be installed into the flow table of each switch.
        self.fwconfig = list()

        # New data structure for tracking source MAC to multiple source IP mapping
        self.source_mac_to_ips = defaultdict(set)
        id_counter = 1  # Initialize the id counter

        '''
        Read the CSV file
        '''
        if l2config == "":
            l2config = "l2firewall.config"

        if l3config == "":
            l3config = "l3firewall.config"
        with open(l2config, 'rb') as rules:
            csvreader = csv.DictReader(rules)  # Map into a dictionary
            for line in csvreader:
                # Read MAC address. Convert string to Ethernet address using the EthAddr() function.
                if line['mac_0'] != 'any':
                    mac_0 = EthAddr(line['mac_0'])
                else:
                    mac_0 = None

                if line['mac_1'] != 'any':
                    mac_1 = EthAddr(line['mac_1'])
                else:
                    mac_1 = None
                # Append to the array storing all MAC pair.
                # Append to the array storing all MAC pair if it's not already present
                if (mac_0, mac_1) not in self.disbaled_MAC_pair:
                    #self.disbaled_MAC_pair.append((mac_0, mac_1))
                    self.disbaled_MAC_pair.append((id_counter, mac_0, mac_1))
                #self.disbaled_MAC_pair.append((mac_0, mac_1))

        with open(l3config) as csvfile:
            log.debug("Reading log file !")
            self.rules = csv.DictReader(csvfile)
            for row in self.rules:
                log.debug("Saving individual rule parameters in rule dict !")
                s_ip = row['src_ip']
                d_ip = row['dst_ip']
                s_port = row['src_port']
                d_port = row['dst_port']
                print "src_ip, dst_ip, src_port, dst_port", s_ip, d_ip, s_port, d_port

        log.debug("Enabling Firewall Module")

    def replyToARP(self, packet, match, event):
        r = arp()
        r.opcode = arp.REPLY
        r.hwdst = match.dl_src
        r.protosrc = match.nw_dst
        r.protodst = match.nw_src
        r.hwsrc = match.dl_dst
        e = ethernet(type=packet.ARP_TYPE, src=r.hwsrc, dst=r.hwdst)
        e.set_payload(r)
        msg = of.ofp_packet_out()
        msg.data = e.pack()
        msg.actions.append(of.ofp_action_output(port=of.OFPP_IN_PORT))
        msg.in_port = event.port
        event.connection.send(msg)

    def allowOther(self, event):
        msg = of.ofp_flow_mod()
        match = of.ofp_match()
        action = of.ofp_action_output(port=of.OFPP_NORMAL)
        msg.actions.append(action)
        event.connection.send(msg)

    def installFlow(self, event, offset, srcmac, dstmac, srcip, dstip, sport, dport, nwproto):
        
        if srcmac is not None:
            print "Source MAC", srcmac
            # Check if the source MAC is in l2firewall.config, if so, block the traffic
            with open(l2config, 'rb') as rules:
                csvreader = csv.DictReader(rules)
                for line in csvreader:
                    mac_0 = EthAddr(line['mac_0'])
                    if srcmac == mac_0:
                        print("Blocking traffic from {srcmac} for port security.")
                        self.installFlow(event, priority, None, EthAddr(srcmac), None, None, None, None, None)
                        return  # Do not install the flow rule, effectively blocking the traffic

        msg = of.ofp_flow_mod()
        match = of.ofp_match()
        if srcip is not None:
            match.nw_src = IPAddr(srcip)
        if dstip is not None:
            match.nw_dst = IPAddr(dstip)
        
        if nwproto is not None:
            print("Value of nwproto:", nwproto)
            match.nw_proto = int(nwproto)
        match.dl_src = srcmac
        match.dl_dst = dstmac
        match.tp_src = sport
        match.tp_dst = dport
        match.dl_type = pkt.ethernet.IP_TYPE
        msg.match = match
        msg.hard_timeout = 0
        msg.idle_timeout = 200
        msg.priority = priority + offset
        msg.priority = min(max(priority + offset, 0), 65535)
        msg.flags = 0  # Set the flags field to 0
        event.connection.send(msg)

    def replyToIP(self, packet, match, event, fwconfig):
        srcmac = str(match.dl_src)
        dstmac = str(match.dl_src)
        sport = str(match.tp_src)
        dport = str(match.tp_dst)
        nwproto = str(match.nw_proto)

        with open(l3config) as csvfile:
            log.debug("Reading log file !")
            self.rules = csv.DictReader(csvfile)
            for row in self.rules:
                prio = row['priority']
                srcmac = row['src_mac']
                dstmac = row['dst_mac']
                s_ip = row['src_ip']
                d_ip = row['dst_ip']
                s_port = row['src_port']
                d_port = row['dst_port']
                nw_proto = row['nw_proto']

                log.debug("You are in the original code block ...")
                srcmac1 = EthAddr(srcmac) if srcmac != 'any' else None
                dstmac1 = EthAddr(dstmac) if dstmac != 'any' else None
                s_ip1 = s_ip if s_ip != 'any' else None
                d_ip1 = d_ip if d_ip != 'any' else None
                s_port1 = int(s_port) if s_port != 'any' else None
                d_port1 = int(d_port) if d_port != 'any' else None
                prio1 = int(prio) if prio != None else priority
                if nw_proto == "tcp":
                    nw_proto1 = pkt.ipv4.TCP_PROTOCOL
                elif nw_proto == "icmp":
                    nw_proto1 = pkt.ipv4.ICMP_PROTOCOL
                    s_port1 = None
                    d_port1 = None
                elif nw_proto == "udp":
                    nw_proto1 = pkt.ipv4.UDP_PROTOCOL
                else:
                    log.debug("PROTOCOL field is mandatory, Choose between ICMP, TCP, UDP")
                print (prio1, s_ip1, d_ip1, s_port1, d_port1, nw_proto1)
                self.installFlow(event, prio1, srcmac1, dstmac1, s_ip1, d_ip1, s_port1, d_port1, nw_proto1)
        self.allowOther(event)

    def _handle_ConnectionUp(self, event):
        ''' Add your logic here ... '''

        '''
        Iterate through the disabled_MAC_pair array, and for each
        pair, we install a rule in each OpenFlow switch
        '''
        self.connection = event.connection

        for (source, destination) in self.disbaled_MAC_pair:
            print source, destination
            message = of.ofp_flow_mod()  # OpenFlow message. Instructs a switch to install a flow
            match = of.ofp_match()  # Create a match
            match.dl_src = source  # Source address
            match.dl_dst = destination  # Destination address
            message.priority = 65535  # Set priority (between 0 and 65535)
            message.match = match
            event.connection.send(message)  # Send instruction to the switch

        log.debug("Firewall rules installed on %s", dpidToStr(event.dpid))

    def _handle_PacketIn(self, event):
        packet = event.parsed
        match = of.ofp_match.from_packet(packet)

        if match.dl_type == packet.ARP_TYPE and match.nw_proto == arp.REQUEST:
            self.replyToARP(packet, match, event)

        if match.dl_type == packet.IP_TYPE:
            ip_packet = packet.payload
            print "Ip_packet.protocol = ", ip_packet.protocol
            if ip_packet.protocol == ip_packet.TCP_PROTOCOL:
                log.debug("TCP it is !")

            src_mac_str = str(match.dl_src)
            src_ip = str(ip_packet.srcip)
            print "Source MAC", src_mac_str
            print "Source IP", src_ip
            #print "Source mac to IPs", source_mac_to_ips
            

            id_counter = 1

            # Check if this source MAC has multiple source IPs
            if src_mac_str not in self.source_mac_to_ips:
                self.source_mac_to_ips[src_mac_str] = set()

            # Check if this source MAC has multiple source IPs
            #if src_mac_str in self.source_mac_to_ips:
            #    print("entering 1st loop")
            #print(source_mac_to_ips[src_mac_str])
            if src_ip not in self.source_mac_to_ips[src_mac_str]:
                print "Detected multiple source IPs for", src_mac_str
                #self.source_mac_to_ips[src_mac_str].add(src_ip)
                self.source_mac_to_ips[src_mac_str].add(src_ip)
                #print(source_mac_to_ips[src_mac_str])
                # Add the source MAC to l2firewall.config for blocking if it's not already present
                mac_entry = "{}\n".format(src_mac_str)
                if mac_entry not in open(l2config).read():
                    with open(l2config, 'a') as l2config_file:
                        #config = "{},{}".format(id_counter, mac_entry)
                        #conf = config + ",any"
                        #conf = "{},{},any".format(id_counter, mac_entry)
                        conf = "{},{},{}".format(id_counter, mac_entry, "any")
                        #config = "{},{}".format(id_counter,mac_entry)
                        #conf = config + ",any"
                        l2config_file.write(conf)
                        #l2config_file.write(mac_entry)
                    id_counter += 1  # Increment the id counter
                # Add the source MAC to l2firewall.config for blocking
                #with open(l2config, 'a') as l2config_file:
                    #print("writing to l2firewall")
                    # Add the source MAC to l2firewall.config for blocking if it's not already present
                    #l2config_file.write("{}\n".format(src_mac_str))
                    #l2config_file.write(f"{src_mac_str}\n")
                    #print("updated l2firewall")

                # Install a flow rule to block traffic from the new source MAC
                self.installFlow(event, priority, None, EthAddr(src_mac_str), None, None, None, None, None)

            self.replyToIP(packet, match, event, self.rules)


def launch(l2config="l2firewall.config", l3config="l3firewall.config"):
    '''
    Starting the Firewall module
    '''
    parser = argparse.ArgumentParser()
    parser.add_argument('--l2config', action='store', dest='l2config',
                        help='Layer 2 config file', default='l2firewall.config')
    parser.add_argument('--l3config', action='store', dest='l3config',
                        help='Layer 3 config file', default='l3firewall.config')
    core.registerNew(Firewall, l2config, l3config)
