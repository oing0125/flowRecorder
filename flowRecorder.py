#!/usr/bin/env python
"""
Use DPKT to read in a pcap file, organise packets into flows, and print out the flow records
"""
import dpkt
import pcapy
import socket
import hashlib
import pandas as pd
import numpy as np
from collections import defaultdict
from dpkt.compat import compat_ord
# from openpyxl import Workbook


def mac_addr(address):
    """Convert a MAC address to a readable/printable string

       Args:
           address (str): a MAC address in hex form (e.g. '\x01\x02\x03\x04\x05\x06')
       Returns:
           str: Printable/readable MAC address
    """
    return ':'.join('%02x' % compat_ord(b) for b in address)



def inet_to_str(inet):
    """Convert inet object to a string

        Args:
            inet (inet struct): inet network address
        Returns:
            str: Printable/readable IP address
    """
    # First try ipv4 and then ipv6
    try:
        return socket.inet_ntop(socket.AF_INET, inet)
    except ValueError:
        return socket.inet_ntop(socket.AF_INET6, inet)



def is_flow_record_present(key,flow_cache):
  if key in flow_cache:
      # print('Flow Record is present in the Flow Cache')
      return True
  else:
      # print('Flow Record is NOT present in the Flow Cache')
      return False



# build the flow record
def create_flow_record(flow_id,flow_cache,timestamp, ip):
    # print('Creating the flow record')
    # flow_cache[flow_id]['bwd_pkt_flow_id'] = bwd_id
    flow_cache[flow_id]['src_ip'] = inet_to_str(ip.src)
    flow_cache[flow_id]['src_port'] = ip.data.sport
    flow_cache[flow_id]['dst_ip'] = inet_to_str(ip.dst)
    flow_cache[flow_id]['dst_port'] = ip.data.dport
    flow_cache[flow_id]['proto'] = ip.p
    flow_cache[flow_id]['flowStart'] = timestamp
    flow_cache[flow_id]['flowEnd'] = timestamp
    flow_cache[flow_id]['flowDuration'] = (timestamp - flow_cache[flow_id]['flowStart'])
    flow_cache[flow_id]['pktTotalCount'] = 1
    flow_cache[flow_id]['octetTotalCount'] = ip.len

# build the flow record
def create_biflow_record(flow_id,flow_cache,timestamp, ip, bwd_id):
    # print('Creating the flow record')
    flow_cache[flow_id]['bwd_pkt_flow_id'] = bwd_id
    flow_cache[flow_id]['src_ip'] = inet_to_str(ip.src)
    flow_cache[flow_id]['dst_ip'] = inet_to_str(ip.dst)
    flow_cache[flow_id]['src_port'] = ip.data.sport
    flow_cache[flow_id]['dst_port'] = ip.data.dport
    flow_cache[flow_id]['proto'] = ip.p

    flow_cache[flow_id]['BI_flowStart'] = timestamp
    flow_cache[flow_id]['BI_flowEnd'] = timestamp
    flow_cache[flow_id]['BI_flowDuration'] = (timestamp - flow_cache[flow_id]['BI_flowStart'])
    flow_cache[flow_id]['BI_pktTotalCount'] = 1
    flow_cache[flow_id]['BI_octetTotalCount'] = ip.len

    flow_cache[flow_id]['F_flowStart'] = timestamp
    flow_cache[flow_id]['F_flowEnd'] = timestamp
    flow_cache[flow_id]['F_flowDuration'] = (timestamp - flow_cache[flow_id]['F_flowStart'])
    flow_cache[flow_id]['F_pktTotalCount'] = 1
    flow_cache[flow_id]['F_octetTotalCount'] = ip.len

    flow_cache[flow_id]['B_flowStart'] = 0
    flow_cache[flow_id]['B_flowEnd'] = 0
    flow_cache[flow_id]['B_flowDuration'] = 0
    flow_cache[flow_id]['B_pktTotalCount'] = 0
    flow_cache[flow_id]['B_octetTotalCount'] = 0



