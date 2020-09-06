#!/usr/bin/env python
# Copyright (C) 2020, 0xCLOVER.
# All rights reserved.

import logging
import requests
import json
import datetime as dt, calendar
import csv
import sys, io, os
import icalendar as ics
import argparse
import pytz
import re
import uuid
from typing import List, Iterable

programName = 'kbparse.py'
programVersion = '0.02'
programFullName = '{}-{}'.format(programName, programVersion)
iCalVersion = '2.0'
defaultOutputFormat = 'ics'
supportedFileFormats = ['ics', 'csv']
defaultTermLength = 20
defaultClassScheduleURI = 'https://wx.nju.edu.cn/njukb/wap/default/classes'
lessonLength = dt.timedelta(minutes=50)
lessonStartTime = list(map(lambda x: x, ['08:00','09:00','10:10','11:10','14:00','15:00','16:10','17:10','18:30', '19:30','20:40','21:30']))
#defaultFirstDay = '2020-02-17'
oneWeek = dt.timedelta(days = 7)
timeZone = pytz.timezone('Asia/Shanghai')
#timeZone = dt.timezone(dt.timedelta(hours=8))
periodTimes = dict(
    (lambda x: [(i+1, x[i]) for i in range(0, len(x))])(
        list(map(lambda x: (dt.time.fromisoformat(x).replace(tzinfo=timeZone),
                    #(dt.datetime.combine(dt.date.today(), dt.time.fromisoformat(x)) + lessonLength).time()),
                    (dt.datetime.combine(dt.date.today(), dt.time.fromisoformat(x)) + lessonLength).time().replace(tzinfo=timeZone)),
                lessonStartTime
            )
        )
    )
)

def generateLessonInfo(**info):
    for s in ['count', 'courseID', 'week']:
        assert s in info
    if 'teachers' in info:
        info['teachers'] = '、'.join(info['teachers'])
    if info['count'] > 1:
        assert 'interval' in info
        if info['interval'] == 1:
            infoStr = '第{week}周开始，每周，共{count}次\n课程编号：{courseID}\n教师：{teachers}'
        elif info['interval'] == 2:
            if info['week'] % 2:
                infoStr = '第{week}周开始，单周，共{count}次\n课程编号：{courseID}\n教师：{teachers}'
            else:
                infoStr = '第{week}周开始，双周，共{count}次\n课程编号：{courseID}\n教师：{teachers}'
        else:
            infoStr = '第{week}周开始，每{interval}周，共{count}次\n课程编号：{courseID}\n教师：{teachers}'
    else:
        infoStr = '第{week}周\n课程编号：{courseID}\n教师：{teachers}'
    return infoStr.format(**info)

