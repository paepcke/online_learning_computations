'''
Created on Aug 4, 2014

@author: paepcke
'''
import datetime
import unittest

from src.engagement import EngagementComputer


class Test(unittest.TestCase):

    def setUp(self):
        self.engageComputer = EngagementComputer([0], 
                                                 'localhost',
                                                 mySQLUser='unittest', 
                                                 mySQLPwd=None, 
                                                 courseToProfile='Medicine/SciWrite/Fall2013',
                                                 sessionInactivityThreshold=30)
    def testWeekComputations(self):
        earlyJan = datetime.datetime(2014,1,4)
        janLastDayFirstWeek = datetime.datetime(2014,1,7)
        janFirstDaySecondWeek = datetime.datetime(2014,1,8)
        self.assertEqual(1, self.engageComputer.weekNumber(earlyJan))
        self.assertEqual(1, self.engageComputer.weekNumber(janLastDayFirstWeek))
        self.assertEqual(2, self.engageComputer.weekNumber(janFirstDaySecondWeek))
        
        lastDayOf52ndWeek = datetime.datetime(2014,12,30)
        lastDayInYear = datetime.datetime(2014,12,31)
        self.assertEqual(52, self.engageComputer.weekNumber(lastDayOf52ndWeek))
        self.assertEqual(53, self.engageComputer.weekNumber(lastDayInYear))
        
        self.assertEqual(1, self.engageComputer.numWeeksToEOY(lastDayOf52ndWeek))
        self.assertEqual(1, self.engageComputer.numWeeksToEOY(lastDayInYear))
        lastDayOf51stWeek = datetime.datetime(2014,12,23)
        self.assertEqual(2, self.engageComputer.numWeeksToEOY(lastDayOf51stWeek))
        
        courseStartDate = datetime.datetime(2014,1,6)
        courseWeek1Date = datetime.datetime(2014,1,12)
        courseWeek2Date = datetime.datetime(2014,1,15)
        self.assertEqual(1, self.engageComputer.courseWeekNumber(courseStartDate, courseWeek1Date))
        self.assertEqual(2, self.engageComputer.courseWeekNumber(courseStartDate, courseWeek2Date))
        
        courseStartDate = datetime.datetime(2014,1,6)
        dateInFirstWeek = datetime.datetime(2014,1,7)
        self.assertEqual(1, self.engageComputer.courseWeekNumber(courseStartDate, dateInFirstWeek)) 

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.test']
    unittest.main()