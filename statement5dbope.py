from pymongo import MongoClient
from pprint import pprint
import re
import bson

db = MongoClient()
mydb = db.dhi_analytics
dhi_internal = mydb['dhi_internal']
dhi_term_details = mydb['dhi_term_detail']
dhi_student_attendance = mydb['dhi_student_attendance']


def getacademicYear():
    academicYear = dhi_internal.aggregate([{"$group":{"_id":"null",
    "academicYear":{"$addToSet":"$academicYear"}}},{"$project":{"academicYear":"$academicYear","_id":0}}])
    for year in academicYear:
        year = year['academicYear']
    return year

def get_term_numbers():
    terms_numbers = dhi_term_details.aggregate([ 
        { "$unwind":"$academicCalendar"}, 
        {"$group":{"_id":"null","termNumber":{"$addToSet":"$academicCalendar.termNumber"}}},
        {"$project":{"_id":0}}
    ])
    for term in terms_numbers:
        terms = term['termNumber']
    terms.sort()
    return terms

def get_attendence(year,usn,sem,subject):
    collection = mydb['dhi_student_attendance']
    attendence = collection.aggregate([
            {"$match":{"students.usn":usn,'courseName':subject}},
            {"$unwind":"$departments"},
            {"$unwind":"$students"},
            {"$match":{"students.usn":usn,"departments.termNumber":sem,"academicYear":year,'courseName':subject}},
            {"$project":{"total_classes":"$students.totalNumberOfClasses","present":"$students.presentCount",
            "absent":"$students.absentCount",
            "percentage":"$students.percentage","_id":0,"courseCode":1,"courseName":1}}
        ])
    res = []
    for x in attendence:
        if x not in res:
            res.append(x)
    #pp.pprint(res)
    return res
#returns the usn of the requested email if present
def get_student_usn(email):
    collection = mydb['dhi_user']
    usn = collection.aggregate([
        {"$match":{"email":email}},
        {"$project":{"_id":0,"usn":1}}
    ])
    res = []
    for x in usn:
        if x["usn"]:
            res = x["usn"]
    #print(res)
    return res
#emp email
def get_emp_id(email):
    collection = db.dhi_user
    usn = collection.aggregate([
    {"$match":{"email":email}},
    {"$project":{"_id":0,"employeeGivenId":1}}
    ])
    res = []
    for x in usn:
        res = x["employeeGivenId"]
    #print(res)
    return res

def get_emp_sub_placement(empID,sub,sem):
    collection =  mydb['dhi_student_attendance']
    students = collection.aggregate([
        {"$match":{"faculties.employeeGivenId" : empID,"departments.termName":sem,"courseName":sub}},
        {"$unwind":"$students"},
        {"$group":{"_id":"$courseName","studentUSNs":{"$addToSet":"$students.usn"}}},
    ])
    res = []
    for x in students:
        res.append(x)
    totalStudents = 0
    filtered = []
    for x in res:
        for usn in x["studentUSNs"]:
            status = get_placed_details(usn)
            if status!=0:
                filtered.append(status)
            totalStudents = len(x["studentUSNs"])
    # print("filtered",filtered)
    # print(f"Placed Students :{len(filtered)},No.of Offers : {sum(filtered)}")
    return (totalStudents,len(filtered),sum(filtered))

def get_placed_details(usn):
    collection = mydb['pms_placement_student_details']
    people = collection.aggregate([
    {"$match":{"studentList.regNo":usn}},
    {"$unwind":"$studentList"},
    {"$match":{"studentList.regNo":usn}},
    ])
    res = []
    for x in people:
        res.append(x)
    return len(res)

#returns the list of all department
def get_all_depts():
    collection = mydb['dhi_user']
    depts = collection.aggregate([
        {"$match":{"roles.roleName":"FACULTY"}},
        {"$project":{"_id":0,"employeeGivenId":1}}
    ])
    res = []
    for d in depts:
        if "employeeGivenId" in d:
            res.append(d["employeeGivenId"])
    #print(len(res))
    dept = []
    for d in res:
        name = re.findall('([a-zA-Z]*).*',d)
        if name[0].upper() not in dept:
            dept.append(name[0].upper())
    dept.remove('ADM')
    dept.remove('EC')
    return dept

