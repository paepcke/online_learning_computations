#!/bin/bash

# Compute engagement for all classes, or one given class.
# Computations occur in parallel, using engagement.py.

USAGE='Usage: '`basename $0`' yearAsYYYY [courseName]'

HELP='Compute engagement statistics for one or all classes. Arg yearAsYYYY: year of classes. Optionally: course name'

COURSE_NAME=''
YEAR=''
needPasswd=false
PASSWD=''
USERNAME=`whoami`

# ----------------------------- Process CLI Args -------------

# Execute getopt
ARGS=`getopt -o "u:pw:h" -l "user:,password,mysqlpwd:help" \
      -n "getopt.sh" -- "$@"`
 
#Bad arguments
# if [ $? -ne 0 ];
# then
#   exit 1
# fi
 
# A little magic
eval set -- "$ARGS"
 
# Now go through all the options
while true;
do
  case "$1" in
    -u|--user)
      shift
      # Grab the option value
      # unless it's null:
      if [ -n "$1" ]
      then
        USERNAME=$1
        shift
      else
	echo $USAGE
	exit 1
      fi;;
 
    -p|--password)
      needPasswd=true
      shift;;
 
    -w|--mysqlpwd)
      shift
      # Grab the option value:
      if [ -n "$1" ]
      then
        PASSWD=$1
	needPasswd=false
        shift
      else
	echo $USAGE
	exit 1
      fi;;
    -h|--help)
      echo $HELP
      shift;;
    --)
      shift
      break;;
  esac
done

if [ -z $1 ]
then
  echo $USAGE
  exit 1
fi
YEAR=$1
shift

if [ ! -z $1 ]
then
   COURSE_NAME=$1
fi

# ----------------------------- Process or Lookup the Password -------------

if $needPasswd
then
    # The -s option suppresses echo:
    read -s -p "Password for user '$USERNAME' on `hostname`'s MySQL server: " PASSWD
    echo
else
    # MySQL pwd may have been provided via the -w option:
    if [ -z $PASSWD ]
    then
	# Password was not provided with -w option.
        # Get home directory of whichever user will
        # log into MySQL:
	HOME_DIR=$(getent passwd $USERNAME | cut -d: -f6)
        # If the home dir has a readable file called mysql in its .ssh
        # subdir, then pull the pwd from there:
	if test -f $HOME_DIR/.ssh/mysql && test -r $HOME_DIR/.ssh/mysql
	then
	    PASSWD=`cat $HOME_DIR/.ssh/mysql`
	fi
    fi
fi

#*************
echo "Year: $YEAR"
echo "Course: '$COURSE_NAME'"
echo "User: '$USERNAME'"
echo "PWD: '$PASSWD'"
if [ -z $PASSWD ]
then
    echo "PWD empty"
else
    echo "PWD full"
fi
# exit
#*************

thisScriptDir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Get course names if needed:
mysql -u $USERNAME -p$PASSWD -e "use Edx; SELECT DISTINCT course_display_name FROM EventXtract;" | \
    sed 's/[\s|]//' | \
    sed '/^$/d' > /tmp/classNames.txt

rm /tmp/engagement_*

echo "Compute course engagement stats for $YEAR: `date`" >> /tmp/engagement.log
time parallel --gnu --progress --arg-file /tmp/classNames.txt $thisScriptDir/../learning_comps/engagement.py $YEAR ::: ${@};
echo "Compute course engagement stats for $YEAR done: `date`"  >> /tmp/engagement.log
