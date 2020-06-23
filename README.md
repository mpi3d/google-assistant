# Google Assistant

Google assistant pour raspberry avec sense-hat et écran en i2c

## ⌨ Installation :

```
sudo apt-get install git
git clone https://github.com/MPi3D/Google_Assistant
```

## ♬ Configuration du son :

```
sudo chmod +x /home/pi/Google_Assistant/scripts/audio_config.sh
sudo /home/pi/Google_Assistant/scripts/audio_config.sh
```

Suivez les instructions [ici](https://developers.google.com/assistant/sdk/guides/library/python/embed/config-dev-project-and-account) pour configurer le projet et les paramètres de compte. Suivez ensuite [ce guide](https://developers.google.com/assistant/sdk/guides/library/python/embed/register-device) pour enregistrer le périphérique et obtenir le fichier client_secret {???} .json

Placez le fichier client_secret {???} .json dans le répertoire /home/pi **⌦ NE PAS LE RENOMMER**

Puis complétez `/home/pi/Google_Assistant/src/settings.yaml` avec vos préférences.

 + [Sense hat](https://www.kubii.fr/cartes-extension-cameras-raspberry-pi/1081-raspberry-pi-sense-hat-kubii-640522710799.html)
 + [Ecran](https://projetsdiy.fr/affichage-oled-ssd1306-i2c-sur-raspberry-pi-code-python-dune-mini-station-meteo-connectee-a-jeedom-avec-la-librairie-adafruit/)
 + [Bandes led](https://www.amazon.fr/Magic-Home/s?ie=UTF8&page=1&rh=i%3Aaps%2Ck%3AMagic%20Home)

```
sudo chmod +x /home/pi/Google_Assistant/scripts/Google_Assistant-installer-pi3.sh
sudo  /home/pi/Google_Assistant/scripts/Google_Assistant-installer-pi3.sh
```

## ❖ Démarrage au boot :

```
sudo chmod +x /home/pi/Google_Assistant/scripts/service-installer.sh
sudo /home/pi/Google_Assistant/scripts/service-installer.sh
sudo systemctl enable Google_Assistant-ok-google.service
sudo systemctl start Google_Assistant-ok-google.service
```

## ❬ ❭ Démarrage manuel :

`/home/pi/env/bin/python -u /home/pi/Google_Assistant/src/main.py`

## + Plus d'informations sur [GassistPi](https://github.com/shivasiddharth/GassistPi)
