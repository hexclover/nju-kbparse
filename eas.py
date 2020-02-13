#!/usr/bin/python
# Copyright (C) 2020, 0xCLOVER.
# All rights reserved.
# Library for working with elite.nju.edu.cn/jiaowu.

import requests
import tkinter as tk
import io
from PIL import Image, ImageTk
from lxml import html

EAS_URI="http://elite.nju.edu.cn/jiaowu/"
EAS_CAPTCHA_URI="http://elite.nju.edu.cn/jiaowu/ValidateCode.jsp"
EAS_LOGIN_URI="http://elite.nju.edu.cn/jiaowu/login.do"
MYCOURSE_URI="http://elite.nju.edu.cn/jiaowu/student/teachinginfo/courseList.do?method=currentTermCourse"

class EASLoginError(Exception):
    """Wrong password, etc."""
    pass

def solve_captcha(pic: bytes) -> str:
    def ask_user(pic: bytes) -> str:
        root = tk.Tk()
        # TODO: why didn't these two lines do the job?
        #img = Image.open(io.BytesIO(pic))
        #wg_img = tk.Label(root, image = ImageTk.PhotoImage(img))
        img = ImageTk.PhotoImage(Image.open(io.BytesIO(pic)))
        wg_img = tk.Label(root, image = img)
        #wg_text = tk.Text(root)
        wg_img.pack(side = "top", fill="both", expand="yes")
        #wg_text.pack(side = "bottom", fill="both", expand="no")
        s = input('Enter the characters in the picture:')
        root.quit()
        return s
    return ask_user(pic)


def login(username: str, password: str) -> requests.Session:
    s = requests.session()
    s.get(EAS_URI)
    validate_img = s.get(EAS_CAPTCHA_URI).content
    r = s.post(EAS_LOGIN_URI, data={'userName': username, 'password': password, 'ValidateCode': solve_captcha(validate_img)})
    if 'Set-Cookie' not in r.headers or username not in r.headers['Set-Cookie']:
        # TODO: is there a better way to check for login success?
        root = html.fromstring(r.text)
        errstr = [e.text for e in root.get_element_by_id('Main') if e.tag=='label'][0]
        raise EASLoginError(errstr)
    return s

username = input('Username:')
password = input('Password:')
session = login(username, password)
r = session.post(MYCOURSE_URI)
root = html.fromstring(r.text)
table = root.find_class('TABLE_BODY')[0]
trows = table.findall('tr')
headers = [th.text for th in trows[0]]
courses = []
for row in trows[1:]:
    course = {}
    for i in range(0, len(headers)):
        td = row.findall('td')[i]
        course[headers[i]] = td
    courses.append(course)

for course in courses:
    print('Course:')
    for key in course:
        text = course[key]
        while text.text == None:
            try:
                text = text[0]
            except IndexError:
                break
        text = text.text or ''
        text = text.strip()
        print('{key}: {text}'.format(key=key.__repr__(), text=text.__repr__()))