class UCourseTime:
    def __init__(self, periods: List[int], name:str, dayOfWeek: int, weeks: List[int], location = '', classroom = '', teachers = [], courseID: str = '', **extraInfo):
        assert len(periods) >= 1
        # check if periods is consecutive
        prev = periods[0]
        for x in periods[1:]:
            if x - prev != 1:
                raise Exception('Periods: {} is not consecutive. Please split it!'.format(periods))
            prev = x
        self.periods = list(periods)
        self.location = location
        self.teachers = teachers
        self.extraInfo = extraInfo
        self.weeks = sorted(set(weeks))
        self.dayOfWeek = dayOfWeek
        self.classroom = classroom
        self.name = name
        self.courseID = courseID
        self.__grouped = False

    def startTime(self):
        return periodTimes[self.periods[0]][0]

    def endTime(self):
        return periodTimes[self.periods[-1]][1]

    def extend(self, weekNumber: int):
        if weekNumber not in self.weeks:
            self.weeks.append(weekNumber)
            self.weeks.sort()
            self.__grouped = False

    def length(self):
        return len(self.weeks)

    def startDateTime(self, firstDayOfTerm: dt.date, recurrenceNumber: int = 1) -> dt.datetime:
        return dt.datetime.combine(self.getDate(firstDayOfTerm=firstDayOfTerm, recurrenceNumber=recurrenceNumber), self.startTime())

    def endDateTime(self, firstDayOfTerm: dt.date, recurrenceNumber: int = 1) -> dt.datetime:
        return dt.datetime.combine(self.getDate(firstDayOfTerm=firstDayOfTerm, recurrenceNumber=recurrenceNumber), self.endTime())

    def getDate(self, firstDayOfTerm: dt.date, recurrenceNumber: int = 1) -> dt.date:
        return firstDayOfTerm + dt.timedelta(days = 7 * (self.weeks[recurrenceNumber-1] - 1) + self.dayOfWeek - 1)

    def toICalEvents(self, firstDay: dt.date, useLocation: bool = False, group: bool = True, groupmin: int = 3) -> Iterable[ics.Event]:
        assert group, 'not implemented'
        location = self.location if useLocation else self.classroom
        def newE():
            e = ics.Event()
            e.add('summary', self.name)
            e.add('location', location)
            e.add('dtstamp', dt.datetime.today())
            e.add('uid', uuid.uuid4())
            return e

        i = 0
        high = len(self.weeks) - 1
        if group:
            while high - i >= groupmin - 1:
                first = self.weeks[i]
                prev  = self.weeks[i+1]
                intv  = prev - first
                count = 2
                j = i + 2
                while j <= high and self.weeks[j] - prev == intv:
                    count += 1
                    prev = self.weeks[j]
                    j += 1

                startDT = self.startDateTime(firstDayOfTerm=firstDay, recurrenceNumber=i+1)
                endDT = self.endDateTime(firstDayOfTerm=firstDay, recurrenceNumber=i+1)
                e = newE()
                e.add('dtstart', startDT)
                e.add('dtend', endDT)
                e.add('description', generateLessonInfo(week=first, interval=intv, count=count, teachers=self.teachers, courseID=self.courseID))
                if count >= groupmin:
                    e.add('rrule', {'freq': 'weekly', 'interval': intv, 'count': count})
                    i = j
                else:
                    i += 1
                yield e

        while i <= high:
            e = newE()
            e.add('description', generateLessonInfo(week=self.weeks[i], count=1, teachers=self.teachers, location=self.location, classroom=self.classroom, courseID=self.courseID))
            e.add('dtstart', self.startDateTime(firstDayOfTerm=firstDay, recurrenceNumber=i+1))
            e.add('dtend', self.endDateTime(firstDayOfTerm=firstDay, recurrenceNumber=i+1))
            yield e
            i += 1

class UCourse:
    def __init__(self, courseID: str, name:str, time: List[UCourseTime], teachers = [], **extraInfo):
        self.courseID = courseID
        self.name = name
        self.time = list(time)
        self.teachers = teachers
        self.extraInfo = extraInfo

    def extend(self, time: UCourseTime):
        if time.courseID != self.courseID:
            raise Exception('Different course ID: {} and {}'.format(self.courseID, time.courseID))
        # TODO: Is this the reasonable behavior?
        for teacher in time.teachers:
            if teacher not in self.teachers:
                self.teachers.append(teacher)
        for t in [t for t in self.time if t.dayOfWeek == time.dayOfWeek and t.periods == time.periods]:
            # TODO: check other properties
            for weekNumber in time.weeks:
                t.extend(weekNumber)
            repeated = True
            break
        else:
            self.time.append(time)

    def toICalEvents(self, firstDay: dt.date, useLocation: bool, group: bool = True) -> Iterable[ics.Event]:
        for t in self.time:
            yield from t.toICalEvents(firstDay, useLocation, group)

class UWeek:
    def __init__(self, weekNumber: int, firstDay: dt.date, lastDay: dt.date, weekName:str, termName: str, coursePeriods):
        if (lastDay - firstDay).days != 6:
            raise Exception('The last and first date of week {}: {}, do not differ by 6 days?!'.format(weekNumber, (firstDay, lastDay)))
        self.firstDay = firstDay
        self.lastDay = lastDay
        self.weekNumber = weekNumber
        self.weekName = weekName
        self.termName = termName
        self.coursePeriods = coursePeriods

