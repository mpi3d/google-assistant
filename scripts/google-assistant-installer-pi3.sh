#!/bin/bash

set -o errexit

scripts_dir="$(dirname "${BASH_SOURCE[0]}")"

RUN_AS="$(ls -ld "$scripts_dir" | awk 'NR==1 {print $3}')"
if [ "$USER" != "$RUN_AS" ]
then
    echo "This script must run as $RUN_AS, trying to change user..."
    exit 1
fi

clear
echo ""
read -r -p "Enter the your full credential file name including the path and .json extension: " credname
echo ""
read -r -p "Enter the your Google Cloud Console Project-Id: " projid
echo ""
read -r -p "Enter the modelid that was generated in the actions console: " modelid
echo ""
echo "Model id : $modelid
Music stop : X,XX,XX
Alarm cron : None
Alarm sound : Def
Alarm led : None" > ~/google-assistant/src/save.yaml

echo "" > ~/google-assistant/src/ga_error

cd ~/
sudo apt-get update -y
sed 's/#.*//' ~/google-assistant/requirements/google-assistant-system-requirements.txt | xargs sudo apt-get install -y

python3 -m venv .env
.env/bin/python -m pip install --upgrade pip setuptools wheel
source .env/bin/activate

cp ~/google-assistant/requirements/RTIMU.cpython-37m-arm-linux-gnueabihf.so ~/.env/lib/python3.7/site-packages
pip3 install -r ~/google-assistant/requirements/google-assistant-pip-requirements.txt
pip3 install google-assistant-library==1.0.0
pip3 install google-assistant-grpc==0.2.0
pip3 install google-assistant-sdk==0.5.0
pip3 install google-assistant-sdk[samples]==0.5.0
google-oauthlib-tool --scope https://www.googleapis.com/auth/assistant-sdk-prototype \
          --scope https://www.googleapis.com/auth/gcm \
          --save --headless --client-secrets $credname
echo "Testing the installed google assistant. Make a note of the generated Device-Id"
googlesamples-assistant-hotword --project_id $projid --device_model_id $modelid
