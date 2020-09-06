# NJU-<ruby>KB<rt>课表</rt></ruby>Parse

从[南京大学信息门户](https://wx.nju.edu.cn/homepage/wap/default/home)获取课表并导出为iCalendar或CSV格式，用于导入到各种日历App中。

Export your Nanjing University class schedule as `.ics` or `.csv`.

## 依赖

- requests
- [icalendar](https://pypi.org/project/icalendar/)（`pacman -Syu python-icalendar`（Arch Linux）或`pip install --user icalendar`)

## 用法

执行`./kbparse.py`并按提示操作即可。

如果不能正确识别当前学期，请尝试`./kbparse.py -t 20192`（`2019`表示年份，`1`和`2`分别表示上、下学期）。

默认输出文件名示例：`NJUClassSchedule-2020-01-18T13:24:01.652600.ics`。

2020-02-15: 如出现SSL错误，可以在清楚其含义的前提下尝试使用`--cert`选项。

详见`./kbparse.py -h`。

## TODO

- Test on Windows
- 考试时间表
- 缓存
- i18n