class USchedule:
    def __init__(self, termName: str, firstDay: dt.date, courses: List[UCourse] = []):
        self.termName = termName
        self.firstDay = firstDay
        self.courses = courses
        self.weeks = []

    def getCourseByID(self, courseID: str) -> UCourse:
        for x in self.courses:
            if x.courseID == courseID:
                return x

    def hasWeek(self, weekNumber: int):
        return any(map(lambda x: x.weekNumber == weekNumber, self.weeks))

    def addWeek(self, week: UWeek):
        for w in self.weeks:
            if week.weekNumber == w.weekNumber:
                raise Exception('Week {} already exists'.format(week.weekNumber))
        if self.termName != week.termName:
            logging.warning('Different termName: {} (schedule), {} (week)'.format(self.termName, week.termName))
        self.weeks.append(week)
        self.weeks.sort(key=lambda x: x.weekNumber)
        for c in week.coursePeriods:
            master = self.getCourseByID(c.courseID)
            if master:
                master.extend(c)
            else:
                logging.warning('发现课程：{}，课程ID：{}'.format(c.name, c.courseID))
                self.courses.append(UCourse(courseID=c.courseID, name=c.name, time=[c], teachers=c.teachers))

    def toCSV(self, useLocation: bool, regEx = []) -> str:
        csvf = io.StringIO()
        fieldnames = ['Subject', 'Start Date', 'Start Time', 'End Date', 'End Time', 'All Day Event', 'Description', 'Location', 'Private']
        writer = csv.DictWriter(csvf, fieldnames)
        for c in self.courses:
            # regex check
            skip = False
            for exp in regEx:
                if exp[1] == None:
                    continue
                assert exp[0]  in ['courseID', 'name']
                assert exp[-1] in ['fullmatch', 'match', 'search'], 'Unknown method of matching: {}'.format(exp[-1])
                if getattr(re.compile(exp[1]), exp[-1])(getattr(c, exp[0])) == None:
                    skip = True
                    break
            if skip:
                continue
            # work
            for t in c.time:
                for i in range(0, len(t.weeks)):
                    writer.writerow({'Subject': c.name, 'Start Date': t.getDate(self.firstDay, i), 'Start Time': t.startTime(), 'End Time': t.endTime(), 'Location': t.location if useLocation else t.classroom, 'Description': '{}'.format('、'.join(t.teachers))})
        return csvf.getvalue()

    def toICal(self, useLocation: bool, group: bool = True, regEx = []) -> str:
        cal = ics.Calendar()
        cal.add('summary', '{}'.format(self.termName))
        cal.add('prodid', programFullName)
        cal.add('version', iCalVersion)
        for c in self.courses:
            # regex check
            skip = False
            for exp in regEx:
                if exp[1] == None:
                    continue
                assert exp[0]  in ['courseID', 'name']
                assert exp[-1] in ['fullmatch', 'match', 'search'], 'Unknown method of matching: {}'.format(exp[-1])
                if getattr(re.compile(exp[1]), exp[-1])(getattr(c, exp[0])) == None:
                    skip = True
                    break
            if skip:
                continue
            logging.warning('导出课程“{}”，课程ID：{}'.format(c.name, c.courseID))
            for e in c.toICalEvents(firstDay=self.firstDay, useLocation=useLocation, group=group):
                cal.add_component(e)
        return cal.to_ical().decode()

def argDate(d: str) -> dt.date:
    try:
        return dt.date.fromisoformat(d)
    except ValueError as e:
        raise argparse.ArgumentTypeError(''.join(e.args))

