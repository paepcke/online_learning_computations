#!/bin/bash
# Copyright (c) 2014, Stanford University
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


# Sources prepEngagementAnalysis.sql to create Misc.Activities
# table. That table is needed for time engagement activities
# computations.

USAGE="Usage: `basename $0` [-u username][-p][-pYourPwd]"

USERNAME=`whoami`
PASSWD=''
needPasswd=false
THIS_SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check whether given -pPassword, i.e. fused -p with a 
# pwd string:

for arg in $@
do
   # The sed -r option enables extended regex, which
   # makes the '+' metachar work. The -n option
   # says to print only if pattern matches:
   PASSWD=`echo $arg | sed -r -n 's/-p(.+)/\1/p'`
   if [ -z $PASSWD ]
   then
       continue
   else
       #echo "Pwd is:"$PASSWD
       break
   fi
done

# Use leading ':' in options list to have
# erroneous optons end up in the \? clause
# below:
while getopts ":u:ph" opt
do
  case $opt in
    u)
      USERNAME=$OPTARG
      shift
      shift
      ;;
    p)
      needPasswd=true
      shift
      ;;
    h)
      echo $USAGE
      exit
      ;;
    \?)
      # If the $PASSWD is set, we *assume* that 
      # the unrecognized option was a
      # -pMyPassword, and don't signal
      # an error. Therefore, if $PASSWD is 
      # set then illegal options are quietly 
      # ignored:
      if [ ! -z $PASSWD ]
      then 
	  continue
      else
	  echo $USAGE
	  exit 1
      fi
      ;;
  esac
done

if $needPasswd && [ -z $PASSWD ]
then
    # The -s option suppresses echo:
    read -s -p "Password for user '$USERNAME' on MySQL server: " PASSWD
    echo
fi

#*****************
#echo "UID: $USERNAME"
#echo "PWD: $PASSWD"
#exit 0
#*****************

# Load the .sql file that contains the 
# table creation and populating SQL code:
if [ -z $PASSWD ]
then
    mysql -u $USERNAME -e "USE Edx; source "$THIS_SCRIPT_DIR"/prepEngagementAnalysis.sql;"
else
    mysql -u $USERNAME -p$PASSWD -e "USE Edx; source "$THIS_SCRIPT_DIR/"prepEngagementAnalysis.sql;"
fi
