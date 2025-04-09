from idex import login
from requests import Session
from util import css_find, css_find1


def get_enrolled_courses(sess, sesskey):
    url = ("https://campus.exactas.uba.ar/lib/ajax/service.php?sesskey="
           + sesskey
           + "&info=core_course_get_enrolled_courses_by_timeline_classification")

    json_request = [{"index":0,"methodname":"core_course_get_enrolled_courses_by_timeline_classification","args":{"offset":0,"limit":0,"classification":"all","sort":"fullname","customfieldname":"","customfieldvalue":""}}]
    res = sess.post(url, json=json_request)
    return res.json()

if __name__ == "__main__":
    sess = Session()
    login(sess)
    res = sess.get("https://campus.exactas.uba.ar/my/courses.php")
    logout_a = css_find(res, ".logininfo a")[1]
    sesskey = logout_a.attrs['href'].split('sesskey=')[1]

    courses = get_enrolled_courses(sess, sesskey)
    for course in courses[0]['data']['courses']:
        print(course['fullname'])

