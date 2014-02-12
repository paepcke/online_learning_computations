'''
Created on Feb 12, 2014

@author: paepcke
'''

class IpCountryDict(object):
    '''
    classdocs
    '''


    def __init__(self, ipTablePath):
        '''
        Constructor
        '''
        self.ipToCountryDict = {}
        with open(ipTablePath, 'r') as fd:
            for line in fd:
                if line[0] == '#':
                    continue
                (startIPStr,endIPStr,auth,assigned,twoLetterCountry,threeLetterCountry,country) = line.split(',')
                # Use first four digits of start ip as hash key:
                self.ipToCountryDict[int(startIPStr.strip('"')[0:4])] = (int(startIPStr.strip('"')), 
                                                                         int(endIPStr.strip('"')), 
                                                                         twoLetterCountry.strip('"'), 
                                                                         threeLetterCountry.strip('"'), 
                                                                         country)
            
    def ipStrToIntStr(self, ipStr):
        (oct0,oct1,oct2,oct3) = ipStr.split('.')
        ipNum = int(oct3) + (int(oct2) * 256) + (int(oct1) * 256 * 256) + (int(oct0) * 256 * 256 * 256)
        return (ipNum, int(str(ipNum)[0:4]))


if __name__ == '__main__':
    lookup = IpCountryDict('ipToCountrySoftware77DotNet.csv')
    (ip,lookupKey) = lookup.ipStrToIntStr('171.64.64.64')
    
    