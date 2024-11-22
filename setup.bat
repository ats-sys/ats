@echo off
setlocal enabledelayedexpansion

:: Call main script
call :main %1

:: Script to create a conda environment from a YAML file
:: Usage: setup.bat [path_to_yml_file]
:: Default yml file is environment.yml if not specified

:: Function to check if conda is installed
:check_conda
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo conda is not installed or not in PATH
    echo Please install conda first: https://docs.conda.io/projects/conda/en/latest/user-guide/install/
    exit /b 1
)
exit /b 0

:: Function to validate YAML file
:validate_yaml
if not exist "%~1" (
    echo Environment file '%~1' not found
    exit /b 1
)

findstr /C:"name:" "%~1" >nul
if errorlevel 1 (
    echo YAML file must specify an environment name
    exit /b 1
)
exit /b 0

:: Function to extract environment name
:extract_env_name
for /f "tokens=2 delims=:" %%a in ('findstr /C:"name:" "%~1"') do set "env_name=%%a"
set "env_name=%env_name: =%"
exit /b 0

:: Function to create the conda environment
:create_environment
call :extract_env_name "%~1"

echo Creating conda environment '!env_name!' from %~1...

call conda env list | findstr /C:"!env_name! " >nul
if %errorlevel% equ 0 (
    set /p update_confirm="Environment '!env_name!' already exists. Update? (y/n): "
    if /i "!update_confirm!"=="y" (
        echo Updating existing environment...
        call conda env update -f "%~1" --prune
    ) else (
        echo Operation cancelled
        exit /b 0
    )
) else (
    call conda env create -f "%~1"
)
exit /b 0

:: Function to install PyTorch
:install_pytorch
call :extract_env_name "%~1"

echo Activating conda environment '!env_name!'...
call conda activate !env_name!
if %errorlevel% neq 0 (
    echo Failed to activate environment '!env_name!'
    exit /b 1
)

echo Successfully activated environment '!env_name!'

set /p pytorch_consent="Would you like to install PyTorch in this environment? (y/n): "
if /i "!pytorch_consent!"=="y" (
    echo Installing PyTorch...

    :: Check for CUDA
    call nvidia-smi >nul 2>&1
    if %errorlevel% equ 0 (
        echo CUDA detected. Installing PyTorch with CUDA support...
        conda install pytorch torchvision torchaudio pytorch-cuda -c pytorch -c nvidia -y
    ) else (
        echo CUDA not detected. Installing CPU-only version of PyTorch...
        conda install pytorch torchvision torchaudio cpuonly -c pytorch -y
    )

    if %errorlevel% equ 0 (
        echo PyTorch successfully installed!
        python -c "import torch; print('PyTorch version:', torch.__version__)" >nul 2>&1
        if %errorlevel% equ 0 (
            echo PyTorch verification successful!
        ) else (
            echo PyTorch verification failed
        )
    ) else (
        echo Failed to install PyTorch
    )
) else (
    echo PyTorch installation skipped.
)

call conda deactivate
exit /b 0

:: Function to display activation instructions
:show_instructions
call :extract_env_name "%~1"
echo Environment setup completed!
echo To activate the environment, run:
echo     conda activate !env_name!
echo To deactivate the environment, run:
echo     conda deactivate
exit /b 0

:: Main script execution
:main
set "yml_file=%~1"
if "%yml_file%"=="" set "yml_file=environment.yml"

call :check_conda
if errorlevel 1 exit /b 1

call :validate_yaml "!yml_file!"
if errorlevel 1 exit /b 1

call :create_environment "!yml_file!"
if errorlevel 1 exit /b 1

call :install_pytorch "!yml_file!"
if errorlevel 1 exit /b 1

call :show_instructions "!yml_file!"
exit /b 0
