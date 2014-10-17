#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# UDP Hole Punching wrapper proxy for ggpofba-ng
#
#  (c) 2014 Pau Oliva Fora (@pof)
#  (c) 2010 Koen Bollen <meneer koenbollen nl>
#   https://gist.github.com/koenbollen/464613
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#

import sys
import os
import socket
from select import select
from subprocess import Popen, PIPE
import struct
import threading
import Queue
import time

def bytes2addr( bytes ):
	"""Convert a hash to an address pair."""
	if len(bytes) != 6:
		raise ValueError, "invalid bytes"
	host = socket.inet_ntoa( bytes[:4] )
	port, = struct.unpack( "H", bytes[-2:] )
	return host, port


def start_fba(quark):

	FBA="ggpofba-ng.exe"

	if not os.path.isfile(FBA):
		print >>sys.stderr, "Can't find", FBA
		os._exit(1)

	# try to find wine
	wine="/Applications/Wine.app/Contents/Resources/bin/wine"
	if not os.path.isfile(wine):
		wine="/usr/bin/wine"
	if not os.path.isfile(wine):
		wine='/usr/local/bin/wine'
	if not os.path.isfile(wine):
		# assume we are on windows
		args=[FBA, quark]
	else:
		args=[wine, FBA, quark]

	try:
		p = Popen(args)
	except OSError:
		print >>sys.stderr, "Can't execute", FBA
		os._exit(1)
	return p

def udp_proxy(quark,q):

	master = ("g.x90.es", 7000)
	port = 7001
	l_sockfd = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
	l_sockfd.bind( ("127.0.0.1", port) )
	#print "listening on 127.0.0.1:%d (udp)" % port

	fba_pid=start_fba(quark)
	q.put(fba_pid)

	#use only the challenge id for the hole punching server
	quark = quark.split(",")[2]

	sockfd = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
	sockfd.sendto( quark, master )
	data, addr = sockfd.recvfrom( len(quark)+3 )
	if data != "ok "+quark:
		print >>sys.stderr, "unable to request!"
		os._exit(1)
	sockfd.sendto( "ok", master )
	#print >>sys.stderr, "request sent, waiting for partner in quark '%s'..." % quark
	print >>sys.stderr, "request sent, waiting for partner in quark..."
	data, addr = sockfd.recvfrom( 6 )

	target = bytes2addr(data)
	#print >>sys.stderr, "connected to %s:%d" % target
	print >>sys.stderr, "connected to target"

	# first request using blocking sockets:
	emudata, emuaddr = l_sockfd.recvfrom(16384)
	if emudata:
		sockfd.sendto( emudata, target )

	peerdata, peeraddr = sockfd.recvfrom(16384)
	if peerdata:
		l_sockfd.sendto( peerdata, emuaddr )

	# now continue the game using nonblocking:
	l_sockfd.setblocking(0)
	sockfd.setblocking(0)

	while True:

		rfds,_,_ = select( [sockfd,l_sockfd], [], [], 0.1)
		if l_sockfd in rfds:
			emudata, emuaddr = l_sockfd.recvfrom(16384)
			if emudata:
				sockfd.sendto( emudata, target )
		if sockfd in rfds:
			peerdata, peeraddr = sockfd.recvfrom(16384)
			if peerdata:
				l_sockfd.sendto( peerdata, emuaddr )

	sockfd.close()
	l_sockfd.close()
	os._exit(0)

def process_checker(q):

	time.sleep(15)
	fba_p=q.get()
	print >>sys.stderr, "FBA pid:", int(fba_p.pid)

	while True:
		time.sleep(5)
		fba_status=fba_p.poll()
		#print "FBA STATUS:", str(fba_status)
		if fba_status!=None:
			print >>sys.stderr, "killing process"
			os._exit(0)

def main():

	quark=''
	try:
		quark = sys.argv[1].strip()
	except (IndexError, ValueError):
		pass

	if quark.startswith('quark:served'):
		q = Queue.Queue()
		t = threading.Thread(target=process_checker, args=(q,))
		t.setDaemon(True)
		t.start()
		udp_proxy(quark,q)
		t.join()
	else:
		start_fba(quark)

if __name__ == "__main__":
	main()