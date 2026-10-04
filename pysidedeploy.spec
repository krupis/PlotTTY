[app]
title = PlotTTY
project_dir = .
input_file = mainwindow.py
exec_directory = dist
project_file = pyproject.toml
icon = icons/Plottty.ico

[python]
python_path = C:\Users\petri\Desktop\WORK\Coding\QT\Plottty\.venv\Scripts\python.exe
packages = Nuitka==4.1.3

[qt]
qml_files = 
excluded_qml_plugins = 
modules = Core,Gui,SerialPort,Widgets
plugins = platforms,styles,imageformats,iconengines

[nuitka]
mode = standalone
macos.permissions = 
extra_args = --include-qt-plugins=platforms,styles,imageformats,iconengines --include-package=pylink --msvc=latest --assume-yes-for-downloads --output-folder-name=mainwindow --output-filename=PlotTTY.exe --windows-console-mode=disable --force-stderr-spec={PROGRAM_BASE}.err.txt --noinclude-qt-translations --noinclude-dlls=**/qpdf.dll --include-data-files=styles/application.qss=styles/application.qss --include-data-files=LICENSE=LICENSE --report=dist/build-report.xml

