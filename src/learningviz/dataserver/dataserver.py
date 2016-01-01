'''
Created on Dec 31, 2015

@author: paepcke
'''

import csv
import itertools
import argparse
import sys
import os

from pymysql_utils import MySQLDB

from redis_bus_python import BusAdapter
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
    

    def __init__(self):
        self.bus = BusAdapter()
        self.colnames = []
        
    def send_all(self, it):
        for info in it:
            bus_msg = BusMessage(content=self.make_json(info))
            self.bus.publish(bus_msg)
    
    def make_json(self, content_line_arr):
        self.colnames = self.invent_colnames(self.colnames)
        return dict(itertools.izip_longest(self.colnames, content_line_arr, fillvalue='null'))

    def invent_colnames(self, existing_colnames, data_arr):
        if len(existing_colnames) >= len(data_arr):
            return existing_colnames
        for i in range(len(existing_colnames), len(data_arr)):
            existing_colnames.append('col-%s' % str(i))
        return existing_colnames

class MySQLDataServer(DataServer):

    def __init__(self, 
                 query, 
                 host=DataServer.mysql_default_host, 
                 port=DataServer.mysql_default_port, 
                 user=DataServer.mysql_default_user,
                 passwd=DataServer.mysql_default_pwd, 
                 db=DataServer.mysql_default_db, 
                 colname_arr=None):
        '''
        Constructor
        '''
        super('MySQLDataServer', self).__init__()
        self.db = MySQLDB(host=host, port=port, user=user, passwd=passwd, db=db)
        # Column name array to superclass instance:
        self.colnames = colname_arr
        self.it = self.db.query(query)
        
class CSVDataServer(DataServer):
    
    def __init__(self, 
                 fileName,
                 first_line_has_colnames=False ):
        super('MySQLDataServer', self).__init__()
                
        fd = open(fileName, 'r')
        csvreader = csv.reader(fd)
        if first_line_has_colnames:
            # Column name array to superclass instance var:
            self.colnames = csvreader.readline()
        self.it = csvreader
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]), 
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-s', '--server',
                        metavar='host', 
                        help="For mysql src: fully qualified db host name.",
                        default=DataServer.mysql_default_host)
    parser.add_argument('-p', '--port',
                        metavar='port', 
                        help="For mysql src: mysql server port.",
                        default=DataServer.mysql_default_port)
    parser.add_argument('-u', '--user',
                        metavar='user', 
                        help="For mysql src: mysql user name.",
                        default=DataServer.mysql_default_user)
    parser.add_argument('-p', '--pwd',
                        metavar='pwd', 
                        help="For mysql src: mysql password.",
                        default=DataServer.mysql_default_pwd)
    parser.add_argument('-d', '--db',
                        metavar='db', 
                        help="For mysql src: mysql database to access.",
                        default=DataServer.mysql_default_db)
    [Next: filename for csv, and first-line-colnames-y/n]
    
    parser.add_argument('source',
                        metavar='source',
                        help="Either 'csv' or 'mysql' to indicate where data is to be obtained.",
    
    parser.add_argument('-s', '--streamMsgs', 
                        help="Send the same bus message over and over. Topic, or both,\n" +\
                             "topic and content may be provided. If content is omitted,\n" +\
                             "a random string of %d characters will be used.\n" % STANDARD_MSG_LENGTH +\
                             "If topic is omitted as well, messages will be streamed to '%s'" % STREAM_TOPIC,
                        dest='stream_topic_and_content',
                        nargs='*',
                        metavar=('topic', 'content'),
                        default=None);

        