def argWeekList(x: str) -> list:
    lst = []
    for s in x.split(','):
        msg = 'Invalid range: {}'
        if s == '':
            raise argparse.ArgumentTypeError(msg.format(x))
        ss = s.split('-')
        if len(ss) not in [1, 2]:
            raise argparse.ArgumentTypeError(msg.format(x))
        try:
            if s[-1] == '-':
                lst.append([int(ss[0]), float('inf')])
            else:
                lst.append([int(ss[0]), int(ss[-1])])
        except ValueError:
            raise argparse.ArgumentTypeError(msg.format(x))
    #return sorted(lst, key=lambda x: x[0])
    return lst

def argTermName(t: str) -> tuple:
    # 20192 -> (2019, 2)
    msg = 'Invalid term: {}'.format(t)
    year = t[:-1]
    term = t[-1]
    if term not in ['1', '2']:
        raise argparse.ArgumentTypeError(msg)
    try:
        return (int(year), int(term))
    except ValueError:
        raise argparse.ArgumentTypeError(msg)

def fetchClassData(date, eaiSess, uri = defaultClassScheduleURI, cert = None):
    verify = cert or True
    response = requests.post(uri, headers={'Cookie': 'eai-sess={}'.format(eaiSess)}, data={'date': date}, verify=verify)
    response = response.content.decode()
    try:
        response = dict(json.loads(response)) # Hint for pylint
    except json.decoder.JSONDecodeError:
        logging.debug(response)
        raise Exception('Response as JSON is illegal')
    logging.debug('Got response JSON:')
    logging.debug(response)
    if any([x not in response for x in ('e', 'm', 'd')]):
        raise Exception('Response JSON appears corrupted')
    if response['e'] != 0:
        logging.error("e != 0 in response JSON. What happened?")
        logging.error("The message reads '{}'".format(response['m']))
        raise Exception('Response JSON appears corrupted')
    courseData = response['d']
    return courseData

def getFirstDay(eaiSess, term: tuple, uri = defaultClassScheduleURI, cert = None) -> dt.date:
    assert term[1] in [1, 2]
    if term[1] == 1:
        date = dt.date(year = term[0], month = 10, day = 1)
    else:
        date = dt.date(year = term[0] + 1, month = 3, day = 1)
    courseData = fetchClassData(date, eaiSess, uri, cert)
    weekNumber = 0
    for w in courseData['dateInfo']['name'].strip().split(' '):
        if (w[0], w[-1]) == ('第', '周'):
            try:
                weekNumber = int(w[1:-1])
                break
            except ValueError:
                logging.error('Don\'t know how to interpret week number {}!'.format(w))
                raise
    if weekNumber == 0:
        logging.error('猜测学期首日失败，请使用-d手动指定')
        logging.debug('Week name returned by server: {}'.format(courseData['dateInfo']['name']))
        return 'error'
    firstDay = dt.date.fromisoformat(sorted(courseData['weekdays'])[0]) - oneWeek * (weekNumber - 1)
    return firstDay

def fetchAndParseClassData(date, eaiSess, uri = defaultClassScheduleURI, weekNumber = float('inf'), cert = None) -> UWeek:
    """
    Leave weekNumber empty to use server provided weekName.
    """
    courseData = fetchClassData(date, eaiSess, uri, cert=cert)

    # parsing
    weekName = courseData['dateInfo']['name'].strip()
    termName = ''
    firstDay, lastDay = dt.date.fromisoformat(courseData['weekdays'][0]), dt.date.fromisoformat(courseData['weekdays'][-1])
    # Parsing week and term name. Example: '2019-2020学年下学期 第2周'
    for w in weekName.split(' '):
        if w[-2:] == '学期':
            termName = w
        elif (w[0], w[-1]) == ('第', '周'):
            try:
                newWeekNumber = int(w[1:-1])
            except ValueError:
                logging.error('Don\'t know how to interpret week number {}!'.format(w))
            if weekNumber != float('inf') and newWeekNumber != weekNumber:
                logging.warning('本周应为第{}周，但服务器返回了第{}周的数据'.format(weekNumber, newWeekNumber))
            weekNumber = newWeekNumber
        else:
            logging.debug('Warning: unknown phrase {} in weekName'.format(w))

    # Parsing courses
    courses = []
    for day in courseData['kclist'].values():
        for cc in day.values():
            for c in cc:
                courses.append(UCourseTime(periods=c['lessArr'], name=c['course_name'], weeks=[weekNumber], dayOfWeek=c['weekday'], teachers=c['teacher'].replace('，', ' ').replace(',', ' ').strip().split(' '), courseID=c['course_id'], location=c['location'], classroom=c['classroom']))

    return UWeek(weekNumber=weekNumber, firstDay=firstDay, lastDay=lastDay, weekName=weekName, termName=termName, coursePeriods=courses)

