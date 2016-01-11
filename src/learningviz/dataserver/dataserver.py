'''
Created on Dec 31, 2015

@author: paepcke
'''

import argparse
import csv
import getpass
import itertools
import os
import sys
import time
import json

from pymysql_utils.pymysql_utils import MySQLDB

from redis_bus_python.redis_bus import BusAdapter
from redis_bus_python.redis_lib.exceptions import ConnectionError 
from redis_bus_python.bus_message import BusMessage

class DataServer(object):
    '''
    Given a query for datastage, post successive
    messages to the SchoolBus for each result.
    Send speed can be regulated.
    NOTE: send speed faster if column names are
          provided, either in a CSV file's first
          line (for CSVDataServer), or explicitly
          as a string array (for MySQLDataServer). 
    '''

    mysql_default_port = 3306
    mysql_default_host = '127.0.0.1'
    mysql_default_user = 'root'
    mysql_default_pwd  = ''
    mysql_default_db   = 'mysql'
    
    inter_msg_delay    = 2 # second

    def __init__(self, topic, redis_server='localhost',):
        super(DataServer,self).__init__()
        try:
            self.bus = BusAdapter(host=redis_server)
        except ConnectionError:
            print("Cannot connect to bus; is redis_bus running?")
            sys.exit()
        self.colnames = []
        self.topic = topic
        
    def send_all(self, batch_size=1):
        row_count = 0
        #******
        tmp = []
        #******
        print('Starting to publish data to %s...' % self.topic)
        for info in self.it:
            if len(info) == 0:
                # Empty line in CSV file:
                continue
            #**************
            #if info[6] != 'i4x://Medicine/HRP258/problem/8c13502687f642e1b514d4b522fc96d3':
            #    tmp = info
            #    continue
            tmp.append(info)
            continue
            #**************
            try:
                bus_msg = BusMessage(content=self.make_json(info),
                                     topicName=self.topic)
                self.bus.publish(bus_msg)
            except:
                print("Could not convert to JSON: %s" % str(info));
                continue;
            row_count += 1
            time.sleep(DataServer.inter_msg_delay)
        #**************
        dict_arr = []
        for one_tuple in tmp:
            dict_arr.append(self.make_data_dict(one_tuple))
        bus_msg = BusMessage(content=json.dumps(dict_arr),
                                     topicName=self.topic)
        self.bus.publish(bus_msg)
        #**************
        print("Published %s data rows." % row_count)
    
    def make_data_dict(self, content_line_arr):
        '''
        given an array [10,20,30], uses method
        invent_colnames() to return a JSON string
        '{"col1" : 10, "col2" : 20, "col3" : 30}'
        The invent_colnames() method either uses either
        a previously defined array of col names, or 
        invents names. 
        
        :param content_line_arr: array of values out of a CSV file or 
            query result.
        :type content_line_arr: [<anyOtherThanObject>]
        :result: a dict {<colName> : <colVal>}
        :rtype: {str, any}
        '''
        self.colnames = self.invent_colnames(self.colnames, content_line_arr)
        # Make dict by combining the colname and data values
        # like a zipper. If fewer data values than columns,
        # fill with 'null' string:
        dataDict = dict(itertools.izip_longest(self.colnames, content_line_arr, fillvalue='null'))
        return dataDict

    def invent_colnames(self, existing_colnames, data_arr):
        '''
        Given a possibly empty array of column names,
        return a new array of column names that is at
        least as long as the number of elements in 
        data_arr. If the given col name array is longer
        than data_arr, it is returned unchanged. If
        col names are missing, the returned array is
        padded with 'col-n' where n is an int.
        
        :param existing_colnames: possibly empty array of known column names in order.
        :type existing_colnames: [str]
        :param data_arr: array of any data
        :type data_arr: [<any>]
        :return: array of column names strings
        :rtype: [str]
        '''
        if len(existing_colnames) >= len(data_arr):
            return existing_colnames
        for i in range(len(existing_colnames), len(data_arr)):
            existing_colnames.append('col-%s' % str(i))
        return existing_colnames

class MySQLDataServer(DataServer):

    def __init__(self, 
                 query,
                 topic,
                 host=DataServer.mysql_default_host, 
                 port=DataServer.mysql_default_port, 
                 user=DataServer.mysql_default_user,
                 pwd=DataServer.mysql_default_pwd, 
                 db=DataServer.mysql_default_db, 
                 redis_server='localhost',
                 colname_arr=[]):
        '''
        Constructor
        '''
        # Super throws 'TypeError: must be type, not str'
        # So need to use explicit superclass call...odd. 
        #super('CSVDataServer', self).__init__(topic)
        #super('MySQLDataServer', self).__init__(topic)
        DataServer.__init__(self, topic)
        self.db = MySQLDB(host=host, port=port, user=user, passwd=pwd, db=db, redis_server=redis_server)
        # Column name array to superclass instance:
        self.colnames = colname_arr
        self.it = self.db.query(query)
        self.send_all()
        