def get_faculties_by_dept(dept):
    collection = mydb['dhi_user']
    pattern = re.compile(f'^{dept}')
    regex = bson.regex.Regex.from_native(pattern)
    regex.flags ^= re.UNICODE 
    faculties = collection.aggregate([
        {"$match":{"roles.roleName":"FACULTY","employeeGivenId":{"$regex":regex}}},
        {"$project":{"employeeGivenId":1,"name":1,"_id":0}}
    ])
    res = [f for f in faculties]
    return res
#get_faculties_by_dept("CSE")

def getAttendanceDetails_bySubject_Faculty(empID,sem,courseCode):
    collection=mydb['dhi_student_attendance']
    attendance_by_fac_sub = collection.aggregate([
        {"$match":{"faculties.employeeGivenId":empID,"departments.termName":sem,"courseCode":courseCode}},
        {"$unwind":"$students"},
        {"$group":{"_id":"courseCode","totalPercentage":{"$sum":"$students.percentage"},"peopleCount":{"$sum":1}}}
        ])
    res=[]
    for x in attendance_by_fac_sub:
        if x not in res:
            res.append(x)
    return res
    

def get_ia_details(usn,courseCode,section,termNumber,deptId,year):
    ia_percent = 0
    avg_ia_score = 0
    ia_details =[x for x in dhi_internal.aggregate([
        {
        '$unwind': '$studentScores'
        },
        {'$unwind': '$departments'},
        {'$unwind':'$studentScores.evaluationParameterScore'},
        {
            '$match':
            {
                'studentScores.usn':usn,
                'academicYear':year,
                'courseCode':courseCode ,
                'studentScores.section': section,
                'departments.deptId': deptId,
                'studentScores.termNumber': termNumber
            }
        
        },

        {
            '$group':
            {
                '_id':'$iaNumber',
                "maxMarks":{"$addToSet":"$studentScores.evaluationParameterScore.maxMarks"},
                "iaNumber":{"$addToSet":"$iaNumber"},
                "obtainedMarks":{"$addToSet":"$studentScores.totalScore"},
                "startTime":{"$addToSet":"$startTime"}
            }
        },
        {'$unwind':'$maxMarks'},
        {'$unwind':'$iaNumber'},
        {'$unwind':'$startTime'},
        {'$unwind':'$obtainedMarks'},
        {
            "$project":
                {
                    "_id":0,
                    "maxMarks":"$maxMarks",
                    "obtainedMarks":"$obtainedMarks",
                    "startTime":"$startTime",
                    "iaNumber":"$iaNumber"
                }
        }

    ])]
    for x in ia_details:
        try:
            ia_percent = (x['obtainedMarks']/x['maxMarks'])*100
            ia_percent =  round(ia_percent,2)
            x['ia_percent'] = ia_percent
            avg_ia_score = avg_ia_score + ia_percent
        except ZeroDivisionError:
            avg_ia_score = 0
    
    try:
        avg_ia_score = avg_ia_score/len(ia_details)
        avg_ia_score = round(avg_ia_score,2)
        return ia_details,avg_ia_score
    except ZeroDivisionError:
        return ia_details,0



def get_avg_attendance(usn,courseCode,section,termNumber,deptId,year):

    for attedance_details in dhi_student_attendance.aggregate([
        {'$unwind': '$departments'},
        {'$unwind':'$students'},
        
    
        {
            '$match':
                    {
                    'academicYear':year,
                    'students.usn':usn,
                    'courseCode': courseCode,
                    'students.deptId': deptId,
                    'students.section':section,
                    'students.termNumber':termNumber
                    }
        },
      
        {
            '$project':
                    {
                        '_id':0,
                        'totalNumberOfClasses':'$students.totalNumberOfClasses',
                        'totalPresent':'$students.presentCount',
                        'totalAbsent':'$students.absentCount'
                    }
        }
 
    ]):
        attendance_per = (attedance_details['totalPresent']/attedance_details['totalNumberOfClasses'])*100
        attendance_per = round(attendance_per,2)
        attendance = {"attedance_details":attedance_details,"attendance_per":attendance_per}
        return attendance



