#!/usr/bin/env python
'''
Created on Feb 2, 2014

Given a course name, compute the student time-on-task (engagement).
Two variants: can use 'All' for course name to have all engagements
computed. Secondly: can add any number of years. When provided, 
only courses whose first event was in any one of those years will
be processed. 

Can be called from commandline, or imported into another module, which
does the little setup in __main__ below, and then invokes run() and
writeToDisk() on an instance of this class. See __main__ for options.
See open_edx_export_class/src/exportClass.py for example of using
this module as a library.

To use, instantiate EngagementComputer, call the run() method,
and then the writeResultsToDisk() method.   

The output are three files: ..._engagementAllCourses_summary.csv,
and ..._engagementAllCourses_allData.csv and _engagementAllCourses_weeklyEffort.csv.
The  ellipses are prefixes to make the files unique. Method writeToDisk()
return the full paths.

The summary file:
TotalStudentSessions,TotalEffortAllStudents,MedPerWeekOneToTwenty,MedPerWeekTwentyoneToSixty,MedPerWeekGreaterSixty

* TotalStudentSessions: the total number of sessions in which at least one minute of time
                        engagement occurred. This counts all sessions for all students.
* TotalEffortAllStudents: total number of engagement minutes across all student.                         
* MedPerWeekOneToTwenty: the number of times in which a weekly median of 1 to 20 minutes of time engagement 
                         was observed, counting each student, each week.
* MedPerWeekTwentyoneToSixty: the number of times in which a weekly median of 21min to 1hr of time engagement 
                         was observed, counting each student, each week.
* MedPerWeekGreaterSixty: the number of times in which a weekly median of >1hr of time engagement 
                         was observed, counting each student, each week.

For example, say a course with 3 learners lasts for two weeks.  The
first week two learners had an observed median session length of 15
minutes. One learner's median was 2hrs. The second week of the course
one learner's median was 25 minutes, and the other two learners
engaged for a median of 13 minutes.

The Median1-20 would be (2 + 2 = 4), the Median21-1hr would be 1, and
the Median>1hr would be 1.


The engagementAllCourses_allData.csv contains every session of every student.

 Platform,Course,anon_screen_name,Date,Time,SessionLength

 * Platform: always OpenEdX
 * Course: full name of course (course_display_name)
 * anon_screen_name: anon_screen_name
 * Date: date of session
 * Time: time of session
 * SessionLength: length of session in minutes
 
Normally all events are considered as engagement. But parameter videoOnly
for the constructor limits events to user video player manipulations.

@author: paepcke
'''
import argparse
import copy
import datetime
import getpass
import numpy
import os
import re
import string
import sys
import tempfile
import time

from pymysql_utils.pymysql_utils import MySQLDB


#from mysqldb import MySQLDB
# Add json_to_relation source dir to $PATH
# for duration of this execution:
source_dir = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../json_to_relation/json_to_relation")]
source_dir.extend(sys.path)
sys.path = source_dir



