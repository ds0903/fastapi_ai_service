@echo off
echo Installing twilio...
pip install twilio==9.0.4

echo.
echo Integrating telephony...
cd /d %~dp0..
python telephony\_integrate_now.py

echo.
echo ✅ DONE! Telephony integrated.
echo.
echo === NEXT STEPS ===
echo 1. Add to .env:
echo    TWILIO_ACCOUNT_SID=ACxxx
echo    TWILIO_AUTH_TOKEN=xxx
echo    TWILIO_PHONE_NUMBER=+380xxx
echo.
echo 2. Get credentials: https://console.twilio.com
echo 3. Buy number: https://console.twilio.com/phone-numbers
echo 4. Start: python start.py
echo 5. Check: http://localhost:8000/telephony/health
echo.
pause
