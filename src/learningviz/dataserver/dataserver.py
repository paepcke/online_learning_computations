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
from Queue import Queue
from Queue import Empty
from __builtin__ import False
import argparse
import csv
import functools
import getpass
import itertools
import json
import logging
import os
from redis_bus_python.bus_message import BusMessage
from redis_bus_python.redis_bus import BusAdapter
from redis_bus_python.redis_lib.exceptions import ConnectionError 
import signal
import sys
import threading
import time

from pymysql_utils.pymysql_utils import MySQLDB
from datetime import datetime, timedelta


class QueueWithEndpoint(Queue):
    '''
    Convenience subclass of Queue that adds
    an 'endpoint' property. We can put into that
    the thread object that listens to an instance
    of this class.
    
    '''
    
    def __init__(self):
        # Since Queue is an old-style class, must
        # call its init method directly, i.e. not
        # calling super():
        Queue.__init__(self)
        self._end_point = None
        
    @property
    def endpoint(self):
        return self._end_point
    @endpoint.setter
    def endpoint(self, new_endpoint):
        self._end_point = new_endpoint
        

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
    
       {"cmd" : "initStream", "sourceId" : "<sourceId>"}
       {"cmd" : "play", "streamId" : "<streamId>"}
       {"cmd" : "pause", streamId : "a39fc5b440dd4be1b02a1a05fd167e68"}
       {"cmd" : "resume", streamId : "a39fc5b440dd4be1b02a1a05fd167e68"}
       {"cmd" : "stop", streamId : "a39fc5b440dd4be1b02a1a05fd167e68"}
       {"cmd" : "restart", streamId : "a39fc5b440dd4be1b02a1a05fd167e68"}
       {"cmd" : "changeSpeed", streamId : "a39fc5b440dd4be1b02a1a05fd167e68", "arg" : "<fractionalSeconds>"}
       {"cmd" : "listSources"}
       
    A stop message will exit the server! Applications who provide
    GUI access to the stop message should warn their users.
        
    Command initStream:
     
    the sourceId must be a key that identifies a
    data source, such as a CSV file to this server. These keys
    are provided to this server via a config file, and available via
    command listSources. The protocol for requesting a new stream uses 
    the SchoolBus callback feature. The details are taken care of
    by the publish() methods of the BusAdapter implementations: 
    redis_bus.py for Python, and js_schoolbus_bride.js for JavaScript. 
      
        - client creates the unique id <msgId> for a request msg to 
          this server.
        - client subscribes to topic "tmp.<msgId>"
        - client publishes newStream request to topic dataserverControl.
        - server publishes a response message to topic "tmp.<msgId>"
             The 'content' field of that response message will be:
             
                    {"streamId" : "<uuidStr>",
                     "sourceId" : "sourceId",
               
          The uuidStr is a streamId. That will be the topic to which this server will publish
          the data once it receives a subsequent 'play' message.  
          That same streamId must also be included in any subsequent
          request by the client that references the new stream. See cmd 
          summary above.
          
          The sourceId is included for convenience of the client.
          
        - client publishes a play message without the sourceId argument
          to 'dataserverControl'.    
    
    Command play: 
    
    If the stream with the given streamId is currently paused, 
    the effect is the same as the resume command. If a stream
    was started with initStream, the play command will start the
    data flowing.
    
    Command changeSpeed:
    
    Takes as argument the transmission period, i.e. the number of 
    fractional seconds between each transmission.  
    
    Command listSources:
    
    Returns a list of source ids and corresponding information.
    The source ids are the keys in the CSVFiles and MySQLQueries
    sections of the configuration file (see below). The corresponding
    information is taken from the InfoText section. The returned
    JSON is structured like this:
       
        {"sourceId" : "mySrc1", "info" : "This source shows my family tree.",
         "sourceId" : "mySrc2"
         }
         
    That is, the information field may or may not be present. The information
    may include '\n' characters. The JSON may also be empty: {} if no
    sources are currently offered by this data pump. This command is
    replied-to via a bus pseudo synchronous call.
    
    The config file provides key/values in which keys
    are names for datasets, and values are either an absolute or
    relative path to a corresponding CSV file, or a MySQL query.
    Example config file content:
    
        [CSVFiles]
        compilers : /home/me/data/compilerGrades.csv
        databases : ../theDbGrades.csv
        statistics : $HOME/Data/Grades/stats.csv
        
        [MySQLQueries]
        artCourse=SELECT * FROM foo WHERE ...
            ...
        
        [InfoText]
        compilers : Grades for ompiler course Spring 2014
        databases: Grades for original un-partitioned database course 
        
    Both ':" and "=" are suported as separator, but for "=" no space
    is permitted. See Python ConfigParser module for details. After
    changing the configuration file, sending a SIGHUP signal to this
    process will re-read the file. So the server does not need to be
    taken down after changing the file.
    
    Signal SIGUSR1 will print current server status to stdout.
    
        
    Status or error messages from the data server to the client will
    be published as error messages to tmp.<msgId>. In particular: when a stream
    has ended, a message with content:

            {"error" : "endOfStream"} 
    
    Various command line options to this server allow some customization
    of this server. See __main__ section.
    
    If this server is to be used with with the real-time assignment
    grade demo, see gradeGraph.js header for details of expected
    schema. 
    
    A stream that is either paused or initiated, but not started
    via a play command for more than DataServer.INACTIVITY_STREAM_KILL will
    be terminated as if the client had issued a stop command. In this
    case an error message will be sent to the client. Re-sending a 
    pause command to a paused stream before DataServer.INACTIVITY_STREAM_KILL
    of inactivity has passed will reset the watchdog. It is also
    permitted to send a pause command to an initiated stream without
    first sending a play command.
    
    '''

    # Topic on which this server listens for control messages,
    # such as pause, resume, newSpeed, and stop:
    
    SERVER_CONTROL_TOPIC = "datapumpControl"
    INTER_BATCH_DELAY    = 2 # second
    STREAM_THREAD_SHUTDOWN_TIMEOUT = 1 # Second
    
    # Time after which a stream is closed if it is either
    # paused or initialized, but not started with a play 
    # command. When closure occurs, the client will be
    # sent an error message:
    INACTIVITY_STREAM_KILL = timedelta(days=2)

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
        
        # The main section may have checked the config parser
        # already, but we do it again:
        if not (os.path.isfile(self.cnf_file_path) and os.access(self.cnf_file_path, os.R_OK)):
                raise IOError('Dataserver config file %s does not exist.')       

        self.conf_parser = ConfigParser.ConfigParser()
        self.relaod_config_file()
        
        # Catch SIGHUP signal and interpret it as
        # command to reload configuration:
        signal.signal(signal.SIGHUP, functools.partial(self.sighup_handler))

        # Whether cnt-c has shut us down:
        self.shutdown = False
        
        # Catch SIGUSR1 and print current streams status:
        signal.signal(signal.SIGUSR1, functools.partial(self.sigusr1_handler))

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

        # Dict to map streamId --> thread,
        self.threads = {}
        
        # Listen to messages from the bus that control
        # how this server functions:
        self.bus.subscribeToTopic(DataServer.SERVER_CONTROL_TOPIC, functools.partial(self.service_control_msgs))
        
        self.logInfo('Data pump now listening for requests on SchoolBus.')
        
        # Hang till keyboard interrupt (a.k.a. kill -2 <procId> in shell)
        while True:
            try:
                if self.shutdown:
                    self.logInfo('Datapump has shut down successfully.')
                    return
                time.sleep(1)
                # Check for streams that delivered all
                # their data and clean up after them:
                for (stream_id, one_thread) in self.threads.items():
                    # Stream sent all data?
                    if not one_thread.isAlive():
                        del self.msg_queues[stream_id]
                        del self.threads[stream_id]
                    # Stream inactive for more than DataServer.INACTIVITY_STREAM_KILL?
                    latest_activity = one_thread._latest_activity_time
                    if (datetime.now() - latest_activity) > DataServer.INACTIVITY_STREAM_KILL:
                        cmd_queue = self.msg_queues.get(stream_id, None)
                        if cmd_queue is None:
                            # Shouldn't happen...
                            continue
                        err_msg = "Paused stream '%s' terminated for inactivity; last command received at %s" %\
                                    (one_thread.source_id, latest_activity.isoformat())
                        self.logInfo('Closed stream %s (%s) for inactivity.' %
                                     (one_thread.source_id, stream_id))
                        self.returnError(stream_id, err_msg)
                        cmd_queue.put('stop')
                        continue
                        
                    
            except KeyboardInterrupt:
                self.do_shutdown()
                continue

    def relaod_config_file(self):
        self.conf_parser.read(self.cnf_file_path)

    def do_shutdown(self):
        self.logInfo('Shutting down data pump ...')
        # Stop all running streams:
        for (stream_id, one_thread) in self.threads.items():
            self.logInfo('Stopping stream %s' % stream_id)
            one_thread.stop()
            one_thread.join(DataServer.STREAM_THREAD_SHUTDOWN_TIMEOUT)
            # If thread still alive, the stop failed:
            if one_thread.is_alive():
                self.logError('Could not stop stream %s' % stream_id)
            else:
                self.logInfo('Stream %s stopped successfully' % stream_id)

        # Shut down the bus adapter:        
        try:
            self.bus.close()
        except RuntimeError as e:
            self.logError('Problem while shutting down BusAdapter: %s' % `e`)
            
        # Release completion of __init__() method and thereby closure of main thread:
        self.shutdown = True
                
    def service_control_msgs(self, controlMsg):
        '''
        Note: Called from a different thread: BusAdapter.
        Receive function control messages from the bus. Recognized
        commands are
            - play
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
            self.logError("Bad JSON in control msg: %s" % str(controlMsg.content))
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
        if stream_id is None and not cmd in ['initStream', 'listSources']:
            self.logError('Received command %s without the required streamId field.' % cmd)
            return
        elif stream_id is not None:
            # Got a stream ID for a command that requires one. 
            # But do we recognize that stream id?
            try:
                cmd_queue = self.msg_queues.get(stream_id, None)
            except Exception as e:
                err_msg = "Unknown stream ID passed to data pump in command '%s': %s" % (cmd, str(stream_id))
                self.logError(err_msg)
                # If the stream_id that the client passed to us 
                # isn't even a string, we can't respond to them,
                # because the stream_id is the return topic. So
                # just log the problem here:
                if type(stream_id) == 'string':
                    self.returnError(stream_id, err_msg)
                return
            if cmd_queue is None:
                err_msg = 'Command %s with unrecognized stream ID %s.' % (cmd, stream_id)
                self.logError(err_msg)
                self.returnError(stream_id, err_msg)
                return
        
        if cmd == 'play':
            # In this context, play is the same as resuming
            # from a pause; if not currently paused, no effect:
            cmd_queue.put('resume')
            self.logInfo('Play stream %s:%s' % (self.get_source_id(cmd_queue), self.topic))
            return
        if cmd == 'pause':
            cmd_queue.put('pause')
            self.logInfo('Pausing %s:%s' % (self.get_source_id(cmd_queue), self.topic))
            return
        elif cmd == 'resume':
            cmd_queue.put('resume')
            self.logInfo( 'Resuming %s:%s' % (self.get_source_id(cmd_queue), self.topic))
            return
        elif cmd == 'stop':
            cmd_queue.put('stop')
            self.logInfo('Received stop %s:%s' % (self.get_source_id(cmd_queue), self.topic))
            return
        elif cmd == 'changeSpeed':
            try:
                new_speed = float(cntrl_dict.get('arg', None))
                if new_speed is None:
                    raise ValueError("")
            except (ValueError, TypeError):
                err_msg = 'Change-Speed command issued without valid new-speed number: %s' % str(cntrl_dict)
                self.logError(err_msg)
                self.returnError(stream_id, err_msg)
                return
            else:
                self.logInfo('Changing speed for %s:%s to %s' % (self.get_source_id(cmd_queue), self.topic, new_speed))
                cmd_queue.put('changeSpeed,%s' % new_speed)
                return
        elif cmd == 'restart':
            cmd_queue.put('restart')
            self.logInfo('Received restart for stream %s:%s' % (self.get_source_id(cmd_queue), stream_id))
            return
        
        elif cmd == 'listSources':
            # Prepare the synchronous reply message with
            # an empty content part for now:
            src_list_reply_msg = self.bus.makeResponseMsg(controlMsg, '')
            try:
                res = self.create_list_source_info()
            except ValueError as e:
                self.logError(`e`)
                # The above-prepared reply message has the return
                # topic already filled in. Use it to tell the
                # error sender where to send the error:
                self.returnError(src_list_reply_msg.topicName(), `e`)
                return
            else:
                src_list_reply_msg.content = res
                self.bus.publish(src_list_reply_msg)
                return
         
        elif cmd == 'initStream':
            
            # Prepare the response message back to the client:
            # Make a BusMessage for the response. That response
            # message will have a unique message identifier. We
            # will use it as the streamId for this new stream going forward.  
            
            response_msg = self.bus.makeResponseMsg(controlMsg, '')
            stream_id    = response_msg.topicName 
            
            # Code earlier already verified that source_id was provided
            # in the request message:
            source_id = cntrl_dict.get('sourceId', None)
            if source_id is None:
                err_msg = 'New stream request without the required source_id.'
                self.logError(err_msg)
                self.returnError(stream_id, err_msg)
                return
            # Create a queue into which later incoming client requests
            # will be fed to the stream-sending thread:
            cmd_queue = QueueWithEndpoint()
            self.msg_queues[stream_id] = cmd_queue
            self.topic = stream_id

            # Create a new thread to feed the stream back to the client:
            try:
                # The first stream_id specifies the topic to which
                # the new thread is to publish. It so happens that we
                # use the stream_id for the topic. The second stream_id
                # parameter is the stream_id, which is included in case
                # the topic convention is ever changed: 
                new_thread = OneStreamServer(stream_id, stream_id, cmd_queue, source_id, self.conf_parser, self.bus)
                # Remember which thread is listening to this queue:
                cmd_queue.endpoint = new_thread
            except (ValueError, IOError, NotImplemented) as e:
                self.logError(`e`)
                self.returnError(stream_id, `e`)
                return
            # Remember the thread keyed by the stream_id that
            # will be included in all subsequent commands from the
            # client:
            self.threads[stream_id] = new_thread
            
            # Share the logging methods with the threads:
            new_thread.logInfo  = self.logInfo
            new_thread.logError = self.logError
            new_thread.logDebug = self.logDebug
            new_thread.logWarn  = self.logWarn
            # Pause the stream so it won't start till client sends
            # a 'play' command:
            cmd_queue.put('pause')
            new_thread.start()
            # Finally, initialize the content field of the response
            # message:
            response_msg.content = '{"streamId" : "%s", "sourceId" : "%s"}' % (stream_id, source_id)
            self.bus.publish(response_msg)
            return

        else:
            # Unrecognized command:
            self.logError('Command not recognized in message %s' % str(controlMsg.content))
            return

    def get_source_id(self, queue):
        '''
        Given a QueueWithEndpoint instance, grab the
        thread that listens to that queue, and ask it
        for the source id it is serving out.
        
        :param queue: queue to the thread whose source id is sought.
        :type queue: QueueWithEndpoint
        '''
        return queue.endpoint.source_id


    def create_list_source_info(self):
        '''
        Return a JSON array of objects:
           [{"sourceId" : "my_source" , "info" : "This is my favorite source."},
            {"sourceId" : "my_other_source, "info" : ''}
            ]
        Both CSV files and MySQL queries are included.
        
        :return JSON construct containing list of source ids and corresponding
            information from the configuration file.
        :raise ValueError if the source list could not be assembled.
        '''
        try:
            csv_sources = self.conf_parser.options('CSVFiles')
        except ConfigParser.NoSectionError:
            # Config file has no CSVFiles section. Shouldn't be, but be defensive:
            csv_sources = []
        try:
            mysql_sources = self.conf_parser.options('MySQLQueries')
        except ConfigParser.NoSectionError:
            # Config file has no MySQLQueries section. Shouldn't be, but be defensive:
            mysql_sources = []

        all_source_ids = []
        all_source_ids.extend(csv_sources)
        all_source_ids.extend(mysql_sources)
        arr_of_dicts = []
        for source_id in all_source_ids:
            source_dict = {'sourceId' : '%s' % source_id} 
            try:
                source_info = self.conf_parser.get('InfoText', source_id)
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                # No info text available for this source:
                arr_of_dicts.append(source_dict)
                continue
            source_dict['info'] = source_info
            arr_of_dicts.append(source_dict)
        try:
            return json.dumps(arr_of_dicts)
        except Exception as e:
            err_msg = "Could not assemble source list: JSONization failed for %s (%s)" % (str(arr_of_dicts), `e`)
            self.logError(err_msg)
            raise ValueError(err_msg)
        
            
    def returnError(self, streamId, errorMsg):
        '''
        Given the streamId of an existing stream, and an
        error message, publish a BusMessage with the given
        message to the topic on which the originating client
        is listening. That topic was derived from the client's
        newStream message. The content field will be:
           {"error" : "<errorMsg>"}
        
        :param streamId: identifier of the stream about which the error message is being sent.
                         this ID is also used as the response channel topic back to the client.
        :type inMsg: str
        :param errorMsg: value of the outgoing message's 'content' JSON "error" field. 
        :type errorMsg: str
        '''
        
        msg = BusMessage()
        msg.topicName = streamId
        msg.content = json.dumps({"error" : '%s'"" % errorMsg})
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
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
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
    
    def sighup_handler(self, sig, frame):
        '''
        Catch SIGHUP, and reload the config file
        in response.
        
        :param sig: signal being sent
        :type sig: int
        :param frame: ?
        :type frame: ?
        '''
        self.logInfo('Reloading config file.')
        self.relaod_config_file()

    def sigusr1_handler(self, sig, frame):
        for (stream_id, one_thread) in self.threads.items():
            self.logInfo('Stream %s (id %s)' % (one_thread.source_id), stream_id)
            self.logInfo('    Sent %s row(s)' % one_thread._sent_sofar)
            self.logInfo('    State: %s' % 'paused' if one_thread.paused else 'running')
            self.logInfo('    Last received command at %s' % one_thread._latest_activity_time.isoformat())
            self.logInfo('------')

class OneStreamServer(threading.Thread):
    
    PUBLISH_LOCK = threading.Lock()
    
    def __init__(self, topic_name, stream_id, cmd_queue, source_id, conf_parser, bus):
        '''
        Thread to serve out one stream to one bus client.
        Communicate with this thread via cmd_queue. Given
        a source_id and an initialized ConfigParser instance,
        find the CSV file to stream to the bus, or the MySQL
        query whose results to stream. The stream_id is the
        id under which the main thread finds this thread.
        
        Thread keeps track of how many rows it has sent
        (property _sent_sofar), and the datetime of the most
        recent command from the client (property _latest_activity_time).
        
        The main thread will periodically check whether 
        the thread's stream has been initialized, but not played
        in more than 
        
        :param topicName: topic to which stream will be published.
        :type topicName: str
        :param stream_id: identifier for this thread
        :type stream_id: str
        :param cmd_queue: queue through which main thread sends 
               client requests that control the stream.
        :type cmd_queue: Queue
        :param source_id: key into the configuration file
        :type source_id: str
        :param conf_parser: initialized configuration parser with 
              values containing CSV file paths or MySQL queries
        :type conf_parser: ConfigParser
        :param bus: the BusAdapter through which to publish
        :type bus: BusAdapter
        '''
        
        super(OneStreamServer, self).__init__()
        
        self.topic_name = topic_name
        self.cmd_queue = cmd_queue
        self._source_id = source_id
        self._stream_id = stream_id
        self.conf_parser = conf_parser
        self.bus = bus
        self.pausing   = False
        self.stopping  = False
        self.inter_batch_delay = DataServer.INTER_BATCH_DELAY
        # Send each 'batch' of 1; if larger, several rows are
        # sent together: 
        self.batch_size = 1
        # No limit on how many rows to send:
        self.max_to_send = -1
        self.source_iterator = None
        
        # How many lines sent to far:
        self._sent_sofar = 0
        # Last time heard from client: 
        self._latest_activity_time = datetime.now()
        
        self.source_iterator = self.get_source_iterator()
        
    @property
    def stream_id(self):
        '''Thread's identifier'''
        return self._stream_id

    @stream_id.setter
    def stream_id(self, val):
        self._stream_id = val
        
    @property
    def source_id(self):
        return self._source_id

    @property
    def sent_sofar(self):
        return self._sent_sofar
    
    @property
    def latest_activity_time(self):
        return self._latest_activity_time

    def stop(self):
        # Pretend the client issued a stop command:
        self.cmd_queue.put_nowait('stop')

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

        # NOTE: the following raises an IOError if CSV file should
        # exist, but does not:
        file_iterator = self.get_csv_iterator()

        # If no CSV iterator, try MySQL iterator.
        # This may raise NotImplemented:
        if file_iterator is None:
            file_iterator = self.get_mysql_iterator()
        else: 
            # CSV file is open. Check whether the data pump config file contains
            # column names for this CSV source:
            try:
                self.colnames = self.conf_parser.get("ColumnNames", self.source_id).strip()
            except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
                # No column names in the config file, so the first line in the
                # CSV file must be the columns, which will be returned as
                # an array of str:
                
                self.colnames = file_iterator.next()
                
                # Now self.colnames has the column names from the first
                # line, or is empty if the entire CSV file is empty, or
                # the first line is empty. If empty, then invent_columns()
                # will come up with reasonable substitutes. 
        
        return file_iterator
        
    def get_csv_iterator(self):
        '''
        Checks whether the configuration file has a CSVFiles-section that
        contains an option keyed as the source_id we are to stream.
        If yes, opens the CSV file and returns a file object.
        
        :returns open file object, or None if no option exists in the config file.
        :rtype CSV reader
        :raise IOError if CSV file specification exists, but file cannot be opened.
        
        '''
        # Is a CSV file path registered in the config file for
        # the given source id?
        try:
            csv_file_name = os.path.expanduser(os.path.expandvars(self.conf_parser.get('CSVFiles', self.source_id)))
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            # No csv file registered:
            return None
        try:
            file_iterator = open(csv_file_name, 'r')
        except IOError:
            raise IOError('Configuration file specs path %s for streamID %s; file does not exist or is not readable' %\
                          (csv_file_name, self.source_id))
        return csv.reader(file_iterator)
        
    def get_mysql_iterator(self):
        raise NotImplemented("MySQL query streams are not yet implemented.")

    
    def run(self):
        
        self._sent_sofar = 0
        tuple_dict_batch = [] #@UnusedVariable
        self.logInfo("Ready to publish '%s' to %s..." % (self.source_id, self.topic_name))
        try:
            # Note: Can't use "for info in self.source_iterator"
            #       for the loop, b/c we want the ability to restart
            #       self.source_iterator from the beginning.
            
            while True:
                try:
                    # Next array of result elements (from CSV file or MySQL query):
                    info = self.source_iterator.next()
                    self._sent_sofar += 1
                except StopIteration:
                    # Sources is exhausted; quit this thread:
                    self.logInfo("Stream '%s' is done." % self.source_id)
                    return

                # Check for control command from client:
                try:
                    cmd = self.cmd_queue.get_nowait()
                    
                    # Update 'last heard from client':
                    self._latest_activity_time = datetime.now()
                    
                    # Do something:
                    if cmd == 'pause':
                        self.pausing = True
                    elif cmd == 'stop':
                        self.stopping = True
                    elif cmd.startswith('changeSpeed'):
                        # We trust that the operator of the other end of
                        # the queue sent a string 'changeSpeed,<fractionalSeconds>':
                        new_speed = cmd.split(',')[1]
                        try:
                            new_speed = float(new_speed)
                        except ValueError:
                            self.logError('The inter_batch_delay parameter for send_all must be float, or int; was %s' % str(new_speed))
                            # Ignore the command
                        else:
                            self.inter_batch_delay = new_speed
                    elif cmd == 'restart':
                        self.source_iterator = self.get_source_iterator()
                        self._sent_sofar = 0;
                        continue
                        
                except Empty:
                    # No new control command:
                    pass
                
                if len(info) == 0:
                    # Empty line in CSV file:
                    continue
                if self.max_to_send > -1 and self._sent_sofar >= self.max_to_send:
                    return                
                tuple_dict_batch.append(self.make_data_dict(info))
                if len(tuple_dict_batch) >= self.batch_size or\
                    len(tuple_dict_batch) + self._sent_sofar >= self.max_to_send:
                    
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
                                         topicName=self.topic_name)

                    # Let's not have multiple streams publish at once. It 
                    # may work, or not. Should...but who knows: 
                    with OneStreamServer.PUBLISH_LOCK:
                        self.bus.publish(bus_msg)
                    self._sent_sofar += len(tuple_dict_batch)
                    tuple_dict_batch = []

                    time.sleep(self.inter_batch_delay)
                    continue
                else:
                    # Continue filling a batch:
                    continue
        finally:
            self.logInfo("Published %s data rows." % self._sent_sofar)
            self.logInfo("Stream '%s' is done." % self.source_id)
    
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
            existing_colnames += ('col-%s' % str(i))
        return existing_colnames