class EngagementComputer(object):
    
    # Time duration counted for any video event (minutes);
    # This is the median time between clicks across all
    # events:

    #VIDEO_EVENT_DURATION = 500                                                                                                                                        
    VIDEO_EVENT_DURATION = 1                                                                                                                                           
    #VIDEO_EVENT_DURATION = 0                                                                                                                                          
                                                                                                                                                                       
    # Time duration counted for any non-video event (minutes);                                                                                                         
    # This is the median time between clicks across all                                                                                                                
    # events:                                                                                                                                                          
                                                                                                                                                                       
    #NON_VIDEO_EVENT_DURATION = 500                                                                                                                                    
    NON_VIDEO_EVENT_DURATION = 1                                                                                                                                       
    #NON_VIDEO_EVENT_DURATION = 0      
    
    # Database that contains EventXtract table:
    EVENT_XTRACT_TABLE_DB = 'Edx'

    # Recognizing fake course names:
    FAKE_COURSE_PATTERN = re.compile(r'([Tt]est|[Ss]and[Bb]ox|[Dd]avid|[Dd]emo|Humaanities|SampleUniversity|[Jj]ane|ZZZ|Education/EDUC115N[^\s]*\s)')
    
    # Event types that are considered true user
    # engagement:
    trueUserEvents = ['book', 
                      'fullscreen', 
                      'hide_transcript', 
                      'hide_transcript', 
                      'load_video', 
                      'not_fullscreen', 
                      'oe_feedback_response_selected', 
                      'oe_hide_question', 
                      'oe_show_question', 
                      'oe_show_full_feedback', 
                      'oe_show_respond_to_feedback', 
                      'openassessmentblock.get_peer_submission',
                      'openassessmentblock.peer_assess',
                      'openassessmentblock.self_assess',
                      'openassessmentblock.submit_feedback_on_assessments',
                      'openassessment.student_training_assess_example',
                      'openassessment.create_submission',
                      'openassessment.save_submission',
                      'openassessment.upload_file',
                      'page_close', 
                      'pause_video', 
                      'peer_grading_hide_question', 
                      'peer_grading_show_question', 
                      'play_video', 
                      'problem_check', 
                      'problem_graded', 
                      'problem_fail', 
                      'problem_reset', 
                      'problem_save', 
                      'problem_show', 
                      'rubric_select', 
                      'seek_video', 
                      'seq_goto', 
                      'seq_next', 
                      'seq_prev', 
                      'show_transcript', 
                      'speed_change_video', 
                      'staff_grading_hide_question', 
                      'staff_grading_show_question'
                      ]
    
    def __init__(self, 
                coursesStartYearsArr=None, 
                dbHost='localhost', 
                mySQLUser=None, 
                mySQLPwd=None, 
                courseToProfile=None, 
                sessionInactivityThreshold=30,
                videoOnly=False):
        '''
        Sets up one session-accounting run through a properly filled table (as
        per file level comment above.

        :param coursesStartYearsArr: array of the years during which courses under investigation ran.
            If None, then any course (or unconditionally the one matching the courseToProfile if 
            that parm is provided) will be processed. 
        :type coursesStartYearsArr: {[int] | None}
        :param dbHost: MySQL host where the activities table resides 
        :type dbHost: string
        :param mySQLUser: user under which to log into MySQL for the work
        :type mySQLUser: string
        :param mySQLPwd: password to use for MySQL
        :type mySQLPwd: string
        :param courseToProfile: name of course to analyze for sessions. If None all courses 
             that started in one of the years listed in coursesStartYearArr will be examined. 
        :type courseToProfile: [string]
        :param sessionInactivityThreshold: time in minutes of student inactivity beyond which 
               it is concluded that the student is no longer working on the computer in the
               current session.
        :type sessionInactivityThreshold: int
        :param videoOnly: if True, then only video events will be considered.
        :type videoOnly: boolean
        '''
        self.dbHost = dbHost
        self.dbName = 'Edx'
        self.mySQLUser = mySQLUser
        self.mySQLPwd  = mySQLPwd
        if courseToProfile == "None":
            self.courseToProfile = None
        else:
            self.courseToProfile = courseToProfile
        self.videoOnly = videoOnly
        
        self.coursesStartYearsArr = coursesStartYearsArr
        self.sessionInactivityThreshold = sessionInactivityThreshold
        self.timeSpentThisSession = 0.0

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
        self.db = MySQLDB(host=self.dbHost, user=self.mySQLUser, passwd=self.mySQLPwd, db='Edx')
        
    def run(self):
        '''
        Run the analysis. In spite of this method name, the EngagementComputer
        class is not a thread. Goes through every wanted course and every student
        within that course. Partitions student activity times into sessions, and
        does the accounting.
        
        Method uses one of two queries as source for session information:
        one query is used when no course name is provided, and engagement
        is thus computed for all courses, the alternative query is used
        when computation is limited to a single course. Here is an explanation 
        of the query, which creates this table: 

             course_display_name, anon_screen_name, time, isVideo
        
        with one row for each event. The query with comments:
        
        -- 'select *' idiom needed to make MySQL use indexes in query optimizer 
          SELECT *
		  FROM  (
	    -- Grab all events, creating binary 1/0 column 'isVideo' on the fly.
	    -- With the latest approach of using mean time between events by one
	    -- student as default duration for the last event in a session, this isVideo
	    -- column is no longer relevant. It stays included in case we change our mind
	    -- and wish to distinguish between video, and other event types after all:
		  	       SELECT course_display_name,
		  	              anon_screen_name,
		  	              time,
		  	              IF((event_type = 'load_video' OR 
		  	                  event_type = 'play_video' OR 
		  	                  event_type = 'pause_video' OR 
		  	                  event_type = 'seek_video' OR 
		  	                  event_type = 'stop_video' OR 
		  	                  event_type = 'speed_change_video'),1,0)
		  	                 AS isVideo
		  	       FROM Edx.EventXtract
		  	    ) AS MainEvents
		  	    
		 -- Union these events with Forum events
		  UNION ALL
		  	    
		  SELECT * 
		  FROM  (
		  	       SELECT course_display_name,\\
		  	              EdxPrivate.idInt2Anon(forum_uid),
		  	              created_at AS time,
		  	              0 AS isVideo
		  	       FROM EdxForum.contents
		  	    ) AS ForumEvents
		  GROUP BY course_display_name
		  ORDER BY anon_screen_name, time;"            
        
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
        self.timeSpentThisSession = 0.0
        # Num of events in current session:
        self.numEventsThisSession = 1
        self.sessionStartTime = 0
        prevEvent       = None
        currEvent       = None
        # Keep track of the active learners
        # in a course, so they don't get counted
        # multiple times:
        activeLearners  = {}
        numActiveLearners = 0
         
        COURSE_INDEX    = 0
        STUDENT_INDEX   = 1
        TIME_INDEX      = 2
        IS_VIDEO_INDEX  = 3
        
        try:
            self.log('About to start the query; will take a while...')
            queryStartTime = time.time()
            queryEndTimeReported = False
            # Currently not following a sequence
            # of video sessions:
            inVideoSession = False
            if self.courseToProfile is None:
                # Profile all courses. Takes a loooong time.
                # consider disallowing:
                mysqlCmd = "SELECT * \
		  	                FROM  (\
		  	                	     SELECT course_display_name, \
		  	                	            anon_screen_name, \
		  	                	            time, \
		  	                	            IF((event_type = 'play_video' OR event_type = 'stop_video' OR event_type = 'load_video' OR event_type = 'pause_video' OR event_type = 'seek_video' OR event_type = 'speed_change_video'),1,0) AS isVideo \
		  	                	     FROM Edx.EventXtract \
		  	                	     WHERE isUserEvent(event_type) \
		  	                    UNION ALL \
		  	                        SELECT course_display_name, EdxPrivate.idForum2Anon(forum_uid) AS anon_screen_name, created_at AS time, 0 AS isVideo \
		  	                        FROM EdxForum.contents \
		  	                      ) AS AllData\
		  	                ORDER BY course_display_name, anon_screen_name, time;"              
            else:
                mysqlCmd = "SELECT * \
		  	                FROM  (\
		  	                	     SELECT course_display_name, \
		  	                	            anon_screen_name, \
		  	                	            time, \
		  	                	            IF((event_type = 'play_video' OR event_type = 'stop_video' OR event_type = 'load_video' OR event_type = 'pause_video' OR event_type = 'seek_video' OR event_type = 'speed_change_video'),1,0) AS isVideo \
		  	                	     FROM Edx.EventXtract \
		  	                	     WHERE course_display_name = '%s'\
		  	                          AND isUserEvent(event_type) \
		  	                    UNION ALL \
		  	                        SELECT course_display_name, EdxPrivate.idForum2Anon(forum_uid) AS anon_screen_name, created_at AS time, 0 AS isVideo \
		  	                        FROM EdxForum.contents \
		  	                        WHERE course_display_name = '%s'\
		  	                      ) AS AllData\
		  	                ORDER BY course_display_name, anon_screen_name, time;" % (self.courseToProfile, self.courseToProfile)              
                
            queryIterator = self.db.query(mysqlCmd)
                
            for activityRecord in queryIterator:
                if not queryEndTimeReported:
                    self.log('Query done in %s' % str(datetime.timedelta(seconds=(time.time() - queryStartTime))))
                    self.log('Beginning computation.')
                    queryEndTimeReported = True
                currEvent = {'course_display_name' : activityRecord[COURSE_INDEX],
                             'anon_screen_name'    : activityRecord[STUDENT_INDEX],
                             'eventDateTime'       : activityRecord[TIME_INDEX], 
                             'isVideo'             : activityRecord[IS_VIDEO_INDEX]}
                # Check whether it's a demo or sandbox course:
                if self.filterCourses(currEvent):
                    continue
                
                # If we are only to pay attention to 
                # video, then a non-video event is only
                # of interest if we are currently in a 
                # sequence of video actions. In that case
                # the non-video event terminates the video
                # sequence:
                if self.videoOnly:
                    if not currEvent['isVideo'] and not inVideoSession:                    
                        continue
                    else:
                        # Else we are still or now newly in a video session: 
                        if not inVideoSession:
                            # Init start time and number of events
                            # for this new video session:
                            self.initOneSession(currEvent['eventDateTime'])
                            inVideoSession = True
                            # If this is the very first video event
                            # we ever saw, fall into the 'if prevEvent is None' below.
                            # Otherwise go get the next event:
                            if prevEvent is not None:
                                continue
                    # Curr event is not video, but we were in a video
                    # session. So this event closes down the current
                    # session. Continue below to account for last video
                    # action...
                    
                # Is this an invalid student?                
                if self.filterStudents(currEvent['anon_screen_name']):
                    continue
                if prevEvent is None:
                    # First event of this course:
                    # If we are only to consider courses that started during
                    # a particular year, then find this course's start/end times,
                    # and ignore the course if it's not in one of the acceptable
                    # years:
                    if self.coursesStartYearsArr is not None:
                        # Get start and end dates of this class:
                        try:
                            (self.courseStartDate, self.courseEndDate) = self.getCourseRuntime(currEvent['course_display_name'])
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
                    self.currCourse = currEvent['course_display_name']
                    prevEvent = currEvent
                    self.log("Starting on course %s..." % currEvent['course_display_name'])
                    continue

                if currEvent['course_display_name'] != self.currCourse:
                    # Previous event was last event of its course
                    # Account for the last session of current student in the current
                    # class:
                    self.wrapUpSession(self.currStudent, prevEvent['isVideo'], self.timeSpentThisSession, prevEvent['eventDateTime'])
                    self.wrapUpCourse(self.currCourse, self.studentSessionsDict, numActiveLearners)
                    # Start a new course:
                    self.currStudent = currEvent['anon_screen_name']
                    self.currCourse  = currEvent['course_display_name']
                    numActiveLearners = 0
                    currStudentCounted = False
                    activeLearners    = {}
                    if self.videoOnly:
                        # Wait for next video event to start a sequence:
                        inVideoSession = False
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
                    currStudentCounted = False
                    self.currStudent = currEvent['anon_screen_name']
                    if self.videoOnly:
                        # Wait for next video event to start a sequence:
                        inVideoSession = False
                    # If curr event is video related, count this 
                    # learner as active:
                    if currEvent['isVideo']:
                        if not currStudentCounted and not self.currStudent in activeLearners:
                            activeLearners[self.currStudent] = 1
                            numActiveLearners += 1
                            currStudentCounted = True
                    prevEvent = currEvent
                    continue
                else:
                    # Same course and student as previous event:
                    self.addTimeToSession(prevEvent['eventDateTime'], currEvent['eventDateTime'], prevEvent['isVideo'], self.timeSpentThisSession)
                    if self.videoOnly and not currEvent['isVideo']:
                        inVideoSession = False
                    # If curr event is video related, count this 
                    # learner as active:
                    if currEvent['isVideo']:
                        if not currStudentCounted and not self.currStudent in activeLearners:
                            activeLearners[self.currStudent] = 1
                            numActiveLearners += 1
                            currStudentCounted = True
                    prevEvent = currEvent;
                    continue
            # Wrap up the last class:
            if currEvent is not None:
                if self.currStudent is not None:
                    # A None student can land here if there never was
                    # a real student, i.e. self.filterStudents() always
                    # caused the DB cursor loop to continue:
                    self.wrapUpSession(self.currStudent, currEvent['isVideo'], self.timeSpentThisSession, currEvent['eventDateTime'])
                self.sessionStartTime = currEvent['eventDateTime']
                if self.currCourse is not None:
                    self.wrapUpCourse(self.currCourse, self.studentSessionsDict, numActiveLearners)
            if not queryEndTimeReported:
                # Query above yielded an empty set, and we
                # never reported that the query finished:
                self.log('Query done, returning zero results')

        finally:
            if self.db is not None:
                try:
                    self.db.close()
                except Exception as e:
                    self.logErr('Could not close activities db: ' % `e`);

    def addTimeToSession(self, dateTimePrevEvent, dateTimeCurrEvent, prevEventWasVideo, timeSpentSoFar):
        '''
        Called when a new event by a student is being processed. Adds the
        event time to self.timeSpentThisSession. If time since previous
        event > self.sessionInactivityThreshold, the current session is finalized, and
        a new session is started.

        :param dateTimePrevEvent:
        :type dateTimePrevEvent:
        :param dateTimeCurrEvent:
        :type dateTimeCurrEvent:
        :param prevEventWasVideo:
        :type prevEventWasVideo:
        :param timeSpentSoFar:
        :type timeSpentSoFar:
        '''
        if self.sessionStartTime == 0:
            self.sessionStartTime = dateTimeCurrEvent
        timeDelta = dateTimeCurrEvent - dateTimePrevEvent
        minutes   = round(timeDelta.total_seconds()/60.0)
        if minutes > self.sessionInactivityThreshold:
            self.wrapUpSession(self.currStudent, prevEventWasVideo, timeSpentSoFar, dateTimeCurrEvent)
        else:
            newTimeSpent = timeSpentSoFar + timeDelta.total_seconds()
            self.timeSpentThisSession = newTimeSpent
            self.numEventsThisSession += 1

    def wrapUpStudent(self, anonStudent, wasVideo, timeSpentSoFar):
        '''
        Last event for a student in one course

        :param studentSessions:
        :type studentSessions:
        :param studentAnon:
        :type studentAnon:
        :param eventTime:
        :type eventTime:
        :param wasVideo: was previous event video?
        :type wasVideo: Boolean
        '''
        pass
    
    def wrapUpSession(self, currentStudent, wasVideo, timeSpentSoFar, dateTimeNewSessionStart):
        '''
        A student event is more than self.sessionInactivityThreshold after the previous
        event by the same student in the same class.

        :param currentStudent: student who is currently under analysis
        :type currentStudent: string
        :param wasVideo: whether or not the current event is a video event
        :type wasVideo: boolean
        :param timeSpentSoFar: cumulative time spent by this student in this session
        :type timeSpentSoFar: datetime
        :param dateTimeNewSessionStart: when the upcoming session will start (i.e. current event's time)
        :type dateTimeNewSessionStart: datetime
        '''
        if wasVideo:
            newTimeSpentSoFar = timeSpentSoFar + EngagementComputer.VIDEO_EVENT_DURATION
        else:
            newTimeSpentSoFar = timeSpentSoFar + EngagementComputer.NON_VIDEO_EVENT_DURATION
        try:
            self.studentSessionsDict[currentStudent]
        except KeyError:
            self.studentSessionsDict[currentStudent] = []
        self.studentSessionsDict[currentStudent].append((self.sessionStartTime, newTimeSpentSoFar, self.numEventsThisSession))
        self.timeSpentThisSession = 0
        
        self.initOneSession(dateTimeNewSessionStart)
        
    def initOneSession(self, dateTimeNewSessionStart):
        # Init num of events in session, but account for the event that's 
        # beyond this session, yet was already pulled from the log:
        self.numEventsThisSession = 1
        
        self.sessionStartTime = dateTimeNewSessionStart

            
    def wrapUpCourse(self, courseName, studentSessionsDict, numActiveLearners):
        '''
        Called when all students of one class have been
        processed. This method receives a dict that maps
        each student of the class being closed out to 
        an array of that student's session times and lenghts. 
        For each student session, the dict value is an
        array of two-tuples: (sessionStartTime,sessionLength).
        The studentSessionsDict thus looks like this:
            {student1 : [(firstTimeS1, 10), (secondTimeS1, 4), ...]
             student2 : [(firstTimeS2, 10), (secondTimeS2, 4), ...]
             
        Important: The times within each array are sorted, so
        sessionStartTime_n+1 > sessionStartTime_n.
        We take advantage of this fact to optimize.

        :param studentSessionsDict:
        :type studentSessionsDict:
        :param numActiveLearners: number of learners who created at least
               one 'real' event.
        :type numActiveLearners: int
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
            numWeeks = self.courseWeekNumber(startDate, endDate)
            oneToTwentyMin = 0
            twentyoneToSixtyMin = 0
            greaterSixtyMin = 0
            
            totalEffortAllStudents = 0
            totalStudentSessions    = 0
            
            studentSessionsLeftToDo = {}
            
            for weekNum in range(numWeeks+1):
                weekStart = startDate + weekNum * datetime.timedelta(weeks=1)
                weekEnd   = weekStart + datetime.timedelta(weeks=1)
                for student in self.studentSessionsDict.keys():
                    thisWeekThisStudentSessionList = []
                    
                    try:
                        # If we looked at this student before (i.e. during
                        # an earlier week, retrieve the array of sessionTime/Len
                        # two-tuples that are left to process: 
                        dateAndSessionLenArr = studentSessionsLeftToDo[student]
                    except KeyError:
                        # First time we see this student. 
                        # Get a *copy* of this student's array of time-sorted sessionTime/sessionLen tuples.
                        # The copying takes time, but working on a copy
                        # will allows us to delete elements we are done with
                        # for the purpose of this loop, rather than having to
                        # go through all the elements left to right each time
                        # through the loop below:
                        dateAndSessionLenArr = copy.copy(self.studentSessionsDict[student])
                        studentSessionsLeftToDo[student] = dateAndSessionLenArr

                    if len(dateAndSessionLenArr) == 0:
                        continue
                    while True: 
                        try:
                            # Always just look at first sessionTime/Len tuple,
                            # because we remove the front of the array each time around:
                            (eventDateTime, engageDurationSecs, numEventsThisSession) = dateAndSessionLenArr[0] #@UnusedVariable
                        except IndexError:
                            # Done with this student
                            break
                        
                        if not isinstance(eventDateTime, datetime.datetime):
                            # self.sessionStartTime was never changed from 0 to
                            # the start of a session. The student never had 
                            #self.logErr("Expected datetime, but got %s ('%s') from dateAndSessionLenArr." % 
                            #                 (type(eventDateTime), str(eventDateTime)))
                            # Don't want to see this array entry again:
                            dateAndSessionLenArr.pop(0)
                            continue
                        if eventDateTime < weekStart or engageDurationSecs == 0: 
                            # Don't want to see this array entry again:
                            dateAndSessionLenArr.pop(0)
                            continue
                        if eventDateTime > weekEnd:
                            # Since session start times in the array are
                            # sorted, no need to continue going through 
                            # the array if session date > end of the 
                            # currently considered week. Note that we
                            # do *not* pop the first element of the
                            # array, so that it will be picked up next time:
                            break
                        thisWeekThisStudentSessionList.append(engageDurationSecs)
                        # Don't want to see this array entry again:
                        dateAndSessionLenArr.pop(0)
                        
                    if len(thisWeekThisStudentSessionList) == 0:
                        continue
                    # Got all session lengths of this student this week:
                    totalStudentSessions += len(thisWeekThisStudentSessionList)
                    studentMedianThisWeek = numpy.median(thisWeekThisStudentSessionList)
                    # Convert to minutes to find the right per-week session length
                    # for this student:
                    studentMedianThisWeek = round(studentMedianThisWeek / 60.0)
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
                        
            self.classStats[courseName] = (numActiveLearners, totalStudentSessions, int(round(totalEffortAllStudents)), oneToTwentyMin, twentyoneToSixtyMin, greaterSixtyMin)
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
        if anon_screen_name in ["9c1185a5c5e9fc54612808977ee8f548b2258d31", 
                                'c8ced366_1048_4b4a_8e36_aa60f7b53dd8', 
                                '-1', 
                                '0',
                                None]:
            return True
        if len(anon_screen_name) == 0:
            return True
        
        return False
        
    def filterCourses(self, currEvent):
        course_display_name = currEvent['course_display_name']
        if course_display_name is None:
            return True
        if len(course_display_name) == 0:
            return True
        # Catch all course names containing demo, sandbox, david,
        # and any space-including versions of the Education/EDUC115N/How_to_Learn_Math
        # course:
        if EngagementComputer.FAKE_COURSE_PATTERN.search(course_display_name) is not None:
            return True 
        if course_display_name == 'Education/EDUC115N/How_to_Lean_Math':
            return True
        try:
            int(course_display_name)
            return True
        except ValueError:
            return False
                
        
    def getCourseRuntime(self, courseName):
        '''
        Query Edx.CourseInfo for the start and end date of the 
        given course. Uses table CourseInfo. If end date in CourseInfo
        is the null date (0000-00-00 00:00:00), then end date 
        is determined by the last event observed in this course.

        :param courseName: name of course whose times are to be found
        :type courseName: String
        :return: Two-tuple with start and end time. May be (None, None) if times 
            could not be found
        :rtype: (datetime, datetime)
        '''
        try:
            try:
                runtimeLookupDb = MySQLDB(host=self.dbHost, user=self.mySQLUser, passwd=self.mySQLPwd, db=EngagementComputer.EVENT_XTRACT_TABLE_DB)
            except Exception as e:
                self.logErr('While looking up course start/end times in getCourseRuntime(): %s' % `e`)
                return(None,None)
            
            courseRunIt = runtimeLookupDb.query("SELECT start_date, end_date FROM Edx.CourseInfo WHERE course_display_name = '%s';" % courseName)
            try:
                (startDate, endDate) = courseRunIt.next()
                # For courses without end time, make the end
                # time the time of the most recent observed event:
                if endDate is None:
                    for lastDate in runtimeLookupDb.query("SELECT MAX(time) FROM Edx.EventXtract WHERE course_display_name = '%s';" % courseName):
                        # The (single) result is a on-tuple
                        # like: (datetime.datetime(2014, 8, 7, 3, 52, 15),):
                        endDate = lastDate[0] 
            except (StopIteration, IndexError):
                (startDate, endDate) = (None, None) 
            return (startDate, endDate) 
            
#             # The following commented code uses first and last observation,
#             # instead of the CourseInfo table to determine course duration:
#             # Get start/end time via earliest/latest observed events for given course:
#             query = 'SELECT MIN(time) AS course_start_date,\
#                             MAX(time) AS course_end_date\
#                             FROM EventXtract\
#                             WHERE course_display_name = "%s";' % courseName
#             
#             for runtimes in runtimeLookupDb.query(query):
#                 if runtimes is None:
#                     return(None,None)
#                 return (runtimes[0], runtimes[1])
#             # No start/end times found for this course:
#             self.logErr("Did not find start/end times for class '%s'" % courseName)
#             return (None,None)
        except ValueError as e:
            self.logErr("While attempting lookup of course start/end times: info for course %s not found" % courseName)
            return (None,None)
        except Exception as e:
            self.logErr("While attempting lookup of course start/end times: '%s'" % `e`)
            return (None,None)
        finally:
            try:
                runtimeLookupDb.close()
            except Exception as e:
                self.logErr('Could not close runtime lookup db: %s' % `e`);
  
    def allDataIterator(self):
        for courseName in self.allStudentsDicts.keys():
            sessionsByStudentDict = self.allStudentsDicts[courseName]
            for student in sessionsByStudentDict.keys():
                sessionsArr = sessionsByStudentDict[student]
                for dateMinutesTuple in sessionsArr:
                    try:
                        yield '%s,%s,%s,%s,%d,%d\n' % (courseName,
                                                    student,
                                                    dateMinutesTuple[0].date(),
                                                    dateMinutesTuple[0].time(),
                                                    dateMinutesTuple[1],   # total time in session
                                                    dateMinutesTuple[2])   # num of events in session
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
        
        :return: Tri-tuple with paths to three files:
                 outFileSummary: one line per course with total sessions, cumulative median weekly effort and such.
                 outFileAll: big file with all sessions of each student in each class
                 outFileWeeklyEffort: shows sum of weekly efforts for each student, week by week.

        :rtype: (string,string,string)
        '''
        # If we considered only video events, we 
        # add 'vidOnly' to each of the three result
        # file names, else we don't:
        if self.videoOnly:
            videoNote = '_vidOnly_'
        else:
            videoNote = '_' 
        if self.courseToProfile is None:
            # Analysis was requested for all courses.
            # The summary goes into one file:
            outFileSummary = tempfile.NamedTemporaryFile(suffix='_engagementAllCourses%ssummary.csv' % videoNote, delete=False)
            # File for all student engagement numbers:
            outFileAll     = tempfile.NamedTemporaryFile(suffix='_engagementAllCourses%sallData.csv' % videoNote, delete=False)
            # File for weekly student effort summary in each course:
            outFileWeeklyEffort = tempfile.NamedTemporaryFile(suffix='_engagementAllCourses%sweeklyEffort.csv' % videoNote, delete=False)
        else:
            # Analysis was requested for a single course.
            # The summary goes into /tmp/engagement_<courseNameNoSpacesOrSlashes>_summary.csv:
            courseNameNoSpaces = string.replace(string.replace(self.courseToProfile,' ',''), '/', '_')
            outFileSummary = tempfile.NamedTemporaryFile(suffix='_engagement_%s%ssummary.csv' % (courseNameNoSpaces, videoNote), delete=False)
            outFileAll     = tempfile.NamedTemporaryFile(suffix='_engagement_%s%sallData.csv' % (courseNameNoSpaces, videoNote), delete=False)
            outFileWeeklyEffort = tempfile.NamedTemporaryFile(suffix='_engagement_%s%sweeklyEffort.csv' % (courseNameNoSpaces, videoNote), delete=False)
        try:
            # For classes that actually have results: write them:
            if len(self.classStats.keys()) > 0:
                # Summary file:
                outFileSummary.write('Platform,Course,NumActiveLearners,TotalEffortAllStudents(hrs),TotalStudentSessions,TotalEffortAllStudents(secs),MedPerWeekOneToTwenty,MedPerWeekTwentyoneToSixty,MedPerWeekGreaterSixty\n')
                for className in self.classStats.keys():
                    output = 'OpenEdX,' + className + ',' + re.sub(r'[\s()]','',str(self.classStats[className]))
                    outFileSummary.write(output + '\n')
                outFileSummary.flush()
                # Big detail file    
                outFileAll.write('Platform,Course,anon_screen_name,Date,Time,SessionLength(sec),NumEventsInSession\n')
                for csvSessionRecord in self.allDataIterator():
                    outFileAll.write('OpenEdX,' + csvSessionRecord)
                outFileAll.flush()    
                # Student weekly effort summary:
                outFileWeeklyEffort.write('Platform,Course,anon_screen_name,Week,Effort (sec)\n')
                # For all dicts of form {student1->[[weekNum0,xMins],[weekNum1,yMins],...,],
                #                        student2->[[...]
                for course in self.allStudentsWeeklyEffortDict.keys():
                    # Get one student's time engagement for all the weeks in this course:
                    studentWeeklyEffortDict = self.allStudentsWeeklyEffortDict[course]
                    for student in studentWeeklyEffortDict.keys():
                        # For this student get array of weekNum/time pairs:
                        studentWeeklyEffort = studentWeeklyEffortDict[student]
                        for weekNumEffortPair in studentWeeklyEffort:
                            # Weeks up to this point have been zero-based.
                            # Add one to the course week-number to make 
                            # it 1-based:
                            outFileWeeklyEffort.write('OpenEdX,%s,%s,%d,%d\n' % (course,student,weekNumEffortPair[0]+1,weekNumEffortPair[1]))
                outFileWeeklyEffort.flush()
        finally:
            outFileSummary.close()
            outFileAll.close()
            outFileWeeklyEffort.close()
            return(outFileSummary.name,outFileAll.name,outFileWeeklyEffort.name)
        
    def courseWeekNumber(self, courseStartDate, date):
        '''
        Given a course start date, and some other, later
        date, return the week number of the course. It is
        the caller's responsibility to check whether the 
        number of returned weeks exceeds the duration of the
        course.
        
        @param courseStartDate:
        @type courseStartDate:
        @param date:
        @type date:
        '''
        if date < courseStartDate:
            return None
        if date.year == courseStartDate.year:
            dateWeek = self.weekNumber(date)
            courseStartWeek = self.weekNumber(courseStartDate)
            weekDiff = dateWeek - courseStartWeek + 1
            return weekDiff
        # Number of full years between the two dates.
        # Ex: date=2014, courseStartDate=2013: 0 full years.
        # Ex: date=2014, courseStartDate=2012: 1 full year: 2013
        fullYearsDiff = (date.year - courseStartDate.year) - 1
        weeksLeftInCourseDate = (datetime.datetime(date.year,12,31) - courseStartDate).days / 7
        totalWeeksDiff = weeksLeftInCourseDate + 52*fullYearsDiff + self.weekNumber(date)
        return totalWeeksDiff 
        
    def weekNumber(self, date):
        '''
        Given a date (or datetime) return the number
        of the week in the year. Note, we do not use ISO, because
        its behavior is unexpeded at the start/end of year. For instance,
        in 2013, Dec 29 was a Sunday. So Jan 1 was the following Wed.
        ISO places Dec 29 into week 1 of 2014. Instead this method
        returns 52. We do use isocalendar as a foundation, but then
        correct for Dec and Jan.
        
        Weeks start on Monday.

        :param date: datetime object for date whose week-in-the-year is to be returned 
        :type date: datetime
        :return: number of week in the year by ISO standard.
        :rtype: int
        '''
        #***return ((date - datetime.datetime(date.year,1,1)).days / 7) + 1
        isoWeekNum = date.isocalendar()[1]
        if isoWeekNum == 1 and date.month == 12:
            return 52
        if isoWeekNum > 51 and date.month == 1:
            # Mon-Sat?
            if date.isocalendar()[2] < 7:
                return 1
            else:
                # Sun:
                return 2
        return isoWeekNum
    

    def courseWeekDate(self, courseStartDate, weekNum):
        '''
        Given a course start date and a number of weeks into the
        course, return the absolute date.
        
        @param courseStartDate: date when course starts
        @type courseStartDate: datetime.datetime
        @param weekNum: number of week into the course. First week is 1
        @type weekNum: int
        '''
        return courseStartDate + datetime.timedelta(7 * (weekNum -1))
        
        
    def numWeeksToEOY(self, date):
        '''
        Returns number of weeks between given date and end of the
        date's year.
        
        @param date: date whose remaining weeks in its year are to be computed
        @type date: datetime.datetime
        '''
        return 1 + (datetime.datetime(date.year,12,31) - date).days / 7
        
    def log(self, msg):
        print('%s: %s' %  (str(datetime.datetime.now()), msg))
        sys.stdout.flush()
        
    def logErr(self, msg):
        sys.stderr.write('     %s: %s\n' %  (str(datetime.datetime.now()), msg))
        sys.stderr.flush()

if __name__ == '__main__':
    
    # -------------- Manage Input Parameters ---------------
    
    usage = 'Usage: engagement.py [{courseName | None} [<year-as-YYYY>, <year-as-YYYY>, ...]]\n'

    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]), formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-u', '--user',
                        action='store',
                        help='User ID that is to log into MySQL. Default: the user who is invoking this script.')
    parser.add_argument('-p', '--pwd',
                        action='store_true',
                        help='Request to be asked for pwd for operating MySQL;\n' +\
                             '    default: content of scriptInvokingUser$Home/.ssh/mysql if --user is unspecified,\n' +\
                             '    or, if specified user is root, then the content of scriptInvokingUser$Home/.ssh/mysql_root.'
                        )
    parser.add_argument('-w', '--password',
                        action='store',
                        help='User explicitly provided password to log into MySQL.\n' +\
                             '    default: content of scriptInvokingUser$Home/.ssh/mysql if --user is unspecified,\n' +\
                             '    or, if specified user is root, then the content of scriptInvokingUser$Home/.ssh/mysql_root.'
                        )
    parser.add_argument('-v', '--videoOnly', 
                        help='Only consider video events as engagement (default: consider all types).', 
                        dest='videoOnly',
                        default=False,
                        action='store_true');
    parser.add_argument('course',
                        action='store',
                        help='The course for which engagement is to be computed. Else: engagement for all courses.\n' +\
                             "To have engagement computed for all courses, use All"
                        ) 
    
    # Optionally: any number of years as ints:
    parser.add_argument('years',
                        nargs='*',
                        type=int,
                        help='A list of start years (YYYY) to limit the courses that are computed. Leave out if all start years are acceptable'
                        ) 
    
    
    args = parser.parse_args();
    if args.user is None:
        user = getpass.getuser()
    else:
        user = args.user
        
    if args.password and args.pwd:
        raise ValueError('Use either -p, or -w, but not both.')
        
    if args.pwd:
        pwd = getpass.getpass("Enter %s's MySQL password on localhost: " % user)
    elif args.password:
        pwd = args.password
    else:
        # Try to find pwd in specified user's $HOME/.ssh/mysql
        currUserHomeDir = os.getenv('HOME')
        if currUserHomeDir is None:
            pwd = None
        else:
            # Don't really want the *current* user's homedir,
            # but the one specified in the -u cli arg:
            userHomeDir = os.path.join(os.path.dirname(currUserHomeDir), user)
            try:
                if user == 'root':
                    with open(os.path.join(currUserHomeDir, '.ssh/mysql_root')) as fd:
                        pwd = fd.readline().strip()
                else:
                    with open(os.path.join(userHomeDir, '.ssh/mysql')) as fd:
                        pwd = fd.readline().strip()
            except IOError:
                # No .ssh subdir of user's home, or no mysql inside .ssh:
                pwd = ''
    
    if args.course.lower() == 'all':
        courseName = None
    else:
        courseName = args.course
    
    if len(args.years) == 0 or args.years[0] == 0:
        years = None
    else:
        years = args.years
        
    #**********
#     print('courseName: %s' % str(courseName))
#     print('years: %s' % str(years))
#     sys.exit()
    #**********
        
    # -------------- Run the Computation ---------------

    invokingUser = getpass.getuser()
    # Set mysql password to None, which will cause
    # the __init__() method to check ~/.ssh...
    comp = EngagementComputer(coursesStartYearsArr=years, dbHost='localhost', mySQLUser=invokingUser, mySQLPwd=None, courseToProfile=courseName, videoOnly=args.videoOnly)
    comp.run()
    
    # -------------- Output Results to Disk ---------------
    (summaryFile, detailFile, weeklyEffortFile) = comp.writeResultsToDisk()
    if os.path.getsize(summaryFile) == 0 and os.path.getsize(detailFile) == 0 and os.path.getsize(weeklyEffortFile) == 0:
        comp.log('No course qualified given year constraints.')
    else: 
        comp.log("Your results are in %s, %s, and %s." % (summaryFile, detailFile, weeklyEffortFile))
