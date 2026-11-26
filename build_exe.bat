@echo off
chcp 65001 >nul
REM ============================================================
REM  Đóng gói PeRC thành PeRC.exe (thư mục dist\PeRC) và file PeRC_v1.0.0.zip
REM  Chạy:  build_exe.bat     (đứng ở thư mục D:\RCDesign)
REM ============================================================
cd /d "%~dp0"

set PY=python
if exist ".venv\Scripts\python.exe" set PY=.venv\Scripts\python.exe

echo [1/3] Cai PyInstaller...
%PY% -m pip install --upgrade pyinstaller pyinstaller-hooks-contrib || goto :err

echo [2/3] Dong goi...
%PY% -m PyInstaller --noconfirm --clean --windowed --name PeRC ^
  --add-data "app\static;app\static" ^
  --add-data "list_combos.py;." ^
  --add-data "export_json.py;." ^
  --add-data "design_beams.py;." ^
  --add-data "design_columns.py;." ^
  --add-data "draw_sections.py;." ^
  --add-data "quantity_takeoff.py;." ^
  --collect-submodules core ^
  --collect-submodules drawing ^
  --collect-submodules quantity ^
  --collect-submodules etabs_link ^
  --collect-submodules comtypes ^
  --collect-submodules keyring ^
  --collect-all ezdxf ^
  --collect-submodules openpyxl ^
  --hidden-import numpy ^
  --hidden-import win32ctypes.core ^
  run_app.py || goto :err

echo [3/3] Nen thanh PeRC_v1.0.0.zip...
if exist PeRC_v1.0.0.zip del PeRC_v1.0.0.zip
powershell -NoProfile -Command "Compress-Archive -Path 'dist\PeRC' -DestinationPath 'PeRC_v1.0.0.zip'" || goto :err

echo.
echo XONG. Chay thu: dist\PeRC\PeRC.exe
echo File phat hanh: PeRC_v1.0.0.zip
pause
exit /b 0

:err
echo.
echo CO LOI - chup man hinh gui lai.
pause
exit /b 1