# update the flow record
def update_flow_record(flow_id,flow_cache,timestamp,ip):
    # print('Updating the flow record')
    flow_cache[flow_id]['flowEnd'] = timestamp
    flow_cache[flow_id]['flowDuration'] = (timestamp - flow_cache[flow_id]['flowStart'])
    flow_cache[flow_id]['pktTotalCount'] += 1
    flow_cache[flow_id]['octetTotalCount'] += ip.len

# update the flow record
def update_biflow_record(flow_id,flow_cache,timestamp,ip, dir):
    # print('Updating the flow record')
    flow_cache[flow_id]['BI_flowEnd'] = timestamp
    flow_cache[flow_id]['BI_flowDuration'] = (timestamp - flow_cache[flow_id]['BI_flowStart'])
    flow_cache[flow_id]['BI_pktTotalCount'] += 1
    flow_cache[flow_id]['BI_octetTotalCount'] += ip.len
    if dir == 'f':
        flow_cache[flow_id]['F_flowEnd'] = timestamp
        flow_cache[flow_id]['F_flowDuration'] = (timestamp - flow_cache[flow_id]['F_flowStart'])
        flow_cache[flow_id]['F_pktTotalCount'] += 1
        flow_cache[flow_id]['F_octetTotalCount'] += ip.len
    else:
        if flow_cache[flow_id]['B_flowStart'] == 0:
            flow_cache[flow_id]['B_flowStart'] = timestamp
        flow_cache[flow_id]['B_flowEnd'] = timestamp
        flow_cache[flow_id]['B_flowDuration'] = (timestamp - flow_cache[flow_id]['B_flowStart'])
        flow_cache[flow_id]['B_pktTotalCount'] += 1
        flow_cache[flow_id]['B_octetTotalCount'] += ip.len



# Print the contents of the flow cache
def show_flow_cache(f_cache):
    for f_id, f_info in f_cache.items():
        print("\nFlow ID            :", f_id)
        for key in f_info:
            print('{:<19s}: {}'.format(key, str(f_info[key])))



def process_packets(pcap,mode):
    """Organises each packet in a pcap into a flow record (flow cache)

       Args:
           pcap: dpkt pcap reader object (dpkt.pcap.Reader)
    """

    # Create an empty flow cache (nested dictionary)
    flow_cache = defaultdict(dict)

    # For each packet in the pcap process the contents
    for timestamp, pkt in pcap:

        # print(timestamp, len(pkt))

        # Make sure the Ethernet data contains an IP packet otherwise just skip processing
        if not isinstance(dpkt.ethernet.Ethernet(pkt).data, dpkt.ip.IP):
            # print('Non IP Packet type not supported %s\n' % eth.data.__class__.__name__)
            continue

        # Print out the timestamp in UTC
        # print('Timestamp: ', str(datetime.datetime.utcfromtimestamp(timestamp)))

        # Unpack the Ethernet frame
        eth = dpkt.ethernet.Ethernet(pkt)
        # print('Ethernet Frame: ', mac_addr(eth.src), mac_addr(eth.dst))

        # Now unpack the data within the Ethernet frame (the IP packet)
        ip = eth.data

        # Now check if this is an ICMP packet
        if isinstance(ip.data, dpkt.icmp.ICMP):
            # print('ICMP packet detected\n')
            continue

        # Now check if this is an ICMP packet
        if isinstance(ip.data, dpkt.pim.PIM):
           # print('PIM detected\n')
           continue

        # Now check if this is an ICMP packet
        if isinstance(ip.data, dpkt.ip6.IP6):
           # print('IPv6 detected\n')
           continue

        # calculate the flow ID and backward flow ID
        flow_id = (hashlib.md5(
            (inet_to_str(ip.src) + ' ' + str(ip.data.sport) + ' ' + inet_to_str(ip.dst) + ' ' + str(ip.data.dport) + ' ' + str(ip.p)).encode(
                'utf-8'))).hexdigest()

        bwd_pkt_flow_id = (hashlib.md5(
            (inet_to_str(ip.dst) + ' ' + str(ip.data.dport) + ' ' + inet_to_str(ip.src) + ' ' + str(ip.data.sport) + ' ' + str(ip.p)).encode(
                'utf-8'))).hexdigest()

        if mode == "u":
            if is_flow_record_present(flow_id,flow_cache) == True:
                update_flow_record(flow_id, flow_cache, timestamp, ip)
            else:
                create_flow_record(flow_id, flow_cache, timestamp, ip)
        elif mode == "b":
            if is_flow_record_present(flow_id,flow_cache) == True:
                update_biflow_record(flow_id, flow_cache, timestamp, ip, 'f')
            elif is_flow_record_present(bwd_pkt_flow_id, flow_cache) == True:
                update_biflow_record(bwd_pkt_flow_id, flow_cache, timestamp, ip, 'b')
            else:
                create_biflow_record(flow_id, flow_cache, timestamp, ip, bwd_pkt_flow_id)

    return flow_cache


