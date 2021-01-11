# Google Assistant

Google assistant for Raspberry with Sense Hat and I2C Screen

## Install

``` sh
cd ~
git clone https://github.com/mpi3d/google-assistant.git
sudo chmod +x ~/google-assistant/scripts/audio-config.sh
sudo ~/google-assistant/scripts/audio-config.sh
```

Follow the instructions [here](https://developers.google.com/assistant/sdk/guides/library/python/embed/config-dev-project-and-account) to configure the project and account settings.
Then follow [this guide](https://developers.google.com/assistant/sdk/guides/library/python/embed/register-device) to register the device and get the secret client_secret{???}.json file.

Place the client_secret{???}.json file in the directory `~/`. **DO NOT RENAME IT**

Then complete `~/google-assistant/src/settings.yaml` with your preferences.

 + [Sense Hat](https://www.kubii.fr/cartes-extension-cameras-raspberry-pi/1081-raspberry-pi-sense-hat-kubii-640522710799.html)
 + [I2C Screen](https://projetsdiy.fr/affichage-oled-ssd1306-i2c-sur-raspberry-pi-code-python-dune-mini-station-meteo-connectee-a-jeedom-avec-la-librairie-adafruit/)
 + [Led Strip](https://www.amazon.fr/Magic-Home/s?ie=UTF8&page=1&rh=i%3Aaps%2Ck%3AMagic%20Home)

``` sh
sudo chmod +x ~/google-assistant/scripts/google-assistant-installer-pi3.sh
sudo  ~/google-assistant/scripts/google-assistant-installer-pi3.sh
```

## Run

``` sh
~/env/bin/python -u ~/google-assistant/src/main.py
```

## Start at boot

``` sh
sudo chmod +x ~/google-assistant/scripts/service-installer.sh
sudo ~/google-assistant/scripts/service-installer.sh
sudo systemctl enable google-assistant-ok-google.service
sudo systemctl start google-assistant-ok-google.service
```

## More information on [GassistPi](https://github.com/shivasiddharth/GassistPi)
