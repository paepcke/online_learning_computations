#!/bin/bash

# Sources prepEngagementAnalysis.sql to create Misc.Activities
# table. That table is needed for time engagement activities.

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