# The following subclasses are no longer used, but 
# I didn't have the heart to take them out yet. Also,
# Let's wait till the MySQL part is implemented:

# class MySQLDataServer(DataServer):
# 
#     def __init__(self, 
#                  query,
#                  topic,
#                  host=DataServer.mysql_default_host, 
#                  port=DataServer.mysql_default_port, 
#                  user=DataServer.mysql_default_user,
#                  pwd=DataServer.mysql_default_pwd, 
#                  db=DataServer.mysql_default_db, 
#                  redis_server='localhost',
#                  colname_arr=[],
#                  max_to_send=-1,
#                  logFile=None,
#                  logLevel=logging.INFO                 
#                  ):
#         '''
#         Constructor
#         '''
#         # Super throws 'TypeError: must be type, not str'
#         # So need to use explicit superclass call...odd. 
#         #super('CSVDataServer', self).__init__(topic)
#         #super('MySQLDataServer', self).__init__(topic)
#         DataServer.__init__(self, topic, logFile=logFile, logLevel=logLevel)
#         self.db = MySQLDB(host=host, port=port, user=user, passwd=pwd, db=db, redis_server=redis_server)
#         # Column name array to superclass instance:
#         self.colnames = colname_arr
#         self.it = self.db.query(query)
#         self.send_all(max_to_send=max_to_send)
#         
# class CSVDataServer(DataServer):
#     
#     def __init__(self, 
#                  fileName,
#                  topic,
#                  first_line_has_colnames=False,
#                  redis_server='localhost',
#                  colnames=[],
#                  max_to_send=-1,
#                  logFile=None,
#                  logLevel=logging.INFO                 
#                  ):
#         # Super throws 'TypeError: must be type, not str'
#         # So need to use explicit superclass call...odd. 
#         #super('CSVDataServer', self).__init__(topic)
#         DataServer.__init__(self, topic, redis_server=redis_server, logFile=logFile, logLevel=logLevel)
#                 
#         fd = open(fileName, 'r')
#         csvreader = csv.reader(fd)
#         # Explicitly provided colnames have precedence
#         # over colnames in first line of file:
#         if len(colnames) > 0:
#             self.colnames = colnames
#             # Trash first line in file if appropriate:
#             if first_line_has_colnames:
#                 csvreader.next()
#         elif first_line_has_colnames:
#             # No explicit col names, but file has them;
#             # send column name array to superclass instance var:
#             self.colnames = csvreader.next()
#         # ... else superclass will invent col names.
#         self.it = csvreader
#         self.send_all(max_to_send=max_to_send)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]), 
                                     formatter_class=argparse.RawTextHelpFormatter)
    
    parser.add_argument('-c', '--config',
                        dest='config_file',
                        help='Configuration file; default is ./dataserver.cnf',
                        default=os.path.join(os.path.dirname(__file__), 'dataserver.cnf'))
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
    parser.add_argument('-l', '--logFile', 
                        help='Fully qualified log file name to which info and error messages \n' +\
                             'are directed. Default: stdout.',
                        dest='logFile',
                        default=None);
    parser.add_argument('-v', '--verbose', 
                        help='Print operational info to log.', 
                        dest='verbose',
                        action='store_true')
    parser.add_argument('--period',
                        dest='period',
                        help="Number fractional seconds to wait between each message. Default is %s" % DataServer.INTER_BATCH_DELAY,
                        default=DataServer.INTER_BATCH_DELAY)

    args = parser.parse_args();

    redis_server = args.redis_server
    
    DataServer.INTER_BATCH_DELAY = args.period
        
    config_parser = ConfigParser.ConfigParser()
    config_file = args.config_file
    # If serving any database queries: Get all the security done:
    if not (os.path.isfile(config_file) and os.access(config_file, os.R_OK)):
            raise IOError('Dataserver config file %s does not exist or is not readable.' % config_file)       

    config_parser.read(config_file)
    
    # If we are to serve out at least on MySQL query,
    # get the security taken care of:
    if config_parser.has_section('MySQLQueries'):
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
    server = DataServer(redis_server=redis_server, 
                        configFile=None, 
                        logFile=None, 
                        logLevel=logging.INFO)
        
#         server = MySQLDataServer(query,
#                                  args.topic, 
#                                  host=host,
#                                  port=port,
#                                  user=user,
#                                  pwd=pwd,
#                                  db=db,
#                                  redis_server=redis_server,
#                                  colname_arr=colnames,
#                                  max_to_send=max_to_send,
#                                  logFile=args.logFile,
#                                  logLevel=logging.DEBUG if args.verbose else logging.INFO
#                                  )
