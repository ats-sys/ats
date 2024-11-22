@echo off
setlocal enabledelayedexpansion

:: Check if conda is installed
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo "conda is not installed. Please install Anaconda or Miniconda first."
    exit /b 1
)

:: Check if main.py exists in current directory
if not exist "ats/main.py" (
    echo "ats/main.py not found in current directory."
    exit /b 1
)

:: set environment name
set env_name="ats"

:: Check if environment exists
conda env list | findstr /C:"!env_name! " >nul 2>&1
if %errorlevel% neq 0 (
    echo "Environment '!env_name!' does not exist."
    exit /b 1
)

:: Activate conda environment
echo "Activating conda environment '!env_name!'..."
call conda activate !env_name!

echo "Successfully activated environment '!env_name!'"

:: Run main.py
echo "Starting the Program..."

call python -m ats.main

if %errorlevel% equ 0 (
    echo "Program executed successfully!"
) else (
    echo "Error occurred while running main.py"
    call conda deactivate
    exit /b 1
)

:: Deactivate environment
call conda deactivate
exit /b 0
