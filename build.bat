@echo off
REM NAI Tag Classifier 빌드 스크립트
REM 사용법: build.bat

echo ============================================
echo NAI Tag Classifier 빌드
echo ============================================

REM 가상환경 활성화
call venv\Scripts\activate.bat

REM viewer-ui 빌드
echo.
echo [1/3] viewer-ui 빌드 중...
cd viewer-ui
call npm run build
if errorlevel 1 (
    echo viewer-ui 빌드 실패!
    exit /b 1
)
cd ..

REM PyInstaller 설치 확인
echo.
echo [2/3] PyInstaller 확인 중...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller 설치 중...
    pip install pyinstaller
)

REM PyInstaller 빌드
echo.
echo [3/3] exe 빌드 중...
pyinstaller build.spec --clean -y

if errorlevel 1 (
    echo 빌드 실패!
    exit /b 1
)

echo.
echo ============================================
echo 빌드 완료!
echo 실행 파일: dist\nai-classifier-server.exe
echo ============================================
echo.
echo 실행 방법:
echo   dist\nai-classifier-server.exe
echo   (브라우저에서 http://localhost:8000 접속)
echo.
pause