def readOptions():
    parser = argparse.ArgumentParser(description='生成一份本学期的日程表。', prog=programName)

    # command-line arguments
    parser.add_argument('-k', '--eai-sess', dest='eaiSess', help='Cookie中eai-sess的值，用于认证')
    # specify at most one of firstDay and termNumber
    gTerm = parser.add_mutually_exclusive_group()
    gTerm.add_argument('-d', '--first-day', dest='firstDay', help='学期的第一天', type=argDate)
    gTerm.add_argument('-t', '--term', dest='termName', help='学期，如20192表示2019-2020学年下学期', type=argTermName)
    parser.add_argument('-L', '--use-location', dest='useLocation', action='store_true', help='输出“地点”（可能含校区）而非“教室”')
    parser.add_argument('-o', dest='outputFile', help='输出文件名，-代表标准输出')
    parser.add_argument('-f', '--format', dest='outputFormat', choices = ['ics', 'csv'], default='', help='输出格式（默认值：参数中指定的文件后缀>{}）'.format(defaultOutputFormat))
    parser.add_argument('--debug', dest='logLevel', action='store_const', const='DEBUG', default='WARNING')
    parser.add_argument('-p', '--dry-run', action='store_true', dest='actDryRun', help='只处理不输出')
    parser.add_argument('-c', '--course-id', dest='courseIDRegEx', help='课程编号（正则，前缀）', type=re.compile)
    parser.add_argument('-n', '--course-name', dest='courseNameRegEx', help='课程名（正则，部分）', type=re.compile)
    parser.add_argument('-w', '--weeks', dest='weeks', type=argWeekList, help='要生成日程表的周数，例如“2”, “1-”, “1,2-5,3”', default=argWeekList('1-'))
    parser.add_argument('--cert', help='连接服务器时使用的证书')

    options = vars(parser.parse_args())
    return options

