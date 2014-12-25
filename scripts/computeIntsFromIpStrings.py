#!/usr/bin/env python

# Given a file in which each line is an IP address string,
# followed by a comma and a number that indicates
# how often that IP address occurred, output a file with
# each line's IP address replaced by its integer equivalent.
#
# Creates an outfile name constructed like this:
#    Chop .csv off infileName
#    add '_ints.csv'
#
# Example file:
#     "",16243
#     "1.0.137.96",45
#     "1.0.138.212",4
#     "1.0.159.37",4
#
# Without the double quotes works as well.


from __future__ import print_function
import sys
import os

if len(sys.argv) != 2 or sys.argv[1] == '-h' or sys.argv[1] == '--help':
  print("Usage: computeIntFromIpStrings.py <file name of file one IP string per line>")
  sys.exit()

fileWithIpStrings = sys.argv[1]
(pathNoExt,ext) = os.path.splitext(fileWithIpStrings)
outFile = pathNoExt + '_ints.csv'

with open(fileWithIpStrings, 'r') as inFd:
  with open(outFile, 'w') as outFd:
    for line in inFd:
      try:
	(ipStr,frequency) = line.split(',')
	ipStr = ipStr.strip('"')
	if len(ipStr) == 0:
	  continue
	(oct0,oct1,oct2,oct3) = ipStr.split('.')
      except ValueError:
	# Given ip str does not contain four octets:
	print("Warning: line '%s' is not an IP address (continuing with next line)." % line)
	continue
      ipNum = int(oct3) + (int(oct2) * 256) + (int(oct1) * 256 * 256) + (int(oct0) * 256 * 256 * 256)
      outFd.write(str(ipNum) + ',' + str(frequency))
