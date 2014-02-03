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


Also assumes availability of the following DB table:

mysql> DESCRIBE CourseRuntimes;
+---------------------+--------------+------+-----+---------+-------+
| Field               | Type         | Null | Key | Default | Extra |
+---------------------+--------------+------+-----+---------+-------+
| course_display_name | varchar(255) | YES  |     | NULL    |       |
| course_start_date   | datetime     | YES  |     | NULL    |       |
| course_end_date     | datetime     | YES  |     | NULL    |       |
+---------------------+--------------+------+-----+---------+-------+

Example rows:
mysql> SELECT * FROM CourseRuntimes;
+-------------------------------------------------------+---------------------+---------------------+
| course_display_name                                   | course_start_date   | course_end_date     |
+-------------------------------------------------------+---------------------+---------------------+
| Medicine/SciWrite/Fall2013                            | 2013-11-10 06:45:16 | 2013-11-17 06:56:35 |
| Engineering/EE-222/Applied_Quantum_Mechanics_I        | 2013-11-10 06:54:21 | 2013-11-17 06:54:21 |
| Engineering/Solar/Fall2013                            | 2013-11-10 06:44:13 | 2013-11-17 07:00:26 |
| Engineering/CS144/Introduction_to_Computer_Networking | 2013-11-10 06:52:22 | 2013-11-17 06:58:49 |
+-------------------------------------------------------+---------------------+---------------------+
4 rows in set (0.00 sec)

Grouped by course, then student, and ordered by time.
See scripts/prepEngagementAnalysis.sh for how to build
that table:

