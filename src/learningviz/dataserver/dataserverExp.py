'''
Created on Dec 31, 2015

@author: paepcke

TODO: 
  o Accept speed control
  o Accept pause control
  o Add total number of objects sent?
  o When clicking Play button: maybe check whether
      need to re-connect to websocket to resume. Needed
      if disconnecting from the Web for a time.

'''

import ConfigParser
import Queue
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
    
    Given either a CSV-filename or an MySQL query,
    this server places the tuples on the SchoolBus
    at controllable speed. (The MySQL query part is
    not yet implemented.)
    
    A column header can be specified or be the first
    line in a CSV file. If none is specified, reasonable
    column header names will be created.

    NOTE: send speed is faster if column names are
          provided, either in a CSV file's first
          line (for CSVDataServer), or explicitly
          as a string array (for MySQLDataServer).
          
    For testing, can use online_learning_computations/src/learningviz/testfile.csv 
    
    The server listens on topic dataserverControl for messages
    that cause it to pause, resume, stop, and change speed. The content
    field of the associated messages are:
    
       {"cmd" : "play", streamId : "a39fc5b440dd4be1b02a1a05fd167e68"}
       {"cmd" : "pause", streamId : "a39fc5b440dd4be1b02a1a05fd167e68"}
       {"cmd" : "resume", streamId : "a39fc5b440dd4be1b02a1a05fd167e68"}
       {"cmd" : "stop", streamId : "a39fc5b440dd4be1b02a1a05fd167e68"}
       {"cmd" : "restart", streamId : "a39fc5b440dd4be1b02a1a05fd167e68"}
       {"cmd" : "changeSpeed", streamId : "a39fc5b440dd4be1b02a1a05fd167e68", "arg" : "<fractionalSeconds>"}
       {"cmd" : "newStream", "arg" : "<sourceId>"}
       
    A stop message will exit the server! Applications who provide
    GUI access to the stop message should warn their users.
    
    Command changeSpeed takes as argument the transmission period,
    i.e. the number of fractional seconds between each transmission.  
    
    Command newStream's argument is a key that identifies a
    data source, such as a CSV file to this server. These keys
    are provided to this server via a config file. 
    
    The config file provides key/values in which keys
    are names for datasets, and values are either an absolute or
    relative path to a corresponding CSV file, or a MySQL query.
    Example config file content:
    
        [CSVFiles]
        compilers : /home/me/data/compilerGrades.csv
        databases : ../theDbGrades.csv
        statistics : $HOME/Data/Grades/stats.csv
        artCourse=SELECT * FROM foo WHERE ...
        
        [MySQLQueries]
            ...
        
    Both ':" and "=" are suported as separator, but for "=" no space
    is permitted. See Python ConfigParser module for details. 
    
    The protocol for requesting a new stream uses the SchoolBus callback
    feature:
      
        - client creates the unique id <msgId> for a request msg to 
          this server.
        - client subscribes to topic "tmp.<msgId>"
        - client publishes newStream request to topic dataserverControl.
        - server publishes a response message to a topic "tmp.<msgId>"
             The 'content' field of that response message will be:
             
                    {"streamId" : <uuidStr>}
               
          The streamId will be the topic to which this server will publish
          the data. That same streamId must also be included in any subsequent
          request by the client that references the new stream. See cmd 
          summary above.
          
        - client publishes a play message to 'dataserverControl'.    
    
    Subsequent status or error messages from the data server to the client will
    be published as error messages to tmp.<msgId>. In particular: when a stream
    has ended, a message with content:

            {"error" : "endOfStream"} 
    
    Various command line options to this server allow some customization
    of this server. See __main__ section.
    
    If this server is to be used with with the real-time assignment
    grade demo, see gradeGraph.js header for details of expected
    schema. 
    
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
    
    
    def __init__(self, redis_server='localhost', configFile=None, logFile=None, logLevel=logging.INFO):
        '''
        Get ready to publish content of a CSV file or results
        from a query to the SchoolBus.
        
        :param topic: SchoolBus topic on which to publish data
        :type topic: str
        :param redis_server: host where Redis server is running. Default: localhost.
        :type redis_server: str
        '''
        super(DataServer,self).__init__()
        self.cnf_file_path = configFile

        self.setupLogging(logLevel, logFile)   

        if self.cnf_file_path is None:
            self.cnf_file_path = os.path.join(os.path.dirname(__file__), 'dataserver.cnf')
        else:
            self.cnf_file_path = configFile
        
        if not (os.path.isfile(self.cnf_file_path) and os.access(self.cnf_file_path, os.R_OK)):
                raise IOError('Dataserver config file %s does not exist.')       

        try:
            self.bus = BusAdapter(host=redis_server)
        except ConnectionError:
            self.logError("Cannot connect to bus; is redis_bus running?")
            sys.exit()
        
        # Dict of message streamId --> queue. Given the streamId
        # that identifies to which thread an incoming control message
        # is directed, get the queue to which that thread listens for
        # commands:   
        self.msg_queues = {}

        # Dict to map streamId --> responseTopic,
        # where responseTopic is the topic to which messages
        # for the client of the streamId's stream are to be
        # sent. The client is expected to listen to that topic:
        self.response_topics = {}
        
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
            - startStream
        
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
        
        stream_id = cntrl_dict.get('streamId', None)
        
        # The only command for which client does not need to
        # pass a stream ID is for a new-stream request:
        if stream_id is None and cmd != 'newStream':
            self.logErr('Received command %s without the required streamId field.' % cmd)
            return
        else:
            # Got a stream ID for a command that requires one. 
            # But do we recognize that stream id?
            cmd_queue = self.msg_queues.get(stream_id, None)
            if cmd_queue is None:
                err_msg = 'Command % with unrecognized stream ID %s.' % (cmd, stream_id)
                self.logErr(err_msg)
                self.returnError(stream_id, err_msg)
                return
        
        
        if cmd == 'pause':
            cmd_queue.put('pause')
            self.logInfo('Pausing %s' % self.topic)
            return
        elif cmd == 'resume':
            cmd_queue.put('resume')
            self.logInfo( 'Resuming %s' % self.topic)
            return
        elif cmd == 'stop':
            cmd_queue.put('stop')
            self.logInfo('Received stop %s' % self.topic)
            return
        elif cmd == 'changeSpeed':
            try:
                new_speed = float(cntrl_dict.get('arg', None))
            except (ValueError, TypeError):
                err_msg = 'Change-Speed command issued without valid new-speed number: %s' % new_speed
                self.logError(err_msg)
                self.returnError(stream_id, err_msg)
                return
            else:
                self.logInfo('Changing speed for topic %s to %s' % (self.topic, new_speed))
                cmd_queue.put('newSpeed,%s' % new_speed)
                return
        elif cmd == 'restart':
            cmd_queue.put('restart')
            self.logInfo('Received restart for streamId %s' % stream_id)
            return
         
        elif cmd == 'newStream':
            
            # Derive the topic to use for response message to the 
            # requesting client. Do this having the bus machinery
            # create an empty response message, and extracting the
            # destination topic from it:
            
            stream_id = self.bus.makeResponseMsg(controlMsg, '').topicName() 
            
            # Code earlier already verified that source_id was provided
            # in the request message:
            source_id = cntrl_dict.get('source_id', None)
            if source_id is None:
                err_msg = 'New stream request without the required source_id.'
                self.logErr(err_msg)
                self.returnError(stream_id, err_msg)
                return
            # Create a queue into which later incoming client requests
            # will be fed to the stream-sending thread:
            cmd_queue = Queue()
            self.msg_queues[stream_id] = cmd_queue
            self.response_topics[stream_id] = 

            # Create a new thread to feed the stream back to the client:
            try:
                new_thread = OneStreamServer(cmd_queue, source_id, self.conf_parser)
            except (ValueError, IOError) as e:
                self.logError(`e`)
                self.returnError(stream_id, `e`)
            
        else:
            # Unrecognized command:
            self.logError('Command not recognized in message %s' % str(controlMsg))
            return



    def returnError(self, streamId, errorMsg):
        '''
        Given the streamId of an existing stream, and an
        error message, publish a BusMessage with the given
        message to the topic on which the originating client
        is listening. That topic was derived from the client's
        newStream message. The content field will be:
           {"error" : "<errorMsg>"}
        
        :param streamId: identifier of the stream about which the error message is being sent.
        :type inMsg: str
        :param errorMsg: value of the outgoing message's 'content' JSON "error" field. 
        :type errorMsg: str
        '''
        
        response_topic = self.response_topics.get(streamId, None)
        if response_topic None:
            self.loogErr("Unknown streamId %s passed to returnError." % streamId)
            return
        msg = BusMessage()
        msg.topic = response_topic
        msg.content = '{"error" : %s)' % errorMsg
        self.bus.publish(msg)

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

