@echo off
setlocal

python -m pip show nbstripout >nul 2>&1
if errorlevel 1 goto :INSTALL

goto :MAIN

:INSTALL
echo nbstripout is not installed. Installing...
python -m pip install nbstripout
if errorlevel 1 goto :FAIL_INSTALL
goto :MAIN

:FAIL_INSTALL
echo Failed to install nbstripout.
exit /b 1

:MAIN
for /r %%F in (*.ipynb) do call :HANDLE "%%F"
echo Done.
exit /b 0

:HANDLE
REM Skip anything under .ipynb_checkpoints
echo %~1 | findstr /i "\.ipynb_checkpoints\\" >nul
if not errorlevel 1 goto :SKIP_CHECKPOINT

REM Skip anything under .git
echo %~1 | findstr /i "\.git\\" >nul
if not errorlevel 1 goto :SKIP_GIT

echo Stripping: %~1
python -m nbstripout "%~1"
if errorlevel 1 goto :FAIL_FILE
goto :EOF

:SKIP_CHECKPOINT
echo Skipping (checkpoint): %~1
goto :EOF

:SKIP_GIT
echo Skipping (git): %~1
goto :EOF

:FAIL_FILE
echo Failed on: %~1
exit /b 1
