NJU-<ruby>KB<rt>课表</rt></ruby>Parse
====


从[南京大学信息门户](https://wx.nju.edu.cn/homepage/wap/default/home)获取课表并导出为iCalendar或CSV格式，用于导入到各种日历App中。
Export your Nanjing University class schedule as `.ics` or `.csv`.

依赖
====
- [icalendar](https://pypi.org/project/icalendar/)（`pacman -Syu python-icalendar`（Arch Linux）或`pip install --user icalendar`)

用法
====
执行`./kbparse.py -t 20192`（`2019`表示2019-2020学年，2表示下学期）并按提示操作即可。默认保存为`ics`格式。

详见`./kbparse.py -h`。

TODO
====
- Test on Windows
- 考试时间表
- 缓存