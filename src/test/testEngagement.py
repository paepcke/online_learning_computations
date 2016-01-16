# Copyright (c) 2014, Stanford University
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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