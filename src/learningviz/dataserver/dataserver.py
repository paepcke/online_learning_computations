'''
Created on Dec 31, 2015

@author: paepcke

TODO: 
  o Accept speed control
  o Accept pause control
  o Add total number of objects sent?

'''

from __builtin__ import False
import argparse
import csv
import functools
import getpass
import itertools
import json
import logging
import os
import sys
import threading
import time

from pymysql_utils.pymysql_utils import MySQLDB
from redis_bus_python.bus_message import BusMessage
from redis_bus_python.redis_bus import BusAdapter
from redis_bus_python.redis_lib.exceptions import ConnectionError 

class DataServer(object):
    '''
    Given a query for datastage, post successive
    messages to the SchoolBus for each result.
    Send speed can be regulated.
    NOTE: send speed faster if column names are
          provided, either in a CSV file's first
          line (for CSVDataServer), or explicitly
          as a string array (for MySQLDataServer).
          
    For testing, can use online_learning_computations/src/learningviz/testfile.csv 
    
    The server listens on topic dataserverControl for messages
    that cause it to pause, resume, stop, and change speed. The content
    field of the associated messages are:
       {"cmd" : "pause"}
       {"cmd" : "resume"}
       {"cmd" : "stop"}
       {"cmd" : "changeSpeed", "arg" : "<fractionalSeconds>"}
       
    A stop message will exit the server!
    
    '''

    # Topic on which this server listens for control messages,
    # such as pause, resume, newSpeed, and stop:
    
    SERVER_CONTROL_TOPIC = "dataserverControl"
    INTER_BATCH_DELAY    = 2 # second

    mysql_default_port = 3306
    mysql_default_host = '127.0.0.1'
    mysql_default_user = 'root'
    mysql_default_pwd  = ''
    mysql_default_db   = 'mysql'
    
    # Remember whether logging has been initialized (class var!):
    loggingInitialized = False
    logger = None
    
    
    def __init__(self, topic, redis_server='localhost', logFile=None, logLevel=logging.INFO):
        '''
        Get ready to publish content of a CSV file or results
        from a query to the SchoolBus.
        
        :param topic: SchoolBus topic on which to publish data
        :type topic: str
        :param redis_server: host where Redis server is running. Default: localhost.
        :type redis_server: str
        '''
        super(DataServer,self).__init__()
        try:
            self.bus = BusAdapter(host=redis_server)
        except ConnectionError:
            self.logError("Cannot connect to bus; is redis_bus running?")
            sys.exit()
            
        self.setupLogging(logLevel, logFile)            
        self.colnames = []
        self.topic = topic
        
        self.pausing = False
        self.pause_done_event = threading.Event()
        
        self.stopping = False
        
        # Listen to messages from the bus that control
        # how this server functions:
        self.bus.subscribeToTopic(DataServer.SERVER_CONTROL_TOPIC, functools.partial(self.service_control_msgs))
        
    def service_control_msgs(self, controlMsg):
        '''
        Receive function control messages from the bus. Recognized
        commands are
            - pause
            - resume
            - stop
            - changeSpeed <newSpeedInFractionalSeconds>
        
        :param controlMsg: Message with content of the form: {"cmd" : "<commandName">", "arg" : "<argIfNeeded>"}
        :type controlMsg: BusMessage
        '''
        
        try:
            cntrl_dict = json.loads(controlMsg.content)
        except (ValueError, TypeError):
            # Not valid JSON:
            self.logError("Bad JSON in control msg: %s" % str(cntrl_dict))
            return
        
        try:
            cmd = cntrl_dict['cmd']
        except KeyError:
            # No command given:
            self.logError("No command in control msg: %s" % str(cntrl_dict))
            return
        
        if cmd == 'pause':
            self.pausing = True
            self.logInfo('Pausing %s' % self.topic)
            return
        elif cmd == 'resume':
            self.pausing = False
            self.pause_done_event.set()
            self.logInfo( 'Resuming %s' % self.topic)
            return
        elif cmd == 'stop':
            self.stopping = True
            self.logInfo('Received stop %s' % self.topic)
            return
        elif cmd == 'changeSpeed':
            try:
                new_speed = float(cntrl_dict.get('arg', None))
            except (ValueError, TypeError):
                self.logError('Change-Speed command issued without valid new-speed number: %s' % new_speed)
                return
            else:
                self.logInfo('Changing speed for topic %s to %s' % (self.topic, new_speed))
                DataServer.INTER_BATCH_DELAY = new_speed
                
        else:
            # Unrecognized command:
            self.logError('Command not recognized in message %s' % str(controlMsg))
            return
        
    def send_all(self, batch_size=1, max_to_send=-1, inter_batch_delay=None):
        if inter_batch_delay is None:
            DataServer.INTER_BATCH_DELAY = DataServer.INTER_BATCH_DELAY
        elif type(inter_batch_delay) != 'float' and type(inter_batch_delay) != 'int':
            raise TypeError('The inter_batch_delay parameter for send_all must be None, float, or int; was %s' % str(inter_batch_delay))
        else:
            DataServer.INTER_BATCH_DELAY = inter_batch_delay 
        row_count = 0
        tuple_dict_batch = []
        self.logInfo('Starting to publish data to %s...' % self.topic)
        try:
            for info in self.it:
                if len(info) == 0:
                    # Empty line in CSV file:
                    continue
                if max_to_send > -1 and row_count >= max_to_send:
                    return                
                tuple_dict_batch.append(self.make_data_dict(info))
                if len(tuple_dict_batch) >= batch_size or\
                    len(tuple_dict_batch) + row_count >= max_to_send:
                    bus_msg = BusMessage(content=json.dumps(tuple_dict_batch),
                                         topicName=self.topic)
                    self.bus.publish(bus_msg)
                    row_count += 1
                    tuple_dict_batch = []
                    if self.pausing:
                        self.pause_done_event.wait()
                    elif self.stopping:
                        return
                    else:
                        time.sleep(DataServer.INTER_BATCH_DELAY)
                    continue
        finally:
            self.logInfo("Published %s data rows." % row_count)
    
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

    def setupLogging(self, loggingLevel, logFile):
        if DataServer.loggingInitialized:
            # Remove previous file or console handlers,
            # else we get logging output doubled:
            DataServer.logger.handlers = []
            
        # Set up logging:
        DataServer.logger = logging.getLogger('dataServer')
        DataServer.logger.setLevel(loggingLevel)
        # Create file handler if requested:
        if logFile is not None:
            handler = logging.FileHandler(logFile)
        else:
            # Create console handler:
            handler = logging.StreamHandler()
        handler.setLevel(loggingLevel)