class CSVDataServer(DataServer):
    
    def __init__(self, 
                 fileName,
                 topic,
                 first_line_has_colnames=False,
                 redis_server='localhost',
                 colnames=[] ):
        # Super throws 'TypeError: must be type, not str'
        # So need to use explicit superclass call...odd. 
        #super('CSVDataServer', self).__init__(topic)
        DataServer.__init__(self, topic, redis_server=redis_server)
                
        fd = open(fileName, 'r')
        csvreader = csv.reader(fd)
        # Explicitly provided colnames have precedence
        # over colnames in first line of file:
        if len(colnames) > 0:
            self.colnames = colnames
            # Trash first line in file if appropriate:
            if first_line_has_colnames:
                csvreader.next()
        elif first_line_has_colnames:
            # No explicit col names, but file has them;
            # send column name array to superclass instance var:
            self.colnames = csvreader.next()
        # ... else superclass will invent col names.
        self.it = csvreader
        self.send_all()
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]), 
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-s', '--server',
                        dest='host', 
                        help="For mysql src: fully qualified db host name.",
                        default=DataServer.mysql_default_host)
    parser.add_argument('-o', '--port',
                        dest='port', 
                        help="For mysql src: mysql server port.",
                        default=DataServer.mysql_default_port)
    parser.add_argument('-u', '--user',
                        dest='user', 
                        help="For mysql src: mysql user name.",
                        default=None)
    parser.add_argument('-p', '--pwd',
                        metavar='password',
                        dest='pwd', 
                        help="For mysql src: mysql password.",
                        default=None)
    parser.add_argument('-d', '--db',
                        metavar='mysqldb',
                        dest='db', 
                        help="For mysql src: mysql database to access.",
                        default=DataServer.mysql_default_db)
    parser.add_argument('-b', '--busserver',
                        dest='redis_server', 
                        help="Name of machine that serves the bus (redis server); default localhost.",
                        default='localhost')
    parser.add_argument('-t', '--type',
                        metavar='csvOrDb',
                        dest='csvOrDb',
                        choices=['csv', 'mysql'],
                        default='csv',
                        required=True,
                        help="Service type: 'csv' file or 'mysql' database; required.",
                        )
    parser.add_argument('-c', '--cols1stline',
                        dest='colsIn1stLine',
                        choices=['true', 'false'],
                        default='false', 
                        help="For csv src: true/false whether 1st line contains col names.",
                        )
    parser.add_argument('fileOrQuery',
                        help="For mysql src: query to run; for csv: file name.",
                       )
    parser.add_argument('topic',
                        help="Topic to which to publish.",
                       )
    parser.add_argument('colnames',
                        nargs='*',
                        metavar='columnnames', 
                        help="Optional list of column names; for CSV may be provided in 1st line.",
                       )

    args = parser.parse_args();

    # Are we to serve CSV file, or a MySQL query:
    src_type = args.csvOrDb
    if src_type == 'csv':
        filename = args.fileOrQuery
    else:
        query = args.fileOrQuery
    colnames = args.colnames
    
    redis_server = args.redis_server
    
    # If serving a database query: Get all the security done:
    if src_type == 'db':
        host = args.host
        port = args.port
        db   = args.db
        if args.user is None:
            # Use current user as MySQL user:
            user = getpass.getuser()
        else:
            user = args.user
            
        pwd = args.pwd
        if pwd is not None and pwd.len == 0:
            # Gave -p w/o arg; ask for pwd:
            pwd = getpass.getpass("Enter %s's MySQL password on %s: " % (user,host))
        elif pwd is None:
            # -p given, but empty:
            # Try to find pwd in specified user's $HOME/.ssh/mysql
            currUserHomeDir = os.getenv('HOME')
            if currUserHomeDir is None:
                pwd = None
            else:
                # Don't really want the *current* user's homedir,
                # but the one specified in the -u cli arg:
                userHomeDir = os.path.join(os.path.dirname(currUserHomeDir), user)
                try:
                    # Need to access MySQL db as its 'root':
                    with open(os.path.join(userHomeDir, '.ssh/mysql')) as fd:
                        pwd = fd.readline().strip()
                    
                except IOError:
                    # No .ssh subdir of user's home, or no mysql inside .ssh:
                    pwd = None
        # We now have all we need to serve a MySQL query
    else:
        # We are to serve a CSV file; does it exist?
        try:
            with open(filename, 'r') as fd:
                pass
        except IOError:
            print("Could not open CSV file %s" % filename)
            sys.exit()
        colsIn1stLine = args.colsIn1stLine
            
    if src_type == 'csv':
        server = CSVDataServer(filename,
                               args.topic,
                               first_line_has_colnames=colsIn1stLine,
                               redis_server=redis_server,
                               colnames=colnames)
    else:
        server = MySQLDataServer(query,
                                 args.topic, 
                                 host=host,
                                 port=port,
                                 user=user,
                                 pwd=pwd,
                                 db=db,
                                 redis_server=redis_server,
                                 colname_arr=colnames)