@author: paepcke
'''
import datetime
import getpass
import math
import numpy
import os
import re
import sys

from mysqldb import MySQLDB


class EngagementComputer(object):
    
    # Time in minutes within which a student activity event
    # must follow her previous event to be counted
    # as having occurred within one session:
    SESSION_TIMEOUT = 3 * 60
    
    # Time duration counted for any video event (minutes):
    VIDEO_EVENT_DURATION = 15
    
    # Time duration counted for any non-video event (minutes):
    NON_VIDEO_EVENT_DURATION = 5
    
    def __init__(self, coursesStartYearsArr, dbHost, dbName, tableName, mySQLUser=None, mySQLPwd=None):
        self.dbHost = dbHost
        self.dbName = dbName
        self.tableName = tableName
        self.mySQLUser = mySQLUser
        self.mySQLPwd  = mySQLPwd
        self.coursesStartYearsArr = coursesStartYearsArr
        
        if mySQLUser is None:
            self.mySQLUser = getpass.getuser()
        if mySQLPwd is None:
            # Try to get it from .ssh/mysql file of user
            try:
                homeDir = os.path.expanduser('~' + mySQLUser)
                pwdFile = os.path.join(homeDir,'.ssh/mysql')
                with open(pwdFile, 'r') as fd:
                    self.mySQLPwd = fd.readline()
            except Exception:
                self.mySQLPwd = ''
        # Place to hold all stats for one class
        self.classStats = {}
        self.db = MySQLDB(host=self.dbHost, user=self.mySQLUser, passwd=self.mySQLPwd, db=dbName)
        
    def run(self):
        self.studentSessionsDict   = {}
        self.sessions         = []
        self.currStudent      = None
        self.currCourse       = None
        self.timeSpentThisSession = 0
        self.sessionStartTime = 0
        prevEvent       = None
         
        COURSE_INDEX    = 0
        STUDENT_INDEX   = 1
        TIME_INDEX      = 2
        IS_VIDEO_INDEX  = 3
        
        for activityRecord in self.db.query('SELECT course_display_name, anon_screen_name, time, isVideo FROM %s ORDER BY course_display_name, time;' % self.tableName):
            currEvent = {'course_display_name' : activityRecord[COURSE_INDEX],
                         'anon_screen_name'    : activityRecord[STUDENT_INDEX],
                         'eventDateTime'       : activityRecord[TIME_INDEX], 
                         'isVideo'             : activityRecord[IS_VIDEO_INDEX]}
            if prevEvent is None:
                # First event of this course:
                if len(currEvent['anon_screen_name']) > 0 and\
                   len(currEvent['course_display_name']) > 0:
                    self.currStudent = currEvent['anon_screen_name']
                    self.currCourse  = currEvent['course_display_name']
                    # Get start and end dates of this class:
                    (self.courseStartDate, self.courseEndDate) = self.getCourseRuntime(self.currCourse)
                    # If getCourseRuntime() failed, that method will have logged
                    # the error, so we just continue:
                    if self.courseStartDate is None or self.courseEndDate is None:
                        continue
                    # Only deal with classes that started in the 
                    # desired year:
                    if not self.courseStartDate.year in self.coursesStartYearsArr:
                        continue
                    self.sessionStartTime = currEvent['eventDateTime']
                    prevEvent = currEvent
                continue
            
            if currEvent['course_display_name'] != self.currCourse:
                # Previous event was last event of its course:
                # Account for the last session of current student in the current
                # class:
                self.wrapUpSession(self.currStudent, currEvent['isVideo'], self.timeSpentThisSession)
                self.sessionStartTime = currEvent['eventDateTime']
                self.wrapUpCourse(self.currCourse, self.studentSessionsDict)
                # Start a new course:
                if len(currEvent['anon_screen_name']) > 0 and\
                   len(currEvent['course_display_name']) > 0:
                    self.currStudent = currEvent['anon_screen_name']
                    self.currCourse  = currEvent['course_display_name']
                    self.sessionStartTime = currEvent['eventDateTime']
                    prevEvent = currEvent
                continue
            # Steady state: Next event in same course as
            # previous event:
            if currEvent['anon_screen_name'] != self.currStudent:
                # Same course as prev event, but different student:
                # Account for this last session of this student in the current
                # class:
                self.wrapUpSession(self.currStudent, currEvent['isVideo'], self.timeSpentThisSession)
                self.sessionStartTime = currEvent['eventDateTime']
                self.wrapUpStudent(self.currStudent, prevEvent['isVideo'], self.timeSpentThisSession)
                self.currStudent = currEvent['anon_screen_name']
                prevEvent = currEvent
            else:
                # Same course and student as previous event:
                self.addTimeToSession(prevEvent['eventDateTime'], currEvent['eventDateTime'], prevEvent['isVideo'], self.timeSpentThisSession)


    def addTimeToSession(self, dateTimePrevEvent, dateTimeCurrEvent, isVideo, timeSpentSoFar):
        if self.sessionStartTime == 0:
            self.sessionStartTime = dateTimeCurrEvent
        timeDelta = dateTimeCurrEvent - dateTimePrevEvent
        minutes   = round(timeDelta.seconds/60.0)
        if minutes > EngagementComputer.SESSION_TIMEOUT:
            self.wrapUpSession(isVideo, timeSpentSoFar)
        else:
            newTimeSpent = timeSpentSoFar + minutes
            self.timeSpentThisSession += newTimeSpent

    def wrapUpStudent(self, anonStudent, wasVideo, timeSpentSoFar):
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
        pass
    
    def wrapUpSession(self, currentStudent, wasVideo, timeSpentSoFar):
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
            newTimeSpentSoFar = timeSpentSoFar + self.getVideoLength()
        else:
            newTimeSpentSoFar = timeSpentSoFar + EngagementComputer.NON_VIDEO_EVENT_DURATION
        try:
            self.studentSessionsDict[currentStudent]
        except KeyError:
            self.studentSessionsDict[currentStudent] = []
        self.studentSessionsDict[currentStudent].append((self.sessionStartTime, newTimeSpentSoFar))
        self.timeSpentThisSession = 0
            
    def wrapUpCourse(self, courseName, studentSessionsDict):
        '''
        Called when all students of one class have been
        processed. This method receives a dict that maps
        each student of the class being closed out to 
        an array of that student's session time.
        
        
        @param studentSessionsDict:
        @type studentSessionsDict:
        '''
        #**************
        #print('%s: %s' % (courseName, str(studentSessionsDict)))
        #**************        
        # Get start and end dates of this class:
        (startDate,endDate) = self.getCourseRuntime(courseName)
        #*****
        #print ("Course: %s: %s to %s" % (courseName, str(startDate), str(endDate)))
        #*****
        if startDate is None or endDate is None:
            return False
        if endDate < startDate:
            sys.stderr.write("%s: endDate (%s) < startDate(%s)\n" % (courseName, endDate, startDate))
            return False
        # Partition into weeks:
        courseDurationDelta = endDate - startDate;
        courseDays = courseDurationDelta.days
        if courseDays < 7:
            sys.stderr.write("%s: lasted less than one week (endDate %s; startDate%s)\n" % (courseName, endDate, startDate))
            return False
        numWeeks = int(math.ceil(courseDays / 7))
        oneToTwentyMin = 0
        twentyoneToSixtyMin = 0
        greaterSixtyMin = 0
        
        totalEffortAllStudents = 0
        totalStudentSessions    = 0
        
        for weekNum in range(numWeeks):
            weekStart = startDate + weekNum * datetime.timedelta(weeks=1)
            weekEnd   = weekStart + datetime.timedelta(weeks=1)
            for student in self.studentSessionsDict.keys():
                thisWeekThisStudentSessionList = []
                dateAndSessionLenArr = self.studentSessionsDict[student]
                for (eventDateTime, engageDurationMins) in dateAndSessionLenArr:
                    if eventDateTime < weekStart or\
                       eventDateTime > weekEnd or\
                       engageDurationMins == 0:
                        continue
                    thisWeekThisStudentSessionList.append(engageDurationMins)
                # Got all session lengths of this student this week:
                studentMedianThisWeek = numpy.median(thisWeekThisStudentSessionList)
                if studentMedianThisWeek > 0:
                    totalStudentSessions += 1
                if studentMedianThisWeek < 20:
                    oneToTwentyMin += 1
                elif studentMedianThisWeek < 60:
                    twentyoneToSixtyMin += 1
                else:
                    greaterSixtyMin += 1
                totalEffortAllStudents += sum(thisWeekThisStudentSessionList)
                    
        self.classStats[courseName] = (totalStudentSessions, totalEffortAllStudents, oneToTwentyMin, twentyoneToSixtyMin, greaterSixtyMin) 

        return True
        
    def getCourseRuntime(self, courseName):
        runtimeLookupDb = MySQLDB(host=self.dbHost, user=self.mySQLUser, passwd=self.mySQLPwd, db='Misc')
        for runtimes in runtimeLookupDb.query("SELECT course_start_date, course_end_date FROM CourseRuntimes WHERE course_display_name = '%s';" % courseName):
            return (runtimes[0], runtimes[1])
        # No start/end times found for this course:
        sys.stderr.write("Did not find start/end times for class '%s'\n" % courseName)
        return (None,None)
    
    def getVideoLength(self):
        return EngagementComputer.VIDEO_EVENT_DURATION # minutes

if __name__ == '__main__':
    comp = EngagementComputer([2013], 'localhost', 'Misc', 'Activities', mySQLUser='paepcke', mySQLPwd=None)
    comp.run()
    with open('/tmp/engageTest.csv', 'w') as fd:
        fd.write('TotalStudentSessions,TotalEffortAllStudents,MedPerWeekOneToTwenty,MedPerWeekTwentyoneToSixty,MedPerWeekGreaterSixty\n')
        for className in comp.classStats.keys():
            output = className + ',' + re.sub(r'[\s()]','',str(comp.classStats[className]))
            fd.write(output + '\n') 
    
    #******
    #print(str(comp.classStats))
    #******    
    