class OneStreamServer(threading.Thread):
    
    def __init__(self, cmd_queue, source_id, conf_parser):
        self.cmd_queue = cmd_queue
        self.source_id = source_id
        self.conf_parser = conf_parser
        self.pausing   = False
        self.stopping  = False
        self.interbatch_delay = DataServer.INTER_BATCH_DELAY
        self.batch_size = 1
        self.max_to_send = 1
        self.source_iterator = None
        
        self.source_iterator = self.get_source_iterator()
        
    def get_source_iterator(self):
        '''
        Given self.source_id and a ConfigParser instance in self.config_parser,
        return an iterator that will feed one line after another upon next().
        First tries to close any existing iterator. Then uses source_id
        as key into config file section CSVFiles. If either that section or
        that option (i.e. source_id) are not available in the config file,
        raise ValueError. Expects the config option to be the path to a CSV
        file. Tries to open that file. If failure, raises IOError.
        
        NOTE: Modify to also try section MySQLQueries with source_id to
              create a query iterator.
        
        :return: An iterator that feeds one result/CSV-line at a time.
        :rtype: iterator(<str>) 
        
        '''
        # If we already have an iterator going, close it first:
        if self.source_iterator is not None:
            try:
                self.source_iterator.close()
            except Exception:
                pass
        # Make sure you catch ValueError when creating a new OneStreamServer thread instance:
        try:
            csv_file_name = self.conf_parser.get('CSVFiles', self.source_id)
        except ConfigParser.NoSectionError:
            raise ValueError('Configuration file does not contain a CSVFiles section.')
        except ConfigParser.NoOptionError:
            raise ValueError('Configuration file does not contain an entry for CSVFiles:%s.' % self.source_id)
        
        try:
            file_iteratoer = open(csv_file_name, 'r')
        except IOError:
            raise IOError('Configuration file specs path %s for streamID %s; file does not exist or is not readable' %\
                          (csv_file_name, self.source_id))
        return file_iteratoer
        
        
    def run(self):
        
        row_count = 0
        tuple_dict_batch = [] #@UnusedVariable
        self.logInfo('Starting to publish data to %s...' % self.topic)
        try:
            # Note: Can't use "for info in self.source_iterator"
            #       for the loop, b/c we want the ability to restart
            #       self.source_iterator from the beginning.
            
            while True:
                try:
                    # Next line or result:
                    info = self.source_iterator.next()
                except StopIteration:
                    # Sources is exhausted; quit this thread:
                    return

                # Check for control command from client:
                try:
                    cmd = self.cmd_queue.get_nowait()
                    # Do something:
                    if cmd == 'pause':
                        self.pausing = True
                    elif cmd == 'stop':
                        self.stopping = True
                    elif cmd.startswith('changeSpeed'):
                        # We trust that the operator of the other end of
                        # the queue sent a string 'changeSpeed,<fractionalSeconds>':
                        new_speed = cmd.split(',')[1]
                        if type(new_speed) != 'float' and type(new_speed) != 'int':
                            self.logErr('The inter_batch_delay parameter for send_all must be float, or int; was %s' % str(new_speed))
                            # Ignore the command
                        else:
                            self.inter_batch_delay = new_speed
                    elif cmd == 'restart':
                        self.source_iterator = self.get_source_iterator()
                        
                except Queue.Empty:
                    # No new control command:
                    pass
                
                if len(info) == 0:
                    # Empty line in CSV file:
                    continue
                if max_to_send > -1 and row_count >= max_to_send:
                    return                
                tuple_dict_batch.append(self.make_data_dict(info))
                if len(tuple_dict_batch) >= self.batch_size or\
                    len(tuple_dict_batch) + row_count >= max_to_send:
                    
                    if self.pausing:
                        # Wait for 'resume' or 'stop' message:
                        while self.pausing:
                            cmd = self.cmd_queue.get()
                            if cmd == 'resume':
                                self.pausing = False
                                continue
                            elif cmd == 'stop':
                                self.pausing = False
                                self.stopping = True
                    elif self.stopping:
                        return
                    
                    bus_msg = BusMessage(content=json.dumps(tuple_dict_batch),
                                         topicName=self.topic)
                    self.bus.publish(bus_msg)
                    row_count += 1
                    tuple_dict_batch = []

                    time.sleep(self.inter_batch_delay)
                    continue
                else:
                    # Continue filling a batch:
                    continue
        finally:
            self.logInfo("Published %s data rows." % row_count)
    
    def make_data_dict(self, content_line_arr):
        '''
        given an array [10,20,30], uses method
        invent_colnames() to return a JSON string
        '{"col1" : 10, "col2" : 20, "col3" : 30}'
        The invent_colnames() method either uses
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
