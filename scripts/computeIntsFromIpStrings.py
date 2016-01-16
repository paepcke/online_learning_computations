#!/usr/bin/env python
# Copyright (c) 2014, Stanford University
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


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
