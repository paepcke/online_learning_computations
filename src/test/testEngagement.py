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
        earlyJan = datetime.datetime(2010,1,1)
        janLastDayFirstWeek = datetime.datetime(2010,1,2)
        janFirstDaySecondWeek = datetime.datetime(2010,1,3)
        self.assertEqual(1, self.engageComputer.weekNumber(earlyJan))
        self.assertEqual(1, self.engageComputer.weekNumber(janLastDayFirstWeek))
        self.assertEqual(2, self.engageComputer.weekNumber(janFirstDaySecondWeek))
        
        earlyDec = datetime.datetime(2009,12,27)
        firstDay53rdWeek = datetime.datetime(2009,12,28)
        mid53rdWeek = datetime.datetime(2009,12,29)
        last53rdWeek = datetime.datetime(2009,12,31)
        self.assertEqual(52, self.engageComputer.weekNumber(earlyDec))
        self.assertEqual(53, self.engageComputer.weekNumber(firstDay53rdWeek))        
        self.assertEqual(53, self.engageComputer.weekNumber(mid53rdWeek))
        self.assertEqual(53, self.engageComputer.weekNumber(last53rdWeek))
        
        
        
        
        lastDayOf51stWeek = datetime.datetime(2014,12,28)
        lastDayInYear = datetime.datetime(2014,12,31)
        self.assertEqual(52, self.engageComputer.weekNumber(lastDayOf51stWeek))
        self.assertEqual(52, self.engageComputer.weekNumber(lastDayInYear))
        
        self.assertEqual(1, self.engageComputer.numWeeksToEOY(lastDayInYear))
        lastDayOf51stWeek = datetime.datetime(2014,12,23)
        self.assertEqual(2, self.engageComputer.numWeeksToEOY(lastDayOf51stWeek))
        
        courseStartDate = datetime.datetime(2014,1,6)
        courseWeek1Date = datetime.datetime(2014,1,11)
        # Sunday:
        courseWeek1stEndWeekDate = datetime.datetime(2014,1,12)
        # Monday:
        courseWeek2ndWeekDate = datetime.datetime(2014,1,13)
        self.assertEqual(1, self.engageComputer.courseWeekNumber(courseStartDate, courseWeek1Date))
        self.assertEqual(1, self.engageComputer.courseWeekNumber(courseStartDate, courseWeek1stEndWeekDate))
        self.assertEqual(2, self.engageComputer.courseWeekNumber(courseStartDate, courseWeek2ndWeekDate))
        
        courseStartDate = datetime.datetime(2014,1,6)
        dateInFirstWeek = datetime.datetime(2014,1,7)
        self.assertEqual(1, self.engageComputer.courseWeekNumber(courseStartDate, dateInFirstWeek)) 

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.test']
    unittest.main()