def sniff(interface):

    global flow_cache
    flow_cache = defaultdict(dict)

    # dev = 'en0'
    dev = interface
    maxlen = 65535  # max size of packet to capture
    promiscuous = 1  # promiscuous mode?
    read_timeout = 100  # in milliseconds
    sniffer = pcapy.open_live(dev, maxlen, promiscuous, read_timeout)

    # filter = 'udp or tcp'
             # 'ip proto \\tcp'
    # cap.setfilter(filter)

    try:
        while True:
            # Grab the next header and packet buffer
            # header, raw_buf = sniffer.next()
            # process_packet(header, raw_buf)
            sniffer.loop(0, process_packet)
    except KeyboardInterrupt:
        print("\n\nSIGINT (Ctrl-c) detected. Exitting...")
        pass

    # show_flow_cache(flow_cache)
    # df = pd.DataFrame.from_dict(flow_cache, orient='index')
    # df.index.name = 'flow_id'
    # df.reset_index(inplace=True)
    # df.replace(0, np.NAN, inplace=True)
    # print(df)

    return flow_cache



def process_packet(hdr, buf):

    global flow_cache

    # print (hdr)
    # print('%s: captured %d bytes, truncated to %d bytes'
    #       % (datetime.datetime.now(), hdr.getlen(), hdr.getcaplen()))

    sec, ms = hdr.getts()
    # print(sec, ms)
    timestamp = sec + ms / 1000000
    # print(timestamp)


    eth = dpkt.ethernet.Ethernet(buf)
    ip = eth.data

    # Make sure the Ethernet data contains an IP packet otherwise just stop processing
    if not isinstance(ip, dpkt.ip.IP):
        # print('%s packet type is not supported\n' % eth.data.__class__.__name__)
        return

    # Now check if this is an ICMP packet
    if isinstance(ip.data, dpkt.icmp.ICMP):
        print('ICMP packet detected. Skipping parsing.\n')
        return

    # Now check if this is an ICMP packet
    if isinstance(ip.data, dpkt.igmp.IGMP):
        print('IGMP packet detected. Skipping parsing.\n')
        return

    # calculate the flow ID and backward flow ID
    flow_id = (hashlib.md5(
        (inet_to_str(ip.src) + ' ' + str(ip.data.sport) + ' ' + inet_to_str(ip.dst) + ' ' + str(ip.data.dport) + ' ' + str(ip.p)).encode(
            'utf-8'))).hexdigest()

    bwd_pkt_flow_id = (hashlib.md5(
        (inet_to_str(ip.dst) + ' ' + str(ip.data.dport) + ' ' + inet_to_str(ip.src) + ' ' + str(ip.data.sport) + ' ' + str(ip.p)).encode(
            'utf-8'))).hexdigest()

    if is_flow_record_present(flow_id, flow_cache) == True:
        update_flow_record(flow_id, flow_cache, timestamp, ip)
    else:
        create_flow_record(flow_id, flow_cache, timestamp, ip)