def main():
    options = readOptions()
    eaiSess    = options['eaiSess']
    #termLength = options['termLength']
    outputFormat = options['outputFormat'].lower()
    useLocation = options['useLocation']
    actDryRun   = options['actDryRun']
    logging.getLogger().setLevel(options['logLevel'].upper())
    weeks = options['weeks']
    courseIDRegEx = options['courseIDRegEx']
    courseNameRegEx = options['courseNameRegEx']
    cert = options['cert']

    if not eaiSess:
        logging.warning('在下面输入eai-sess的值。')
        logging.warning('这个值可以在登录“南京大学信息门户”（https://wx.nju.edu.cn/homepage/wap/default/home）后在cookies中找到。')
        eaiSess = input()

    # store first day of term in firstDay
    if options['firstDay']:
        firstDay = options['firstDay']
        logging.warning('已指定学期首日：{}'.format(firstDay))
    else:
        if not options['termName']:
            optToday = dt.date.today()
            if optToday.month in [1, 2, 3, 4, 5, 6]:
                # Spring
                optTerm = (optToday.year - 1, 2)
            elif optToday.month in [7, 8, 9, 10, 11, 12]:
                # Fall
                optTerm = (optToday.year, 1)
            logging.warning('未指定学期，使用{}'.format(''.join(map(str, optTerm))))
        else:
            optTerm = options['termName']
        firstDay = getFirstDay(eaiSess, optTerm, cert=cert)
        if firstDay == 'error':
            return 1
        logging.warning('未指定学期首日，猜测为{}'.format(firstDay))

    # determine output file name and format (and suffix)
    if options['outputFile'] not in [None, '-']:
        outputFileName = options['outputFile']
        outputFileSuffix = '' if outputFileName.endswith('.') or '.' not in outputFileName else outputFileName.split('.')[-1]
        if not outputFormat:
            if outputFileSuffix in ['csv', 'ics']:
                outputFormat = outputFileSuffix
                logging.warning('根据文件后缀选择输出格式{}'.format(outputFormat))
            else:
                logging.warning('使用默认输出格式{}'.format(defaultOutputFormat))
                outputFormat = defaultOutputFormat
    else:
        if options['outputFile'] == '-':
            outputFileName = '-'
            outputFileSuffix = ''
            if not outputFormat:
                outputFormat = defaultOutputFormat
        elif options['outputFile'] == None:
            if not outputFormat:
                logging.warning('未指定输出格式，使用默认格式{}'.format(defaultOutputFormat))
                outputFormat = defaultOutputFormat
            outputFileSuffix = outputFormat
            outputFileName = 'NJUClassSchedule-{}.{}'.format(dt.datetime.today().isoformat(), outputFormat)

    logging.warning('正在生成这些周的日程表：{}'.format(weeks))

    termName = ''
    termFirstDay = firstDay
    schedule = USchedule(termName, termFirstDay)

    processed = {}
    for ww in weeks:
        # if ww[1] is infinity continue processing until it's likely that the current term has ended
        weekNumber = ww[0]-1

        while weekNumber < ww[1]:
            weekNumber += 1
            if weekNumber in processed:
                logging.warning('已经处理过，跳过第{}周'.format(weekNumber))
                continue
            else:
                logging.warning('正在获取第{}周的信息'.format(weekNumber))
            firstDay = termFirstDay + oneWeek * (weekNumber - 1)
            logging.debug('Fetching courses for week {}'.format(weekNumber))
            weekData = fetchAndParseClassData(date=firstDay.isoformat(), eaiSess=eaiSess, weekNumber=weekNumber, cert=cert)

            if not termName:
                schedule.termName = termName = weekData.termName
                logging.warning('本学期是{}'.format(termName))
            elif weekData.weekNumber == 0 or weekData.termName != termName:
                logging.debug('Reached week {}, probably the next term.'.format(weekData.weekName))
                if ww[1] == float('inf'):
                    logging.warning('本学期共有{}周'.format(weekNumber - 1))
                    break
                else:
                    logging.warning('第{week}周时本学期已经结束'.format(week=weekNumber))
            logging.debug('It is {} (from {} to {}) now'.format(weekData.weekName, weekData.firstDay, weekData.lastDay))
            if not weekData.coursePeriods:
                logging.warning('本周没有课程，可以休息 :-)')

            schedule.addWeek(weekData)


    # warn if file format and suffix do not match
    if outputFormat != outputFileSuffix and outputFileSuffix in supportedFileFormats:
        logging.warning('导出为{}格式，但输出文件名后缀为{}'.format(outputFormat, outputFileSuffix))

    regEx = [('courseID', courseIDRegEx, 'match'), ('name', courseNameRegEx, 'search')]
    if outputFormat == 'csv':
        logging.warning('生成CSV……')
        outputData = schedule.toCSV(useLocation=useLocation, regEx = regEx)
    elif outputFormat == 'ics':
        logging.warning('生成iCalendar……')
        outputData = schedule.toICal(useLocation=useLocation, regEx = regEx)
    if not actDryRun:
        if outputFileName == '-':
            print(outputData, end='')
        else:
            outputFile = open(outputFileName, 'w')
            outputFile.write(outputData)
            outputFile.close()
            logging.warning('已保存到{}。'.format(outputFileName))
    else:
        logging.warning('没有输出。')

    return 0

if __name__ == '__main__':
    exit(main())