#         # create formatter and add it to the handlers
#         formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#         fh.setFormatter(formatter)
#         ch.setFormatter(formatter)
        # Add the handler to the logger
        DataServer.logger.addHandler(handler)
        
        DataServer.loggingInitialized = True

    def logWarn(self, msg):
        DataServer.logger.warn(msg)

    def logInfo(self, msg):
        DataServer.logger.info(msg)
     
    def logError(self, msg):
        DataServer.logger.error(msg)

    def logDebug(self, msg):
        DataServer.logger.debug(msg)


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
                 colname_arr=[],
                 max_to_send=-1,
                 logFile=None,
                 logLevel=logging.INFO                 
                 ):
        '''
        Constructor
        '''
        # Super throws 'TypeError: must be type, not str'
        # So need to use explicit superclass call...odd. 
        #super('CSVDataServer', self).__init__(topic)
        #super('MySQLDataServer', self).__init__(topic)
        DataServer.__init__(self, topic, logFile=logFile, logLevel=logLevel)
        self.db = MySQLDB(host=host, port=port, user=user, passwd=pwd, db=db, redis_server=redis_server)
        # Column name array to superclass instance:
        self.colnames = colname_arr
        self.it = self.db.query(query)
        self.send_all(max_to_send=max_to_send)
        
class CSVDataServer(DataServer):
    
    def __init__(self, 
                 fileName,
                 topic,
                 first_line_has_colnames=False,
                 redis_server='localhost',
                 colnames=[],
                 max_to_send=-1,
                 logFile=None,
                 logLevel=logging.INFO                 
                 ):
        # Super throws 'TypeError: must be type, not str'
        # So need to use explicit superclass call...odd. 
        #super('CSVDataServer', self).__init__(topic)
        DataServer.__init__(self, topic, redis_server=redis_server, logFile=logFile, logLevel=logLevel)
                
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
        self.send_all(max_to_send=max_to_send)
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]), 
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-s', '--host',
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
                        help="Service type: 'csv' file or 'mysql' database; required.",
                        )
    parser.add_argument('-c', '--cols1stline',
                        dest='colsIn1stLine',
                        choices=['true', 'false'],
                        default='false', 
                        help="For csv src: true/false whether 1st line contains col names.",
                        )
    parser.add_argument('-m', '--maxmsgs',
                        dest='max_to_send',
                        type=int,
                        help="Maximum number of messages to send. Default: all (a.k.a. -1)",
                        default='-1')
    parser.add_argument('-e', '--period',
                        dest='period',
                        type=float,
                        help="Fractional seconds to wait between data batches. Default: %s" % DataServer.INTER_BATCH_DELAY,
                        default=DataServer.INTER_BATCH_DELAY)
    parser.add_argument('-l', '--logFile', 
                        help='Fully qualified log file name to which info and error messages \n' +\
                             'are directed. Default: stdout.',
                        dest='logFile',
                        default=None);
    parser.add_argument('-v', '--verbose', 
                        help='Print operational info to log.', 
                        dest='verbose',
                        action='store_true');
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
    
    max_to_send = args.max_to_send
    
    DataServer.INTER_BATCH_DELAY = args.period
        
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
                               colnames=colnames,
                               max_to_send=max_to_send,
                               logFile=args.logFile,
                               logLevel=logging.DEBUG if args.verbose else logging.INFO)
    else:
        server = MySQLDataServer(query,
                                 args.topic, 
                                 host=host,
                                 port=port,
                                 user=user,
                                 pwd=pwd,
                                 db=db,
                                 redis_server=redis_server,
                                 colname_arr=colnames,
                                 max_to_send=max_to_send,
                                 logFile=args.logFile,
                                 logLevel=logging.DEBUG if args.verbose else logging.INFO
                                 )