if __name__ == '__main__':

    import click

    # global control
    # global flow_cache

    @click.command()
    @click.option('-d', '--direction', 'direction', help='The directionality of measurement.')
    @click.option('-i', '--interface', 'interface', help='The interface for live packet capture.')
    @click.option('-f', '--file', 'file', help='PCAP file for parsing.')


    def main(direction, interface, file):
        """
            A packet parser tool. It parses the packets and organize them into flow records. The tool has two options.

            1. Live packet capture from an interface card.
            2. Parsing packet in a PCAP file.
           """

        if direction not in ['u', 'b']:
            print("Invalid or wrong input for flow directionality.\n"
              "Packets will be organized into flows in one-direction.\n")
            dir = 'u'
        else:
            if direction == "u":
                print("Packets will be organized into flows in one-direction.\n")
            if direction == "b":
                print("Packets will be organized into flows in bi-direction.\n")
            dir = direction

        if interface is None:
            pass
        else:

            f_cache = sniff(interface)

            df = pd.DataFrame.from_dict(f_cache, orient='index')
            df.index.name = 'flow_id'
            df.reset_index(inplace=True)
            df.replace(0, np.NAN, inplace=True)

            pd.options.display.float_format = '{:.6f}'.format

            print(df)


        if file is None:
            pass
        else:
            with open(file, 'rb') as file:
                pcap = dpkt.pcap.Reader(file)

                # process packets
                # 'u' is for unidirectional flows, 'b' is for bidirectional flows
                f_cache = process_packets(pcap,dir)

            # show_flow_cache(f_cache)
            df = pd.DataFrame.from_dict(f_cache, orient='index')
            df.index.name = 'flow_id'
            df.reset_index(inplace=True)
            df.replace(0, np.NAN, inplace=True)

            print(df)

            # print(df.dtypes)

            # write into CSV file
            # df.to_csv('out.csv')


    main()


    # https://jon.oberheide.org/blog/2008/08/25/dpkt-tutorial-1-icmp-echo/
    # https://jon.oberheide.org/blog/2008/10/15/dpkt-tutorial-2-parsing-a-pcap-file/
    # https://jon.oberheide.org/blog/2008/12/20/dpkt-tutorial-3-dns-spoofing/
    # https://jon.oberheide.org/blog/2009/03/25/dpkt-tutorial-4-as-paths-from-mrt-bgp/



    # dev = 'en0'
    #
    # expr = 'udp or tcp'
    #
    # maxlen = 65535  # max size of packet to capture
    # promiscuous = 1  # promiscuous mode?
    # read_timeout = 100  # in milliseconds
    # max_pkts = 5  # number of packets to capture; -1 => no limit
    #
    # cap = pcapy.open_live(dev, maxlen, promiscuous, read_timeout)
    # cap.setfilter(expr)
    #
    #
    # while (1):
    #     (header, packet) = cap.next()
    #     print(header.src)
    #
    #     print("TU")
    #     # print ('%s: captured %d bytes, truncated to %d bytes' %(datetime.datetime.now(), header.getlen(), header.getcaplen()))
    #     parse_packet(packet)


    # with open('t.pcap', 'rb') as file:
    #     pcap = dpkt.pcap.Reader(file)
    #
    #     # process packets
    #     # 'u' is for unidirectional flows, 'b' is for bidirectional flows
    #     f_cache = process_packets(pcap,"b")
    #
    # show_flow_cache(f_cache)
    #
    # df = pd.DataFrame.from_dict(f_cache, orient='index')
    # df.index.name = 'flow_id'
    # df.reset_index(inplace=True)
    # df.replace(0, np.NAN, inplace=True)
    #
    # # print(df.dtypes)
    #
    # # write into CSV file
    # df.to_csv('out.csv')
    #
    # # write into XLSX file
    # # writer = pd.ExcelWriter('output.xlsx')
    # # df.to_excel(writer, 'Sheet1')
    # # writer.save()
    #
    #     # print(df.values)
    #
    # # print the number of flow records in the flow cache
    # # print("\n", len(f_cache.keys()))