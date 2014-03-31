#!/bin/bash

# Compute engagement for all classes, or one given class.
# Computations occur in parallel, using engagement.py.

USAGE='Usage: '`basename $0`' [options] [{courseName | None} [yearAsYYYY1, yearAsYYYY2,...]]'

HELP='Compute engagement statistics for one or all classes. Optionally: course name or None, followed optionally by any number of years that constrain when qualifying courses must have been started (YYYY)'

COURSE_NAME='None'
YEAR='None'
needPasswd=false
PASSWD=''
USERNAME=`whoami`
YEARS_SPECIFIED=false

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
      echo $USAGE
      echo $HELP
      shift;;
    --)
      shift
      break;;
  esac
done

if [ ! -z $1 ]
then
  COURSE_NAME=$1
  shift
fi

if [ -z $1 ]
then
    YEARS='None'
else
    YEARS=$@
    YEARS_SPECIFIED=true
fi

#**************
#echo "Course name: $COURSE_NAME"
#echo "YEARS: $YEARS"
#exit 0
#**************


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
# echo "Years: $YEARS"
# echo "Course: '$COURSE_NAME'"
# echo "User: '$USERNAME'"
# echo "PWD: '$PASSWD'"
# if [ -z $PASSWD ]
# then
#     echo "PWD empty"
# else
#     echo "PWD full"
# fi
# exit
#*************

thisScriptDir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Get course names if needed, removing spaces and empty lines:

if [ $COURSE_NAME == 'None' ]
then
    echo 'None' > /tmp/classNames.txt
else
    echo "`date`: Querying db to get all course names..." >> /tmp/engagement.log
    mysql -u $USERNAME -p$PASSWD -e "use Edx; SELECT DISTINCT course_display_name FROM EventXtract;" | \
        sed 's/[\s|]//' | \
        sed '/^$/d' > /tmp/classNames.txt
    echo "`date`: Done querying db to get all course names..." >> /tmp/engagement.log
fi

# Remove old engagement results:
#******Now goes to custom?********rm /tmp/engagement_* 2> /dev/null


echo "Logging to /tmp/engagement.log"
# '-n': no terminating CR:
echo -n "Compute course engagement stats for " >> /tmp/engagement.log
if [ $COURSE_NAME == 'None' ]
then
    echo -n "all courses; "  >> /tmp/engagement.log
else
    echo -n "course $COURSE_NAME; "  >> /tmp/engagement.log
fi

if [ $YEARS_SPECIFIED ]
then
    echo "year(s) $YEARS."  >> /tmp/engagement.log
else
    echo "any start year."  >> /tmp/engagement.log
fi

#**********
exit
#**********

echo "Compute course engagement stats for $YEARS: `date`" >> /tmp/engagement.log
if [ -z $COURSE_NAME ]
then
    $thisScriptDir/../src/engagement.py $YEARS &>> /tmp/engagement.log
else
    $thisScriptDir/../src/engagement.py $YEARS $COURSE_NAME &>> /tmp/engagement.log
fi
echo "Compute course engagement stats for $YEARS done: `date`"  >> /tmp/engagement.log
