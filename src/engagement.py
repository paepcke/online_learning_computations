#!/usr/bin/env python
'''
Created on Feb 2, 2014

Can be called from commandline, or imported into another module, which
does the little setup in __main__ below, and then invokes run() and
writeToDisk() on an instance of this class. A convenience script 
scripts/computeEngagement.sh is available, but not necessary.

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


Also assumes availability of the following DB table;
See scripts/prepEngagementAnalysis.sh for how to build
that table:

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
The course end time is only used to filter
out courses that seem to have lasted less than 7 days.
Those courses tend to be test courses.

The output are three files: /tmp/engagement.log,  /tmp/engagementAllCourses_summary.csv,
and /tmp/engagementAllCourses_allData.csv. The summary file:

TotalStudentSessions,TotalEffortAllStudents,MedPerWeekOneToTwenty,MedPerWeekTwentyoneToSixty,MedPerWeekGreaterSixty

- TotalStudentSessions: the total number of sessions in which at least one minute of time
                        engagement occurred. This counts all sessions for all students.
- TotalEffortAllStudents: total number of engagement minutes across all student.                         
- MedPerWeekOneToTwenty: the number of weeks in which a median of 1 to 20 minutes of time engagement 
                         was observed, counting each student, each week.
- MedPerWeekTwentyoneToSixty: the number of weeks in which a median of 21min to 1hr of time engagement 
                         was observed, counting each student, each week.
- MedPerWeekGreaterSixty: the number of weeks in which a median >1hr of time engagement 
                         was observed, counting each student, each week.
                        

The engagementAllCourses_allData.csv contains every session of every student.

 Platform,Course,Student,Date,Time,SessionLength
 
 - Platform: always OpenEdX
 - Course: full name of course (course_display_name)
 - Student: anon_screen_name
 - Date: date of session
 - Time: time of session
 - SessionLength: length of session in minutes
 

@author: paepcke
'''
import datetime
import getpass
import math
import numpy
import os
import re
import string
import sys
import tempfile
import time

from mysqldb import MySQLDB


# Add json_to_relation source dir to $PATH
# for duration of this execution:
source_dir = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../json_to_relation/json_to_relation")]
source_dir.extend(sys.path)
sys.path = source_dir