def get_iadate_wise_attendance(usn,courseCode,section,termNumber,deptId,year,iadate,iaNumber):
    present_details = []
    present = []
    absent = []
    perc_of_present = 0
    perc_of_absent = 0 
    for x in dhi_student_attendance.aggregate([
        {'$unwind': '$departments'},
        {'$unwind':'$students'},
        {
            '$match':
                    {
                    'academicYear':year,
                    'students.usn':usn,
                    'courseCode': courseCode,
                    'students.deptId': deptId,
                    'students.section':section,
                    'students.termNumber':termNumber
                    }
        },
        {'$unwind':'$students.studentAttendance'},
        { 
            '$match': 
            {
                "students.studentAttendance.date":{"$lte":iadate}
            }   
        },      
        {
            '$project':
                    {
                        "_id":0,
                        "date":"$students.studentAttendance.date",
                        "present":"$students.studentAttendance.present"
                    }
        }
 
    ]):
        present_details.append(x['present'])
        if x['present'] == True:
            present.append(x['present'])
        if x['present'] == False:
            absent.append(x['present'])
    try:
        perc_of_present = (len(present)/len(present_details))*100
        perc_of_present = round(perc_of_present,2)
        perc_of_absent = (len(absent)/len(present_details))*100
        perc_of_absent = round(perc_of_absent,2)
    except:
        perc_of_present = 0 
        perc_of_absent = 0

    return perc_of_present,perc_of_absent


def get_details(usn,year,terms):   
    final_attendance = []

    for x in dhi_internal.aggregate([
        {'$unwind':'$studentScores'},
        {'$unwind':'$departments'},
        {
        '$match':
        {
            'studentScores.usn':usn,
            'academicYear': year,
            'departments.termNumber': {'$in':terms}
        }
        },
        {
            '$group':
            {
                '_id':
                {
                    'courseCode': '$courseCode',
                    'courseName': '$courseName',
                    'section': '$studentScores.section',
                    'termNumber': '$studentScores.termNumber',
                    'deptId': '$departments.deptId'
                }   
            }
        }
    ]):
        details = {}
        ia_details,avg_ia_score = get_ia_details(usn,x['_id']['courseCode'],x["_id"]
                                ["section"],x["_id"]["termNumber"], x["_id"]["deptId"],year)
        attedance_total_avg_details = get_avg_attendance(usn,x['_id']['courseCode'],x["_id"]
                                ["section"],x["_id"]["termNumber"], x["_id"]["deptId"],year)
        for ia_detail in ia_details:
            try:
                ia_detail['perc_of_present'],ia_detail['perc_of_absent'] = get_iadate_wise_attendance(usn,x['_id']['courseCode'],x["_id"]
                                    ["section"],x["_id"]["termNumber"], x["_id"]["deptId"],year,ia_detail['startTime'],ia_detail['iaNumber'])
            except KeyError:
                ia_detail['perc_of_present'] = 0 
                ia_detail['perc_of_absent'] = 0
        details['total_avg'] = {}
        details['attendance_per'] = 0
        details['courseCode'] = x['_id']['courseCode']
        details['courseName'] = x['_id']['courseName']
        details['section'] = x['_id']['section']
        details['termNumber'] = x['_id']['termNumber']
        details['deptId'] = x['_id']['deptId']
        details['ia_attendance_%'] = ia_details
        details['avg_ia_score'] = avg_ia_score
        if attedance_total_avg_details != None:
            details['total_avg'] = attedance_total_avg_details['attedance_details']
            details['attendance_per'] = attedance_total_avg_details['attendance_per']
        final_attendance.append(details)
    return final_attendance
# get_details('4MT16CV004','2017-18',['1','2','3','4','5','6','7','8'])


def get_student_placment_offers(term, usn):
    collection=mydb.pms_placement_student_details
    offers = collection.aggregate([
        {"$unwind":"$studentList"},
        {"$match":{"studentList.regNo":usn,"academicYear":term}},
        {"$project":{"companyName":1,"salary":1,"_id":0}}
    ])
    res = []
    for x in offers:
        res.append(x)
    # print(res)
    return res