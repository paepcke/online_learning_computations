'''
Created on Feb 2, 2014

Assumes availability of the following DB table:
mysql> DESCRIBE Activities;
+---------------------+--------------+------+-----+---------------------+-------+
| Field               | Type         | Null | Key | Default             | Extra |
+---------------------+--------------+------+-----+---------------------+-------+
| course_display_name | varchar(255) | NO   |     |                     |       |
| anon_screen_name    | text         | NO   |     | NULL                |       |
| event_type          | text         | NO   |     | NULL                |       |
| time                | datetime     | NO   |     | 0000-00-00 00:00:00 |       |
| isVideo             | tinyint(4)   | NO   |     | 0                   |       |
+---------------------+--------------+------+-----+---------------------+-------

Example rows:
| Education/EDUC115N/How_to_Learn_Math | 00014bffc716bf9d8d656d2f668f737cd43acde8 | seek_video | 2013-07-20 22:56:36      | 1 |
| Education/EDUC115N/How_to_Learn_Math | 00014bffc716bf9d8d656d2f668f737cd43acde8 | hide_transcript | 2013-07-20 22:57:28 | 0 |
| Education/EDUC115N/How_to_Learn_Math | 00014bffc716bf9d8d656d2f668f737cd43acde8 | play_video | 2013-07-20 22:59:36      | 1 |

Grouped by course, then student, and ordered by time.
See scripts/prepEngagementAnalysis.sh for how to build
that table:

@author: paepcke
'''
import datetime
import getpass
import os

from json_to_relation.mysqldb import MySQLDB


class EngagementComputer(object):
    
    # Time in minutes within which a student activity event
    # must follow her previous event to be counted
    # as having occurred within one session:
    SESSION_TIMEOUT = 3 * 60
    
    # Time duration counted for any video event (minutes):
    VIDEO_EVENT_DURATION = 15
    
    # Time duration counted for any non-video event (minutes):
    NON_VIDEO_EVENT_DURATION = 5
    
    def __init__(self, dbHost, dbName, tableName, mySQLUser=None, mySQLPwd=None):
        self.dbHost = dbHost
        self.dbName = dbName
        self.tableName = tableName
        if mySQLUser is None:
            mySQLUser = getpass.getuser()
        if mySQLPwd is None:
            # Try to get it from .ssh/mysql file of user
            try:
                homeDir = os.path.expanduser('~' + mySQLUser)
                pwdFile = os.path.join(homeDir,'mysql')
                with open(pwdFile, 'r') as fd:
                    mySQLPwd = fd.readline()
            except Exception:
                pass
        # Place to hold all stats for one class
        self.classStats = {}
        self.db = MySQLDB(host=dbHost, user=mySQLUser, passwd=mySQLPwd, db=dbName)
        
    def run(self):
        studentSessionsDict   = {}
        sessions        = []
        currStudent     = None
        currCourse      = None
        prevEvent       = None
        timeSpent       = 0
        prevActivityRec = None
         
        COURSE_INDEX    = 0
        STUDENT_INDEX   = 1
        TIME_INDEX      = 2
        IS_VIDEO_INDEX  = 3
        
        for activityRecord in self.db.query('SELECT course_display_name, anon_screen_name, time, isVideo FROM %s;' % self.tableName):
            currEvent = {'course_display_name' : activityRecord[COURSE_INDEX],
                         'anon_screen_name'    : activityRecord[STUDENT_INDEX],
                         'eventDateTime'       : datetime.datetime.strptime(activityRecord[TIME_INDEX], 
                                                                  '%Y-%m-%d %H:%M:%S'),
                         'isVideo'             : activityRecord[IS_VIDEO_INDEX]}
            if prevEvent is None:
                # First event of this course:
                currStudent = currEvent.anon_screen_name
                currCourse  = currEvent.course_display_name
                prevEvent = currEvent
                continue
            
            if currEvent['course_display_name'] != currCourse:
                # Previous event was last event of its course:
                self.wrapUpCourse()
                # Start a new course:
                currCourse = currEvent['course_display_name']
                currStudent = currEvent.anon_screen_name
                prevEvent = currEvent;
                continue
            # Steady state: Next event in same course as
            # previous event:
            if currEvent['anon_screen_name'] != currStudent:
                # Same course as prev event, but different student:
                timeLastEvent = self.wrapUpStudent(prevEvent['anon_screen_name'],
                                                   prevEvent['eventDateTime'],
                                                   prevEvent['isVideo'],
                                                   timeSpent)
                timeSpent += timeLastEvent
                sessions.append(timeSpent)
                studentSessionsDict[currStudent] = sessions
                currStudent = currEvent['anon_screen_name']
                sessions = []
                prevEvent = currEvent
            else:
                # Same course and student as previous event:
                (timeSpent,sessionOver) = self.addTimeToSession(prevEvent.eventDateTime, currEvent.eventDateTime, prevEvent.isVideo, timeSpent)
                timeSpent += timeLastEvent
                if sessionOver:
                    sessions.append(timeSpent)

    def addTimeToSession(self, dateTimePrevEvent, dateTimeCurrEvent, isVideo, timeSpentSoFar):
        timeDelta = dateTimeCurrEvent - dateTimePrevEvent
        minutes   = round(timeDelta.seconds/60.0)
        if minutes > EngagementComputer.SESSION_TIMEOUT:
            newTimeSpent = self.wrapUpSession(isVideo, timeSpentSoFar)
            sessionOver = True
        else:
            newTimeSpent = timeSpentSoFar + minutes
            sessionOver = False
        return (newTimeSpent, sessionOver)

    def wrapUpStudent(self, studentSessions, studentAnon, lastStudentEventTime, wasVideo, timeSpentSoFar):
        '''
        Last event for a student in one course
        @param studentSessions:
        @type studentSessions:
        @param studentAnon:
        @type studentAnon:
        @param eventTime:
        @type eventTime:
        @param wasVideo: was previous event video?
        @type wasVideo: Boolean
        '''
        # Account for this last session of this student in the current
        # class:
        sessions = self.wrapUpSession(studentSessions, wasVideo, timeSpentSoFar)
        return sessions
        
    
    def wrapUpSession(self, wasVideo, timeSpentSoFar):
        '''
        A student event is more than SESSION_TIMEOUT after the previous
        event by the same student in the same class.
        @param sessions:
        @type sessions:
        @param time:
        @type time:
        @param wasVideo:
        @type wasVideo:
        @param timeSpentSoFar:
        @type timeSpentSoFar:
        '''
        if wasVideo:
            timeSpentThisSession = timeSpentSoFar + self.getVideoLength()
        else:
            timeSpentThisSession = timeSpentSoFar + EngagementComputer.NON_VIDEO_EVENT_DURATION
        return timeSpentThisSession
            
    def wrapUpClass(self, studentSessionsDict):
        '''
        Called when all students of one class have been
        processed. This method receives a dict that maps
        each student of the class being closed out to 
        an array of that student's session time.
        
        
        @param studentSessionsDict:
        @type studentSessionsDict:
        '''
        print("Would bin a class")
        
            
    def getVideoLength(self):
        return EngagementComputer.VIDEO_EVENT_DURATION # minutes

if __name__ == '__main__':
    comp = EngagementComputer('localhost', 'Misc', 'Activities', mySQLUser='paepcke', mySQLPwd=None)
    comp.run()
    
    