class EngagementComputer(object):
    
    # Time in minutes within which a student activity event
    # must follow her previous event to be counted
    # as having occurred within one session:
    SESSION_TIMEOUT = 3 * 60
    
    # Time duration counted for any video event (minutes):
    VIDEO_EVENT_DURATION = 15
    
    # Time duration counted for any non-video event (minutes):
    NON_VIDEO_EVENT_DURATION = 5
    
    # Recognizing fake course names:
    FAKE_COURSE_PATTERN = re.compile(r'([Tt]est|[Ss]and[Bb]ox|[Dd]avid|[Dd]emo|Humaanities|SampleUniversity|[Jj]ane|ZZZ|Education/EDUC115N[^\s]*\s)')
    
    def __init__(self, coursesStartYearsArr, dbHost, dbName, tableName, mySQLUser=None, mySQLPwd=None, courseToProfile=None):
        '''
        Sets up one session-accounting run through a properly filled table (as
        per file level comment above.
        @param coursesStartYearsArr: array of the years during which courses under investigation ran.
            If None, then any course (or unconditionally the one matching the courseToProfile if 
            that parm is provided) will be processed. 
        @type coursesStartYearsArr: {[int] | None}
        @param dbHost: MySQL host where the activities table resides 
        @type dbHost: string
        @param dbName: name of db within server in which the activities table resides. Use 
            this parameter to place test tables into, say the 'test' database. Point this dbName
            parameter to 'test' and all ops will look for the activities table and CourseRuntimes
            table in that db.
        @type dbName: string
        @param tableName: name of table that holds the activities as per file level header. 
        @type tableName: string
        @param mySQLUser: user under which to log into MySQL for the work
        @type mySQLUser: string
        @param mySQLPwd: password to use for MySQL
        @type mySQLPwd: string
        @param courseToProfile: name of course to analyze for sessions. If None all courses 
             that started in one of the years listed in coursesStartYearArr will be examined. 
        @type courseToProfile: [string]
        '''
        self.dbHost = dbHost
        self.dbName = dbName
        self.tableName = tableName
        self.mySQLUser = mySQLUser
        self.mySQLPwd  = mySQLPwd
        self.courseToProfile = courseToProfile
        self.coursesStartYearsArr = coursesStartYearsArr
        # To keep track of which course runtimes
        # we already output an error msg for,
        # b/c we didn't find it:
        self.runtimesNotFoundCourses = []
        
        if mySQLUser is None:
            self.mySQLUser = getpass.getuser()
        if mySQLPwd is None:
            # Try to get it from .ssh/mysql file of user
            try:
                homeDir = os.path.expanduser('~' + mySQLUser)
                pwdFile = os.path.join(homeDir,'.ssh/mysql')
                with open(pwdFile, 'r') as fd:
                    self.mySQLPwd = fd.readline().strip()
            except Exception:
                self.mySQLPwd = ''
        # Place to hold all stats for one class
        self.classStats = {}
        self.db = MySQLDB(host=self.dbHost, user=self.mySQLUser, passwd=self.mySQLPwd, db=dbName)
        # Ensure that the CourseRuntimes table exists:
        self.getCourseRuntime('fakename', testOnly=True)        
        
    def run(self):
        '''
        Run the analysis. In spite of this method name, the EngagementComputer
        class is not a thread. Goes through every wanted course and every student
        within that course. Partitions student activity times into sessions, and
        does the accounting.
        '''
        self.studentSessionsDict   = {}
        # For saving all sessions for all students across all classes:
        self.allStudentsDicts = {}
        # For saving week by week effort of each student in a class.
        # Each student has a dict of week-by-week effort for each
        # class: 
        self.allStudentsWeeklyEffortDict ={}
        self.currStudent      = None
        self.currCourse       = None
        self.timeSpentThisSession = 0
        self.sessionStartTime = 0
        prevEvent       = None
        currEvent       = None
         
        COURSE_INDEX    = 0
        STUDENT_INDEX   = 1
        TIME_INDEX      = 2
        IS_VIDEO_INDEX  = 3
        
        try:
            self.log('About to start the query; will take a while...')
            queryStartTime = time.time()
            queryEndTimeReported = False
            if self.courseToProfile is None:
                # Profile all courses:
                queryIterator = self.db.query('SELECT course_display_name, anon_screen_name, time, isVideo FROM %s ORDER BY course_display_name, anon_screen_name, time;' % 
                                              self.tableName)
            else:
                queryIterator = self.db.query('SELECT course_display_name, anon_screen_name, time, isVideo FROM %s WHERE course_display_name = "%s" ORDER BY anon_screen_name, time;' % 
                                              (self.tableName, self.courseToProfile))
            for activityRecord in queryIterator:
                if not queryEndTimeReported:
                    self.log('Query done in %s' % str(datetime.timedelta(seconds=(time.time() - queryStartTime))))
                    queryEndTimeReported = True
                currEvent = {'course_display_name' : activityRecord[COURSE_INDEX],
                             'anon_screen_name'    : activityRecord[STUDENT_INDEX],
                             'eventDateTime'       : activityRecord[TIME_INDEX], 
                             'isVideo'             : activityRecord[IS_VIDEO_INDEX]}
                if prevEvent is None:
                    # First event of this course:
                    # Check whether it's a demo or sandbox course:
                    if self.filterCourses(currEvent):
                        continue
                    #... or a ghost student:
                    if self.filterStudents(currEvent['anon_screen_name']):
                        continue
                    if len(currEvent['anon_screen_name']) > 0 and\
                       len(currEvent['course_display_name']) > 0:
                        self.currStudent = currEvent['anon_screen_name']
                        self.currCourse  = currEvent['course_display_name']
                        # Get start and end dates of this class:
                        try:
                            (self.courseStartDate, self.courseEndDate) = self.getCourseRuntime(self.currCourse)
                        except Exception as e:
                            self.logErr("While calling getCourseRuntime() from run(): '%s'" % `e`)
                            continue
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
                        self.log("Starting on course %s..." % currEvent['course_display_name'])
                    continue

                # Is this an invalid student?                
                if self.filterStudents(currEvent['anon_screen_name']):
                    continue
                if currEvent['course_display_name'] != self.currCourse:
                    # Previous event was last event of its course
                    # Is this new event processable? I.e. does it have
                    # all the info we need? If not, skip this event: 
                    if self.filterCourses(currEvent):
                        continue
                    if len(currEvent['anon_screen_name']) > 0 and\
                       len(currEvent['course_display_name']) > 0:
                        # Account for the last session of current student in the current
                        # class:
                        self.wrapUpSession(self.currStudent, prevEvent['isVideo'], self.timeSpentThisSession, prevEvent['eventDateTime'])
                        self.wrapUpCourse(self.currCourse, self.studentSessionsDict)
                        # Start a new course:
                        self.currStudent = currEvent['anon_screen_name']
                        self.currCourse  = currEvent['course_display_name']
                        self.sessionStartTime = currEvent['eventDateTime']
                        prevEvent = currEvent
                        self.log("Starting on course %s..." % self.currCourse)
                    continue
                # Steady state: Next event in same course as
                # previous event:
                if currEvent['anon_screen_name'] != self.currStudent:
                    # Same course as prev event, but different student:
                    # Account for this last session of this student in the current
                    # class:
                    self.wrapUpSession(self.currStudent, currEvent['isVideo'], self.timeSpentThisSession, prevEvent['eventDateTime'])
                    self.sessionStartTime = currEvent['eventDateTime']
                    self.wrapUpStudent(self.currStudent, prevEvent['isVideo'], self.timeSpentThisSession)
                    self.currStudent = currEvent['anon_screen_name']
                    prevEvent = currEvent
                    continue
                else:
                    # Same course and student as previous event:
                    self.addTimeToSession(prevEvent['eventDateTime'], currEvent['eventDateTime'], prevEvent['isVideo'], self.timeSpentThisSession)
                    prevEvent = currEvent;
                    continue
            # Wrap up the last class:
            if currEvent is not None:
                self.wrapUpSession(self.currStudent, currEvent['isVideo'], self.timeSpentThisSession, currEvent['eventDateTime'])
                self.sessionStartTime = currEvent['eventDateTime']
                self.wrapUpCourse(self.currCourse, self.studentSessionsDict)
        finally:
            if self.db is not None:
                try:
                    self.db.close()
                except Exception as e:
                    self.logErr('Could not close activities db: ' % `e`);

    def addTimeToSession(self, dateTimePrevEvent, dateTimeCurrEvent, isVideo, timeSpentSoFar):
        '''
        Called when a new event by a student is being processed. Adds the
        event time to self.timeSpentThisSession. If time since previous
        event > SESSION_TIMEOUT, the current session is finalized, and
        a new session is started.
        @param dateTimePrevEvent:
        @type dateTimePrevEvent:
        @param dateTimeCurrEvent:
        @type dateTimeCurrEvent:
        @param isVideo:
        @type isVideo:
        @param timeSpentSoFar:
        @type timeSpentSoFar:
        '''
        if self.sessionStartTime == 0:
            self.sessionStartTime = dateTimeCurrEvent
        timeDelta = dateTimeCurrEvent - dateTimePrevEvent
        minutes   = round(timeDelta.total_seconds()/60.0)
        if minutes > EngagementComputer.SESSION_TIMEOUT:
            self.wrapUpSession(self.currStudent, isVideo, timeSpentSoFar, dateTimeCurrEvent)
        else:
            newTimeSpent = timeSpentSoFar + minutes
            self.timeSpentThisSession = newTimeSpent

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
    
    def wrapUpSession(self, currentStudent, wasVideo, timeSpentSoFar, dateTimeNewSessionStart):
        '''
        A student event is more than SESSION_TIMEOUT after the previous
        event by the same student in the same class.
        @param currentStudent: student who is currently under analysis
        @type currentStudent: string
        @param wasVideo: whether or not the current event is a video event
        @type wasVideo: boolean
        @param timeSpentSoFar: cumulative time spent by this student in this session
        @type timeSpentSoFar: datetime
        @param dateTimeNewSessionStart: when the upcoming session will start (i.e. current event's time)
        @type dateTimeNewSessionStart: datetime
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
        self.sessionStartTime = dateTimeNewSessionStart

            
    def wrapUpCourse(self, courseName, studentSessionsDict):
        '''
        Called when all students of one class have been
        processed. This method receives a dict that maps
        each student of the class being closed out to 
        an array of that student's session time.
        
        
        @param studentSessionsDict:
        @type studentSessionsDict:
        '''
        try:
            # Data struct to hold student --> [[week0,x],[week1,y],...],
            # where x,y,... are minutes of engagement.
            studentPerWeekEffort = {}

            # Get start and end dates of this class:
            (startDate,endDate) = self.getCourseRuntime(courseName)
            if startDate is None or endDate is None or\
                not isinstance(startDate, datetime.datetime) or\
                not isinstance(endDate, datetime.datetime):
                return False
            if endDate < startDate:
                self.logErr("%s: endDate (%s) < startDate(%s)" % (courseName, endDate, startDate))
                return False
            # Partition into weeks:
            courseDurationDelta = endDate - startDate;
            courseDays = courseDurationDelta.days
            if courseDays < 7:
                self.logErr("%s: lasted less than one week (endDate %s; startDate%s)" % (courseName, endDate, startDate))
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
                        if not isinstance(eventDateTime, datetime.datetime):
                            self.logErr("Expected datetime, but got %s ('%s') from dateAndSessionLenArr." % 
                                             (type(eventDateTime), str(eventDateTime)))
                            continue
                        if eventDateTime < weekStart or\
                           eventDateTime > weekEnd or\
                           engageDurationMins == 0:
                            continue
                        thisWeekThisStudentSessionList.append(engageDurationMins)
                    if len(thisWeekThisStudentSessionList) == 0:
                        continue
                    # Got all session lengths of this student this week:
                    totalStudentSessions += len(thisWeekThisStudentSessionList)
                    studentMedianThisWeek = numpy.median(thisWeekThisStudentSessionList)
                    if studentMedianThisWeek < 20:
                        oneToTwentyMin += 1
                    elif studentMedianThisWeek < 60:
                        twentyoneToSixtyMin += 1
                    else:
                        greaterSixtyMin += 1
                    sumEffortThisStudentThisWeek = sum(thisWeekThisStudentSessionList)
                    # Update this student's efforts with the effort expended this week:
                    # First occurrence of this student?
                    try:
                        thisStudentRecord = studentPerWeekEffort[student]
                    except KeyError:
                        studentPerWeekEffort[student] = thisStudentRecord = []
                    thisStudentRecord.append([weekNum, sumEffortThisStudentThisWeek])  
                    totalEffortAllStudents += sumEffortThisStudentThisWeek
                        
            self.classStats[courseName] = (totalStudentSessions, int(round(totalEffortAllStudents)), oneToTwentyMin, twentyoneToSixtyMin, greaterSixtyMin)
        finally:
            # Save this course's record of all student sessions
            self.allStudentsDicts[courseName] = self.studentSessionsDict
            self.allStudentsWeeklyEffortDict[courseName] = studentPerWeekEffort
            # Start a new sessions record for
            # the next course we'll tackle: 
            self.studentSessionsDict = {}
            self.log("Done with course %s." % courseName)
        return True
        
    def filterStudents(self, anon_screen_name):
        if anon_screen_name == "9c1185a5c5e9fc54612808977ee8f548b2258d31":
            return True
        
    def filterCourses(self, currEvent):
        if len(currEvent['course_display_name']) == 0:
            return True
        if currEvent['anon_screen_name'] == '3c1276fa_c58b_43ef_bafa_d4d9f18bedf5' or currEvent['anon_screen_name'] == 'c8ced366_1048_4b4a_8e36_aa60f7b53dd8':
            return True
        # Catch all course names containing demo, sandbox, david,
        # and any space-including versions of the Education/EDUC115N/How_to_Learn_Math
        # course:
        if EngagementComputer.FAKE_COURSE_PATTERN.search(currEvent['course_display_name']) is not None:
            return True 
        if currEvent['course_display_name'] == 'Education/EDUC115N/How_to_Lean_Math':
            return True
        
        
        
    def getCourseRuntime(self, courseName, testOnly=False):
        
        # Already provided an error msg for this course name?
        if courseName in self.runtimesNotFoundCourses:
            return(None,None)
        
        try:
            try:
                runtimeLookupDb = MySQLDB(host=self.dbHost, user=self.mySQLUser, passwd=self.mySQLPwd, db=self.dbName)
            except Exception as e:
                self.logErr('While looking up course start/end times in getCourseRuntime(): %s' % `e`)
                return (None,None)
            if testOnly:
                # Just ensure that the 'CourseRuntimes' table exists so
                # that we can fail early:
                try:
                    runtimeLookupDb.query("SELECT course_start_date, course_end_date FROM CourseRuntimes LIMIT 1;")
                    return
                except Exception as e:
                    raise ValueError('Cannot read CourseRuntimes table: %s' % `e`)
                
            for runtimes in runtimeLookupDb.query("SELECT course_start_date, course_end_date FROM CourseRuntimes WHERE course_display_name = '%s';" % courseName):
                return (runtimes[0], runtimes[1])
            # No start/end times found for this course:
            self.logErr("Did not find start/end times for class '%s'" % courseName)
            self.runtimesNotFoundCourses.append(courseName)
            return (None,None)
        except Exception as e:
            self.logErr("While attempting lookup of course start/end times: '%s'" % `e`)
            return (None,None)
        finally:
            try:
                runtimeLookupDb.close()
            except Exception as e:
                self.logErr('Could not close runtime lookup db: %s' % `e`);
  
    def getVideoLength(self):
        return EngagementComputer.VIDEO_EVENT_DURATION # minutes
    
    def allDataIterator(self):
        for courseName in self.allStudentsDicts.keys():
            sessionsByStudentDict = self.allStudentsDicts[courseName]
            for student in sessionsByStudentDict.keys():
                sessionsArr = sessionsByStudentDict[student]
                for dateMinutesTuple in sessionsArr:
                    try:
                        yield '%s,%s,%s,%s,%d\n' % (courseName,
                                                    student,
                                                    dateMinutesTuple[0].date(),
                                                    dateMinutesTuple[0].time(),
                                                    dateMinutesTuple[1])
                    except AttributeError as e:
                        self.logErr('In allDataIterator() dataMinutesTuple[0] was bad: (%s): %s' % (str(dateMinutesTuple),`e`));

    def writeResultsToDisk(self):
        '''
        Assumes that run() has been called, and that therefore 
        instance self.classStats is a dictionary with all computed
        stats for each class. Computes three final results, and writes
        them to three temp files. Returns three-tuple with names of
        those files. The files are tempfiles, and will therefore not
        be overwritten by multiple successive calls.
        
        @return: Tri-tuple with paths to three files:
                 outFileSummary: one line per course with total sessions, cumulative median weekly effort and such.
                 outFileAll: big file with all sessions of each student in each class
                 outFileWeeklyEffort: shows sum of weekly efforts for each student, week by week.
        @rtype: (string,string,string)
        '''
        if courseToProfile is None:
            # Analysis was requested for all courses.
            # The summary goes into one file:
            outFileSummary = tempfile.NamedTemporaryFile(suffix='_engagementAllCourses_summary.csv', delete=False)
            # File for all student engagement numbers:
            outFileAll     = tempfile.NamedTemporaryFile(suffix='_engagementAllCourses_allData.csv', delete=False)
            # File for weekly student effort summary in each course:
            outFileWeeklyEffort = tempfile.NamedTemporaryFile(suffix='_engagementAllCourses_weeklyEffort.csv', delete=False)
        else:
            # Analysis was requested for a single course.
            # The summary goes into /tmp/engagement_<courseNameNoSpacesOrSlashes>_summary.csv:
            courseNameNoSpaces = string.replace(string.replace(courseToProfile,' ',''), '/', '_')
            outFileSummary = tempfile.NamedTemporaryFile(suffix='_engagement_%s_summary.csv' % courseNameNoSpaces, delete=False)
            outFileAll     = tempfile.NamedTemporaryFile(suffix='_engagement_%s_allData.csv' % courseNameNoSpaces, delete=False)
            outFileWeeklyEffort = tempfile.NamedTemporaryFile(suffix='_engagement_%s_weeklyEffort.csv' % courseNameNoSpaces, delete=False)
        try:
            # For classes that actually have results: write them:
            if len(self.classStats.keys()) > 0:
                # Summary file:
                outFileSummary.write('platform,course_display_name,TotalStudentSessions,TotalEffortAllStudents,MedPerWeekOneToTwenty,MedPerWeekTwentyoneToSixty,MedPerWeekGreaterSixty\n')
                for className in self.classStats.keys():
                    output = 'OpenEdX,' + className + ',' + re.sub(r'[\s()]','',str(self.classStats[className]))
                    outFileSummary.write(output + '\n') 
                # Big detail file    
                outFileAll.write('Platform,Course,Student,Date,Time,SessionLength\n')
                for csvSessionRecord in self.allDataIterator():
                    outFileAll.write('OpenEdX,' + csvSessionRecord)
                    
                # Student weekly effort summary:
                outFileWeeklyEffort.write('platform,course,student,week,effortMinutes\n')
                # For all dicts of form {student1->[[weekNum0,xMins],[weekNum1,yMins],...,],
                #                        student2->[[...]
                for course in self.allStudentsWeeklyEffortDict.keys():
                    # Get one student's time engagement for all the weeks in this course:
                    studentWeeklyEffortDict = self.allStudentsWeeklyEffortDict[course]
                    for student in studentWeeklyEffortDict.keys():
                        # For this student get array of weekNum/time pairs:
                        studentWeeklyEffort = studentWeeklyEffortDict[student]
                        for weekNumEffortPair in studentWeeklyEffort:
                            outFileWeeklyEffort.write('OpenEdX,%s,%s,%d,%d\n' % (course,student,weekNumEffortPair[0],weekNumEffortPair[1]))
        finally:
            outFileSummary.close()
            outFileAll.close()
            outFileWeeklyEffort.close()
            return(outFileSummary.name,outFileAll.name,outFileWeeklyEffort.name)
        
    def log(self, msg):
        print('%s: %s' %  (str(datetime.datetime.now()), msg))
        sys.stdout.flush()
        
    def logErr(self, msg):
        sys.stderr.write('     %s: %s\n' %  (str(datetime.datetime.now()), msg))
        sys.stderr.flush()

if __name__ == '__main__':
    
    # -------------- Manage Input Parameters ---------------
    if len(sys.argv) < 2:
        sys.stderr.write('Usage: engagement.py <year as YYYY [courseName]\n')
        sys.exit()
    yearToProfile = sys.argv[1]
    if len(sys.argv) > 2:
        courseToProfile = sys.argv[2]
    else:
        courseToProfile = None
        
    # -------------- Run the Computation ---------------
    #***** Switch between testing and real:
    #testing = True
    testing = False
    if testing:
        db = 'test'
    else:
        db = 'Misc'
    invokingUser = getpass.getuser()
    comp = EngagementComputer([int(yearToProfile)], 'localhost', db, 'Activities', mySQLUser=invokingUser, mySQLPwd=None, courseToProfile=courseToProfile)
    comp.run()
    
    # -------------- Output Results to Disk ---------------
    (summaryFile, detailFile, weeklyEffortFile) = comp.writeResultsToDisk()
    comp.log("Your results are in %s, %s, and %s." % (summaryFile, detailFile, weeklyEffortFile))