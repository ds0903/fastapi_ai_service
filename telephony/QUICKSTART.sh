#!/bin/bash

echo "===================================================="
echo "   TELEPHONY QUICK START"
echo "===================================================="
echo ""

echo "Step 1/4: Installing Twilio..."
pip install twilio==9.0.4
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install twilio"
    exit 1
fi
echo "  [OK] Twilio installed"
echo ""

echo "Step 2/4: Integrating telephony into main.py..."
python telephony/integrate.py
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to integrate telephony"
    exit 1
fi
echo "  [OK] Integration complete"
echo ""

echo "Step 3/4: Checking .env configuration..."
if grep -q "TWILIO_ACCOUNT_SID" .env 2>/dev/null; then
    echo "  [OK] Twilio credentials found in .env"
else
    echo ""
    echo "[!] TWILIO CREDENTIALS NOT FOUND IN .env"
    echo ""
    echo "Please add these lines to your .env file:"
    echo ""
    echo "TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    echo "TWILIO_AUTH_TOKEN=your_auth_token_here"
    echo "TWILIO_PHONE_NUMBER=+380xxxxxxxxx"
    echo ""
    echo "Get credentials from: https://console.twilio.com"
    echo ""
    echo "See telephony/.env.example for full template"
    echo ""
fi
echo ""

echo "Step 4/4: Checking telephony health..."
python -c "from telephony.config import twilio_settings; print('  [OK] Configuration loaded') if twilio_settings.twilio_account_sid else print('  [!] Please set Twilio credentials in .env')"
echo ""

echo "===================================================="
echo "   SETUP COMPLETE!"
echo "===================================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Configure Twilio credentials in .env if not done yet"
echo "2. Start server: python start.py"
echo "3. Check status: http://localhost:8000/telephony/health"
echo "4. For local testing, setup ngrok:"
echo "   - Download: https://ngrok.com/download"
echo "   - Run: ngrok http 8000"
echo "   - Use ngrok URL in Twilio webhook settings"
echo ""
echo "Documentation: telephony/README.md"
echo ""
