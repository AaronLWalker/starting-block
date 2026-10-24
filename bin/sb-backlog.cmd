@echo off
rem Run scripts\backlog.py with the Windows py launcher, or python if there is no launcher.
setlocal
set "SCRIPT=%~dp0..\scripts\backlog.py"
where py >nul 2>&1 && goto :launcher
where python >nul 2>&1 || goto :missing
python "%SCRIPT%" %*
exit /b
:launcher
py -3 "%SCRIPT%" %*
exit /b
:missing
echo starting-block: needs Python 3.9 or later (install it from python.org, which adds the py launcher) 1>&2
exit /b 9009
