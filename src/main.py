import os
import time
import json
import yaml
import psutil
import random
import difflib
import datetime
import argparse
import requests
import traceback
import threading
import subprocess
import mediaplayer
import pathlib2 as pathlib
import google.oauth2.credentials
from gtts import gTTS
from googletrans import Translator
from google.assistant.library import Assistant
from google.assistant.library.event import EventType
from google.assistant.library.file_helpers import existing_file
from google.assistant.library.device_helpers import register_device

settings_file = open("/home/pi/Google_Assistant/src/settings.yaml", "r")
settings = settings_file.read()
settings = yaml.load(settings)
settings_file.close()

if settings.get("Led strips"):
	import flux_led

if settings.get("Sense hat"):
	from sense_hat import SenseHat
	hat = SenseHat()
	hat.low_light = True
	hat.clear()

if settings.get("Lcd screen"):
	from PIL import Image
	from PIL import ImageOps
	from PIL import ImageDraw
	from PIL import ImageFont
	from RPi import GPIO
	import Adafruit_SSD1306

	bsquare = int(settings.get("Square button"))
	bround = int(settings.get("Round button"))
	brigt = int(settings.get("Right button"))
	bleft = int(settings.get("Left button"))

	GPIO.setwarnings(False)
	GPIO.setmode(GPIO.BCM)
	GPIO.setup(bsquare, GPIO.OUT)
	GPIO.setup(bround, GPIO.OUT)
	GPIO.setup(brigt, GPIO.OUT)
	GPIO.setup(bleft, GPIO.OUT)
	GPIO.output(bsquare, GPIO.HIGH)
	GPIO.output(bround, GPIO.HIGH)
	GPIO.output(brigt, GPIO.HIGH)
	GPIO.output(bleft, GPIO.HIGH)

	font = ImageFont.load_default()
	disp = Adafruit_SSD1306.SSD1306_128_64(rst = 0)
	disp.begin()
	disp.reset()
	disp.dim(True)
	disp.set_contrast(1)
	disp.clear()
	disp.display()

if settings.get("Weather"):
	from forecastiopy import *
	apikey = settings.get('Apikey')
	coutry = str(settings.get('Location')).split(',')
	coutry[0] = float(coutry[0])
	coutry[1] = float(coutry[1])
	fio = ForecastIO.ForecastIO(apikey,units='ca',latitude=coutry[1],longitude=coutry[0])

vlc = mediaplayer.vlcplayer()

class Myassistant():

	def __init__(self):
		var_save_file = open("/home/pi/Google_Assistant/src/save.yaml", "r")
		self.var_save = var_save_file.read()
		self.var_save = yaml.load(self.var_save)
		var_save_file.close()
		self.al = False
		self.buton = []
		self.veil = settings.get("Time stand by")*2+1
		self.tink = []
		self.affichage = 'heure'
		self.text_say = 'Sorry I do not remeber'
		self.act_cron = [[str(self.var_save.get("Music stop").split(',')[0]), str(self.var_save.get("Music stop").split(',')[1]), str(self.var_save.get("Music stop").split(',')[2]), 'vlc.stop_vlc()#cantdel']]
		if settings.get("Network constraint"):
			self.act_cron.append(['-',str(settings.get("Start of conection").split(',')[0]),str(settings.get("Start of conection").split(',')[1]),'os.system("sudo systemctl restart Google_Assistant-ok-google.service")#cantdel'])
			m = str(settings.get("End of conection").split(',')[1])
			h = str(settings.get("End of conection").split(',')[0])
			if m == '00':
				m = '59'
				h = Myassistant.remove_hour(h,1)
			else:
				m = Myassistant.remove_min(m,1)
			self.act_cron.append(['-',str(h),str(m),'self.assistant.set_mic_mute(True)#cantdel'])
		if not settings.get("Add actions in crontab") == None:
			for apl in settings.get("Add actions in crontab"):
				self.act_cron.append(apl)
		if not self.var_save.get("Alarm cron") == 'None':
			for apl in self.var_save.get("Alarm cron"):
				self.act_cron.append(apl)

	def process_event(self,event):
		print('\n'+str(event))
		if 'ON_CONVERSATION_TURN_STARTED' in str(event):
			if self.al == True:
				self.al = False
				os.system('sudo killall mpg123')
			vlc.pause_vlc()
			threading.Thread(target=Myassistant.sound,args=()).start()
			if settings.get("Sense hat"):
				threading.Thread(target=Myassistant.logo,args=()).start()
			if not Myassistant.have_network(time.strftime("%H"),time.strftime("%M")):
				if settings.get("Sense hat"):
					Myassistant.logo_low()
				vlc.resume_vlc()
		if 'ON_RESPONDING_STARTED' in str(event):
			vlc.pause_vlc()
			if settings.get("Sense hat"):
				Myassistant.logo_low()
				Myassistant.logo_high()
		if 'ON_ALERT_STARTED' in str(event):
			vlc.pause_vlc()
			if settings.get("Sense hat"):
				Myassistant.logo_high()
		if 'ON_ALERT_FINISHED' in str(event):
			vlc.resume_vlc()
			if settings.get("Sense hat"):
				Myassistant.logo_low()
		if 'ON_CONVERSATION_TURN_TIMEOUT' in str(event):
			if settings.get("Sense hat"):
				Myassistant.logo_low()
			vlc.resume_vlc()
		if 'ON_CONVERSATION_TURN_FINISHED' in str(event):
			if settings.get("Sense hat"):
				Myassistant.logo_low()
			vlc.resume_vlc()

	def register_device(self,project_id, credentials, device_model_id, device_id):
		base_url = '/'.join([DEVICE_API_URL, 'projects', project_id, 'devices'])
		device_url = '/'.join([base_url, device_id])
		session = google.auth.transport.requests.AuthorizedSession(credentials)
		r = session.get(device_url)
		print(device_url, r.status_code)
		if r.status_code == 404:
			print('Registering....')
			r = session.post(base_url, data=json.dumps({
				'id': device_id,
				'model_id': device_model_id,
				'client_type': 'SDK_LIBRARY'
			}))
			if r.status_code != 200:
				if settings.get("Sense hat"):
					Myassistant.logo_high()
				raise Exception('failed to register device: ' + r.text)
				if settings.get("Sense hat"):
					Myassistant.logo_low()
			print('\rDevice registered.')

	def main(self):
		parser = argparse.ArgumentParser(
			formatter_class=argparse.RawTextHelpFormatter)
		parser.add_argument('--device-model-id', '--device_model_id', type=str,
							metavar='DEVICE_MODEL_ID', required=False,
							help='the device model ID registered with Google')
		parser.add_argument('--project-id', '--project_id', type=str,
							metavar='PROJECT_ID', required=False,
							help='the project ID used to register this device')
		parser.add_argument('--device-config', type=str,
							metavar='DEVICE_CONFIG_FILE',
							default=os.path.join(
								os.path.expanduser('~/.config'),
								'googlesamples-assistant',
								'device_config_library.json'
							),
							help='path to store and read device configuration')
		parser.add_argument('--credentials', type=existing_file,
							metavar='OAUTH2_CREDENTIALS_FILE',
							default=os.path.join(
								os.path.expanduser('~/.config'),
								'google-oauthlib-tool',
								'credentials.json'
							),
							help='path to store and read OAuth2 credentials')
		parser.add_argument('-v', '--version', action='version',
							version='%(prog)s ' + Assistant.__version_str__())
		args = parser.parse_args()
		with open(args.credentials, 'r') as f:
			credentials = google.oauth2.credentials.Credentials(token=None,
																**json.load(f))
		device_model_id = None
		last_device_id = None
		try:
			with open(args.device_config) as f:
				device_config = json.load(f)
				device_model_id = device_config['model_id']
				last_device_id = device_config.get('last_device_id', None)
		except FileNotFoundError:
			pass
		should_register = (
			args.device_model_id and args.device_model_id != device_model_id)
		device_model_id = self.var_save.get("Model id")
		with Assistant(credentials, device_model_id) as assistant:
			self.assistant = assistant
			if settings.get("Lcd screen"):
				Myassistant.reload_aff_heure_st(self)
				Myassistant.main_heure(self)
			events = assistant.start()
			device_id = assistant.device_id
			if should_register or (device_id != last_device_id):
				if args.project_id:
					register_device(args.project_id, credentials,
									device_model_id, device_id)
					pathlib.Path(os.path.dirname(args.device_config)).mkdir(
						exist_ok=True)
					with open(args.device_config, 'w') as f:
						json.dump({
							'last_device_id': device_id,
							'model_id': device_model_id,
						}, f)
			self.assistant.set_mic_mute(False)
			for event in events:
				self.process_event(event)
				brusrcmd = event.args
				if event.type == EventType.ON_RECOGNIZING_SPEECH_FINISHED:
					usrcmd = event.args
				else:
					usrcmd = {}
				if event.type == EventType.ON_RECOGNIZING_SPEECH_FINISHED:
					actionev = []
					act = str(brusrcmd).lower()
					act = act.split(": ")
					act = act[1]
					r = 0
					while r > -1 :
						if r == len(act) :
							r = -1
						else :
							actionev.append(act[r].lower())
							r = r + 1
					del actionev[0]
					del actionev[len(act) - 2]
					del actionev[len(act) - 3]
					act = "".join(actionev)
					actionev = act.split(" ")
				if event.type == EventType.ON_RENDER_RESPONSE:
					self.text_say = ()
					act = str(brusrcmd).lower()
					if not '"' in act :
						act = act.split("'")
						i = len(act) - 1
						while i > -1 :
							if not 'renderresponsetype.text' in act[i] and not '}' in act[i] and not '{' in act[i] and not ':' in act[i] and not "'text'" in act[i] and not "'type'" in act[i] and not "'type'" in act[i] and not act[i] == 'text' and not act[i] == 'type' and not act[i] == ', ':
								act = act[i]
								i = -1
							i = i - 1
					else:
						act = act.split('"')
						i = len(act) - 1
						while i > -1 :
							if not 'renderresponsetype.text' in act[i] and not '}' in act[i] and not '{' in act[i] and not ':' in act[i] and not "'text'" in act[i] and not "'type'" in act[i] and not "'type'" in act[i] and not act[i] == 'text' and not act[i] == 'type' and not act[i] == ', ':
								act = act[i]
								i = -1
							i = i - 1
					self.text_say = act
				if event.type == EventType.ON_RECOGNIZING_SPEECH_FINISHED:
					if settings.get("Command voice"):
						for command in settings.get("Command configuration"):
							if command[0] in str(usrcmd).lower():
								for execut in command[1]:
									try:
										eval(execut)
									except:
										print('Failed to execute "'+execut+'"')
					if settings.get("Translation"):
						if 'repeat in' in str(usrcmd).lower() or 'translation' in self.tink:
							assistant.stop_conversation()
							i = len(settings.get("Languages")) - 1
							ood = True
							while i > -1:
								if settings.get("Languages")[i][0].lower() in str(usrcmd).lower():
									ood = False
									Myassistant.say(self, Myassistant.trans(Myassistant.alpha(self.text_say),settings.get("Languages")[i][1]), settings.get("Languages")[i][1])
								i = i - 1
							if ood == True:
								if 'translation' in self.tink:
									del self.tink[self.tink.index('translation')]
									Myassistant.say(self, "Sorry, I don't understand.", 'en')
								else:
									self.tink.append('translation')
									Myassistant.say(self, 'Repeat in what ?', 'en',False)
									assistant.start_conversation()
							elif 'translation' in self.tink:
								del self.tink[self.tink.index('translation')]
					if settings.get("Volume"):
						if 'volume' in str(usrcmd).lower() or 'volume' in self.tink:
							assistant.stop_conversation()
							epo = True
							if 'up' in str(usrcmd).lower():
								assistant.stop_conversation()
								Myassistant.volume_set(int(Myassistant.volume_get())+5)
							elif 'down' in str(usrcmd).lower():
								assistant.stop_conversation()
								Myassistant.volume_set(int(Myassistant.volume_get())-5)
							elif 'maximum' in str(usrcmd).lower():
								assistant.stop_conversation()
								Myassistant.volume_set(100)
							elif 'minimum' in str(usrcmd).lower():
								assistant.stop_conversation()
								Myassistant.volume_set(0)
							elif 'get' in str(usrcmd).lower():
								assistant.stop_conversation()
								Myassistant.say(self,"the volume is at "+str(int(Myassistant.volume_get()))+'%', 'en')
							elif 'softer' in str(usrcmd).lower():
								assistant.stop_conversation()
								Myassistant.volume_set(int(Myassistant.volume_get())+5)
							elif 'louder' in str(usrcmd).lower():
								assistant.stop_conversation()
								Myassistant.volume_set(int(Myassistant.volume_get())-5)
							elif '%' in str(usrcmd).lower():
								assistant.stop_conversation()
								try:
									yytr = str(usrcmd).lower().index('%')
									oppm = []
									ppg = True
									while ppg:
										yytr = yytr - 1
										if str(usrcmd).lower()[yytr] == ' ':
											ppg = False
										else:
											oppm.append(str(usrcmd).lower()[yytr])
									oppm.reverse()
									ll = "".join(oppm)
									ll = int(ll)
									Myassistant.volume_set(ll)
								except:
									pass
							elif 'volume' in self.tink:
								assistant.stop_conversation()
								del self.tink[self.tink.index('volume')]
								Myassistant.say(self, "Sorry, I don't understand.", 'en')
							else:
								epo = False
								assistant.stop_conversation()
								self.tink.append('volume')
								Myassistant.say(self, "What do you want to do with the volume ?", 'en')
								assistant.start_conversation()
							if epo:
								if 'volume' in self.tink:
									del self.tink[self.tink.index('volume')]
						elif 'softer' in str(usrcmd).lower():
							assistant.stop_conversation()
							Myassistant.volume_set(int(Myassistant.volume_get())+5)
						elif 'louder' in str(usrcmd).lower():
							assistant.stop_conversation()
							Myassistant.volume_set(int(Myassistant.volume_get())-5)
					if settings.get("Music"):
						if str(usrcmd).lower() == "{'text': 'stop'}" and vlc.is_vlc_playing():
							assistant.stop_conversation()
							vlc.stop_vlc()
						if str(usrcmd).lower() == "{'text': 'previous'}" in str(usrcmd).lower() and vlc.is_vlc_playing():
							assistant.stop_conversation()
							vlc.previous_vlc()
						if str(usrcmd).lower() == "{'text': 'next'}" in str(usrcmd).lower() and vlc.is_vlc_playing():
							assistant.stop_conversation()
							vlc.next_vlc()
						if 'music' in str(usrcmd).lower() or 'play' in str(usrcmd).lower() or 'song' in str(usrcmd).lower() or 'track' in str(usrcmd).lower():
							assistant.stop_conversation()
							if 'previous' in str(usrcmd).lower() and vlc.is_vlc_playing():
								assistant.stop_conversation()
								vlc.previous_vlc()
							if 'next' in str(usrcmd).lower() and vlc.is_vlc_playing():
								assistant.stop_conversation()
								vlc.next_vlc()
							if 'stop' in str(usrcmd).lower() and vlc.is_vlc_playing():
								assistant.stop_conversation()
								vlc.stop_vlc()
							if 'play' in str(usrcmd).lower() or 'music' in str(usrcmd).lower():
								i = len(settings.get("Radios")) - 1
								while i > -1:
									if settings.get("Radios")[i][0].lower() in str(usrcmd).lower():
										assistant.stop_conversation()
										Myassistant.say(self, Myassistant.yes() + ', ' + str(settings.get("Radios")[i][0]) + ' playback', 'en')
										vlc.play_audio_file(str(settings.get("Radios")[i][1]))
										i = -4
									i = i - 1
								if i == -1 and ('dj' in str(usrcmd).lower() or str(usrcmd).lower() == "{'text': 'music'}" or str(usrcmd).lower() == "{'text': 'play'}" or ('music' in str(usrcmd).lower() and 'play' in str(usrcmd).lower())):
									assistant.stop_conversation()
									Myassistant.say(self, Myassistant.yes() + ', music playback', 'en')
									vlc.play_audio_folder(settings.get("Path to your music"))
								elif i == -1:
									mus = []
									mus.extend(actionev)
									if 'music' in mus :
										mus.remove('music')
									if 'play' in mus :
										mus.remove('play')
									chemin = Myassistant.cherchefichier(str(" ".join(mus)) + ".mp3",settings.get("Path to your music"))
									y = True
									if chemin!="" :
										assistant.stop_conversation()
										Myassistant.say(self, Myassistant.yes() + ', ' + str(" ".join(mus)) + ' playback', 'en')
										vlc.play_audio_file(str(chemin) + "/" + str(" ".join(mus)) + ".mp3")
									else:
										for path, dirs, file in os.walk(settings.get("Path to your music")):
											t = path.split("/")
											if str(t[len(t)-1]) == str(" ".join(mus)):
												assistant.stop_conversation()
												Myassistant.say(self, Myassistant.yes() + ', ' + str(" ".join(mus)) + ' playback', 'en')
												vlc.play_audio_folder(path)
												y = False
									if y == True:
										lllf = []
										for path, dirs, files in os.walk(settings.get("Path to your music")):
											for file in files:
												lllf.append([file,path + '/' + file])
											for adir in dirs:
												lllf.append([adir,path + '/' + adir])
										jhg = []
										for ggf in lllf:
											jhg.append(ggf[0])
										resultmotw = Myassistant.get_mots(str(" ".join(mus)) + ".mp3",jhg,2)
										if not resultmotw == []:
											assistant.stop_conversation()
											kkj = lllf[jhg.index(resultmotw[0])][1]
											if os.path.isdir(kkj):
												Myassistant.say(self, Myassistant.yes() + ', ' + lllf[jhg.index(resultmotw[0])][0] + ' playback', 'en')
												vlc.play_audio_folder(kkj)
											else:
												Myassistant.say(self, Myassistant.yes() + ', ' + lllf[jhg.index(resultmotw[0])][0].replace('.mp3','') + ' playback', 'en')
												vlc.play_audio_file(kkj)
											y = False
					if settings.get("Alarm"):
						uytpv = False
						for e in self.tink:
							if 'alarm' in e:
								uytpv = True
						if 'alarm' in str(usrcmd).lower() or uytpv:
							assistant.stop_conversation()
							alarm_option_add = ()
							alarm_setting_add = []
							alarm_time_add = ()
							if 'set' in str(usrcmd).lower():
								alarm_option_add = 'new'
							elif 'remove' in str(usrcmd).lower() or 'del' in str(usrcmd).lower() or 'delete' in str(usrcmd).lower():
								alarm_option_add = 'del'
							elif 'enable' in str(usrcmd).lower():
								alarm_option_add = 'enable'
							elif 'disable' in str(usrcmd).lower():
								alarm_option_add = 'disable'
							else:
								alarm_option_add = 'get'
							today = ['-',str(time.strftime("%A"))]
							listal = []
							i = len(self.act_cron)-1
							while i > -1:
								if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
									listal.append(self.act_cron[i])
								i = i - 1
							if 'monday' in str(usrcmd).lower():
								alarm_setting_add.append('Monday')
							if 'tuesday' in str(usrcmd).lower():
								alarm_setting_add.append('Tuesday')
							if 'wednesday' in str(usrcmd).lower():
								alarm_setting_add.append('Wednesday')
							if 'thursday' in str(usrcmd).lower():
								alarm_setting_add.append('Thursday')
							if 'friday' in str(usrcmd).lower():
								alarm_setting_add.append('Friday')
							if 'saturday' in str(usrcmd).lower():
								alarm_setting_add.append('Saturday')
							if 'sunday' in str(usrcmd).lower():
								alarm_setting_add.append('Sunday')
							if 'tomorrow' in str(usrcmd).lower():
								alarm_setting_add.append(Myassistant.ad_day(time.strftime("%A"),1))
							if 'today' in str(usrcmd).lower():
								alarm_setting_add.append(time.strftime("%A"))
							if 'all' in str(usrcmd).lower():
								alarm_setting_add.append('all')
							if 'in' in str(usrcmd).lower():
								pass
							else:
								m = []
								for word in actionev:
									eds = []
									for letter in word:
										numb = '0123456789'
										if letter in numb:
											eds.append(letter)
									if len(eds) == 1:
										m.append('0'+eds[0])
									elif len(eds) == 2:
										m.append(eds[0]+eds[1])
								if len(m) == 1:
									m = [m[0],'00']
								elif len(m) == 2:
									m = [m[0],m[1]]
								elif len(m) > 2:
									m = [m[0],m[1]]
								if not len(m) == 0:
									if 'pm' in ' '.join(actionev):
										m[0] = str(int(m[0]+12))
									if m[0] == '24':
										m[0] = '00'
									if m[1] == '60':
										m[1] = '00'
									if not (int(m[0]) > 23 or int(m[1]) > 59):
										alarm_time_add = m
							for e in self.tink:
								if 'alarm' in e:
									fg = eval(e.replace('alarm',''))
									if fg[0] == 'new':
										alarm_option_add = 'new'
										if alarm_setting_add == []:
											alarm_setting_add = fg[1]
									elif fg[0] == 'del':
										alarm_option_add = 'del'
									elif fg[0] == 'disable':
										alarm_option_add = 'disable'
									elif fg[0] == 'enable':
										alarm_option_add = 'enable'
							if alarm_option_add == 'get':
								if len(listal) == 0:
									Myassistant.say(self, "You don't have any alarm", 'en')
								elif len(listal) == 1:
									if 'Myassistant.alarm_dring(self)#cantdel' in listal[0][3]:
										if 'Myassistant.alarm_dring(self)#cantdel#disable' == listal[0][3]:
											if listal[0][0] in today:
												if Myassistant.time_as_not_pass(listal[0][1],listal[0][2]):
													Myassistant.say(self, 'You have 1 alarm disable for today at '+listal[0][1]+':'+listal[0][2], 'en')
												else:
													if listal[0][0] == '-':
														Myassistant.say(self, 'You have 1 alarm disable for tomorrow at '+listal[0][1]+':'+listal[0][2], 'en')
													else:
														Myassistant.say(self, 'You have 1 alarm disable on '+listal[0][0]+' at '+listal[0][1]+':'+listal[0][2], 'en')
											else:
												Myassistant.say(self, 'You have 1 alarm disable on '+listal[0][0]+' at '+listal[0][1]+':'+listal[0][2], 'en')
										else:
											if listal[0][0] in today:
												if Myassistant.time_as_not_pass(listal[0][1],listal[0][2]):
													Myassistant.say(self, 'You have 1 alarm for today at '+listal[0][1]+':'+listal[0][2], 'en')
												else:
													if listal[0][0] == '-':
														Myassistant.say(self, 'You have 1 alarm for tomorrow at '+listal[0][1]+':'+listal[0][2], 'en')
													else:
														Myassistant.say(self, 'You have 1 alarm on '+listal[0][0]+' at '+listal[0][1]+':'+listal[0][2], 'en')
											else:
												Myassistant.say(self, 'You have 1 alarm on '+listal[0][0]+' at '+listal[0][1]+':'+listal[0][2], 'en')
								else:
									if not len(alarm_setting_add) == 0:
										if 'all' in alarm_setting_add:
											f = ['You have '+str(len(listal))+' alarms']
											for alar in listal:
												if 'Myassistant.alarm_dring(self)#cantdel' in alar[3]:
													if 'Myassistant.alarm_dring(self)#cantdel#disable' == alar[3]:
														if alar[0] in today:
															if Myassistant.time_as_not_pass(alar[1],alar[2]):
																f.append('an alarm disable for today at '+alar[1]+':'+alar[2])
															else:
																if alar[0] == '-':
																	f.append('an alarm disable for tomorrow at '+alar[1]+':'+alar[2])
																else:
																	f.append('an alarm disable on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															f.append('an alarm disable on '+alar[0]+' at '+alar[1]+':'+alar[2])
													else:
														if alar[0] in today:
															if Myassistant.time_as_not_pass(alar[1],alar[2]):
																f.append('an alarm  for today at '+alar[1]+':'+alar[2])
															else:
																if alar[0] == '-':
																	f.append('an alarms for tomorrow at '+alar[1]+':'+alar[2])
																else:
																	f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
											uts = str(f[len(f)-1])
											del f[len(f)-1]
											tr = [", ".join(f),uts]
											tr = " and ".join(tr)
											Myassistant.say(self, tr, 'en')
										else:
											listalchoice = []
											for alar in listal:
												if alar[0] in alarm_setting_add:
													listalchoice.append(alar)
											if listalchoice == []:
												Myassistant.say(self, "You don't have any alarm in your choice", 'en')
											elif len(listalchoice) == 1:
												if 'Myassistant.alarm_dring(self)#cantdel' in alar[3]:
													if 'Myassistant.alarm_dring(self)#cantdel#disable' == alar[3]:
														Myassistant.say(self, "You have 1 alarm disable on "+listalchoice[0][0]+" at "+listalchoice[0][1]+":"+listalchoice[0][2], 'en')
													else:
														Myassistant.say(self, "You have 1 alarm on "+listalchoice[0][0]+" at "+listalchoice[0][1]+":"+listalchoice[0][2], 'en')
											else:
												f = ['You have '+str(len(listalchoice))+' alarms in your choice']
												for alar in listalchoice:
													if 'Myassistant.alarm_dring(self)#cantdel' in alar[3]:
														if 'Myassistant.alarm_dring(self)#cantdel#disable' == alar[3]:
															if alar[0] in today:
																if Myassistant.time_as_not_pass(alar[1],alar[2]):
																	f.append('an alarm disable for today at '+alar[1]+':'+alar[2])
																else:
																	if alar[0] == '-':
																		f.append('an alarm disable for tomorrow at '+alar[1]+':'+alar[2])
																	else:
																		f.append('an alarm disable on '+alar[0]+' at '+alar[1]+':'+alar[2])
															else:
																f.append('an alarm disable on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															if alar[0] in today:
																if Myassistant.time_as_not_pass(alar[1],alar[2]):
																	f.append('an alarm  for today at '+alar[1]+':'+alar[2])
																else:
																	if alar[0] == '-':
																		f.append('an alarms for tomorrow at '+alar[1]+':'+alar[2])
																	else:
																		f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
															else:
																f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
												uts = str(f[len(f)-1])
												del f[len(f)-1]
												tr = [", ".join(f),uts]
												tr = " and ".join(tr)
												Myassistant.say(self, tr, 'en')
									elif not alarm_time_add == ():
										listalchoice = []
										for alar in listal:
											if alar[1] == alarm_time_add[0] and alar[2] == alarm_time_add[1]:
												listalchoice.append(alar)
										if listalchoice == []:
											Myassistant.say(self, "You don't have any alarm in your choice", 'en')
										elif len(listalchoice) == 1:
											if 'Myassistant.alarm_dring(self)#cantdel' in alar[3]:
												if 'Myassistant.alarm_dring(self)#cantdel#disable' == alar[3]:
													Myassistant.say(self, "You have 1 alarm disable on "+listalchoice[0][0]+" at "+listalchoice[0][1]+":"+listalchoice[0][2], 'en')
												else:
													Myassistant.say(self, "You have 1 alarm on "+listalchoice[0][0]+" at "+listalchoice[0][1]+":"+listalchoice[0][2], 'en')
										else:
											f = ['You have '+str(len(listalchoice))+' alarms in your choice']
											for alar in listalchoice:
												if 'Myassistant.alarm_dring(self)#cantdel' in alar[3]:
													if 'Myassistant.alarm_dring(self)#cantdel#disable' == alar[3]:
														if alar[0] in today:
															if Myassistant.time_as_not_pass(alar[1],alar[2]):
																f.append('an alarm disable for today at '+alar[1]+':'+alar[2])
															else:
																if alar[0] == '-':
																	f.append('an alarm disable for tomorrow at '+alar[1]+':'+alar[2])
																else:
																	f.append('an alarm disable on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															f.append('an alarm disable on '+alar[0]+' at '+alar[1]+':'+alar[2])
													else:
														if alar[0] in today:
															if Myassistant.time_as_not_pass(alar[1],alar[2]):
																f.append('an alarm  for today at '+alar[1]+':'+alar[2])
															else:
																if alar[0] == '-':
																	f.append('an alarms for tomorrow at '+alar[1]+':'+alar[2])
																else:
																	f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
											uts = str(f[len(f)-1])
											del f[len(f)-1]
											tr = [", ".join(f),uts]
											tr = " and ".join(tr)
											Myassistant.say(self, tr, 'en')
									else:
										f = ['You have '+str(len(listal))+' alarms']
										for alar in listal:
											if 'Myassistant.alarm_dring(self)#cantdel' in alar[3]:
												if 'Myassistant.alarm_dring(self)#cantdel#disable' == alar[3]:
													if alar[0] in today:
														if Myassistant.time_as_not_pass(alar[1],alar[2]):
															f.append('an alarm disable for today at '+alar[1]+':'+alar[2])
														else:
															if alar[0] == '-':
																f.append('an alarm disable for tomorrow at '+alar[1]+':'+alar[2])
															else:
																f.append('an alarm disable on '+alar[0]+' at '+alar[1]+':'+alar[2])
													else:
														f.append('an alarm disable on '+alar[0]+' at '+alar[1]+':'+alar[2])
												else:
													if alar[0] in today:
														if Myassistant.time_as_not_pass(alar[1],alar[2]):
															f.append('an alarm  for today at '+alar[1]+':'+alar[2])
														else:
															if alar[0] == '-':
																f.append('an alarms for tomorrow at '+alar[1]+':'+alar[2])
															else:
																f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
													else:
														f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
										uts = str(f[len(f)-1])
										del f[len(f)-1]
										tr = [", ".join(f),uts]
										tr = " and ".join(tr)
										Myassistant.say(self, tr, 'en')
							elif alarm_option_add == 'new':
								if not alarm_time_add == ():
									if alarm_setting_add == []:
										self.act_cron.append(['-',alarm_time_add[0],alarm_time_add[1],'Myassistant.alarm_dring(self)#cantdel'])
										Myassistant.say(self, 'You have 1 new alarm at '+alarm_time_add[0]+':'+alarm_time_add[1], 'en')
									elif len(alarm_setting_add) == 1:
										self.act_cron.append([dayb,alarm_time_add[0],alarm_time_add[1],'Myassistant.alarm_dring(self)#cantdel'])
										Myassistant.say(self, 'You have 1 new alarm on '+dayb+' at '+alarm_time_add[0]+':'+alarm_time_add[1], 'en')
									else:
										f = ['You have '+str(len(alarm_setting_add))+' new alarms']
										for dayb in alarm_setting_add:
											self.act_cron.append([dayb,alarm_time_add[0],alarm_time_add[1],'Myassistant.alarm_dring(self)#cantdel'])
											f.append('an alarm on '+dayb+' at '+alarm_time_add[0]+':'+alarm_time_add[1])
										uts = str(f[len(f)-1])
										del f[len(f)-1]
										tr = [", ".join(f),uts]
										tr = " and ".join(tr)
										Myassistant.say(self, tr, 'en')
								else:
									jjfd = True
									ttytrj = 0
									for e in self.tink:
										if 'alarm' in e:
											jjfd = False
											del self.tink[ttytrj]
										else:
											ttytrj = ttytrj + 1
									if jjfd:
										self.tink.append('alarm["new",'+str(alarm_setting_add)+']')
										Myassistant.say(self, 'For when ?', 'en')
										assistant.start_conversation()
									else:
										Myassistant.say(self, "Sorry, I don't understand.", 'en')
							elif alarm_option_add == 'del':
								if len(listal) == 0:
									Myassistant.say(self, "You don't have any alarm", 'en')
								elif len(listal) == 1:
									i = len(self.act_cron)-1
									while i > -1:
										if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
											del self.act_cron[i]
										i = i - 1
									Myassistant.say(self, "Ok, your alarm have been removed", 'en')
								else:
									if alarm_time_add == ():
										if alarm_setting_add == []:
											jjfd = True
											ttytrj = 0
											for e in self.tink:
												if 'alarm' in e:
													jjfd = False
													del self.tink[ttytrj]
												else:
													ttytrj = ttytrj + 1
											if jjfd:
												f = ['You have '+str(len(listal))+' alarms']
												for alar in listal:
													if alar[0] in today:
														if Myassistant.time_as_not_pass(alar[1],alar[2]):
															f.append('an alarm for today at '+alar[1]+':'+alar[2])
														else:
															if alar[0] == '-':
																f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
															else:
																f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
													else:
														f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
												uts = str(f[len(f)-1])
												del f[len(f)-1]
												tr = [", ".join(f),uts]
												tr = " and ".join(tr)
												tr = tr + '. What is your choice ?'
												self.tink.append('alarm["del"]')
												Myassistant.say(self, tr, 'en')
												assistant.start_conversation()
											else:
												Myassistant.say(self, "Sorry, I don't understand.", 'en')
										else:
											if 'all' in alarm_setting_add:
												i = len(self.act_cron)-1
												while i > -1:
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
														del self.act_cron[i]
													i = i - 1
												Myassistant.say(self, "Ok, all alarm have been removed", 'en')
											else:
												listalchoice = []
												for alar in listal:
													if alar[0] in alarm_setting_add:
														listalchoice.append(alar)
												if listalchoice == []:
													Myassistant.say(self, "You don't have any alarm in your choice", 'en')
												elif len(listalchoice) == 1:
													del self.act_cron[self.act_cron.index(listalchoice[0])]
													Myassistant.say(self, "Ok, your alarm on "+listalchoice[0][0]+' at '+listalchoice[0][1]+':'+listalchoice[0][2]+' has been removed', 'en')
												else:
													f = ['Ok, '+str(len(listalchoice))+' alarms have been removed']
													for alar in listalchoice:
														if alar[0] in today:
															if Myassistant.time_as_not_pass(alar[1],alar[2]):
																f.append('an alarm for today at '+alar[1]+':'+alar[2])
															else:
																if alar[0] == '-':
																	f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
																else:
																	f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														del self.act_cron[self.act_cron.index(alar)]
													uts = str(f[len(f)-1])
													del f[len(f)-1]
													tr = [", ".join(f),uts]
													tr = " and ".join(tr)
													Myassistant.say(self, tr, 'en')
									else:
										if alarm_setting_add == []:
											listalchoice = []
											for alar in listal:
												if alar[1] == alarm_time_add[0] and alar[2] == alarm_time_add[1]:
													listalchoice.append(alar)
											if listalchoice == []:
												Myassistant.say(self, "You don't have any alarm in your choice", 'en')
											elif len(listalchoice) == 1:
												del self.act_cron[self.act_cron.index(listalchoice[0])]
												Myassistant.say(self, "Ok, your alarm on "+listalchoice[0][0]+' at '+listalchoice[0][1]+':'+listalchoice[0][2]+' has been removed', 'en')
											else:
												f = ['Ok, '+str(len(listalchoice))+' alarms have been removed']
												for alar in listalchoice:
													if alar[0] in today:
														if Myassistant.time_as_not_pass(alar[1],alar[2]):
															f.append('an alarm for today at '+alar[1]+':'+alar[2])
														else:
															if alar[0] == '-':
																f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
															else:
																f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
													else:
														f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
													del self.act_cron[self.act_cron.index(alar)]
												uts = str(f[len(f)-1])
												del f[len(f)-1]
												tr = [", ".join(f),uts]
												tr = " and ".join(tr)
												Myassistant.say(self, tr, 'en')
										else:
											if 'all' in alarm_setting_add:
												i = len(self.act_cron)-1
												while i > -1:
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
														del self.act_cron[i]
													i = i - 1
												Myassistant.say(self, "Ok, all alarm have been removed", 'en')
											else:
												listalchoice = []
												for alar in listal:
													if alar[0] in alarm_setting_add and alar[1] == alarm_time_add[0] and alar[2] == alarm_time_add[1]:
														listalchoice.append(alar)
												if listalchoice == []:
													Myassistant.say(self, "You don't have any alarm in your choice", 'en')
												elif len(listalchoice) == 1:
													del self.act_cron[self.act_cron.index(listalchoice[0])]
													Myassistant.say(self, "Ok, your alarm on "+listalchoice[0][0]+' at '+listalchoice[0][1]+':'+listalchoice[0][2]+' has been removed', 'en')
												else:
													f = ['Ok, '+str(len(listalchoice))+' alarms have been removed']
													for alar in listalchoice:
														if alar[0] in today:
															if Myassistant.time_as_not_pass(alar[1],alar[2]):
																f.append('an alarm for today at '+alar[1]+':'+alar[2])
															else:
																if alar[0] == '-':
																	f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
																else:
																	f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														del self.act_cron[self.act_cron.index(alar)]
													uts = str(f[len(f)-1])
													del f[len(f)-1]
													tr = [", ".join(f),uts]
													tr = " and ".join(tr)
													Myassistant.say(self, tr, 'en')
							elif alarm_option_add == 'disable':
								if len(listal) == 0:
									Myassistant.say(self, "You don't have any alarm", 'en')
								elif len(listal) == 1:
									i = len(self.act_cron)-1
									while i > -1:
										if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
											if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
												self.act_cron[i][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
										i = i - 1
									Myassistant.say(self, "Ok, your alarm is disable", 'en')
								else:
									if alarm_time_add == ():
										if alarm_setting_add == []:
											jjfd = True
											ttytrj = 0
											for e in self.tink:
												if 'alarm' in e:
													jjfd = False
													del self.tink[ttytrj]
												else:
													ttytrj = ttytrj + 1
											if jjfd:
												f = ['You have '+str(len(listal))+' alarms']
												for alar in listal:
													if alar[0] in today:
														if Myassistant.time_as_not_pass(alar[1],alar[2]):
															f.append('an alarm for today at '+alar[1]+':'+alar[2])
														else:
															if alar[0] == '-':
																f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
															else:
																f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
													else:
														f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
												uts = str(f[len(f)-1])
												del f[len(f)-1]
												tr = [", ".join(f),uts]
												tr = " and ".join(tr)
												tr = tr + '. What is your choice ?'
												self.tink.append('alarm["disable"]')
												Myassistant.say(self, tr, 'en')
												assistant.start_conversation()
											else:
												Myassistant.say(self, "Sorry, I don't understand.", 'en')
										else:
											if 'all' in alarm_setting_add:
												i = len(self.act_cron)-1
												while i > -1:
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
														if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
															self.act_cron[i][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
													i = i - 1
												Myassistant.say(self, "Ok, all alarm are disable", 'en')
											else:
												listalchoice = []
												for alar in listal:
													if alar[0] in alarm_setting_add:
														listalchoice.append(alar)
												if listalchoice == []:
													Myassistant.say(self, "You don't have any alarm in your choice", 'en')
												elif len(listalchoice) == 1:
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(listalchoice[0])][3]:
														if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(listalchoice[0])][3]:
															self.act_cron[self.act_cron.index(listalchoice[0])][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
													Myassistant.say(self, "Ok, your alarm on "+listalchoice[0][0]+' at '+listalchoice[0][1]+':'+listalchoice[0][2]+' is disable', 'en')
												else:
													f = ['Ok, '+str(len(listalchoice))+' alarms are disable']
													for alar in listalchoice:
														if alar[0] in today:
															if Myassistant.time_as_not_pass(alar[1],alar[2]):
																f.append('an alarm for today at '+alar[1]+':'+alar[2])
															else:
																if alar[0] == '-':
																	f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
																else:
																	f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(alar)][3]:
															if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(alar)][3]:
																self.act_cron[self.act_cron.index(alar)][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
													uts = str(f[len(f)-1])
													del f[len(f)-1]
													tr = [", ".join(f),uts]
													tr = " and ".join(tr)
													Myassistant.say(self, tr, 'en')
									else:
										if alarm_setting_add == []:
											listalchoice = []
											for alar in listal:
												if alar[1] == alarm_time_add[0] and alar[2] == alarm_time_add[1]:
													listalchoice.append(alar)
											if listalchoice == []:
												Myassistant.say(self, "You don't have any alarm in your choice", 'en')
											elif len(listalchoice) == 1:
												if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(listalchoice[0])][3]:
													if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(listalchoice[0])][3]:
														self.act_cron[self.act_cron.index(listalchoice[0])][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
												Myassistant.say(self, "Ok, your alarm on "+listalchoice[0][0]+' at '+listalchoice[0][1]+':'+listalchoice[0][2]+' are disable', 'en')
											else:
												f = ['Ok, '+str(len(listalchoice))+' alarms are disable']
												for alar in listalchoice:
													if alar[0] in today:
														if Myassistant.time_as_not_pass(alar[1],alar[2]):
															f.append('an alarm for today at '+alar[1]+':'+alar[2])
														else:
															if alar[0] == '-':
																f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
															else:
																f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
													else:
														f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(alar)][3]:
														if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(alar)][3]:
															self.act_cron[self.act_cron.index(alar)][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
												uts = str(f[len(f)-1])
												del f[len(f)-1]
												tr = [", ".join(f),uts]
												tr = " and ".join(tr)
												Myassistant.say(self, tr, 'en')
										else:
											if 'all' in alarm_setting_add:
												i = len(self.act_cron)-1
												while i > -1:
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
														if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
															self.act_cron[i][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
													i = i - 1
												Myassistant.say(self, "Ok, all alarm are disable", 'en')
											else:
												listalchoice = []
												for alar in listal:
													if alar[0] in alarm_setting_add and alar[1] == alarm_time_add[0] and alar[2] == alarm_time_add[1]:
														listalchoice.append(alar)
												if listalchoice == []:
													Myassistant.say(self, "You don't have any alarm in your choice", 'en')
												elif len(listalchoice) == 1:
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(listalchoice[0])][3]:
														if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(listalchoice[0])][3]:
															self.act_cron[self.act_cron.index(listalchoice[0])][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
													Myassistant.say(self, "Ok, your alarm on "+listalchoice[0][0]+' at '+listalchoice[0][1]+':'+listalchoice[0][2]+' is disable', 'en')
												else:
													f = ['Ok, '+str(len(listalchoice))+' alarms are disable']
													for alar in listalchoice:
														if alar[0] in today:
															if Myassistant.time_as_not_pass(alar[1],alar[2]):
																f.append('an alarm for today at '+alar[1]+':'+alar[2])
															else:
																if alar[0] == '-':
																	f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
																else:
																	f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(alar)][3]:
															if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(alar)][3]:
																self.act_cron[self.act_cron.index(alar)][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
													uts = str(f[len(f)-1])
													del f[len(f)-1]
													tr = [", ".join(f),uts]
													tr = " and ".join(tr)
													Myassistant.say(self, tr, 'en')
							elif alarm_option_add == 'enable':
								if len(listal) == 0:
									Myassistant.say(self, "You don't have any alarm", 'en')
								elif len(listal) == 1:
									i = len(self.act_cron)-1
									while i > -1:
										if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
											if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
												self.act_cron[i][3] = 'Myassistant.alarm_dring(self)#cantdel'
										i = i - 1
									Myassistant.say(self, "Ok, your alarm is enable", 'en')
								else:
									if alarm_time_add == ():
										if alarm_setting_add == []:
											jjfd = True
											ttytrj = 0
											for e in self.tink:
												if 'alarm' in e:
													jjfd = False
													del self.tink[ttytrj]
												else:
													ttytrj = ttytrj + 1
											if jjfd:
												f = ['You have '+str(len(listal))+' alarms']
												for alar in listal:
													if alar[0] in today:
														if Myassistant.time_as_not_pass(alar[1],alar[2]):
															f.append('an alarm for today at '+alar[1]+':'+alar[2])
														else:
															if alar[0] == '-':
																f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
															else:
																f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
													else:
														f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
												uts = str(f[len(f)-1])
												del f[len(f)-1]
												tr = [", ".join(f),uts]
												tr = " and ".join(tr)
												tr = tr + '. What is your choice ?'
												self.tink.append('alarm["enable"]')
												Myassistant.say(self, tr, 'en')
												assistant.start_conversation()
											else:
												Myassistant.say(self, "Sorry, I don't understand.", 'en')
										else:
											if 'all' in alarm_setting_add:
												i = len(self.act_cron)-1
												while i > -1:
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
														if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
															self.act_cron[i][3] = 'Myassistant.alarm_dring(self)#cantdel'
													i = i - 1
												Myassistant.say(self, "Ok, all alarm are enable", 'en')
											else:
												listalchoice = []
												for alar in listal:
													if alar[0] in alarm_setting_add:
														listalchoice.append(alar)
												if listalchoice == []:
													Myassistant.say(self, "You don't have any alarm in your choice", 'en')
												elif len(listalchoice) == 1:
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(listalchoice[0])][3]:
														if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(listalchoice[0])][3]:
															self.act_cron[self.act_cron.index(listalchoice[0])][3] = 'Myassistant.alarm_dring(self)#cantdel'
													Myassistant.say(self, "Ok, your alarm on "+listalchoice[0][0]+' at '+listalchoice[0][1]+':'+listalchoice[0][2]+' is enable', 'en')
												else:
													f = ['Ok, '+str(len(listalchoice))+' alarms are enable']
													for alar in listalchoice:
														if alar[0] in today:
															if Myassistant.time_as_not_pass(alar[1],alar[2]):
																f.append('an alarm for today at '+alar[1]+':'+alar[2])
															else:
																if alar[0] == '-':
																	f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
																else:
																	f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(alar)][3]:
															if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(alar)][3]:
																self.act_cron[self.act_cron.index(alar)][3] = 'Myassistant.alarm_dring(self)#cantdel'
													uts = str(f[len(f)-1])
													del f[len(f)-1]
													tr = [", ".join(f),uts]
													tr = " and ".join(tr)
													Myassistant.say(self, tr, 'en')
									else:
										if alarm_setting_add == []:
											listalchoice = []
											for alar in listal:
												if alar[1] == alarm_time_add[0] and alar[2] == alarm_time_add[1]:
													listalchoice.append(alar)
											if listalchoice == []:
												Myassistant.say(self, "You don't have any alarm in your choice", 'en')
											elif len(listalchoice) == 1:
												if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(listalchoice[0])][3]:
													if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(listalchoice[0])][3]:
														self.act_cron[self.act_cron.index(listalchoice[0])][3] = 'Myassistant.alarm_dring(self)#cantdel'
												Myassistant.say(self, "Ok, your alarm on "+listalchoice[0][0]+' at '+listalchoice[0][1]+':'+listalchoice[0][2]+' are enable', 'en')
											else:
												f = ['Ok, '+str(len(listalchoice))+' alarms are enable']
												for alar in listalchoice:
													if alar[0] in today:
														if Myassistant.time_as_not_pass(alar[1],alar[2]):
															f.append('an alarm for today at '+alar[1]+':'+alar[2])
														else:
															if alar[0] == '-':
																f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
															else:
																f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
													else:
														f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(alar)][3]:
														if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(alar)][3]:
															self.act_cron[self.act_cron.index(alar)][3] = 'Myassistant.alarm_dring(self)#cantdel'
												uts = str(f[len(f)-1])
												del f[len(f)-1]
												tr = [", ".join(f),uts]
												tr = " and ".join(tr)
												Myassistant.say(self, tr, 'en')
										else:
											if 'all' in alarm_setting_add:
												i = len(self.act_cron)-1
												while i > -1:
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
														if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
															self.act_cron[i][3] = 'Myassistant.alarm_dring(self)#cantdel'
													i = i - 1
												Myassistant.say(self, "Ok, all alarm are enable", 'en')
											else:
												listalchoice = []
												for alar in listal:
													if alar[0] in alarm_setting_add and alar[1] == alarm_time_add[0] and alar[2] == alarm_time_add[1]:
														listalchoice.append(alar)
												if listalchoice == []:
													Myassistant.say(self, "You don't have any alarm in your choice", 'en')
												elif len(listalchoice) == 1:
													if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(listalchoice[0])][3]:
														if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(listalchoice[0])][3]:
															self.act_cron[self.act_cron.index(listalchoice[0])][3] = 'Myassistant.alarm_dring(self)#cantdel'
													Myassistant.say(self, "Ok, your alarm on "+listalchoice[0][0]+' at '+listalchoice[0][1]+':'+listalchoice[0][2]+' is enable', 'en')
												else:
													f = ['Ok, '+str(len(listalchoice))+' alarms are enable']
													for alar in listalchoice:
														if alar[0] in today:
															if Myassistant.time_as_not_pass(alar[1],alar[2]):
																f.append('an alarm for today at '+alar[1]+':'+alar[2])
															else:
																if alar[0] == '-':
																	f.append('an alarm for tomorrow at '+alar[1]+':'+alar[2])
																else:
																	f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														else:
															f.append('an alarm on '+alar[0]+' at '+alar[1]+':'+alar[2])
														if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[self.act_cron.index(alar)][3]:
															if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[self.act_cron.index(alar)][3]:
																self.act_cron[self.act_cron.index(alar)][3] = 'Myassistant.alarm_dring(self)#cantdel'
													uts = str(f[len(f)-1])
													del f[len(f)-1]
													tr = [", ".join(f),uts]
													tr = " and ".join(tr)
													Myassistant.say(self, tr, 'en')
							i = 0
							alarim = []
							while i < len(self.act_cron):
								if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
									alarim.append(self.act_cron[i])
								i = i + 1
							if str(alarim) == '[]':
								alarim = 'None'
							self.var_save["Alarm cron"] = alarim
							Myassistant.save_var_in_file(self)
					if settings.get("Led strips"):
						leditest = []
						for leds in settings.get("Led strips names"):
							if str(leds[0]).lower() in str(usrcmd).lower():
								leditest.append(str(leds[0]))
						if 'my light' in str(usrcmd).lower():
							if str(leditest) == '[]':
								leditest = ['All']
						for ffd in self.tink:
							if 'led strip' in ffd:
								hudgfisdu = []
								hudgfisdu = eval(str(ffd.split('$')[1]))
								for te in hudgfisdu:
									leditest.append(te)
						if not str(leditest) == '[]':
							lmk = []
							if 'turn on' in str(usrcmd).lower():
								lmk.append('turnOn()')
							elif 'turn off' in str(usrcmd).lower():
								lmk.append('turnOff()')
							llmmh = True
							colorlist = ['seven color cross fade','red gradual change','green gradual change','blue gradual change','yellow gradual change','cyan gradual change','purple gradual change','white gradual change','red green cross fade','red blue cross fade','green blue cross fade','seven color strobe flash','red strobe flash','green strobe flash','blue strobe flash','yellow strobe flash','cyan strobe flash','purple strobe flash','white strobe flash','seven color jumping']
							coloraction = ['setPresetPattern(0x25,100)','setPresetPattern(0x26,100)','setPresetPattern(0x27,100)','setPresetPattern(0x28,100)','setPresetPattern(0x29,100)','setPresetPattern(0x2a,100)','setPresetPattern(0x2b,100)','setPresetPattern(0x2c,100)','setPresetPattern(0x2d,100)','setPresetPattern(0x2e,100)','setPresetPattern(0x2f,100)','setPresetPattern(0x30,100)','setPresetPattern(0x31,100)','setPresetPattern(0x32,100)','setPresetPattern(0x33,100)','setPresetPattern(0x34,100)','setPresetPattern(0x35,100)','setPresetPattern(0x36,100)','setPresetPattern(0x37,100)','setPresetPattern(0x38,100)']
							oogjg = len(colorlist) - 1
							while oogjg > - 1:
								if colorlist[oogjg].lower() in str(usrcmd).lower() and llmmh == True:
									llmmh = False
									if '%' in str(usrcmd).lower():
										try:
											yytr = str(usrcmd).lower().index('%')
											oppm = []
											ppg = True
											while ppg:
												yytr = yytr - 1
												if str(usrcmd).lower()[yytr] == ' ':
													ppg = False
												else:
													oppm.append(str(usrcmd).lower()[yytr])
											oppm.reverse()
											ll = "".join(oppm)
											lmk.append(coloraction[oogjg].replace('100',str(ll)))
										except:
											lmk.append(coloraction[oogjg])
									else:
										lmk.append(coloraction[oogjg])
								oogjg = oogjg - 1
							if '%' in str(usrcmd).lower() and llmmh == True:
								try:
									yytr = str(usrcmd).lower().index('%')
									oppm = []
									ppg = True
									while ppg:
										yytr = yytr - 1
										if str(usrcmd).lower()[yytr] == ' ':
											ppg = False
										else:
											oppm.append(str(usrcmd).lower()[yytr])
									oppm.reverse()
									ll = "".join(oppm)
									ghf = int(ll)
									ghf = 255 * ghf / 100
									ghf = round(ghf)
									ll = str(ghf)
									lmk.append('brightness='+ll)
								except:
									pass
							if llmmh == True:
								for color in settings.get('Custom colors'):
									if str(color[0]).lower() in str(usrcmd).lower() and llmmh == True:
										llmmh = False
										lmk.append(str(color[1]))
							if llmmh == True:
								responscoled = flux_led.utils.get_color_names_list()
								for tey in responscoled:
									if str(tey).lower() in str(usrcmd).lower() and llmmh == True:
										llmmh = False
										resultintero = flux_led.utils.color_object_to_tuple(str(tey))
										lmk.append('setRgb('+str(resultintero[0])+','+str(resultintero[1])+','+str(resultintero[2])+')')
							assistant.stop_conversation()
							if not str(lmk) == '[]':
								pr = 0
								while pr < len(self.tink):
									if 'led strip' in self.tink[pr]:
										del self.tink[pr]
									pr = pr + 1
								name_wifi_led = []
								led = flux_led.__main__
								for wifi_led in settings.get('Led strips names'):
									listwifi[str(wifi_led[0])]=led.WifiLedBulb(wifi_led[1])
									name_wifi_led.append(wifi_led[0])
								try:
									for hhg in leditest:
										if hhg == 'All':
											for adresr in listwifi:
												wifiled = listwifi[adresr]
												if not wifiled.isOn() and not 'turnOff()' in lmk and not 'turnOn()' in lmk:
													wifiled.turnOn()
													time.sleep(1)
												for kdk in lmk:
													if 'brightness' in kdk:
														y = wifiled.getRgbw()
														eval('wifiled.setRgbw(r='+str(y[0])+',g='+str(y[1])+',b='+str(y[2])+',w='+str(y[3])+','+str(kdk)+')')
													else:
														eval('wifiled.'+kdk)
										else:
											wifiled = listwifi[name]
											if not wifiled.isOn() and not 'turnOff()' in lmk and not 'turnOn()' in lmk:
												wifiled.turnOn()
												time.sleep(1)
											for kdk in lmk:
												if 'brightness' in kdk:
													y = wifiled.getRgbw()
													eval('wifiled.setRgbw(r='+str(y[0])+',g='+str(y[1])+',b='+str(y[2])+',w='+str(y[3])+','+str(kdk)+')')
												else:
													eval('wifiled.'+kdk)
								except BrokenPipeError:
									print('Failed : "led strip"')
							else:
								ytr = True
								pr = 0
								while pr < len(self.tink):
									if 'led strip' in self.tink[pr]:
										ytr = False
										del self.tink[pr]
									pr = pr + 1
								if ytr:
									self.tink.append('led strip$'+str(leditest))
									Myassistant.say(self, "What do you want to do with this led strips ?", 'en')
									assistant.start_conversation()
								else:
									Myassistant.say(self, "Sorry, I don't understand.", 'en')
					if settings.get("Shutdown option"):
						if 'reboot' in str(usrcmd).lower() or 'reboot' in self.tink:
							if 'reboot' in self.tink:
								del self.tink[self.tink.index('reboot')]
								assistant.stop_conversation()
								if 'yes' in str(usrcmd).lower():
									Myassistant.say(self, Myassistant.yes(), 'en')
									if settings.get("Sense hat"):
										hat.clear()
									os.system('sudo reboot')
								else:
									Myassistant.say(self, 'Ok, cancel', 'en')
							elif 'please' in str(usrcmd).lower():
								assistant.stop_conversation()
								Myassistant.say(self, Myassistant.yes(), 'en')
								if settings.get("Sense hat"):
									hat.clear()
								os.system('sudo reboot')
							else:
								assistant.stop_conversation()
								self.tink.append('reboot')
								Myassistant.say(self, "Are you sure ?", 'en')
								assistant.start_conversation()
						if 'shut down' in str(usrcmd).lower() or 'power off' in str(usrcmd).lower() or 'shut down' in self.tink:
							if 'shut down' in self.tink:
								del self.tink[self.tink.index('shut down')]
								assistant.stop_conversation()
								if 'yes' in str(usrcmd).lower():
									Myassistant.say(self, Myassistant.yes(), 'en')
									if settings.get("Sense hat"):
										hat.clear()
									os.system('sudo halt')
								else:
									Myassistant.say(self, 'Ok, cancel', 'en')
							elif 'please' in str(usrcmd).lower():
								assistant.stop_conversation()
								Myassistant.say(self, Myassistant.yes(), 'en')
								if settings.get("Sense hat"):
									hat.clear()
								os.system('sudo halt')
							else:
								assistant.stop_conversation()
								self.tink.append('shut down')
								Myassistant.say(self, "Are you sure ?", 'en')
								assistant.start_conversation()

	def alpha(chaine):
		alphabet = 'abcdefghijklmnopqrstuvwxyz 0123456789 éêëè áâäà ùñóíç ’""° ,. !¡ ?¿ +-÷x='
		l = []
		chaine = chaine
		i = len(chaine) - 1
		while i > -1 :
			l.append(chaine[i])
			i = i - 1
		i = len(l) - 1
		while i > -1 :
			if not l[i].lower() in str(alphabet):
				del l[i]
			i = i - 1
		l.reverse()
		l = "".join(l)
		return l

	def trans(words,lang):
		translator = Translator()
		transword= translator.translate(words, dest=lang)
		transword=transword.text
		transword=transword.replace("Text, ",'',1)
		transword=transword.strip()
		return transword

	def yes():
		b = random.randint(0,11)
		p = ()
		if b == 0 or b == 1 or b == 2:
			p = 'ok'
		elif b == 3 or b == 4:
			p = 'okay'
		elif b == 5 or b == 6:
			p = 'of course'
		elif b == 7 or b == 8:
			p = 'yes'
		elif b == 9:
			p = 'yep'
		elif b == 10:
			p = 'yea'
		elif b == 11:
			p = 'yeah'
		else:
			p = ''
		b = random.randint(0,1)
		if b == 0 :
			p = p + ' ' + settings.get("Name")
		return p

	def get_mots(word,listc,sensibility=0):
		listclower = []
		for element in listc:
			listclower.append(str(element).lower())
		if sensibility == 0:
			result = difflib.get_close_matches(str(word).lower(), listclower)
		else:
			result = difflib.get_close_matches(str(word).lower(), listclower,sensibility)
		resultuper = []
		for elementlow in result:
			resultuper.append(str(listc[listclower.index(elementlow)]))
		return resultuper

	def search_wordt(word,listc):
		fgh = []
		i = len(word) - 1
		while i > -1:
			o = len(listc) - 1
			while o > -1:
				if word.lower() in listc[o].lower():
					fgh.append(str(listc[o]))
					del listc[o]
				o = o - 1
			kj = []
			for g in word:
				kj.append(g)
			del kj[len(kj)-1]
			word = "".join(kj)
			i = i - 1
		return fgh

	def cherchefichier(fichier, rep):
		entrees = os.listdir(rep)
		for entree in entrees:
			if (not os.path.isdir(os.path.join(rep, entree))) and (entree==fichier):
				return rep
		for entree in entrees:
			rep2 = os.path.join(rep, entree)
			if os.path.isdir(rep2):
				chemin = Myassistant.cherchefichier(fichier, rep2)
				if chemin!="":
					return chemin
		return ""

	def time_as_not_pass(hour,minute):
		if int(time.strftime("%H")) < int(hour):
			return True
		elif int(time.strftime("%H")) == int(hour):
			if int(time.strftime("%M")) < int(minute):
				return True
			else:
				return False
		else:
			return False

	def have_network(hour,minute):
		if settings.get("Network constraint"):
			startnet = settings.get("Start of conection").split(",")
			endnet = settings.get("End of conection").split(",")
			startnet = datetime.time(int(startnet[0]),int(startnet[1]))
			endnet = datetime.time(int(endnet[0]),int(endnet[1]))
			timefornet = datetime.time(int(hour),int(minute))
			if timefornet > startnet and timefornet < endnet:
				return True
			else:
				return False
		else:
			return True

	def ad_min_hour(hour,minu,ad):
		while ad > 0:
			minu = int(minu) + 1
			if minu > 59:
				minu = '00'
				hour = Myassistant.ad_hour(hour,1)
			elif len(str(minu)) < 2:
				minu = '0' + str(minu)
			ad = ad - 1
		return [str(hour),str(minu)]

	def remove_min_hour(hour,minu,ad):
		while ad > 0:
			minu = int(minu) + 1
			if minu < 0:
				minu = '59'
				hour = Myassistant.remove_hour(hour,1)
			elif len(str(minu)) < 2:
				minu = '0' + str(minu)
			ad = ad - 1
		return [str(hour),str(minu)]

	def ad_hour(hour,ad):
		while ad > 0:
			hour = int(hour) + 1
			if hour > 23:
				hour = '00'
			elif len(str(hour)) < 2:
				hour = '0' + str(hour)
			ad = ad - 1
		return str(hour)

	def remove_hour(hour,remove):
		while remove > 0:
			hour = int(hour) - 1
			if hour < 0:
				hour = '23'
			elif len(str(hour)) < 2:
				hour = '0' + str(hour)
			remove = remove - 1
		return str(hour)

	def ad_min(minu,ad):
		while ad > 0:
			minu = int(minu) + 1
			if minu > 59:
				minu = '00'
			elif len(str(minu)) < 2:
				minu = '0' + str(minu)
			ad = ad - 1
		return str(minu)

	def remove_min(minu,remove):
		while remove > 0:
			minu = int(minu) - 1
			if minu < 0:
				minu = '59'
			elif len(str(minu)) < 2:
				minu = '0' + str(minu)
			remove = remove - 1
		return str(minu)

	def ad_day(day,ad):
		while ad > 0:
			if day == "Monday" :
				day = 'Tuesday'
			elif day == "Tuesday" :
				day = 'Wednesday'
			elif day == "Wednesday" :
				day = 'Thursday'
			elif day == "Thursday" :
				day = 'Friday'
			elif day == "Friday" :
				day = 'Saturday'
			elif day == "Saturday" :
				day = 'Sunday'
			elif day == "Sunday" :
				day = 'Monday'
			ad = ad - 1
		return str(day)

	def remove_day(day,remove):
		while remove > 0:
			if day == "Monday" :
				day = 'Sunday'
			elif day == "Tuesday" :
				day = 'Monday'
			elif day == "Wednesday" :
				day = 'Tuesday'
			elif day == "Thursday" :
				day = 'Wednesday'
			elif day == "Friday" :
				day = 'Thursday'
			elif day == "Saturday" :
				day = 'Friday'
			elif day == "Sunday" :
				day = 'Saturday'
			remove = remove - 1
		return str(day)

	def ad_letter(letter,ad,listl='abcdefghijklmnopqrstuvwxyz '):
		listm = []
		for letre in listl:
			listm.append(letre)
		posi = listm.index(letter)
		while ad > 0:
			posi = posi + 1
			if posi > len(listm)-1:
				posi = 0
			ad = ad - 1
		return listm[posi]

	def remove_letter(letter,remove,listl='abcdefghijklmnopqrstuvwxyz '):
		listm = []
		for letre in listl:
			listm.append(letre)
		posi = listm.index(letter)
		while remove > 0:
			posi = posi - 1
			if posi < 0:
				posi = len(listm)-1
			remove = remove - 1
		return listm[posi]

	def butonshearch(self):
		pressed = 0
		while not self.affichage == 'heure' and not self.affichage == '':
			bouton = True
			while not self.affichage == 'heure' and not self.affichage == '' and bouton:
				if GPIO.input(bsquare) == 0 or GPIO.input(bround) == 0 or GPIO.input(brigt) == 0 or GPIO.input(bleft) == 0:
					self.veil = 0
					if GPIO.input(bsquare) == 0:
						self.buton.append(0)
					elif GPIO.input(bround) == 0:
						self.buton.append(1)
					elif GPIO.input(brigt) == 0:
						self.buton.append(2)
					elif GPIO.input(bleft) == 0:
						self.buton.append(3)
					bouton = False
				else:
					time.sleep(0.1)
			if not pressed > 2:
				time.sleep(0.3)
			else:
				time.sleep(0.15)
			if GPIO.input(bsquare) == 0 or GPIO.input(bround) == 0 or GPIO.input(brigt) == 0 or GPIO.input(bleft) == 0:
				pressed = pressed + 1
			else:
				pressed = 0

	def logo():
		t = 0.05
		b = (0,0,255)
		r = (255,0,0)
		j = (255,255,0)
		v = (0,255,0)
		hat.clear()
		hat.set_pixel(2,2,b)
		hat.set_pixel(5,2,r)
		hat.set_pixel(5,5,j)
		hat.set_pixel(2,5,v)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(3,2,b)
		hat.set_pixel(5,3,r)
		hat.set_pixel(4,5,j)
		hat.set_pixel(2,4,v)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(4,2,b)
		hat.set_pixel(5,4,r)
		hat.set_pixel(3,5,j)
		hat.set_pixel(2,3,v)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(2,2,v)
		hat.set_pixel(5,2,b)
		hat.set_pixel(5,5,r)
		hat.set_pixel(2,5,j)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(3,2,v)
		hat.set_pixel(5,3,b)
		hat.set_pixel(4,5,r)
		hat.set_pixel(2,4,j)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(4,2,v)
		hat.set_pixel(5,4,b)
		hat.set_pixel(3,5,r)
		hat.set_pixel(2,3,j)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(2,2,j)
		hat.set_pixel(5,2,v)
		hat.set_pixel(5,5,b)
		hat.set_pixel(2,5,r)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(3,2,j)
		hat.set_pixel(5,3,v)
		hat.set_pixel(4,5,b)
		hat.set_pixel(2,4,r)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(4,2,j)
		hat.set_pixel(5,4,v)
		hat.set_pixel(3,5,b)
		hat.set_pixel(2,3,r)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(2,2,r)
		hat.set_pixel(5,2,j)
		hat.set_pixel(5,5,v)
		hat.set_pixel(2,5,b)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(3,2,r)
		hat.set_pixel(5,3,j)
		hat.set_pixel(4,5,v)
		hat.set_pixel(2,4,b)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(4,2,r)
		hat.set_pixel(5,4,j)
		hat.set_pixel(3,5,v)
		hat.set_pixel(2,3,b)
		time.sleep(t)
		hat.clear()
		hat.set_pixel(2,2,b)
		hat.set_pixel(5,2,r)
		hat.set_pixel(5,5,j)
		hat.set_pixel(2,5,v)

	def logo_high():
		t = 0.01
		hat.clear()
		i = 0
		while i < 226:
			b = (0,0,i)
			r = (i,0,0)
			j = (i,i,0)
			v = (0,i,0)
			hat.set_pixel(2,2,b)
			hat.set_pixel(5,2,r)
			hat.set_pixel(5,5,j)
			hat.set_pixel(2,5,v)
			time.sleep(t)
			i = i + 15

	def logo_low():
		t = 0.01
		i = 225
		while i > -1:
			b = (0,0,i)
			r = (i,0,0)
			j = (i,i,0)
			v = (0,i,0)
			hat.set_pixel(2,2,b)
			hat.set_pixel(5,2,r)
			hat.set_pixel(5,5,j)
			hat.set_pixel(2,5,v)
			time.sleep(t)
			i = i - 15
		hat.clear()

	def sound():
		subprocess.Popen(["aplay", "/home/pi/Google_Assistant/src/sound/Bip.wav"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

	def volume_set(volume):
		os.system("amixer set 'Master' "+str(volume)+"%")

	def volume_get():
		vol = os.popen("amixer get 'Master' | grep 'Front Right'").read()
		vol = vol.split("[")[1]
		vol = vol.replace("%] ","")
		vol = int(vol)
		return vol

	def say(self, words, language,save=True):
		if not words == '':
			gTTS(text=words, lang=language).save("/home/pi/Google_Assistant/src/say.mp3")
			threading.Thread(target=self.process_event('ON_RESPONDING_STARTED:\n  {"is_error_response": false}'),args=()).start()
			os.system("mpg123 -q /home/pi/Google_Assistant/src/say.mp3")
			os.remove("/home/pi/Google_Assistant/src/say.mp3")
			if save:
				self.text_say = words
			self.process_event('ON_RESPONDING_FINISHED')
			self.process_event('ON_RENDER_RESPONSE:\n  {"text": "' + words + '", "type": 0}')

	def refrech_error():
		try:
			disp.display()
		except OSError:
			time.sleep(0.1)
			try:
				disp.display()
			except OSError:
				time.sleep(0.1)
				try:
					disp.display()
				except OSError:
					pass

	def aff_clean(self,cl):
		if cl:
			self.veil = settings.get("Time stand by")*2+1
			self.affichage = ''
			time.sleep(0.3)
			disp.clear()
			Myassistant.refrech_error()
		else:
			if self.affichage == '':
				self.affichage = 'heure'
				Myassistant.reload_aff_heure_st(self)

	def reload_aff_heure_st(self):
		image = Image.new('1', (disp.width,disp.height))
		draw = ImageDraw.Draw(image)
		listal = []
		alfortom = False
		i = len(self.act_cron)-1
		while i > -1:
			if 'Myassistant.alarm_dring(self)#cantdel' == self.act_cron[i][3]:
				listal.append(self.act_cron[i])
			i = i - 1
		if int(time.strftime("%H")) > 17:
			ood = Myassistant.ad_day(time.strftime("%A"),1)
			for li in listal:
				if str(ood) == li[0] or '-' == li[0]:
					if int(li[1]) < 12:
						alfortom = True
		for li in listal:
			if time.strftime("%A") == li[0] or '-' == li[0]:
				if int(time.strftime("%H")) < int(li[1]):
					alfortom = True
				elif int(time.strftime("%H")) == int(li[1]):
					if int(time.strftime("%M")) < int(li[2]):
						alfortom = True
		if alfortom:
			alarm = Image.open('/home/pi/Google_Assistant/src/images/clock/alarme.jpg')
			alarm = alarm.resize((10,9))
			alarm = ImageOps.invert(alarm)
			o = random.randint(1,4)
			if o == 1:
				image.paste(alarm, (random.randint(0,119),random.randint(0,7)))
			elif o == 2:
				image.paste(alarm, (random.randint(0,6),random.randint(0,55)))
			elif o == 3:
				image.paste(alarm, (random.randint(112,119),random.randint(0,55)))
			elif o == 4:
				image.paste(alarm, (random.randint(0,119),random.randint(48,55)))
			draw.text((random.randint(15,47),random.randint(14,39)), str(time.strftime("%H")), font=font, fill=255)
			draw.text((random.randint(59,101),random.randint(14,39)), str(time.strftime("%M")), font=font, fill=255)
		else:
			draw.text((random.randint(0,47),random.randint(0,55)), str(time.strftime("%H")), font=font, fill=255)
			draw.text((random.randint(59,116),random.randint(0,55)), str(time.strftime("%M")), font=font, fill=255)
		disp.image(image)
		Myassistant.refrech_error()

	def exec_error(self,ex):
		try:
			ex = str(ex)
			if not '#disable' in ex:
				if '#cantdel' in ex:
					ex = ex.replace("#cantdel","")
				eval(ex)
				print('Action cron : "' + ex + '"')
		except:
			print('Failed to execute : "' + ex + '"')

	def execute_next(self,direc):
		e = settings.get("Custom menu")
		i = len(e)-1
		while i > -1:
			if not settings.get("Led strips"):
				if 'Led strip' == e[i]:
					del e[i]
			elif not settings.get("Music"):
				if 'Music' == e[i]:
					del e[i]
			elif not settings.get("Weather"):
				if 'Weather' == e[i]:
					del e[i]
			i = i - 1
		if self.affichage == 'heure total':
			fghd = 'Clock'
		elif self.affichage == 'led strip':
			fghd = 'Led strip'
		elif self.affichage == 'météo':
			fghd = 'Weather'
		elif self.affichage == 'music':
			fghd = 'Music'
		k = e.index(str(fghd))
		if direc == 'left':
			if k - 1 < 0:
				k = len(e)-1
			else:
				k = k - 1
		else:
			if k + 1 > len(e)-1:
				k = 0
			else:
				k = k + 1
		disp.clear()
		Myassistant.refrech_error()
		while not len(self.buton) == 0:
			del self.buton[0]
		if e[k] == 'Clock':
			threading.Timer(0, Myassistant.aff_heure,[self]).start()
		elif e[k] == 'Weather':
			threading.Timer(0, Myassistant.aff_meteo,[self]).start()
		elif e[k] == 'Music':
			threading.Timer(0, Myassistant.aff_music,[self]).start()
		elif e[k] == 'Led strip':
			threading.Timer(0, Myassistant.aff_led_strip,[self]).start()

	def save_var_in_file(self):
		w = []
		for u in self.var_save:
			w.append(str(str(u)+" : "+str(self.var_save.get(str(u)))))
		w = "\n".join(w)
		fichier = open("/home/pi/Google_Assistant/src/save.yaml", "w")
		fichier.write(w)
		fichier.close()

	def adprogvolume(self):
		vol = Myassistant.volume_get()
		vol1 = vol
		while self.al:
			vol1 = vol1 + 1
			Myassistant.volume_set(vol1)
			time.sleep(2)
		Myassistant.volume_set(vol)

	def stop_al_time(self):
		l = 300
		while self.al :
			if l < 1 :
				self.al = False
				os.system('sudo killall mpg123')
				if settings.get("Led strips"):
					try:
						led = flux_led.__main__
						for adresr in self.var_save.get("Alarm led")[0]:
							wifiled = listwifi[adresr]
							wifiled.turnOff()
					except BrokenPipeError:
						print('Failed : "led strip"')
			else:
				l = l - 1
			time.sleep(1)

	def alarm_dring(self):
		self.al = True
		vlc.pause_vlc()
		if settings.get("Sense hat"):
			Myassistant.logo_high()
		self.veil = settings.get("Time stand by")*2+1
		if not self.affichage == 'heure total':
			if self.affichage == 'heure' or self.affichage == '':
				self.affichage = 'heure total'
				threading.Timer(0, Myassistant.aff_heure,[self]).start()
				threading.Timer(0, Myassistant.butonshearch,[self]).start()
			else:
				threading.Timer(0, Myassistant.aff_heure,[self]).start()
		if settings.get("Led strips"):
			if not str(self.var_save.get("Alarm led")) == 'None':
				try:
					led = flux_led.__main__
					for adresr in self.var_save.get("Alarm led")[0]:
						wifiled = listwifi[adresr]
						if not wifiled.isOn():
							wifiled.turnOn()
							time.sleep(1)
						eval('wifiled.'+str(self.var_save.get("Alarm led")[1]))
				except BrokenPipeError:
					print('Failed : "led strip"')
		threading.Timer(5, Myassistant.adprogvolume,[self]).start()
		threading.Timer(0, Myassistant.stop_al_time,[self]).start()
		if self.var_save.get("Alarm sound") == 'Def':
			while self.al:
				os.system("mpg123 -q /home/pi/Google_Assistant/src/sound/Alarm.mp3")
		else:
			fileplay = self.var_save.get("Alarm sound")
			if os.path.isdir(fileplay):
				files = []
				for path, dirs, file in os.walk(fileplay):
					for filename in file:
						files.append(path + '/' + filename)
				i = len(files) - 1
				while i > -1 :
					if not ".mp3" in str(files[i]) :
						del files[i]
					i = i - 1
				if not len(files) == 0 :
					sefulfiles = []
					uuf = files
					while len(uuf) > 0:
						u = random.randint(0,len(uuf)-1)
						sefulfiles.append(uuf[u])
						del uuf[u]
					dfgh = True
					while self.al and dfgh:
						p = subprocess.Popen(['mpg123', '-q', str(sefulfiles[random.randint(0,len(sefulfiles)-1)])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
						out, err = p.communicate()
						if not str(err) == "b''":
							dfgh = False
			else:
				dfgh = True
				while self.al and dfgh:
					os.system("mpg123 -q "+str(fileplay))
					p = subprocess.Popen(['mpg123', '-q', str(fileplay)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
					out, err = p.communicate()
					if not str(err) == "b''":
						dfgh = False
		while self.al:
			os.system("mpg123 -q /home/pi/Google_Assistant/src/sound/Alarm.mp3")
		self.al = False
		self.veil = 0
		if settings.get("Sense hat"):
			Myassistant.logo_low()
		vlc.resume_vlc()

	def alarm_action(self):
		set_alarm_list = [['Set new alarm','newalarm'],
						  ['Get alarm','getal'],
						  ['Change alarm','changealarm'],
						  ['Remove alarm',[[['All','removeall'],
											['Specific alarm','removespec'],
											['Exit','exit']],'remove']],
						  ['Set alarm statut',[[['All','actall'],
											['Specific alarm','actspec'],
											['Exit','exit']],'statut']],
						  ['Costum alarm','costumalarm'],
						  ['Exit','exit']]
		setal = Myassistant.select_list(self,set_alarm_list,'alarm menu')
		tmasone = Myassistant.ad_min_hour(time.strftime("%H"),time.strftime("%M"),1)
		if setal == 'newalarm':
			selecttime = Myassistant.select_time(self,'--', '--', '-', 'new alarm',True)
			if not (selecttime[0] == '--' or selecttime[1] == '--'):
				self.act_cron.append([selecttime[2],selecttime[0],selecttime[1],'Myassistant.alarm_dring(self)#cantdel'])
		elif setal == 'removeall':
			i = len(self.act_cron)-1
			while i > -1:
				if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
					del self.act_cron[i]
				i = i - 1
		elif setal == 'removespec':
			i = 0
			alarmcrons = [['All','all']]
			while i < len(self.act_cron):
				if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
					if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
						if self.act_cron[i][0] == '-':
							alarmcrons.append(['(Disable) Alarm at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
						else:
							alarmcrons.append(['(Disable) Alarm on '+self.act_cron[i][0]+' at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
					else:
						if self.act_cron[i][0] == '-':
							alarmcrons.append(['Alarm at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
						else:
							alarmcrons.append(['Alarm on '+self.act_cron[i][0]+' at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
				i = i + 1
			alarmcrons.append(['Exit','exit'])
			delalarm = Myassistant.select_list(self,alarmcrons,'select alarm')
			if delalarm == 'all':
				i = len(self.act_cron)-1
				while i > -1:
					if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
						del self.act_cron[i]
					i = i - 1
			elif not delalarm == 'exit' and not delalarm == None:
				del self.act_cron[int(delalarm)]
		elif setal == 'changealarm':
			i = 0
			alarmcrons = []
			while i < len(self.act_cron):
				if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
					if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
						if self.act_cron[i][0] == '-':
							alarmcrons.append(['(Disable) Alarm at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
						else:
							alarmcrons.append(['(Disable) Alarm on '+self.act_cron[i][0]+' at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
					else:
						if self.act_cron[i][0] == '-':
							alarmcrons.append(['Alarm at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
						else:
							alarmcrons.append(['Alarm on '+self.act_cron[i][0]+' at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
				i = i + 1
			alarmcrons.append(['Exit','exit'])
			delalarm = Myassistant.select_list(self,alarmcrons,'select alarm')
			if not delalarm == 'exit' and not delalarm == None:
				selecttime = Myassistant.select_time(self,self.act_cron[int(delalarm)][1],self.act_cron[int(delalarm)][2],self.act_cron[int(delalarm)][0], 'new time',True)
				if not (selecttime[0] == '--' or selecttime[1] == '--'):
					self.act_cron[int(delalarm)] = [selecttime[2],selecttime[0],selecttime[1],'Myassistant.alarm_dring(self)#cantdel']
				else:
					del self.act_cron[int(delalarm)]
		elif setal == 'getal':
			i = 0
			alarmcrons = []
			while i < len(self.act_cron):
				if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
					if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
						if self.act_cron[i][0] == '-':
							alarmcrons.append(['(Disable) Alarm at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
						else:
							alarmcrons.append(['(Disable) Alarm on '+self.act_cron[i][0]+' at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
					else:
						if self.act_cron[i][0] == '-':
							alarmcrons.append(['Alarm at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
						else:
							alarmcrons.append(['Alarm on '+self.act_cron[i][0]+' at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
				i = i + 1
			alarmcrons.append(['Exit','exit'])
			delalarm = Myassistant.select_list(self,alarmcrons,'alarm')
		elif setal == 'costumalarm':
			if settings.get("Led strips"):
				vffffffv = Myassistant.select_list(self,[['Led strip','led'],['Sound','sound'],['Exit','exit']],'costum')
				if vffffffv == 'sound':
					choic = Myassistant.select_list(self,[['Default','def'],['File','file'],['Exit','exit']],'alarm sound')
					if choic == 'def':
						self.var_save["Alarm sound"] = 'Def'
					elif choic == 'file':
						mscel = Myassistant.select_list(self,[['Radios','radios'],['File','file'],['Exit','exit']],'music')
						if mscel == 'radios':
							radiona = []
							for hgj in settings.get("Radios"):
								radiona.append(hgj)
							j = Myassistant.select_list(self,radiona,'Radios')
						elif mscel == 'file':
							j = Myassistant.select_path(self,settings.get("Path to your music"),True)
						if not mscel == 'exit' and not mscel == None and not j == None:
							self.var_save["Alarm sound"] = str(j)
				elif vffffffv == 'led':
					choic = Myassistant.select_list(self,[['Color','color'],['None','nones'],['Exit','exit']],'alarm led')
					if choic == 'color':
						coolor = Myassistant.select_led_strip_color_all(self)
						if not '[' in str(coolor[0]):
							coolor[0] = [str(coolor[0])]
						self.var_save["Alarm led"] = coolor
					elif choic == 'nones':
						self.var_save["Alarm led"] = 'None'
			else:
				choic = Myassistant.select_list(self,[['Default','def'],['File','file'],['Exit','exit']],'alarm sound')
				if choic == 'def':
					self.var_save["Alarm sound"] = 'Def'
				elif choic == 'file':
					mscel = Myassistant.select_list(self,[['Radios','radios'],['File','file'],['Exit','exit']],'music')
					if mscel == 'radios':
						radiona = []
						for hgj in settings.get("Radios"):
							radiona.append(hgj)
						j = Myassistant.select_list(self,radiona,'Radios')
					elif mscel == 'file':
						j = Myassistant.select_path(self,settings.get("Path to your music"),True)
					if not mscel == 'exit' and not mscel == None and not j == None:
						self.var_save["Alarm sound"] = str(j)
		elif setal == 'actall':
			choic = Myassistant.select_list(self,[['Enable','en'],['Disable','di'],['Exit','exit']],'select statut')
			if choic == 'en':
				i = 0
				while i < len(self.act_cron):
					if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
						if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
							self.act_cron[i][3] = 'Myassistant.alarm_dring(self)#cantdel'
					i = i + 1
			elif choic == 'di':
				i = 0
				while i < len(self.act_cron):
					if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
						if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
							self.act_cron[i][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
					i = i + 1
		elif setal == 'actspec':
			i = 0
			alarmcrons = [['All','all']]
			while i < len(self.act_cron):
				if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
					if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
						if self.act_cron[i][0] == '-':
							alarmcrons.append(['(Disable) Alarm at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
						else:
							alarmcrons.append(['(Disable) Alarm on '+self.act_cron[i][0]+' at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
					else:
						if self.act_cron[i][0] == '-':
							alarmcrons.append(['Alarm at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
						else:
							alarmcrons.append(['Alarm on '+self.act_cron[i][0]+' at '+self.act_cron[i][1]+':'+self.act_cron[i][2],str(i)])
				i = i + 1
			alarmcrons.append(['Exit','exit'])
			delalarm = Myassistant.select_list(self,alarmcrons,'select alarm')
			if delalarm == 'all':
				choic = Myassistant.select_list(self,[['Enable','en'],['Disable','di'],['Exit','exit']],'select statut')
				if choic == 'en':
					i = 0
					while i < len(self.act_cron):
						if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
							if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
								self.act_cron[i][3] = 'Myassistant.alarm_dring(self)#cantdel'
						i = i + 1
				elif choic == 'di':
					i = 0
					while i < len(self.act_cron):
						if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
							if not 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[i][3]:
								self.act_cron[i][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
						i = i + 1
			elif not delalarm == 'exit' and not delalarm == None:
				if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[int(delalarm)][3]:
					if 'Myassistant.alarm_dring(self)#cantdel#disable' == self.act_cron[int(delalarm)][3]:
						self.act_cron[int(delalarm)][3] = 'Myassistant.alarm_dring(self)#cantdel'
					else:
						self.act_cron[int(delalarm)][3] = 'Myassistant.alarm_dring(self)#cantdel#disable'
		i = 0
		alarim = []
		while i < len(self.act_cron):
			if 'Myassistant.alarm_dring(self)#cantdel' in self.act_cron[i][3]:
				alarim.append(self.act_cron[i])
			i = i + 1
		if str(alarim) == '[]':
			alarim = 'None'
		self.var_save["Alarm cron"] = alarim
		Myassistant.save_var_in_file(self)

	def main_heure(self):
		if time.strftime("%S") == '00':
			stime = [str(time.strftime("%A")),str(time.strftime("%H")),str(time.strftime("%M"))]
			i = len(self.act_cron) - 1
			while i > -1:
				if self.act_cron[i][0] == '-' or self.act_cron[i][0] == stime[0]:
					if self.act_cron[i][1] == '--' or self.act_cron[i][1] == stime[1]:
						if self.act_cron[i][2] == '--' or self.act_cron[i][2] == stime[2]:
							threading.Timer(0,Myassistant.exec_error,[self,self.act_cron[i][3]]).start()
				i = i - 1
			if self.affichage == 'heure' :
				Myassistant.reload_aff_heure_st(self)
			if time.strftime("%M") == '00' :
				if Myassistant.have_network(time.strftime("%H"),time.strftime("%M")):
					try:
						fio.get_forecast(latitude=coutry[1],longitude=coutry[0])
					except:
						print('Failed to get forecast')
			time.sleep(0.5)
		if self.veil == settings.get("Time stand by")*2:
			self.affichage = 'heure'
			time.sleep(0.5)
			disp.clear()
			Myassistant.refrech_error()
			Myassistant.reload_aff_heure_st(self)
			self.veil = self.veil + 1
		elif self.veil < settings.get("Time stand by")*2:
			self.veil = self.veil + 1
		threading.Timer(0.5, Myassistant.main_heure,[self]).start()
		if GPIO.input(bsquare) == 0 and GPIO.input(bround) == 0 and GPIO.input(brigt) == 0 and GPIO.input(bleft) == 0:
			self.affichage = 'shutdown'
			self.veil = settings.get("Time stand by")*2+1
			if settings.get("Sense hat"):
				hat.clear()
			disp.clear()
			Myassistant.refrech_error()
			thetime = 40
			while thetime > 0:
				time.sleep(0.1)
				if GPIO.input(bround) == 1 or GPIO.input(bround) == 1 or GPIO.input(brigt) == 1 or GPIO.input(bleft) == 1:
					disp.clear()
					Myassistant.refrech_error()
					os.system('sudo reboot')
				thetime = thetime - 1
			disp.clear()
			Myassistant.refrech_error()
			os.system('sudo halt')
		elif (GPIO.input(bsquare) == 0 or GPIO.input(bround) == 0 or GPIO.input(brigt) == 0 or GPIO.input(bleft) == 0) and (self.affichage == 'heure' or self.affichage == ''):
			self.veil = 0
			self.affichage = 'heure total'
			disp.clear()
			Myassistant.refrech_error()
			time.sleep(0.3)
			threading.Timer(0, Myassistant.aff_heure,[self]).start()
			threading.Timer(0, Myassistant.butonshearch,[self]).start()

	def aff_heure(self):
		direc = 0
		x = 4
		self.affichage = 'heure total'
		decemb = []
		alblink = 0
		day = time.strftime("%a")
		mon = time.strftime("%b")
		if time.strftime("%B") == "December" :
			i = random.randint(64,320)
			while i > 0:
				decemb.append([random.randint(0,127),random.randint(0,63)])
				i = i - 1
		for done_i in decemb:
			draw.point((done_i[0],done_i[1]),fill=255)
		listal = []
		alfortom = False
		i = len(self.act_cron)-1
		while i > -1:
			if 'Myassistant.alarm_dring(self)#cantdel' == self.act_cron[i][3]:
				listal.append(self.act_cron[i])
			i = i - 1
		if int(time.strftime("%H")) > 17:
			ood = Myassistant.ad_day(time.strftime("%A"),1)
			for li in listal:
				if str(ood) == li[0] or '-' == li[0]:
					if int(li[1]) < 12:
						alfortom = True
		for li in listal:
			if time.strftime("%A") == li[0] or '-' == li[0]:
				if int(time.strftime("%H")) < int(li[1]):
					alfortom = True
				elif int(time.strftime("%H")) == int(li[1]):
					if int(time.strftime("%M")) < int(li[2]):
						alfortom = True
		while self.affichage == 'heure total' :
			image = Image.new('1', (disp.width,disp.height))
			draw = ImageDraw.Draw(image)
			heure = time.strftime("%H")
			minute = time.strftime("%M")
			chiffre1 = Image.open('/home/pi/Google_Assistant/src/images/clock/' + str(heure[0]) + '.jpg')
			chiffre1 = chiffre1.resize((35,35))
			chiffre1 = ImageOps.invert(chiffre1)
			image.paste(chiffre1, (-4,0))
			chiffre2 = Image.open('/home/pi/Google_Assistant/src/images/clock/' + str(heure[1]) + '.jpg')
			chiffre2 = chiffre2.resize((35,35))
			chiffre2 = ImageOps.invert(chiffre2)
			image.paste(chiffre2, (27,0))
			chiffre3 = Image.open('/home/pi/Google_Assistant/src/images/clock/' + str(minute[0]) + '.jpg')
			chiffre3 = chiffre3.resize((35,35))
			chiffre3 = ImageOps.invert(chiffre3)
			image.paste(chiffre3, (66,0))
			chiffre4 = Image.open('/home/pi/Google_Assistant/src/images/clock/' + str(minute[1]) + '.jpg')
			chiffre4 = chiffre4.resize((35,35))
			chiffre4 = ImageOps.invert(chiffre4)
			image.paste(chiffre4, (97,0))
			if int(time.strftime("%S")) % 2 == 0 :
				draw.line((62,12,64,12), fill=255)
				draw.line((62,14,64,14), fill=255)
				draw.line((62,18,64,18), fill=255)
				draw.line((62,20,64,20), fill=255)
			draw.line((0,34,54,34), fill=255)
			draw.line((0,36,54,36), fill=255)
			draw.line((0,38,54,38), fill=255)
			draw.line((0,40,54,40), fill=255)
			draw.text((58,32), time.strftime("%S"), font=font, fill=225)
			draw.line((72,34,128,34), fill=255)
			draw.line((72,36,128,36), fill=255)
			draw.line((72,38,128,38), fill=255)
			draw.line((72,40,128,40), fill=255)
			if time.strftime("%S") == '00' :
				day = time.strftime("%a")
				mon = time.strftime("%b")
				if time.strftime("%B") == "December" :
					mon = 'Dec'
				listal = []
				alfortom = False
				i = len(self.act_cron)-1
				while i > -1:
					if 'Myassistant.alarm_dring(self)#cantdel' == self.act_cron[i][3]:
						listal.append(self.act_cron[i])
					i = i - 1
				if int(time.strftime("%H")) > 17:
					ood = Myassistant.ad_day(time.strftime("%A"),1)
					for li in listal:
						if str(ood) == li[0] or '-' == li[0]:
							if int(li[1]) < 12:
								alfortom = True
				for li in listal:
					if time.strftime("%A") == li[0] or '-' == li[0]:
						if int(time.strftime("%H")) < int(li[1]):
							alfortom = True
						elif int(time.strftime("%H")) == int(li[1]):
							if int(time.strftime("%M")) < int(li[2]):
								alfortom = True
			draw.text(((128 - (len(day + time.strftime(" %d ") + mon + time.strftime(" %Y")) * 6)) / 2,42),day + time.strftime(" %d ") + mon + time.strftime(" %Y"), font=font, fill=225)
			if settings.get("Messages"):
				goder = True
				try:
					for actmess in settings.get("Messages configuration"):
						if eval(actmess[0]):
							goder = False
							if len(actmess[1]) * 6 > 128 :
								if direc == 0 :
									if len(actmess[1]) * 6 + x > 128 :
										x = x - 4
									else :
										direc = 1
								else :
									x = x + 4
									if x > 3 :
										direc = 0
								draw.rectangle((0, 53, 127, 63), outline=0, fill=0)
								draw.text((x,53),actmess[1], font=font, fill=225)
							else:
								draw.rectangle((0, 53, 127, 63), outline=0, fill=0)
								draw.text(((128 - (len(actmess[1]) * 6)) / 2,53),actmess[1], font=font, fill=225)
				except:
					print('Failed print message')
					draw.rectangle((0, 53, 127, 63), outline=0, fill=0)
					resources = 'CPU:'+str(psutil.cpu_percent())+'% MEM:'+str(psutil.virtual_memory().percent)+'%'
					draw.text(((128 - (len(resources) * 6)) / 2,53),resources, font=font, fill=225)
				if goder:
					draw.rectangle((0, 53, 127, 63), outline=0, fill=0)
					resources = 'CPU:'+str(psutil.cpu_percent())+'% MEM:'+str(psutil.virtual_memory().percent)+'%'
					draw.text(((128 - (len(resources) * 6)) / 2,53),resources, font=font, fill=225)
			else:
				draw.rectangle((0, 53, 127, 63), outline=0, fill=0)
				resources = 'CPU:'+str(psutil.cpu_percent())+'% MEM:'+str(psutil.virtual_memory().percent)+'%'
				draw.text(((128 - (len(resources) * 6)) / 2,53),resources, font=font, fill=225)
			if self.al:
				if alblink < 3:
					alarm = Image.open('/home/pi/Google_Assistant/src/images/clock/alarme.jpg')
					alarm = alarm.resize((10,9))
					alarm = ImageOps.invert(alarm)
					image.paste(alarm, (59,0))
					alblink = alblink + 1
				else:
					if alblink > 4:
						alblink = 0
					else:
						alblink = alblink + 1
			elif alfortom:
				alarm = Image.open('/home/pi/Google_Assistant/src/images/clock/alarme.jpg')
				alarm = alarm.resize((10,9))
				alarm = ImageOps.invert(alarm)
				image.paste(alarm, (59,0))
			if mon == 'Dec':
				if not len(decemb) == 0:
					i = len(decemb)-1
					while i > -1:
						if decemb[i][1]+1 > 63:
							del decemb[i]
						else:
							if decemb[i][0] % 2 == 0:
								decemb[i] = [decemb[i][0]+1,decemb[i][1]+1]
							else:
								decemb[i] = [decemb[i][0]-1,decemb[i][1]+1]
						i = i - 1
					i = random.randint(0,5)
					while i > 0:
						decemb.append([random.randint(0,127),0])
						i = i - 1
				else:
					decemb = []
					i = random.randint(64,320)
					while i > 0:
						decemb.append([random.randint(0,127),random.randint(0,63)])
						i = i - 1
				for done_i in decemb:
					draw.point((done_i[0],done_i[1]),fill=255)
			disp.image(image)
			Myassistant.refrech_error()
			buton = 20000
			while buton > 0 and self.affichage == 'heure total':
				if not len(self.buton) == 0:
					self.veil = 0
					if self.al == True:
						del self.buton[0]
						self.al = False
						os.system('sudo killall mpg123')
					elif self.buton[0] == 0 or self.buton[0] == 1:
						del self.buton[0]
						if settings.get("Alarm"):
							Myassistant.alarm_action(self)
							disp.clear()
							Myassistant.refrech_error()
							time.sleep(0.3)
							while not len(self.buton) == 0:
								del self.buton[0]
							listal = []
							alfortom = False
							i = len(self.act_cron)-1
							while i > -1:
								if 'Myassistant.alarm_dring(self)#cantdel' == self.act_cron[i][3]:
									listal.append(self.act_cron[i])
								i = i - 1
							if int(time.strftime("%H")) > 17:
								ood = Myassistant.ad_day(time.strftime("%A"),1)
								for li in listal:
									if str(ood) == li[0] or '-' == li[0]:
										if int(li[1]) < 12:
											alfortom = True
							for li in listal:
								if time.strftime("%A") == li[0] or '-' == li[0]:
									if int(time.strftime("%H")) < int(li[1]):
										alfortom = True
									elif int(time.strftime("%H")) == int(li[1]):
										if int(time.strftime("%M")) < int(li[2]):
											alfortom = True
					elif self.buton[0] == 2:
						del self.buton[0]
						Myassistant.execute_next(self,'right')
					elif self.buton[0] == 3:
						del self.buton[0]
						Myassistant.execute_next(self,'left')
					self.veil = 0
					if not len(self.buton) == 0:
						buton = 5
					else:
						buton = 0
				buton = buton - 1

	def aff_meteo(self):
		self.affichage = 'météo'
		if Myassistant.have_network(time.strftime("%H"),time.strftime("%M")):
			try:
				fio.get_forecast(latitude=coutry[1],longitude=coutry[0])
			except:
				print('Failed to get forecast')
		afmete = 'currently'
		direc = 0
		x = 4
		if fio.has_currently() is True:
			currently = FIOCurrently.FIOCurrently(fio)
		else:
			self.veil = 0
			threading.Timer(0, Myassistant.aff_heure,[self]).start()
			print('Failed : "weather"')
		if fio.has_daily() is True:
			daily = FIODaily.FIODaily(fio)
		else:
			self.veil = 0
			threading.Timer(0, Myassistant.aff_heure,[self]).start()
			print('Failed : "weather"')
		if daily.days() > 0:
			daysel = 1
		else:
			daysel = 0
		while self.affichage == 'météo':
			image = Image.new('1', (disp.width,disp.height))
			draw = ImageDraw.Draw(image)
			buton = 20000
			if time.strftime("%S") == '00' :
				if Myassistant.have_network(time.strftime("%H"),time.strftime("%M")):
					try:
						fio.get_forecast(latitude=coutry[1],longitude=coutry[0])
					except:
						print('Failed to get forecast')
				if fio.has_currently() is True:
					currently = FIOCurrently.FIOCurrently(fio)
				else:
					self.veil = 0
					threading.Timer(0, Myassistant.aff_heure,[self]).start()
					print('Failed : "weather"')
				if fio.has_daily() is True:
					daily = FIODaily.FIODaily(fio)
				else:
					self.veil = 0
					threading.Timer(0, Myassistant.aff_heure,[self]).start()
					print('Failed : "weather"')
			if afmete == 'currently':
				if currently.icon == 'cloudy':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Cloud.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'hail' or currently.icon == 'sleet':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Hail.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'fog':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Haze.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'clear-night':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Moon.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'partly-cloudy-night':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Partly Moon.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'partly-cloudy-day':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Partly Sunny.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'rain':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Rain.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'snow':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Snow.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'thunderstorm':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Storm.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'clear-day':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Sun.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'tornado':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Tornado.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif currently.icon == 'wind':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Wind.jpg')
					icon = icon.resize((34,35))
					icon = ImageOps.invert(icon)
					image.paste(icon,(0,12))
					draw.line((2,26,11,26), fill=255)
				temp = Image.open('/home/pi/Google_Assistant/src/images/weather/temperature.jpg')
				temp = temp.resize((18,15))
				temp = ImageOps.invert(temp)
				temp = temp.crop(temp.getbbox())
				image.paste(temp,(38,14))
				draw.rectangle((39, 25, 42, 27), outline=255, fill=255)
				humidity = Image.open('/home/pi/Google_Assistant/src/images/weather/humidity.jpg')
				humidity = humidity.resize((14,14))
				humidity = ImageOps.invert(humidity)
				humidity = humidity.crop(humidity.getbbox())
				image.paste(humidity,(37,33))
				wind = Image.new('1', (11,11))
				ImageDraw.Draw(wind).polygon([(5,0),(0,5),(4,5),(4,10),(6,10),(6,5),(10,5)],fill=255,outline=255)
				try:
					wind = wind.rotate(angle=round(currently.windBearing),expand=True,fillcolor=0)
				except AttributeError:
					pass
				image.paste(wind,(round(78.5-(wind.size[0]/2)),round(21.5-(wind.size[1]/2))))
				precip = Image.open('/home/pi/Google_Assistant/src/images/weather/pluviometer.jpg')
				precip = precip.resize((15,15))
				precip = ImageOps.invert(precip)
				image.paste(precip,(71,32))
				draw.line((78,45,78,46), fill=0)
				draw.line((73,32,83,32), fill=0)
				draw.text((47,16),str(round(currently.temperature))+'°C', font=font, fill=225)
				draw.text((47,34),str(round(currently.humidity*100))+'%', font=font, fill=225)
				if currently.windSpeed < 10:
					if '.0' in str(round(currently.windSpeed,1)):
						draw.text((87,16),str(round(currently.windSpeed,1)).replace('.0','')+'km/h', font=font, fill=225)
					else:
						draw.text((87,16),str(round(currently.windSpeed,1))+'km/h', font=font, fill=225)
				else:
					draw.text((87,16),str(round(currently.windSpeed))+'km/h', font=font, fill=225)
				if currently.precipIntensity < 10:
					if '.0' in str(round(currently.precipIntensity,1)):
						draw.text((87,34),str(round(currently.precipIntensity,1)).replace('.0','')+'mm/h', font=font, fill=225)
					else:
						draw.text((87,34),str(round(currently.precipIntensity,1))+'mm/h', font=font, fill=225)
				else:
					draw.text((87,34),str(round(currently.precipIntensity))+'mm/h', font=font, fill=225)
				if int(time.strftime("%S")) % 2 == 0 :
					time_day = time.strftime('%a %d %b %Y %H:%M')
				else:
					time_day = time.strftime('%a %d %b %Y %H %M')
				draw.text(((128 - (len(time_day) * 6)) / 2,0),time_day, font=font, fill=225)
				if len(currently.summary) * 6 > 128 :
					if direc == 0 :
						if len(currently.summary) * 6 + x > 128 :
							x = x - 4
						else :
							direc = 1
					else :
						x = x + 4
						if x > 3 :
							direc = 0
					draw.text((x,50),currently.summary, font=font, fill=225)
				else:
					draw.text(((128 - (len(currently.summary) * 6)) / 2,50),currently.summary, font=font, fill=225)
			elif afmete == 'dailys':
				for day in range(0, daily.days()):
					if day > -1 and day < 6:
						fday = daily.get_day(day)
						if fday['icon'] == 'cloudy':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Cloud.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'hail' or fday['icon'] == 'sleet':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Hail.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'fog':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Haze.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'clear-night':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Moon.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'partly-cloudy-night':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Partly Moon.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'partly-cloudy-day':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Partly Sunny.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'rain':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Rain.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'snow':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Snow.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'thunderstorm':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Storm.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'clear-day':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Sun.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'tornado':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Tornado.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
						elif fday['icon'] == 'wind':
							icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Wind.jpg').resize((50,50))
							icon = ImageOps.invert(icon)
							icon = icon.crop(icon.getbbox())
							icon = icon.resize((27,17))
							ImageDraw.Draw(icon).rectangle((0, 7, 21, 7), outline=0, fill=0)
						if day == 0:
							if daysel == 0:
								draw.rectangle((6, 0, 36, 20), outline=255, fill=0)
							image.paste(icon,(8,2))
							time_day = 'Ytd'
							draw.text((22 - ((len(time_day) * 6) / 2),20),time_day, font=font, fill=225)
						elif day == 1:
							if daysel == 1:
								draw.rectangle((48, 0, 78, 20), outline=255, fill=0)
							image.paste(icon,(50,2))
							time_day = 'Tdy'
							draw.text((64 - ((len(time_day) * 6) / 2),20),time_day, font=font, fill=225)
						elif day == 2:
							if daysel == 2:
								draw.rectangle((90, 0, 120, 20), outline=255, fill=0)
							image.paste(icon,(92,2))
							time_day = 'Tmw'
							draw.text((106 - ((len(time_day) * 6) / 2),20),time_day, font=font, fill=225)
						elif day == 3:
							if daysel == 3:
								draw.rectangle((6, 32, 36, 52), outline=255, fill=0)
							image.paste(icon,(8,34))
							time_day = datetime.datetime.utcfromtimestamp(int(fday['time'])).strftime('%a')
							draw.text((22 - ((len(time_day) * 6) / 2),52),time_day, font=font, fill=225)
						elif day == 4:
							if daysel == 4:
								draw.rectangle((48, 32, 78, 52), outline=255, fill=0)
							image.paste(icon,(50,34))
							time_day = datetime.datetime.utcfromtimestamp(int(fday['time'])).strftime('%a')
							draw.text((64 - ((len(time_day) * 6) / 2),52),time_day, font=font, fill=225)
						elif day == 5:
							if daysel == 5:
								draw.rectangle((90, 32, 120, 52), outline=255, fill=0)
							image.paste(icon,(92,34))
							time_day = datetime.datetime.utcfromtimestamp(int(fday['time'])).strftime('%a')
							draw.text((106 - ((len(time_day) * 6) / 2),52),time_day, font=font, fill=225)
			elif afmete == 'daily':
				day = daysel
				fday = daily.get_day(day)
				if fday['icon'] == 'cloudy':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Cloud.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'hail' or fday['icon'] == 'sleet':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Hail.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'fog':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Haze.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'clear-night':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Moon.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'partly-cloudy-night':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Partly Moon.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'partly-cloudy-day':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Partly Sunny.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'rain':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Rain.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'snow':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Snow.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'thunderstorm':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Storm.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'clear-day':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Sun.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'tornado':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Tornado.jpg')
					icon = icon.resize((50,50))
					icon = ImageOps.invert(icon)
					image.paste(icon,(-7,5))
				elif fday['icon'] == 'wind':
					icon = Image.open('/home/pi/Google_Assistant/src/images/weather/Wind.jpg')
					icon = icon.resize((34,35))
					icon = ImageOps.invert(icon)
					image.paste(icon,(0,12))
					draw.line((2,26,11,26), fill=255)
				tmin = Image.open('/home/pi/Google_Assistant/src/images/weather/tmin.jpg')
				tmin = tmin.resize((18,15))
				tmin = ImageOps.invert(tmin)
				tmin = tmin.crop(tmin.getbbox())
				image.paste(tmin,(38,14))
				draw.rectangle((39, 25, 42, 27), outline=255, fill=255)
				tmax = Image.open('/home/pi/Google_Assistant/src/images/weather/tmax.jpg')
				tmax = tmax.resize((18,15))
				tmax = ImageOps.invert(tmax)
				tmax = tmax.crop(tmax.getbbox())
				image.paste(tmax,(38,32))
				draw.rectangle((39, 43, 42, 45), outline=255, fill=255)
				wind = Image.new('1', (11,11))
				ImageDraw.Draw(wind).polygon([(5,0),(0,5),(4,5),(4,10),(6,10),(6,5),(10,5)],fill=255,outline=255)
				try:
					wind = wind.rotate(angle=round(fday['windBearing']),expand=True,fillcolor=0)
				except AttributeError:
					pass
				image.paste(wind,(round(78.5-(wind.size[0]/2)),round(21.5-(wind.size[1]/2))))
				precip = Image.open('/home/pi/Google_Assistant/src/images/weather/pluviometer.jpg')
				precip = precip.resize((15,15))
				precip = ImageOps.invert(precip)
				image.paste(precip,(71,32))
				draw.line((78,45,78,46), fill=0)
				draw.line((73,32,83,32), fill=0)
				draw.text((47,16),str(round(fday['temperatureMin']))+'°C', font=font, fill=225)
				draw.text((47,34),str(round(fday['temperatureMax']))+'°C', font=font, fill=225)
				if fday['windSpeed'] < 10:
					if '.0' in str(round(fday['windSpeed'],1)):
						draw.text((87,16),str(round(fday['windSpeed'],1)).replace('.0','')+'km/h', font=font, fill=225)
					else:
						draw.text((87,16),str(round(fday['windSpeed'],1))+'km/h', font=font, fill=225)
				else:
					draw.text((87,16),str(round(fday['windSpeed']))+'km/h', font=font, fill=225)
				if fday['precipIntensity'] < 10:
					if '.0' in str(round(fday['precipIntensity'],1)):
						draw.text((87,34),str(round(fday['precipIntensity'],1)).replace('.0','')+'mm/h', font=font, fill=225)
					else:
						draw.text((87,34),str(round(fday['precipIntensity'],1))+'mm/h', font=font, fill=225)
				else:
					draw.text((87,34),str(round(fday['precipIntensity']))+'mm/h', font=font, fill=225)
				if day == 0:
					time_day = 'Yesterday'
				elif day == 1:
					time_day = 'Today'
				elif day == 2:
					time_day = 'Tomorrow'
				else:
					time_day = datetime.datetime.utcfromtimestamp(int(fday['time'])).strftime('%a %d %b %Y')
				draw.text(((128 - (len(time_day) * 6)) / 2,0),time_day, font=font, fill=225)
				if len(fday['summary']) * 6 > 128 :
					if direc == 0 :
						if len(fday['summary']) * 6 + x > 128 :
							x = x - 4
						else :
							direc = 1
					else :
						x = x + 4
						if x > 3 :
							direc = 0
					draw.text((x,50),fday['summary'], font=font, fill=225)
				else:
					draw.text(((128 - (len(fday['summary']) * 6)) / 2,50),fday['summary'], font=font, fill=225)
			disp.image(image)
			Myassistant.refrech_error()
			while self.affichage == 'météo' and buton > 0:
				if not len(self.buton) == 0:
					direc = 0
					x = 4
					self.veil = 0
					if self.buton[0] == 0:
						del self.buton[0]
						if afmete == 'currently':
							afmete = 'dailys'
						elif afmete == 'dailys':
							afmete = 'currently'
						elif afmete == 'daily':
							afmete = 'currently'
					elif self.buton[0] == 1:
						del self.buton[0]
						if afmete == 'currently':
							afmete = 'dailys'
						elif afmete == 'dailys':
							afmete = 'daily'
						elif afmete == 'daily':
							afmete = 'dailys'
					elif self.buton[0] == 2:
						del self.buton[0]
						if afmete == 'currently':
							Myassistant.execute_next(self,'right')
						elif afmete == 'dailys':
							daysel = daysel+1
							if daysel+1 > daily.days() or daysel > 5:
								daysel = 0
						elif afmete == 'daily':
							daysel = daysel+1
							if daysel+1 > daily.days() or daysel > 5:
								daysel = 0
					elif self.buton[0] == 3:
						del self.buton[0]
						if afmete == 'currently':
							Myassistant.execute_next(self,'left')
						elif afmete == 'dailys':
							daysel = daysel-1
							if daysel < 0:
								if daily.days()+1 > 6:
									daysel = 5
								else:
									daysel = daily.days()
						elif afmete == 'daily':
							daysel = daysel-1
							if daysel < 0:
								if daily.days()+1 > 6:
									daysel = 5
								else:
									daysel = daily.days()
					self.veil = 0
					if not len(self.buton) == 0:
						buton = 20000
					else:
						buton = 0
				buton = buton - 1

	def aff_music(self):
		self.affichage = 'music'
		mop = 0
		mux = random.randint(0,128)
		while self.affichage == 'music':
			image = Image.new('1', (disp.width,disp.height))
			draw = ImageDraw.Draw(image)
			draw.rectangle((0, 0, 127, 34), outline=255, fill=0)
			draw.rectangle((0, 37, 127, 63), outline=255, fill=0)
			if mop == 1:
				draw.polygon([(90,8), (95,8), (105,2),(105,20),(95,14),(90,14)], outline=255, fill=255)
			else :
				draw.polygon([(90,8), (95,8), (105,2),(105,20),(95,14),(90,14)], outline=255, fill=0)
			if mop == 2:
				draw.rectangle((107, 2, 125, 20), outline=255, fill=255)
				draw.text((111,5),'Zz' , font=font, fill=0)
			else :
				draw.rectangle((107, 2, 125, 20), outline=255, fill=0)
				draw.text((111,5),'Zz' , font=font, fill=255)
			t = 14
			lx = 2
			ly = 20
			if not vlc.is_pause():
				mux = mux - 4
				if mux < 0-(len(vlc.get_title())*6) :
					mux = 128
				draw.text((mux,22),vlc.get_title() , font=font, fill=225)
				if mop == 4:
					draw.rectangle((41, 40, 46, 60), outline=255, fill=255)
					draw.rectangle((51, 40, 56, 60), outline=255, fill=255)
				else:
					draw.rectangle((41, 40, 46, 60), outline=255, fill=0)
					draw.rectangle((51, 40, 56, 60), outline=255, fill=0)
				while t > 0 :
					s = random.randint(1,10)
					ly = 20
					while s > 0 :
						draw.rectangle((lx,ly,lx + 4,ly), outline=255, fill=255)
						ly = ly - 2
						s = s - 1
					lx = lx + 6
					t = t - 1
			else :
				if vlc.is_vlc_playing():
					mux = mux - 4
					if mux < 0-(len(vlc.get_title())*6) :
						mux = 128
					draw.text((mux,22),vlc.get_title() , font=font, fill=225)
				if mop == 4:
					draw.polygon([(44,40), (54,50), (44,60)], outline=255, fill=255)
				else:
					draw.polygon([(44,40), (54,50), (44,60)], outline=255, fill=0)
				while t > 0 :
					draw.rectangle((lx,ly,lx + 4,ly), outline=255, fill=255)
					lx = lx + 6
					t = t - 1
			if mop == 3:
				draw.rectangle((3, 40, 8, 60), outline=255, fill=255)
				draw.polygon([(19,40), (9,50), (19,60)], outline=255, fill=255)
				draw.polygon([(30,40), (20,50), (30,60)], outline=255, fill=255)
			else:
				draw.rectangle((3, 40, 8, 60), outline=255, fill=0)
				draw.polygon([(19,40), (9,50), (19,60)], outline=255, fill=0)
				draw.polygon([(30,40), (20,50), (30,60)], outline=255, fill=0)
			if mop == 5:
				draw.polygon([(67,40), (77,50), (67,60)], outline=255, fill=255)
				draw.polygon([(78,40), (88,50), (78,60)], outline=255, fill=255)
				draw.rectangle((89, 40, 94, 60), outline=255, fill=255)
			else:
				draw.polygon([(67,40), (77,50), (67,60)], outline=255, fill=0)
				draw.polygon([(78,40), (88,50), (78,60)], outline=255, fill=0)
				draw.rectangle((89, 40, 94, 60), outline=255, fill=0)
			if mop == 6:
				draw.rectangle((104, 40, 124, 60), outline=255, fill=255)
			else:
				draw.rectangle((104, 40, 124, 60), outline=255, fill=0)
			disp.image(image)
			Myassistant.refrech_error()
			buton = 20000
			while self.affichage == 'music' and buton > 0:
				if not len(self.buton) == 0:
					self.veil = 0
					if self.buton[0] == 0:
						del self.buton[0]
						if mop == 0:
							mop = 4
						else:
							mop = 0
					elif self.buton[0] == 1:
						del self.buton[0]
						if mop == 0:
							mop = 4
						else:
							if mop == 1:
								vol = Myassistant.volume_get()
								Myassistant.volume_set(int(Myassistant.select_cursor(self,100,0,5,vol,'%','volume')))
							elif mop == 2:
								if self.act_cron[0] == ['X','XX','XX','vlc.stop_vlc()#cantdel']:
									slt = Myassistant.select_time(self,'--', '--', '-', 'sleep time',True)
								else:
									slt = Myassistant.select_time(self,self.act_cron[0][1], self.act_cron[0][2], self.act_cron[0][0], 'sleep time',True)
								if slt[0] == '--' or slt[1] == '--':
									self.act_cron[0] = ['X','XX','XX','vlc.stop_vlc()#cantdel']
									self.var_save["Music stop"] = str('X,XX,XX')
								else:
									self.act_cron[0] = [slt[2],slt[0],slt[1],'vlc.stop_vlc()#cantdel']
									self.var_save["Music stop"] = str(slt[2] + ',' + slt[0] + ',' + slt[1])
								Myassistant.save_var_in_file(self)
							elif mop == 3:
								vlc.previous_vlc()
							elif mop == 4:
								if vlc.is_vlc_playing():
									if vlc.is_pause():
										vlc.resume_vlc()
									else:
										vlc.pause_vlc()
								elif not vlc.is_vlc_playing():
									if Myassistant.have_network(time.strftime("%H"),time.strftime("%M")):
										mscel = Myassistant.select_list(self,[['Radios','radios'],['File','file'],['Exit','exit']],'music')
										if mscel == 'radios':
											radiona = []
											for hgj in settings.get("Radios"):
												radiona.append(hgj)
											radsel = Myassistant.select_list(self,radiona,'Radios')
											if not radsel == None:
												if Myassistant.have_network(time.strftime("%H"),time.strftime("%M")):
													vlc.play_audio_file(radsel)
										elif mscel == 'file':
											j = Myassistant.select_path(self,settings.get("Path to your music"),True)
											if not j == None:
												disp.clear()
												Myassistant.refrech_error()
												if os.path.isdir(j):
													vlc.play_audio_folder(j)
												else:
													vlc.play_audio_file(j)
												time.sleep(0.2)
												while not len(self.buton) == 0:
													del self.buton[0]
									else:
										j = Myassistant.select_path(self,settings.get("Path to your music"),True)
										if not j == None:
											disp.clear()
											Myassistant.refrech_error()
											if os.path.isdir(j):
												vlc.play_audio_folder(j)
											else:
												vlc.play_audio_file(j)
											time.sleep(0.2)
											while not len(self.buton) == 0:
												del self.buton[0]
								else:
									vlc.resume_vlc()
							elif mop == 5:
								vlc.next_vlc()
							elif mop == 6:
								vlc.stop_vlc()
					elif self.buton[0] == 2:
						del self.buton[0]
						if mop == 0:
							Myassistant.execute_next(self,'right')
						elif not mop + 1 > 6:
							mop = mop + 1
						else:
							mop = 1
					elif self.buton[0] == 3:
						del self.buton[0]
						if mop == 0:
							Myassistant.execute_next(self,'left')
						elif not mop - 1 < 1:
							mop = mop - 1
						else:
							mop = 6
					self.veil = 0
					if not len(self.buton) == 0:
						buton = 5
					else:
						buton = 0
				buton = buton - 1

	def aff_led_strip(self):
		self.affichage = 'led strip'
		try:
			ifwantreload = 0
			cont = True
			name = 'All'
			name_wifi_led = []
			ip_wifi_led=[]
			listwifi={}
			led = flux_led.__main__
			for wifi_led in settings.get('Led strips names'):
				listwifi[str(wifi_led[0])]=led.WifiLedBulb(wifi_led[1],timeout=1)
				name_wifi_led.append(wifi_led[0])
				ip_wifi_led.append(wifi_led[1])
			colorlist = []
			coloraction = []
			for color in settings.get('Custom colors'):
				colorlist.append(color[0])
				coloraction.append(color[1])
			selectlist = round((len(colorlist) - 1) / 2)
			selection = [False, 10]
			while cont and self.affichage == 'led strip' :
				image = Image.new('1', (disp.width,disp.height))
				draw = ImageDraw.Draw(image)
				if name == 'All':
					r = 0
					g = 0
					b = 0
					w = 0
					ison = False
					brightnes = 0
					i = 0
					for adress in listwifi:
						wifiled = listwifi[adress]
						#print('e')
						wifiled.refreshState()
						#print('a')
						y = wifiled.getRgbw()
						r = r + y[0]
						g = g + y[1]
						b = b + y[2]
						w = w + y[3]
						if wifiled.is_on:
							ison = True
						brightnes = brightnes + wifiled.brightness
						i = i + 1
					r = round(r/i)
					g = round(g/i)
					b = round(b/i)
					w = round(w/i)
					brightnes = round(brightnes/i)
				else:
					wifiled = listwifi[name]
					wifiled.refreshState()
					y = wifiled.getRgbw()
					r = y[0]
					g = y[1]
					b = y[2]
					w = y[3]
					ison = wifiled.is_on
					brightnes = wifiled.brightness
				brightnessim = Image.open('/home/pi/Google_Assistant/src/images/led_strip/brightness.jpg')
				brightnessim = brightnessim.resize((17,17))
				brightnessim = ImageOps.invert(brightnessim)
				image.paste(brightnessim, (28,12))
				draw.text(((127 - (len(name) * 6)) / 2,0), name, font=font, fill=225)
				if ison:
					if selection[1] == 0:
						if selection[0]:
							draw.rectangle((0, 15, (len(str('on')) * 6) + 2, 25), outline=255, fill=255)
							draw.text((2,15), 'on', font=font, fill=0)
						else:
							draw.rectangle((0, 15, (len(str('on')) * 6) + 2, 25), outline=255, fill=0)
							draw.text((2,15), 'on', font=font, fill=225)
					else:
						draw.text((2,15), 'on', font=font, fill=225)
				else:
					if selection[1] == 0:
						if selection[0]:
							draw.rectangle((0, 15, (len(str('off')) * 6) + 2, 25), outline=255, fill=255)
							draw.text((2,15), 'off', font=font, fill=0)
						else:
							draw.rectangle((0, 15, (len(str('off')) * 6) + 2, 25), outline=255, fill=0)
							draw.text((2,15), 'off', font=font, fill=225)
					else:
						draw.text((2,15), 'off', font=font, fill=225)
				if selection[1] == 1:
					if selection[0]:
						draw.rectangle((44, 15, (len(str(brightnes)) * 6) + 46, 25), outline=255, fill=255)
						draw.text((46,15), str(brightnes), font=font, fill=0)
					else:
						draw.rectangle((44, 15, (len(str(brightnes)) * 6) + 46, 25), outline=255, fill=0)
						draw.text((46,15), str(brightnes), font=font, fill=225)
				else:
					draw.text((46,15), str(brightnes), font=font, fill=225)
				if selection[1] == 2:
					draw.rectangle((74, 15, 88, 25), outline=255, fill=0)
				draw.line((76,17,86,17), fill=255)
				draw.line((76,19,86,19), fill=255)
				draw.line((76,21,86,21), fill=255)
				draw.line((76,23,86,23), fill=255)
				if selection[1] == 3:
					draw.rectangle((99, 15, (len(str('+')) * 6) + 101, 25), outline=255, fill=0)
				draw.text((101,15), '+', font=font, fill=225)
				if selection[1] == 4:
					draw.rectangle((117, 15, 127, 25), outline=255, fill=0)
				alar = Image.open('/home/pi/Google_Assistant/src/images/led_strip/alarme.jpg')
				alar = alar.resize((7,7))
				alar = ImageOps.invert(alar)
				image.paste(alar, (119,17))
				draw.line((122,21,122,19), fill=255)
				draw.line((122,21,123,21), fill=255)
				xcenter = (127 - (len(colorlist[selectlist]) * 6)) / 2
				if selection[1] == 5:
					draw.rectangle((0, 29, 127, 48), outline=255, fill=0)
					if selection[0]:
						draw.rectangle((xcenter - 4, 31, (len(colorlist[selectlist]) * 6) + xcenter + 3, 46), outline=255, fill=0)
				i = selectlist - 1
				while i > -1:
					xcenter = xcenter - (12 + (len(colorlist[i]) * 6))
					i = i - 1
				draw.text((xcenter,33), "  ".join(colorlist), font=font, fill=225)
				if selection[1] == 6:
					if selection[0]:
						draw.rectangle((8, 53, (len(str(r)) * 6) + 11, 63), outline=255, fill=255)
						draw.text((10,53), str(r), font=font, fill=0)
					else:
						draw.rectangle((8, 53, (len(str(r)) * 6) + 11, 63), outline=255, fill=0)
						draw.text((10,53), str(r), font=font, fill=225)
					draw.text((0,53), 'R', font=font, fill=225)
				else:
					draw.text((0,53), 'R:', font=font, fill=225)
					draw.text((10,53), str(r), font=font, fill=225)
				if selection[1] == 7:
					if selection[0]:
						draw.rectangle((40, 53, (len(str(g)) * 6) + 43, 63), outline=255, fill=255)
						draw.text((42,53), str(g), font=font, fill=0)
					else:
						draw.rectangle((40, 53, (len(str(g)) * 6) + 43, 63), outline=255, fill=0)
						draw.text((42,53), str(g), font=font, fill=225)
					draw.text((32,53), 'G', font=font, fill=225)
				else:
					draw.text((32,53), 'G:', font=font, fill=225)
					draw.text((42,53), str(g), font=font, fill=225)
				if selection[1] == 8:
					if selection[0]:
						draw.rectangle((72, 53, (len(str(b)) * 6) + 75, 63), outline=255, fill=255)
						draw.text((74,53), str(b), font=font, fill=0)
					else:
						draw.rectangle((72, 53, (len(str(b)) * 6) + 75, 63), outline=255, fill=0)
						draw.text((74,53), str(b), font=font, fill=225)
					draw.text((64,53), 'B', font=font, fill=225)
				else:
					draw.text((64,53), 'B:', font=font, fill=225)
					draw.text((74,53), str(b), font=font, fill=225)
				if selection[1] == 9:
					if selection[0]:
						draw.rectangle((104, 53, (len(str(w)) * 6) + 107, 63), outline=255, fill=255)
						draw.text((106,53), str(w), font=font, fill=0)
					else:
						draw.rectangle((104, 53, (len(str(w)) * 6) + 107, 63), outline=255, fill=0)
						draw.text((106,53), str(w), font=font, fill=225)
					draw.text((96,53), 'W', font=font, fill=225)
				else:
					draw.text((96,53), 'W:', font=font, fill=225)
					draw.text((106,53), str(w), font=font, fill=225)
				disp.image(image)
				Myassistant.refrech_error()
				buton = 20000
				while self.affichage == 'led strip' and buton > 0:
					#print('r')
					if not len(self.buton) == 0:
						self.veil = 0
						if self.buton[0] == 0 :
							del self.buton[0]
							if selection[1] == 10:
								selection[1] = 0
								for adresr in listwifi:
									wifiled = listwifi[adresr]
									if not wifiled.isOn():
										wifiled.turnOn()
							else:
								selection[1] = 10
						elif self.buton[0] == 1 :
							del self.buton[0]
							if selection[1] == 2:
								ledsearchaff = [['All','All']]
								for sdna in name_wifi_led:
									ledsearchaff.append([str(sdna),str(sdna)])
								name = Myassistant.select_list(self,ledsearchaff,'select led strip')
								if name == None:
									name == 'All'
							elif selection[1] == 3:
								ffgddsj = Myassistant.select_list(self,[['Colors','color'],['Preset pattern','pattern'],['Exit','exit']],'choice')
								if ffgddsj == 'pattern':
									fgcolorpatname = ['seven color cross fade','red gradual change','green gradual change','blue gradual change','yellow gradual change','cyan gradual change','purple gradual change','white gradual change','red green cross fade','red blue cross fade','green blue cross fade','seven color strobe flash','red strobe flash','green strobe flash','blue strobe flash','yellow strobe flash','cyan strobe flash','purple strobe flash','white strobe flash','seven color jumping']
									fgcolorpat = ['setPresetPattern(0x25,100)','setPresetPattern(0x26,100)','setPresetPattern(0x27,100)','setPresetPattern(0x28,100)','setPresetPattern(0x29,100)','setPresetPattern(0x2a,100)','setPresetPattern(0x2b,100)','setPresetPattern(0x2c,100)','setPresetPattern(0x2d,100)','setPresetPattern(0x2e,100)','setPresetPattern(0x2f,100)','setPresetPattern(0x30,100)','setPresetPattern(0x31,100)','setPresetPattern(0x32,100)','setPresetPattern(0x33,100)','setPresetPattern(0x34,100)','setPresetPattern(0x35,100)','setPresetPattern(0x36,100)','setPresetPattern(0x37,100)','setPresetPattern(0x38,100)']
									collen = 0
									mixcolornamepat = []
									while collen < len(fgcolorpatname):
										mixcolornamepat.append([str(fgcolorpatname[collen]),str(fgcolorpat[collen])])
										collen = collen + 1
									presety = Myassistant.select_list(self,mixcolornamepat,'preset pattern')
									if not presety == None:
										if name == 'All':
											for adresr in listwifi:
												wifiled = listwifi[adresr]
												eval('wifiled.' + str(presety))
										else:
											eval('wifiled.' + str(presety))
										speed = Myassistant.select_cursor(self,100,0,5,100,"",'speed')
										presety = str(presety).replace(',100)',','+str(speed)+')')
										if name == 'All':
											for adresr in listwifi:
												wifiled = listwifi[adresr]
												eval('wifiled.' + str(presety))
										else:
											eval('wifiled.' + str(presety))
								elif ffgddsj == 'color':
									jgiush = []
									responscoled = flux_led.utils.get_color_names_list()
									for tey in responscoled:
										jgiush.append([tey,tey])
									dflfd = Myassistant.select_search_list(self,jgiush)
									if not dflfd == None:
										resultintero = flux_led.utils.color_object_to_tuple(dflfd)
										if name == 'All':
											for adresr in listwifi:
												wifiled = listwifi[adresr]
												if wifiled.brightness+10 > 255 :
													wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
												else:
													wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
										else:
											if brightnes+10 > 255:
												wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
											else:
												wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
							elif selection[1] == 4:
								set_alarm_list = [['Set new alarm','newalarm'],
												  ['Get alarm','getalarm'],
												  ['Remove alarm',[[['All','removeall'],
																	['Specific alarm','removespecific'],
																	['Exit','exit']],'remove']],
												  ['Exit','exit']]
								setal = Myassistant.select_list(self,set_alarm_list,'led strip alarm')
								if setal == 'newalarm':
									selecttime = Myassistant.select_time(self,'--', '--', '-', 'new alarm',True)
									if not (selecttime[0] == '--' or selecttime[1] == '--'):
										color = Myassistant.select_led_strip_color_alarm(self)
										Myassistant.set_word_aff(self, 'Loading please wait')
										f = flux_led.LedTimer()
										f.setActive()
										f.setTime(int(selecttime[0]),int(selecttime[1]))
										if selecttime[2] == '-':
											f.setRepeatMask(flux_led.LedTimer.Everyday)
										else:
											if selecttime[2] == "Monday" :
												f.setRepeatMask(flux_led.LedTimer.Mo)
											elif selecttime[2] == "Tuesday" :
												f.setRepeatMask(flux_led.LedTimer.Tu)
											elif selecttime[2] == "Wednesday" :
												f.setRepeatMask(flux_led.LedTimer.We)
											elif selecttime[2] == "Thursday" :
												f.setRepeatMask(flux_led.LedTimer.Th)
											elif selecttime[2] == "Friday" :
												f.setRepeatMask(flux_led.LedTimer.Fr)
											elif selecttime[2] == "Saturday" :
												f.setRepeatMask(flux_led.LedTimer.Sa)
											elif selecttime[2] == "Sunday" :
												f.setRepeatMask(flux_led.LedTimer.Su)
										eval('f.'+str(color[1]))
										if '[' in str(color[0]):
											for adress in color[0]:
												wifiled = led.WifiLedBulb(adress)
												timeur = wifiled.getTimers()
												timeur[5] = timeur[4]
												timeur[4] = timeur[3]
												timeur[3] = timeur[2]
												timeur[2] = timeur[1]
												timeur[1] = timeur[0]
												timeur[0] = f
												wifiled.sendTimers(timeur)
										else:
											wifiled = led.WifiLedBulb(color[0])
											timeur = wifiled.getTimers()
											timeur[5] = timeur[4]
											timeur[4] = timeur[3]
											timeur[3] = timeur[2]
											timeur[2] = timeur[1]
											timeur[1] = timeur[0]
											timeur[0] = f
											wifiled.sendTimers(timeur)
								elif setal == 'getalarm':
									lljsdj = []
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											timeur = wifiled.getTimers()
											for t in timeur:
												if not str(t) == 'Unset':
													lljsdj.append([str(t),'any'])
									else:
										timeur = wifiled.getTimers()
										for t in timeur:
											if not str(t) == 'Unset':
												lljsdj.append([str(t),'any'])
									lljsdj.append(['Exit','any'])
									rien = Myassistant.select_list(self,lljsdj,'led strip alarm')
								elif setal == 'removespecific':
									lljsdj = []
									conteur = 0
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											timeur = wifiled.getTimers()
											conteur = 0
											for t in timeur:
												if not str(t) == 'Unset':
													lljsdj.append([str(t),str(adress)+','+str(conteur)])
												conteur = conteur + 1
									else:
										timeur = wifiled.getTimers()
										conteur = 0
										for t in timeur:
											if not str(t) == 'Unset':
												lljsdj.append([str(t),str(conteur)])
											conteur = conteur + 1
									lljsdj.append(['Exit','exit'])
									rien = Myassistant.select_list(self,lljsdj,'select alarm')
									if ',' in str(rien):
										ghhjf = rien.split(',')
										wifiled = led.WifiLedBulb(ghhjf[0])
										f = flux_led.LedTimer()
										f.setActive(False)
										timeur = wifiled.getTimers()
										timeur[int(ghhjf[1])] = f
										Myassistant.set_word_aff(self, 'Loading please wait')
										wifiled.sendTimers(timeur)
										while not len(self.buton) == 0:
											del self.buton[0]
									elif not rien == 'exit' and not rien == None:
										f = flux_led.LedTimer()
										f.setActive(False)
										timeur = wifiled.getTimers()
										timeur[int(rien)] = f
										Myassistant.set_word_aff(self, 'Loading please wait')
										wifiled.sendTimers(timeur)
										while not len(self.buton) == 0:
											del self.buton[0]
								elif setal ==  'removeall':
									Myassistant.set_word_aff(self, 'Loading please wait')
									f = flux_led.LedTimer()
									f.setActive(False)
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											wifiled.sendTimers([f,f,f,f,f,f])
									else:
										wifiled.sendTimers([f,f,f,f,f,f])
							elif not selection[1] == 10:
								selection[0] = not selection[0]
								if selection[0] and selection[1] == 5:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											try:
												eval('wifiled.' + str(coloraction[selectlist]))
											except:
												print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									else:
										try:
											eval('wifiled.' + str(coloraction[selectlist]))
										except:
											print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									ifwantreload = 0
							elif selection[1] == 10:
								selection[1] = 0
								for adresr in listwifi:
									wifiled = listwifi[adresr]
									if not wifiled.isOn():
										wifiled.turnOn()
						elif self.buton[0] == 2 :
							del self.buton[0]
							if selection[1] == 10:
								cont = False
								Myassistant.execute_next(self,'right')
							elif selection[0]:
								if selection[1] == 0:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											if ison:
												wifiled.turnOff()
											else:
												wifiled.turnOn()
									else:
										if ison:
											wifiled.turnOff()
										else:
											wifiled.turnOn()
								elif selection[1] == 1:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if wifiled.brightness+10 > 255 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=255)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=wifiled.brightness+10)
									else:
										if brightnes+10 > 255:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=255)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=brightnes+10)
								elif selection[1] == 6:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[0]+10 > 255 :
												wifiled.setRgbw(r=255,g=y[1],b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0]+10,g=y[1],b=y[2],w=y[3])
									else:
										if r+10 > 255:
											wifiled.setRgbw(r=255,g=g,b=b,w=w)
										else:
											wifiled.setRgbw(r=r+10,g=g,b=b,w=w)
								elif selection[1] == 7:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[1]+10 > 255 :
												wifiled.setRgbw(r=y[0],g=255,b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1]+10,b=y[2],w=y[3])
									else:
										if g+10 > 255:
											wifiled.setRgbw(r=r,g=255,b=b,w=w)
										else:
											wifiled.setRgbw(r=r,g=g+10,b=b,w=w)
								elif selection[1] == 8:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[2]+10 > 255 :
												wifiled.setRgbw(r=y[0],g=y[1],b=255,w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2]+10,w=y[3])
									else:
										if g+10 > 255:
											wifiled.setRgbw(r=r,g=g,b=255,w=w)
										else:
											wifiled.setRgbw(r=r,g=g,b=b+10,w=w)
								elif selection[1] == 9:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[3]+10 > 255 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=255)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3]+10)
									else:
										if w+10 > 255:
											wifiled.setRgbw(r=r,g=g,b=b,w=255)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w+10)
								elif selection[1] == 5:
									if not selectlist + 1 > len(colorlist)-1:
										selectlist = selectlist + 1
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											try:
												eval('wifiled.' + str(coloraction[selectlist]))
											except:
												print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									else:
										try:
											eval('wifiled.' + str(coloraction[selectlist]))
										except:
											print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									ifwantreload = 0
							else:
								if not selection[1] + 1 > 9:
									selection[1] = selection[1] + 1
								else:
									selection[1] = 0
						elif self.buton[0] == 3 :
							del self.buton[0]
							if selection[1] == 10:
								cont = False
								Myassistant.execute_next(self,'left')
							elif selection[0]:
								if selection[1] == 0:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											if ison:
												wifiled.turnOff()
											else:
												wifiled.turnOn()
									else:
										if ison:
											wifiled.turnOff()
										else:
											wifiled.turnOn()
								elif selection[1] == 1:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if wifiled.brightness-10 < 0 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=0)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=wifiled.brightness-10)
									else:
										if brightnes-10 < 0:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=0)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=brightnes-10)
								elif selection[1] == 6:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[0]-10 < 0 :
												wifiled.setRgbw(r=0,g=y[1],b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0]-10,g=y[1],b=y[2],w=y[3])
									else:
										if r-10 < 0:
											wifiled.setRgbw(r=0,g=g,b=b,w=w)
										else:
											wifiled.setRgbw(r=r-10,g=g,b=b,w=w)
								elif selection[1] == 7:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[1]-10 < 0 :
												wifiled.setRgbw(r=y[0],g=0,b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1]-10,b=y[2],w=y[3])
									else:
										if g-10 < 0:
											wifiled.setRgbw(r=r,g=0,b=b,w=w)
										else:
											wifiled.setRgbw(r=r,g=g-10,b=b,w=w)
								elif selection[1] == 8:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[2]-10 < 0 :
												wifiled.setRgbw(r=y[0],g=y[1],b=0,w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2]-10,w=y[3])
									else:
										if b-10 < 0:
											wifiled.setRgbw(r=r,g=g,b=0,w=w)
										else:
											wifiled.setRgbw(r=r,g=g,b=b-10,w=w)
								elif selection[1] == 9:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[3]-10 < 0 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=0)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3]-10)
									else:
										if w-10 < 0:
											wifiled.setRgbw(r=r,g=g,b=b,w=0)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w-10)
								elif selection[1] == 5:
									if not selectlist - 1 < 0:
										selectlist = selectlist - 1
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											try:
												eval('wifiled.' + str(coloraction[selectlist]))
											except:
												print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									else:
										try:
											eval('wifiled.' + str(coloraction[selectlist]))
										except:
											print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									ifwantreload = 0
							else:
								if not selection[1] - 1 < 0:
									selection[1] = selection[1] - 1
								else:
									selection[1] = 9
						ifwantreload = 0
						if not len(self.buton) == 0:
							buton = 5
						else:
							buton = 0
						self.veil = 0
					buton = buton - 1
		except BrokenPipeError :
			self.veil = 0
			threading.Timer(0, Myassistant.aff_heure,[self]).start()
			print('Failed : "led strip"')

	def select_path(self, path, stetdff):
		choice = True
		selist = [15, 0]
		memy = 3
		x = 2
		xpat = 0
		direcpat = 0
		direc = 0
		while choice and not self.al:
			try:
				listaff = os.listdir(path)
			except:
				listaff = []
			ct = len(listaff) - 1
			while ct > -1:
				if str(listaff[ct])[0] == '.' :
					del listaff[ct]
				ct = ct - 1
			if listaff == []:
				image = Image.new('1', (disp.width,disp.height))
				draw = ImageDraw.Draw(image)
				draw.text((xpat,0), path, font=font, fill=225)
				draw.line((0, 12, 127, 12), fill=255)
				disp.image(image)
				Myassistant.refrech_error()
				time.sleep(1)
				xpat = 0
				path = path.split("/")
				del path[len(path) - 1]
				path = "/".join(path)
				if path == '':
					path = '/'
				selist = [15,0]
				memy = 3
				try:
					listaff = os.listdir(path)
				except:
					path = '/'
					listaff = os.listdir('/')
				if listaff == []:
					path = '/'
					listaff = os.listdir('/')
				ct = len(listaff) - 1
				while ct > -1:
					if str(listaff[ct])[0] == '.' :
						del listaff[ct]
					ct = ct - 1
			image = Image.new('1', (disp.width,disp.height))
			draw = ImageDraw.Draw(image)
			if len(listaff[selist[1]]) * 6 > 124 :
				if direc == 0 :
					if len(listaff[selist[1]]) * 6 + x > 124 :
						x = x - 4
					else :
						direc = 1
				else :
					x = x + 4
					if x > 3 :
						direc = 0
			if len(path) * 6 > 128 :
				if direcpat == 0 :
					if len(path) * 6 + xpat > 128 :
						xpat = xpat - 4
					else :
						direcpat = 1
				else :
					xpat = xpat + 4
					if xpat > 1 :
						direcpat = 0
			draw.rectangle((0, selist[0], 127, selist[0] + 12), outline=255, fill=0)
			y = memy
			lllo = 0
			while lllo < len(listaff):
				y = y + 12
				if lllo == selist[1]:
					draw.text((x,y), str(listaff[lllo]), font=font, fill=225)
				else :
					draw.text((2,y), str(listaff[lllo]), font=font, fill=225)
				lllo = lllo + 1
			draw.rectangle((126, 16, 126, 26), outline=0, fill=0)
			draw.rectangle((126, 28, 126, 38), outline=0, fill=0)
			draw.rectangle((126, 40, 126, 50), outline=0, fill=0)
			draw.rectangle((126, 52, 126, 62), outline=0, fill=0)
			draw.rectangle((127, 16, 127, 26), outline=0, fill=0)
			draw.rectangle((127, 28, 127, 38), outline=0, fill=0)
			draw.rectangle((127, 40, 127, 50), outline=0, fill=0)
			draw.rectangle((127, 52, 127, 62), outline=0, fill=0)
			draw.rectangle((1, 16, 1, 26), outline=0, fill=0)
			draw.rectangle((1, 28, 1, 38), outline=0, fill=0)
			draw.rectangle((1, 40, 1, 50), outline=0, fill=0)
			draw.rectangle((1, 52, 1, 62), outline=0, fill=0)
			draw.rectangle((0, 0, 127, 14), outline=0, fill=0)
			draw.text((xpat,0), path, font=font, fill=225)
			draw.line((127, selist[0], 127, selist[0] + 12), fill=255)
			draw.line((0, 12, 127, 12), fill=255)
			disp.image(image)
			Myassistant.refrech_error()
			buton = 20000
			while buton > 0 and not self.al:
				self.veil = 0
				if not len(self.buton) == 0:
					if self.buton[0] == 0 :
						del self.buton[0]
						xpat = 0
						path = path.split("/")
						del path[len(path) - 1]
						path = "/".join(path)
						if path == '':
							path = '/'
						selist = [15,0]
						memy = 3
					elif self.buton[0] == 1 :
						del self.buton[0]
						xpat = 0
						if stetdff:
							thetime = 10
							while thetime > 0:
								time.sleep(0.1)
								if GPIO.input(bround) == 1 :
									thetime = -9
								thetime = thetime - 1
								while not len(self.buton) == 0:
									del self.buton[0]
							while not len(self.buton) == 0:
								del self.buton[0]
						else:
							thetime = -10
						if thetime == -10:
							if path == '/':
								path = '/' + listaff[selist[1]]
							else:
								path = path + '/' + listaff[selist[1]]
							if os.path.isfile(path):
								choice = False
						else:
							if path == '/':
								path = '/' + listaff[selist[1]]
							else:
								path = path + '/' + listaff[selist[1]]
							choice = False
						selist = [15,0]
						memy = 3
					elif self.buton[0] == 2 :
						del self.buton[0]
						if not selist[1] + 1 > len(listaff) - 1:
							selist = [selist[0] + 12,selist[1] + 1]
						if selist[0] > 52 :
							memy = memy - 12
							selist[0] = 51
					elif self.buton[0] == 3 :
						del self.buton[0]
						selist = [selist[0] - 12,selist[1] - 1]
						if selist[1] < 0:
							selist = [15, 0]
						elif selist[0] < 14 :
							memy = memy + 12
							selist[0] = 15
					if not len(self.buton) == 0:
						buton = 5
					else:
						buton = 0
					x = 2
				if len(listaff[selist[1]]) * 6 > 124 :
					buton = buton - 1
				elif len(path) * 6 > 128 :
					buton = buton - 1
		if choice:
			return None
		else:
			return path

	def select_cursor(self, nmax, nmin, increment, start, unit, name):
		cont = True
		cu = start
		while cont and not self.al:
			image = Image.new('1', (disp.width,disp.height))
			draw = ImageDraw.Draw(image)
			draw.text(((127 - (len(name) * 6)) / 2,0), name, font=font, fill=225)
			draw.line((10,31,117,31), fill = 255)
			pos = ((107 / ((nmax - nmin) + 1)) * cu) + 10
			draw.rectangle((pos - 2, 36, pos + 2, 26), outline=255, fill=255)
			draw.text((pos - (len(str(cu) + unit) * 6) / 2 + 1,40), str(cu) + unit, font=font, fill=225)
			disp.image(image)
			Myassistant.refrech_error()
			buton = True
			while buton and not self.al:
				self.veil = 0
				if not len(self.buton) == 0:
					if self.buton[0] == 0 :
						del self.buton[0]
						cont = False
					elif self.buton[0] == 1 :
						del self.buton[0]
						cont = False
					elif self.buton[0] == 2 :
						del self.buton[0]
						if not cu + increment > nmax:
							cu = cu + increment
						else:
							cu = nmax
					elif self.buton[0] == 3 :
						del self.buton[0]
						if not cu - increment < nmin:
							cu = cu - increment
						else:
							cu = nmin
					if not len(self.buton) == 0:
						buton = True
					else:
						buton = False
		return cu

	def select_time(self, shour, sminu, sday, name,ops = False):
		cont = True
		sel = [False,0]
		while cont and not self.al:
			image = Image.new('1', (disp.width,disp.height))
			draw = ImageDraw.Draw(image)
			draw.text(((127 - (len(name) * 6)) / 2,0), name, font=font, fill=225)
			draw.text(((128 - (len(sday) * 6)) / 2,32),sday, font=font, fill=225)
			draw.text((43,20), shour + '   ' + sminu, font=font, fill=225)
			if sel[1] == 2:
				if sel[0] :
					draw.rectangle((((128 - (len(sday) * 6)) / 2) - 2, 32, (((128 - (len(sday) * 6)) / 2) + len(sday) * 6) + 1, 44), outline=255, fill=255)
					draw.text(((128 - (len(sday) * 6)) / 2,32),sday, font=font, fill=0)
				else:
					draw.rectangle((((128 - (len(sday) * 6)) / 2) - 2, 32, (((128 - (len(sday) * 6)) / 2) + len(sday) * 6) + 1, 44), outline=255, fill=0)
					draw.text(((128 - (len(sday) * 6)) / 2,32),sday, font=font, fill=225)
			elif sel[1] == 0:
				if sel[0] :
					draw.rectangle((41, 20, 56, 30), outline=255, fill=255)
					draw.text((43,20), shour, font=font, fill=0)
				else:
					draw.rectangle((41, 20, 56, 30), outline=255, fill=0)
					draw.text((43,20), shour, font=font, fill=225)
			elif sel[1] == 1:
				if sel[0] :
					draw.rectangle((71, 20, 86, 30), outline=255, fill=255)
					draw.text((43,20), '     ' + sminu, font=font, fill=0)
				else:
					draw.rectangle((71, 20, 86, 30), outline=255, fill=0)
					draw.text((43,20),'     ' + sminu, font=font, fill=225)
			draw.text((61,20),':', font=font, fill=225)
			if int(time.strftime("%S")) % 2 == 0 :
				draw.text((49,54),str(time.strftime("%H")) + ":" + str(time.strftime("%M")) , font=font, fill=225)
			else :
				draw.text((49,54),str(time.strftime("%H")) + " " + str(time.strftime("%M")) , font=font, fill=225)
			disp.image(image)
			Myassistant.refrech_error()
			buton = 20000
			self.veil = 0
			while buton > 0 and not self.al:
				if not len(self.buton) == 0:
					if self.buton[0] == 0 :
						del self.buton[0]
						cont = False
					elif self.buton[0] == 1 :
						del self.buton[0]
						sel[0] = not sel[0]
					elif self.buton[0] == 2 :
						del self.buton[0]
						if sel[0]:
							if sel[1] == 0:
								if ops:
									if shour == '23':
										shour = "--"
									elif shour == '--':
										shour = "00"
									else:
										shour = Myassistant.ad_hour(shour,1)
								else:
									shour = Myassistant.ad_hour(shour,1)
							elif sel[1] == 1:
								if ops:
									if sminu == '59':
										sminu = "--"
									elif sminu == '--':
										sminu = "00"
									else:
										sminu = Myassistant.ad_min(sminu,1)
								else:
									sminu = Myassistant.ad_min(sminu,1)
							elif sel[1] == 2:
								if ops:
									if sday == 'Sunday':
										sday = "-"
									elif sday == '-':
										sday = "Monday"
									else:
										sday = Myassistant.ad_day(sday,1)
								else:
									sday = Myassistant.ad_day(sday,1)
						else:
							sel[1] = sel[1] + 1
							if sel[1] > 2 :
								sel[1] = 0
					elif self.buton[0] == 3 :
						del self.buton[0]
						if sel[0]:
							if sel[1] == 0:
								if ops:
									if shour == '00':
										shour = "--"
									elif shour == '--':
										shour = "23"
									else:
										shour = Myassistant.remove_hour(shour,1)
								else:
									shour = Myassistant.remove_hour(shour,1)
							elif sel[1] == 1:
								if ops:
									if sminu == '00':
										sminu = "--"
									elif sminu == '--':
										sminu = "59"
									else:
										sminu = Myassistant.remove_min(sminu,1)
								else:
									sminu = Myassistant.remove_min(sminu,1)
							elif sel[1] == 2:
								if ops:
									if sday == 'Monday':
										sday = "-"
									elif sday == '-':
										sday = "Sunday"
									else:
										sday = Myassistant.remove_day(sday,1)
								else:
									sday = Myassistant.remove_day(sday,1)
						else:
							sel[1] = sel[1] - 1
							if sel[1] < 0 :
								sel[1] = 2
					if not len(self.buton) == 0:
						buton = 5
					else:
						buton = 0
				buton = buton - 1
		if cont:
			return ['--','--','-']
		else:
			return [shour, sminu, sday]

	def select_list(self, listl, name):
		choice = True
		selist = [15, 0]
		memy = 3
		x = 2
		xpat = 0
		direcpat = 0
		direc = 0
		namegf = name
		listachang = listl
		response = ''
		historlist = []
		historlist.append(listl)
		while choice and not self.al:
			listaff = []
			for hap in listachang:
				listaff.append(hap[0])
			image = Image.new('1', (disp.width,disp.height))
			draw = ImageDraw.Draw(image)
			if len(listaff[selist[1]]) * 6 > 124 :
				if direc == 0 :
					if len(listaff[selist[1]]) * 6 + x > 124 :
						x = x - 4
					else :
						direc = 1
				else :
					x = x + 4
					if x > 3 :
						direc = 0
			if len(namegf) * 6 > 128 :
				if direcpat == 0 :
					if len(namegf) * 6 + xpat > 128 :
						xpat = xpat - 4
					else :
						direcpat = 1
				else :
					xpat = xpat + 4
					if xpat > 1 :
						direcpat = 0
			draw.rectangle((0, selist[0], 127, selist[0] + 12), outline=255, fill=0)
			y = memy
			lllo = 0
			while lllo < len(listaff):
				y = y + 12
				if lllo == selist[1]:
					draw.text((x,y), str(listaff[lllo]), font=font, fill=225)
				else :
					draw.text((2,y), str(listaff[lllo]), font=font, fill=225)
				lllo = lllo + 1
			draw.rectangle((126, 16, 126, 26), outline=0, fill=0)
			draw.rectangle((126, 28, 126, 38), outline=0, fill=0)
			draw.rectangle((126, 40, 126, 50), outline=0, fill=0)
			draw.rectangle((126, 52, 126, 62), outline=0, fill=0)
			draw.rectangle((127, 16, 127, 26), outline=0, fill=0)
			draw.rectangle((127, 28, 127, 38), outline=0, fill=0)
			draw.rectangle((127, 40, 127, 50), outline=0, fill=0)
			draw.rectangle((127, 52, 127, 62), outline=0, fill=0)
			draw.rectangle((1, 16, 1, 26), outline=0, fill=0)
			draw.rectangle((1, 28, 1, 38), outline=0, fill=0)
			draw.rectangle((1, 40, 1, 50), outline=0, fill=0)
			draw.rectangle((1, 52, 1, 62), outline=0, fill=0)
			draw.rectangle((0, 0, 127, 14), outline=0, fill=0)
			draw.text((xpat,0), namegf, font=font, fill=225)
			draw.line((127, selist[0], 127, selist[0] + 12), fill=255)
			draw.line((0, 12, 127, 12), fill=255)
			disp.image(image)
			Myassistant.refrech_error()
			buton = 20000
			while buton > 0 and not self.al:
				self.veil = 0
				if not len(self.buton) == 0:
					if self.buton[0] == 0 :
						del self.buton[0]
						xpat = 0
						if not len(historlist) - 2 < 0:
							namegf = namegf.split('>')
							namegf = namegf[len(namegf)-2]
							listachang = historlist[len(historlist)-2]
							del historlist[len(historlist)-1]
						selist = [15,0]
						memy = 3
					elif self.buton[0] == 1 :
						del self.buton[0]
						xpat = 0
						if '[' in str(listachang[selist[1]][1]):
							namegf = namegf + '>' + str(listachang[selist[1]][1][1])
							historlist.append(listachang[selist[1]][1][0])
							listachang = listachang[selist[1]][1][0]
						else:
							response = str(listachang[selist[1]][1])
							choice = False
						selist = [15,0]
						memy = 3
					elif self.buton[0] == 2 :
						del self.buton[0]
						if not selist[1] + 1 > len(listaff) - 1:
							selist = [selist[0] + 12,selist[1] + 1]
						if selist[0] > 52 :
							memy = memy - 12
							selist[0] = 51
					elif self.buton[0] == 3 :
						del self.buton[0]
						selist = [selist[0] - 12,selist[1] - 1]
						if selist[1] < 0:
							selist = [15, 0]
						elif selist[0] < 14 :
							memy = memy + 12
							selist[0] = 15
					if not len(self.buton) == 0:
						buton = 5
					else:
						buton = 0
					x = 2
				if len(listaff[selist[1]]) * 6 > 124 :
					buton = buton - 1
				elif len(namegf) * 6 > 128 :
					buton = buton - 1
		if choice:
			return None
		else:
			return response

	def select_search_list(self, listl):
		choice = True
		selist = [15, 0]
		memy = 3
		x = 2
		direcpat = 0
		direc = 0
		namegf = ''
		listachang = listl
		response = ''
		hresqtr = False
		seraselect = [0,False]
		while choice and not self.al:
			if not (namegf == '' or namegf == ' '):
				kghl = []
				for hap in listl:
					kghl.append(hap[0])
				if namegf[len(namegf)-1] == ' ':
					hkhkk = []
					for leter in namegf:
						hkhkk.append(leter)
					del hkhkk[len(hkhkk)-1]
					fghdhgh = "".join(hkhkk)
					nlistv = Myassistant.search_wordt(fghdhgh,kghl)
				else:
					nlistv = Myassistant.search_wordt(namegf,kghl)
				listachang = []
				for xmots in nlistv:
					wlit = len(listl)-1
					while wlit > -1:
						if xmots == listl[wlit][0]:
							listachang.append([listl[wlit][0],listl[wlit][1]])
							wlit = -1
						wlit = wlit - 1
			else:
				listachang = listl
			listaff = []
			for hap in listachang:
				listaff.append(hap[0])
			image = Image.new('1', (disp.width,disp.height))
			draw = ImageDraw.Draw(image)
			if not listaff == [] and hresqtr:
				if len(listaff[selist[1]]) * 6 > 124 :
					if direc == 0 :
						if len(listaff[selist[1]]) * 6 + x > 124 :
							x = x - 4
						else :
							direc = 1
					else :
						x = x + 4
						if x > 3 :
							direc = 0
			if hresqtr:
				draw.rectangle((0, selist[0], 127, selist[0] + 12), outline=255, fill=0)
			y = memy
			lllo = 0
			while lllo < len(listaff):
				y = y + 12
				if lllo == selist[1]:
					draw.text((x,y), str(listaff[lllo]), font=font, fill=225)
				else :
					draw.text((2,y), str(listaff[lllo]), font=font, fill=225)
				lllo = lllo + 1
			draw.rectangle((126, 16, 126, 26), outline=0, fill=0)
			draw.rectangle((126, 28, 126, 38), outline=0, fill=0)
			draw.rectangle((126, 40, 126, 50), outline=0, fill=0)
			draw.rectangle((126, 52, 126, 62), outline=0, fill=0)
			draw.rectangle((127, 16, 127, 26), outline=0, fill=0)
			draw.rectangle((127, 28, 127, 38), outline=0, fill=0)
			draw.rectangle((127, 40, 127, 50), outline=0, fill=0)
			draw.rectangle((127, 52, 127, 62), outline=0, fill=0)
			draw.rectangle((1, 16, 1, 26), outline=0, fill=0)
			draw.rectangle((1, 28, 1, 38), outline=0, fill=0)
			draw.rectangle((1, 40, 1, 50), outline=0, fill=0)
			draw.rectangle((1, 52, 1, 62), outline=0, fill=0)
			draw.rectangle((0, 0, 127, 14), outline=0, fill=0)
			draw.text((0,-2), namegf, font=font, fill=225)
			if not hresqtr:
				if seraselect[1]:
					draw.rectangle((seraselect[0]*6, 0, seraselect[0]*6+5, 10), outline=255, fill=255)
					if len(namegf) == 0:
						namegf = ' '
						seraselect[0] = 0
					draw.text((seraselect[0]*6,-1), namegf[seraselect[0]], font=font, fill=0)
				else:
					draw.line((seraselect[0]*6, 10, seraselect[0]*6+5, 10), fill=255)
			if hresqtr:
				draw.line((127, selist[0], 127, selist[0] + 12), fill=255)
			draw.line((0, 12, 127, 12), fill=255)
			disp.image(image)
			Myassistant.refrech_error()
			buton = 20000
			while buton > 0 and not self.al:
				self.veil = 0
				if not len(self.buton) == 0:
					if self.buton[0] == 0 :
						del self.buton[0]
						if not listaff == []:
							hresqtr = not hresqtr
						selist = [15,0]
						memy = 3
					elif self.buton[0] == 1 :
						del self.buton[0]
						if hresqtr:
							response = str(listachang[selist[1]][1])
							choice = False
						else:
							seraselect[1] = not seraselect[1]
						selist = [15,0]
						memy = 3
					elif self.buton[0] == 2 :
						del self.buton[0]
						if hresqtr:
							if not selist[1] + 1 > len(listaff) - 1:
								selist = [selist[0] + 12,selist[1] + 1]
							if selist[0] > 52 :
								memy = memy - 12
								selist[0] = 51
						else:
							if seraselect[1]:
								hkhkk = []
								for leter in namegf:
									hkhkk.append(leter)
								hkhkk[len(hkhkk)-1] = Myassistant.ad_letter(hkhkk[len(hkhkk)-1],1)
								namegf = "".join(hkhkk)
							else:
								if not seraselect[0]+1 > 20:
									namegf = namegf+' '
									seraselect[0] = len(namegf)-1
					elif self.buton[0] == 3 :
						del self.buton[0]
						if hresqtr:
							selist = [selist[0] - 12,selist[1] - 1]
							if selist[1] < 0:
								selist = [15, 0]
							elif selist[0] < 14 :
								memy = memy + 12
								selist[0] = 15
						else:
							if seraselect[1]:
								hkhkk = []
								for leter in namegf:
									hkhkk.append(leter)
								hkhkk[len(hkhkk)-1] = Myassistant.remove_letter(hkhkk[len(hkhkk)-1],1)
								namegf = "".join(hkhkk)
							else:
								if not seraselect[0]-1 < 0:
									hkhkk = []
									for leter in namegf:
										hkhkk.append(leter)
									del hkhkk[len(hkhkk)-1]
									namegf = "".join(hkhkk)
									seraselect[0] = seraselect[0]-1
								else:
									namegf = ""
					if not len(self.buton) == 0:
						buton = 5
					else:
						buton = 0
					x = 2
				if not listaff == [] and hresqtr:
					if len(listaff[selist[1]]) * 6 > 124 :
						buton = buton - 1
		if choice:
			return None
		else:
			return response

	def select_led_strip_color_alarm(self):
		try:
			response = None
			ifwantreload = 0
			cont = True
			name = 'All'
			listwifi={}
			name_wifi_led = []
			ip_wifi_led = []
			led = flux_led.__main__
			for wifi_led in settings.get('Led strips names'):
				listwifi[str(wifi_led[0])]=led.WifiLedBulb(wifi_led[1])
				name_wifi_led.append(wifi_led[0])
				ip_wifi_led.append(wifi_led[1])
			colorlist = ['seven color cross fade','red gradual change','green gradual change','blue gradual change','yellow gradual change','cyan gradual change','purple gradual change','white gradual change','red green cross fade','red blue cross fade','green blue cross fade','seven color strobe flash','red strobe flash','green strobe flash','blue strobe flash','yellow strobe flash','cyan strobe flash','purple strobe flash','white strobe flash','seven color jumping']
			coloraction = ['setPresetPattern(0x25,100)','setPresetPattern(0x26,100)','setPresetPattern(0x27,100)','setPresetPattern(0x28,100)','setPresetPattern(0x29,100)','setPresetPattern(0x2a,100)','setPresetPattern(0x2b,100)','setPresetPattern(0x2c,100)','setPresetPattern(0x2d,100)','setPresetPattern(0x2e,100)','setPresetPattern(0x2f,100)','setPresetPattern(0x30,100)','setPresetPattern(0x31,100)','setPresetPattern(0x32,100)','setPresetPattern(0x33,100)','setPresetPattern(0x34,100)','setPresetPattern(0x35,100)','setPresetPattern(0x36,100)','setPresetPattern(0x37,100)','setPresetPattern(0x38,100)']
			selectlist = round((len(colorlist) - 1) / 2)
			selection = [False, 0]
			save_list_color = []
			for adresr in listwifi:
				wifiled = listwifi[adress]
				y = wifiled.getRgbw()
				save_list_color.append([int(y[0]),int(y[1]),int(y[2]),int(y[3]),wifiled.is_on])
			r = 0
			g = 0
			b = 0
			w = 0
			for adresr in listwifi:
				wifiled = listwifi[adresr]
				if not wifiled.isOn():
					wifiled.turnOn()
			while cont and not self.al:
				image = Image.new('1', (disp.width,disp.height))
				draw = ImageDraw.Draw(image)
				if name == 'All':
					r = 0
					g = 0
					b = 0
					w = 0
					ison = False
					brightnes = 0
					i = 0
					for adress in listwifi:
						wifiled = listwifi[adress]
						wifiled.refreshState()
						y = wifiled.getRgbw()
						r = r + y[0]
						g = g + y[1]
						b = b + y[2]
						w = w + y[3]
						if wifiled.is_on:
							ison = True
						brightnes = brightnes + wifiled.brightness
						i = i + 1
					r = round(r/i)
					g = round(g/i)
					b = round(b/i)
					w = round(w/i)
					brightnes = round(brightnes/i)
				else:
					wifiled = listwifi[name]
					wifiled.refreshState()
					y = wifiled.getRgbw()
					r = y[0]
					g = y[1]
					b = y[2]
					w = y[3]
					ison = wifiled.is_on
					brightnes = wifiled.brightness
				brightnessim = Image.open('/home/pi/Google_Assistant/src/images/led_strip/brightness.jpg')
				brightnessim = brightnessim.resize((17,17))
				brightnessim = ImageOps.invert(brightnessim)
				image.paste(brightnessim, (28,12))
				if selection[1] == 4:
					sunrise = Image.open('/home/pi/Google_Assistant/src/images/led_strip/sunrise.png')
					sunrise = sunrise.resize((15,13))
					sunrise = ImageOps.invert(sunrise)
					image.paste(sunrise, (111,11))
					draw.rectangle((111, 8, 124, 14), outline=0, fill=0)
					draw.line((109,15,109,25), fill=255)
					draw.line((109,25,127,25), fill=255)
					draw.line((127,15,127,25), fill=255)
					draw.line((109,15,127,15), fill=255)
				else:
					sunrise = Image.open('/home/pi/Google_Assistant/src/images/led_strip/sunrise.png')
					sunrise = sunrise.resize((15,13))
					sunrise = ImageOps.invert(sunrise)
					image.paste(sunrise, (111,11))
					draw.rectangle((111, 8, 126, 15), outline=0, fill=0)
				draw.text(((127 - (len(name) * 6)) / 2,0), name, font=font, fill=225)
				if ison:
					if selection[1] == 0:
						if selection[0]:
							draw.rectangle((0, 15, (len(str('on')) * 6) + 2, 25), outline=255, fill=255)
							draw.text((2,15), 'on', font=font, fill=0)
						else:
							draw.rectangle((0, 15, (len(str('on')) * 6) + 2, 25), outline=255, fill=0)
							draw.text((2,15), 'on', font=font, fill=225)
					else:
						draw.text((2,15), 'on', font=font, fill=225)
				else:
					if selection[1] == 0:
						if selection[0]:
							draw.rectangle((0, 15, (len(str('off')) * 6) + 2, 25), outline=255, fill=255)
							draw.text((2,15), 'off', font=font, fill=0)
						else:
							draw.rectangle((0, 15, (len(str('off')) * 6) + 2, 25), outline=255, fill=0)
							draw.text((2,15), 'off', font=font, fill=225)
					else:
						draw.text((2,15), 'off', font=font, fill=225)
				if selection[1] == 1:
					if selection[0]:
						draw.rectangle((44, 15, (len(str(brightnes)) * 6) + 46, 25), outline=255, fill=255)
						draw.text((46,15), str(brightnes), font=font, fill=0)
					else:
						draw.rectangle((44, 15, (len(str(brightnes)) * 6) + 46, 25), outline=255, fill=0)
						draw.text((46,15), str(brightnes), font=font, fill=225)
				else:
					draw.text((46,15), str(brightnes), font=font, fill=225)
				if selection[1] == 2:
					draw.rectangle((74, 15, 88, 25), outline=255, fill=0)
				draw.line((76,17,86,17), fill=255)
				draw.line((76,19,86,19), fill=255)
				draw.line((76,21,86,21), fill=255)
				draw.line((76,23,86,23), fill=255)
				if selection[1] == 3:
					draw.rectangle((96, 15, (len(str('+')) * 6) + 98, 25), outline=255, fill=0)
				draw.text((98,15), '+', font=font, fill=225)
				xcenter = (127 - (len(colorlist[selectlist]) * 6)) / 2
				if selection[1] == 5:
					draw.rectangle((0, 29, 127, 48), outline=255, fill=0)
					if selection[0]:
						draw.rectangle((xcenter - 4, 31, (len(colorlist[selectlist]) * 6) + xcenter + 3, 46), outline=255, fill=0)
				i = selectlist - 1
				while i > -1:
					xcenter = xcenter - (12 + (len(colorlist[i]) * 6))
					i = i - 1
				draw.text((xcenter,33), "  ".join(colorlist), font=font, fill=225)
				if selection[1] == 6:
					if selection[0]:
						draw.rectangle((8, 53, (len(str(r)) * 6) + 11, 63), outline=255, fill=255)
						draw.text((10,53), str(r), font=font, fill=0)
					else:
						draw.rectangle((8, 53, (len(str(r)) * 6) + 11, 63), outline=255, fill=0)
						draw.text((10,53), str(r), font=font, fill=225)
					draw.text((0,53), 'R', font=font, fill=225)
				else:
					draw.text((0,53), 'R:', font=font, fill=225)
					draw.text((10,53), str(r), font=font, fill=225)
				if selection[1] == 7:
					if selection[0]:
						draw.rectangle((40, 53, (len(str(g)) * 6) + 43, 63), outline=255, fill=255)
						draw.text((42,53), str(g), font=font, fill=0)
					else:
						draw.rectangle((40, 53, (len(str(g)) * 6) + 43, 63), outline=255, fill=0)
						draw.text((42,53), str(g), font=font, fill=225)
					draw.text((32,53), 'G', font=font, fill=225)
				else:
					draw.text((32,53), 'G:', font=font, fill=225)
					draw.text((42,53), str(g), font=font, fill=225)
				if selection[1] == 8:
					if selection[0]:
						draw.rectangle((72, 53, (len(str(b)) * 6) + 75, 63), outline=255, fill=255)
						draw.text((74,53), str(b), font=font, fill=0)
					else:
						draw.rectangle((72, 53, (len(str(b)) * 6) + 75, 63), outline=255, fill=0)
						draw.text((74,53), str(b), font=font, fill=225)
					draw.text((64,53), 'B', font=font, fill=225)
				else:
					draw.text((64,53), 'B:', font=font, fill=225)
					draw.text((74,53), str(b), font=font, fill=225)
				if selection[1] == 9:
					if selection[0]:
						draw.rectangle((104, 53, (len(str(w)) * 6) + 107, 63), outline=255, fill=255)
						draw.text((106,53), str(w), font=font, fill=0)
					else:
						draw.rectangle((104, 53, (len(str(w)) * 6) + 107, 63), outline=255, fill=0)
						draw.text((106,53), str(w), font=font, fill=225)
					draw.text((96,53), 'W', font=font, fill=225)
				else:
					draw.text((96,53), 'W:', font=font, fill=225)
					draw.text((106,53), str(w), font=font, fill=225)
				disp.image(image)
				Myassistant.refrech_error()
				buton = 20000
				while buton > 0 and not self.al:
					self.veil = 0
					if not len(self.buton) == 0:
						if self.buton[0] == 0 :
							del self.buton[0]
							cont = False
							buton = 0
						elif self.buton[0] == 1 :
							del self.buton[0]
							if selection[1] == 2:
								ledsearchaff = [['All','All']]
								for sdna in name_wifi_led:
									ledsearchaff.append([str(sdna),str(sdna)])
								name = Myassistant.select_list(self,ledsearchaff,'select led strip')
								if name == None:
									name = 'All'
							elif selection[1] == 3:
								jgiush = []
								responscoled = flux_led.utils.get_color_names_list()
								for tey in responscoled:
									jgiush.append([tey,tey])
								efdgk = Myassistant.select_search_list(self,jgiush)
								if not efdgk == None:
									resultintero = flux_led.utils.color_object_to_tuple(efdgk)
									if name == 'All':
										for adress in listwifi:
											wifiled = listwifi[adress]
											if wifiled.brightness+10 > 255 :
												wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
											else:
												wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
									else:
										if brightnes+10 > 255:
											wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
										else:
											wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
									response = None
							elif selection[1] == 4:
								choicoco = Myassistant.select_list(self,[['Sunset','sunset'],['Sunrise','sunrise'],['Exit','exit']],'choice')
								delay = Myassistant.select_cursor(self,30,0,1,1,"'",'delay')
								if choicoco == 'sunset':
									start = Myassistant.select_cursor(self,100,0,5,100,"%",'start')
									stop = Myassistant.select_cursor(self,100,0,5,0,"%",'end')
									response = choicoco+','+str(start)+','+str(stop)+','+str(delay)
								elif choicoco == 'sunrise':
									start = Myassistant.select_cursor(self,100,0,5,0,"%",'start')
									stop = Myassistant.select_cursor(self,100,0,5,100,"%",'end')
									response = choicoco+','+str(start)+','+str(stop)+','+str(delay)
							elif selection[1] == 5:
								if not selection[0]:
									selection[0] = not selection[0]
									if name == 'All':
										for adress in listwifi:
											wifiled = listwifi[adress]
											try:
												eval('wifiled.' + str(coloraction[selectlist]))
											except:
												print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									else:
										try:
											eval('wifiled.' + str(coloraction[selectlist]))
										except:
											print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									ifwantreload = 0
									response = str(coloraction[selectlist])
								else:
									selection[0] = not selection[0]
									speed = Myassistant.select_cursor(self,100,0,5,100,"",'speed')
									ffgghhfg = str(coloraction[selectlist]).replace(',100)',','+str(speed)+')')
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											try:
												eval('wifiled.' + ffgghhfg)
											except:
												print('Failed to execute : "' + ffgghhfg + '"')
									else:
										try:
											eval('wifiled.' + ffgghhfg)
										except:
											print('Failed to execute : "' + ffgghhfg + '"')
									response = ffgghhfg
									ifwantreload = 0
							else:
								selection[0] = not selection[0]
						elif self.buton[0] == 2 :
							del self.buton[0]
							if selection[0]:
								if selection[1] == 0:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											if ison:
												wifiled.turnOff()
												response = 'turnOff()'
											else:
												wifiled.turnOn()
												response = 'turnOn()'
									else:
										if ison:
											wifiled.turnOff()
											response = 'turnOff()'
										else:
											wifiled.turnOn()
											response = 'turnOn()'
								elif selection[1] == 1:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if wifiled.brightness+10 > 255 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=255)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=wifiled.brightness+10)
									else:
										if brightnes+10 > 255:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=255)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=brightnes+10)
									response = None
								elif selection[1] == 6:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[0]+10 > 255 :
												wifiled.setRgbw(r=255,g=y[1],b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0]+10,g=y[1],b=y[2],w=y[3])
									else:
										if r+10 > 255:
											wifiled.setRgbw(r=255,g=g,b=b,w=w)
										else:
											wifiled.setRgbw(r=r+10,g=g,b=b,w=w)
									response = None
								elif selection[1] == 7:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[1]+10 > 255 :
												wifiled.setRgbw(r=y[0],g=255,b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1]+10,b=y[2],w=y[3])
									else:
										if g+10 > 255:
											wifiled.setRgbw(r=r,g=255,b=b,w=w)
										else:
											wifiled.setRgbw(r=r,g=g+10,b=b,w=w)
									response = None
								elif selection[1] == 8:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[2]+10 > 255 :
												wifiled.setRgbw(r=y[0],g=y[1],b=255,w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2]+10,w=y[3])
									else:
										if g+10 > 255:
											wifiled.setRgbw(r=r,g=g,b=255,w=w)
										else:
											wifiled.setRgbw(r=r,g=g,b=b+10,w=w)
									response = None
								elif selection[1] == 9:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[3]+10 > 255 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=255)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3]+10)
									else:
										if w+10 > 255:
											wifiled.setRgbw(r=r,g=g,b=b,w=255)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w+10)
									response = None
								elif selection[1] == 5:
									if not selectlist + 1 > len(colorlist)-1:
										selectlist = selectlist + 1
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											try:
												eval('wifiled.' + str(coloraction[selectlist]))
											except:
												print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									else:
										try:
											eval('wifiled.' + str(coloraction[selectlist]))
										except:
											print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									ifwantreload = 0
									response = str(coloraction[selectlist])
							else:
								if not selection[1] + 1 > 9:
									selection[1] = selection[1] + 1
								else:
									selection[1] = 0
						elif self.buton[0] == 3 :
							del self.buton[0]
							if selection[0]:
								if selection[1] == 0:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											if ison:
												wifiled.turnOff()
												response = 'turnOff()'
											else:
												wifiled.turnOn()
												response = 'turnOn()'
									else:
										if ison:
											wifiled.turnOff()
											response = 'turnOff()'
										else:
											wifiled.turnOn()
											response = 'turnOn()'
								elif selection[1] == 1:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if wifiled.brightness-10 < 0 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=0)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=wifiled.brightness-10)
									else:
										if brightnes-10 < 0:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=0)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=brightnes-10)
									response = None
								elif selection[1] == 6:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[0]-10 < 0 :
												wifiled.setRgbw(r=0,g=y[1],b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0]-10,g=y[1],b=y[2],w=y[3])
									else:
										if r-10 < 0:
											wifiled.setRgbw(r=0,g=g,b=b,w=w)
										else:
											wifiled.setRgbw(r=r-10,g=g,b=b,w=w)
									response = None
								elif selection[1] == 7:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[1]-10 < 0 :
												wifiled.setRgbw(r=y[0],g=0,b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1]-10,b=y[2],w=y[3])
									else:
										if g-10 < 0:
											wifiled.setRgbw(r=r,g=0,b=b,w=w)
										else:
											wifiled.setRgbw(r=r,g=g-10,b=b,w=w)
									response = None
								elif selection[1] == 8:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[2]-10 < 0 :
												wifiled.setRgbw(r=y[0],g=y[1],b=0,w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2]-10,w=y[3])
									else:
										if b-10 < 0:
											wifiled.setRgbw(r=r,g=g,b=0,w=w)
										else:
											wifiled.setRgbw(r=r,g=g,b=b-10,w=w)
									response = None
								elif selection[1] == 9:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[3]-10 < 0 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=0)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3]-10)
									else:
										if w-10 < 0:
											wifiled.setRgbw(r=r,g=g,b=b,w=0)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w-10)
									response = None
								elif selection[1] == 5:
									if not selectlist - 1 < 0:
										selectlist = selectlist - 1
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											try:
												eval('wifiled.' + str(coloraction[selectlist]))
											except:
												print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									else:
										try:
											eval('wifiled.' + str(coloraction[selectlist]))
										except:
											print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									ifwantreload = 0
									response = str(coloraction[selectlist])
							else:
								if not selection[1] - 1 < 0:
									selection[1] = selection[1] - 1
								else:
									selection[1] = 9
						ifwantreload = 0
						if not len(self.buton) == 0:
							buton = 5
						else:
							buton = 0
						self.veil = 0
					buton = buton - 1
			resoul = ['','']
			if name == 'All':
				resoul[0] = []
				for adress in ip_wifi_led:
					resoul[0].append(adress)
			else:
				resoul[0] = ip_wifi_led[name_wifi_led.index(name)]
			if response == 'turnOn()':
				resoul[1] = 'setModeDefault()'
			elif response == 'turnOff()':
				resoul[1] = 'setModeTurnOff()'
			elif 'sunset' in str(response):
				ret = response.split(',')
				resoul[1] = 'setModeSunset('+str(ret[1])+','+str(ret[2])+','+str(ret[3])+')'
			elif 'sunrise' in str(response):
				ret = response.split(',')
				resoul[1] = 'setModeSunrise('+str(ret[1])+','+str(ret[2])+','+str(ret[3])+')'
			elif 'setPresetPattern' in str(response):
				kdkd = response.split(',')
				shemode = kdkd[0].replace('setPresetPattern(','')
				spedmode = kdkd[1].replace(')','')
				resoul[1] = 'setModePresetPattern('+str(shemode)+','+str(spedmode)+')'
			else:
				if name == 'All':
					r = 0
					g = 0
					b = 0
					w = 0
					i = 0
					for adresr in listwifi:
						wifiled = listwifi[adresr]
						y = wifiled.getRgbw()
						r = r + y[0]
						g = g + y[1]
						b = b + y[2]
						w = w + y[3]
						i = i + 1
					r = round(r/i)
					g = round(g/i)
					b = round(b/i)
					w = round(w/i)
				else:
					wifiled = listwifi[name]
					y = wifiled.getRgbw()
					r = y[0]
					g = y[1]
					b = y[2]
					w = y[3]
				if w == 0:
					resoul[1] = 'setModeColor('+str(r)+','+str(g)+','+str(b)+')'
				else:
					resoul[1] = 'setModeWarmWhite('+str(w)+')'
			i = len(save_list_color) - 1
			while i > -1:
				wifiled = led.WifiLedBulb(ip_wifi_led[i])
				if save_list_color[i][4]:
					wifiled.turnOn()
					wifiled.setRgbw(r=save_list_color[i][0],g=save_list_color[i][1],b=save_list_color[i][2],w=save_list_color[i][3])
				else:
					wifiled.turnOff()
				i = i - 1
			return resoul
		except BrokenPipeError:
			self.veil = 0
			print('Failed : "led strip"')
			resoul = ['','']
			resoul[0] = []
			for adresr in ip_wifi_led:
				resoul[0].append(adress)
			resoul[1] = 'setModeDefault()'
			return resoul

	def select_led_strip_color_all(self):
		try:
			response = None
			ifwantreload = 0
			cont = True
			name = 'All'
			listwifi={}
			ip_wifi_led=[]
			name_wifi_led = []
			led = flux_led.__main__
			for wifi_led in settings.get('Led strips names'):
				listwifi[str(wifi_led[0])]=led.WifiLedBulb(wifi_led[1])
				name_wifi_led.append(wifi_led[0])
				ip_wifi_led.append(wifi_led[1])
			colorlist = []
			coloraction = []
			for color in settings.get('Custom colors'):
				colorlist.append(color[0])
				coloraction.append(color[1])
			selectlist = round((len(colorlist) - 1) / 2)
			selection = [False, 0]
			save_list_color = []
			for adresr in listwifi:
				wifiled = listwifi[adresr]
				y = wifiled.getRgbw()
				save_list_color.append([int(y[0]),int(y[1]),int(y[2]),int(y[3]),wifiled.is_on])
			r = 0
			g = 0
			b = 0
			w = 0
			for adresr in listwifi:
				wifiled = listwifi[adresr]
				if not wifiled.isOn():
					wifiled.turnOn()
			while cont and not self.al:
				image = Image.new('1', (disp.width,disp.height))
				draw = ImageDraw.Draw(image)
				if name == 'All':
					r = 0
					g = 0
					b = 0
					w = 0
					ison = False
					brightnes = 0
					i = 0
					for adresr in listwifi:
						wifiled = listwifi[adresr]
						wifiled.refreshState()
						y = wifiled.getRgbw()
						r = r + y[0]
						g = g + y[1]
						b = b + y[2]
						w = w + y[3]
						if wifiled.is_on:
							ison = True
						brightnes = brightnes + wifiled.brightness
						i = i + 1
					r = round(r/i)
					g = round(g/i)
					b = round(b/i)
					w = round(w/i)
					brightnes = round(brightnes/i)
				else:
					wifiled = listwifi[name]
					wifiled.refreshState()
					y = wifiled.getRgbw()
					r = y[0]
					g = y[1]
					b = y[2]
					w = y[3]
					ison = wifiled.is_on
					brightnes = wifiled.brightness
				brightnessim = Image.open('/home/pi/Google_Assistant/src/images/led_strip/brightness.jpg')
				brightnessim = brightnessim.resize((17,17))
				brightnessim = ImageOps.invert(brightnessim)
				image.paste(brightnessim, (28,12))
				draw.text(((127 - (len(name) * 6)) / 2,0), name, font=font, fill=225)
				if ison:
					if selection[1] == 0:
						if selection[0]:
							draw.rectangle((0, 15, (len(str('on')) * 6) + 2, 25), outline=255, fill=255)
							draw.text((2,15), 'on', font=font, fill=0)
						else:
							draw.rectangle((0, 15, (len(str('on')) * 6) + 2, 25), outline=255, fill=0)
							draw.text((2,15), 'on', font=font, fill=225)
					else:
						draw.text((2,15), 'on', font=font, fill=225)
				else:
					if selection[1] == 0:
						if selection[0]:
							draw.rectangle((0, 15, (len(str('off')) * 6) + 2, 25), outline=255, fill=255)
							draw.text((2,15), 'off', font=font, fill=0)
						else:
							draw.rectangle((0, 15, (len(str('off')) * 6) + 2, 25), outline=255, fill=0)
							draw.text((2,15), 'off', font=font, fill=225)
					else:
						draw.text((2,15), 'off', font=font, fill=225)
				if selection[1] == 1:
					if selection[0]:
						draw.rectangle((44, 15, (len(str(brightnes)) * 6) + 46, 25), outline=255, fill=255)
						draw.text((46,15), str(brightnes), font=font, fill=0)
					else:
						draw.rectangle((44, 15, (len(str(brightnes)) * 6) + 46, 25), outline=255, fill=0)
						draw.text((46,15), str(brightnes), font=font, fill=225)
				else:
					draw.text((46,15), str(brightnes), font=font, fill=225)
				if selection[1] == 2:
					draw.rectangle((74, 15, 88, 25), outline=255, fill=0)
				draw.line((76,17,86,17), fill=255)
				draw.line((76,19,86,19), fill=255)
				draw.line((76,21,86,21), fill=255)
				draw.line((76,23,86,23), fill=255)
				if selection[1] == 3:
					draw.rectangle((108, 15, (len(str('+')) * 6) + 110, 25), outline=255, fill=0)
				draw.text((110,15), '+', font=font, fill=225)
				xcenter = (127 - (len(colorlist[selectlist]) * 6)) / 2
				if selection[1] == 5:
					draw.rectangle((0, 29, 127, 48), outline=255, fill=0)
					if selection[0]:
						draw.rectangle((xcenter - 4, 31, (len(colorlist[selectlist]) * 6) + xcenter + 3, 46), outline=255, fill=0)
				i = selectlist - 1
				while i > -1:
					xcenter = xcenter - (12 + (len(colorlist[i]) * 6))
					i = i - 1
				draw.text((xcenter,33), "  ".join(colorlist), font=font, fill=225)
				if selection[1] == 6:
					if selection[0]:
						draw.rectangle((8, 53, (len(str(r)) * 6) + 11, 63), outline=255, fill=255)
						draw.text((10,53), str(r), font=font, fill=0)
					else:
						draw.rectangle((8, 53, (len(str(r)) * 6) + 11, 63), outline=255, fill=0)
						draw.text((10,53), str(r), font=font, fill=225)
					draw.text((0,53), 'R', font=font, fill=225)
				else:
					draw.text((0,53), 'R:', font=font, fill=225)
					draw.text((10,53), str(r), font=font, fill=225)
				if selection[1] == 7:
					if selection[0]:
						draw.rectangle((40, 53, (len(str(g)) * 6) + 43, 63), outline=255, fill=255)
						draw.text((42,53), str(g), font=font, fill=0)
					else:
						draw.rectangle((40, 53, (len(str(g)) * 6) + 43, 63), outline=255, fill=0)
						draw.text((42,53), str(g), font=font, fill=225)
					draw.text((32,53), 'G', font=font, fill=225)
				else:
					draw.text((32,53), 'G:', font=font, fill=225)
					draw.text((42,53), str(g), font=font, fill=225)
				if selection[1] == 8:
					if selection[0]:
						draw.rectangle((72, 53, (len(str(b)) * 6) + 75, 63), outline=255, fill=255)
						draw.text((74,53), str(b), font=font, fill=0)
					else:
						draw.rectangle((72, 53, (len(str(b)) * 6) + 75, 63), outline=255, fill=0)
						draw.text((74,53), str(b), font=font, fill=225)
					draw.text((64,53), 'B', font=font, fill=225)
				else:
					draw.text((64,53), 'B:', font=font, fill=225)
					draw.text((74,53), str(b), font=font, fill=225)
				if selection[1] == 9:
					if selection[0]:
						draw.rectangle((104, 53, (len(str(w)) * 6) + 107, 63), outline=255, fill=255)
						draw.text((106,53), str(w), font=font, fill=0)
					else:
						draw.rectangle((104, 53, (len(str(w)) * 6) + 107, 63), outline=255, fill=0)
						draw.text((106,53), str(w), font=font, fill=225)
					draw.text((96,53), 'W', font=font, fill=225)
				else:
					draw.text((96,53), 'W:', font=font, fill=225)
					draw.text((106,53), str(w), font=font, fill=225)
				disp.image(image)
				Myassistant.refrech_error()
				buton = 20000
				while buton > 0 and not self.al:
					self.veil = 0
					if not len(self.buton) == 0:
						if self.buton[0] == 0 :
							del self.buton[0]
							cont = False
							buton = 0
						elif self.buton[0] == 1 :
							del self.buton[0]
							if selection[1] == 2:
								ledsearchaff = [['All','All']]
								for sdna in name_wifi_led:
									ledsearchaff.append([str(sdna),str(sdna)])
								name = Myassistant.select_list(self,ledsearchaff,'select led strip')
								if name == None:
									name = 'All'
							elif selection[1] == 3:
								ffgddsj = Myassistant.select_list(self,[['Colors','color'],['Preset pattern','pattern'],['Exit','exit']],'choice')
								if ffgddsj == 'pattern':
									fgcolorpatname = ['seven color cross fade','red gradual change','green gradual change','blue gradual change','yellow gradual change','cyan gradual change','purple gradual change','white gradual change','red green cross fade','red blue cross fade','green blue cross fade','seven color strobe flash','red strobe flash','green strobe flash','blue strobe flash','yellow strobe flash','cyan strobe flash','purple strobe flash','white strobe flash','seven color jumping']
									fgcolorpat = ['setPresetPattern(0x25,100)','setPresetPattern(0x26,100)','setPresetPattern(0x27,100)','setPresetPattern(0x28,100)','setPresetPattern(0x29,100)','setPresetPattern(0x2a,100)','setPresetPattern(0x2b,100)','setPresetPattern(0x2c,100)','setPresetPattern(0x2d,100)','setPresetPattern(0x2e,100)','setPresetPattern(0x2f,100)','setPresetPattern(0x30,100)','setPresetPattern(0x31,100)','setPresetPattern(0x32,100)','setPresetPattern(0x33,100)','setPresetPattern(0x34,100)','setPresetPattern(0x35,100)','setPresetPattern(0x36,100)','setPresetPattern(0x37,100)','setPresetPattern(0x38,100)']
									collen = 0
									mixcolornamepat = []
									while collen < len(fgcolorpatname):
										mixcolornamepat.append([str(fgcolorpatname[collen]),str(fgcolorpat[collen])])
										collen = collen + 1
									presety = Myassistant.select_list(self,mixcolornamepat,'preset pattern')
									if not presety == None:
										if name == 'All':
											for adresr in listwifi:
												wifiled = listwifi[adresr]
												eval('wifiled.' + str(presety))
										else:
											eval('wifiled.' + str(presety))
										speed = Myassistant.select_cursor(self,100,0,5,100,"",'speed')
										presety = str(presety).replace(',100)',','+str(speed)+')')
										if name == 'All':
											for adresr in listwifi:
												wifiled = listwifi[adresr]
												eval('wifiled.' + str(presety))
										else:
											eval('wifiled.' + str(presety))
										response = str(presety)
								elif ffgddsj == 'color':
									jgiush = []
									responscoled = flux_led.utils.get_color_names_list()
									for tey in responscoled:
										jgiush.append([tey,tey])
									fdlghfdh = Myassistant.select_search_list(self,jgiush)
									if not fdlghfdh == None:
										resultintero = flux_led.utils.color_object_to_tuple(fdlghfdh)
										if name == 'All':
											for adresr in listwifi:
												wifiled = listwifi[adresr]
												if wifiled.brightness+10 > 255 :
													wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
												else:
													wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
										else:
											if brightnes+10 > 255:
												wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
											else:
												wifiled.setRgb(resultintero[0],resultintero[1],resultintero[2])
										response = None
							elif selection[1] == 5:
								if not selection[0]:
									selection[0] = not selection[0]
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											try:
												eval('wifiled.' + str(coloraction[selectlist]))
											except:
												print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									else:
										try:
											eval('wifiled.' + str(coloraction[selectlist]))
										except:
											print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									ifwantreload = 0
									response = str(coloraction[selectlist])
								else:
									selection[0] = not selection[0]
									ifwantreload = 0
							else:
								selection[0] = not selection[0]
						elif self.buton[0] == 2 :
							del self.buton[0]
							if selection[0]:
								if selection[1] == 0:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											if ison:
												wifiled.turnOff()
												response = 'turnOff()'
											else:
												wifiled.turnOn()
												response = 'turnOn()'
									else:
										if ison:
											wifiled.turnOff()
											response = 'turnOff()'
										else:
											wifiled.turnOn()
											response = 'turnOn()'
								elif selection[1] == 1:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if wifiled.brightness+10 > 255 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=255)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=wifiled.brightness+10)
									else:
										if brightnes+10 > 255:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=255)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=brightnes+10)
									response = None
								elif selection[1] == 6:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[0]+10 > 255 :
												wifiled.setRgbw(r=255,g=y[1],b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0]+10,g=y[1],b=y[2],w=y[3])
									else:
										if r+10 > 255:
											wifiled.setRgbw(r=255,g=g,b=b,w=w)
										else:
											wifiled.setRgbw(r=r+10,g=g,b=b,w=w)
									response = None
								elif selection[1] == 7:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[1]+10 > 255 :
												wifiled.setRgbw(r=y[0],g=255,b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1]+10,b=y[2],w=y[3])
									else:
										if g+10 > 255:
											wifiled.setRgbw(r=r,g=255,b=b,w=w)
										else:
											wifiled.setRgbw(r=r,g=g+10,b=b,w=w)
									response = None
								elif selection[1] == 8:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[2]+10 > 255 :
												wifiled.setRgbw(r=y[0],g=y[1],b=255,w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2]+10,w=y[3])
									else:
										if g+10 > 255:
											wifiled.setRgbw(r=r,g=g,b=255,w=w)
										else:
											wifiled.setRgbw(r=r,g=g,b=b+10,w=w)
									response = None
								elif selection[1] == 9:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[3]+10 > 255 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=255)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3]+10)
									else:
										if w+10 > 255:
											wifiled.setRgbw(r=r,g=g,b=b,w=255)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w+10)
									response = None
								elif selection[1] == 5:
									if not selectlist + 1 > len(colorlist)-1:
										selectlist = selectlist + 1
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											try:
												eval('wifiled.' + str(coloraction[selectlist]))
											except:
												print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									else:
										try:
											eval('wifiled.' + str(coloraction[selectlist]))
										except:
											print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									ifwantreload = 0
									response = str(coloraction[selectlist])
							else:
								if not selection[1] + 1 > 9:
									selection[1] = selection[1] + 1
									if selection[1] == 4:
										selection[1] = 5
								else:
									selection[1] = 0
						elif self.buton[0] == 3 :
							del self.buton[0]
							if selection[0]:
								if selection[1] == 0:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											if ison:
												wifiled.turnOff()
												response = 'turnOff()'
											else:
												wifiled.turnOn()
												response = 'turnOn()'
									else:
										if ison:
											wifiled.turnOff()
											response = 'turnOff()'
										else:
											wifiled.turnOn()
											response = 'turnOn()'
								elif selection[1] == 1:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if wifiled.brightness-10 < 0 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=0)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3],brightness=wifiled.brightness-10)
									else:
										if brightnes-10 < 0:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=0)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w,brightness=brightnes-10)
									response = None
								elif selection[1] == 6:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[0]-10 < 0 :
												wifiled.setRgbw(r=0,g=y[1],b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0]-10,g=y[1],b=y[2],w=y[3])
									else:
										if r-10 < 0:
											wifiled.setRgbw(r=0,g=g,b=b,w=w)
										else:
											wifiled.setRgbw(r=r-10,g=g,b=b,w=w)
									response = None
								elif selection[1] == 7:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[1]-10 < 0 :
												wifiled.setRgbw(r=y[0],g=0,b=y[2],w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1]-10,b=y[2],w=y[3])
									else:
										if g-10 < 0:
											wifiled.setRgbw(r=r,g=0,b=b,w=w)
										else:
											wifiled.setRgbw(r=r,g=g-10,b=b,w=w)
									response = None
								elif selection[1] == 8:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[2]-10 < 0 :
												wifiled.setRgbw(r=y[0],g=y[1],b=0,w=y[3])
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2]-10,w=y[3])
									else:
										if b-10 < 0:
											wifiled.setRgbw(r=r,g=g,b=0,w=w)
										else:
											wifiled.setRgbw(r=r,g=g,b=b-10,w=w)
									response = None
								elif selection[1] == 9:
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											y = wifiled.getRgbw()
											if y[3]-10 < 0 :
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=0)
											else:
												wifiled.setRgbw(r=y[0],g=y[1],b=y[2],w=y[3]-10)
									else:
										if w-10 < 0:
											wifiled.setRgbw(r=r,g=g,b=b,w=0)
										else:
											wifiled.setRgbw(r=r,g=g,b=b,w=w-10)
									response = None
								elif selection[1] == 5:
									if not selectlist - 1 < 0:
										selectlist = selectlist - 1
									if name == 'All':
										for adresr in listwifi:
											wifiled = listwifi[adresr]
											try:
												eval('wifiled.' + str(coloraction[selectlist]))
											except:
												print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									else:
										try:
											eval('wifiled.' + str(coloraction[selectlist]))
										except:
											print('Failed to execute : "' + str(coloraction[selectlist]) + '"')
									ifwantreload = 0
									response = str(coloraction[selectlist])
							else:
								if not selection[1] - 1 < 0:
									selection[1] = selection[1] - 1
									if selection[1] == 4:
										selection[1] = 3
								else:
									selection[1] = 9
						ifwantreload = 0
						if not len(self.buton) == 0:
							buton = 5
						else:
							buton = 0
						self.veil = 0
					buton = buton - 1
			resoul = ['','']
			if name == 'All':
				resoul[0] = []
				for adress in ip_wifi_led:
					resoul[0].append(adress)
			else:
				resoul[0] = ip_wifi_led[name_wifi_led.index(name)]
			if not response == None:
				resoul[1] = str(response)
			else:
				if name == 'All':
					r = 0
					g = 0
					b = 0
					w = 0
					i = 0
					for adresr in listwifi:
						wifiled = listwifi[adresr]
						y = wifiled.getRgbw()
						r = r + y[0]
						g = g + y[1]
						b = b + y[2]
						w = w + y[3]
						i = i + 1
					r = round(r/i)
					g = round(g/i)
					b = round(b/i)
					w = round(w/i)
				else:
					wifiled = listwifi[name]
					y = wifiled.getRgbw()
					r = y[0]
					g = y[1]
					b = y[2]
					w = y[3]
				if w == 0:
					resoul[1] = 'setRgb(r='+str(r)+',g='+str(g)+',b='+str(b)+')'
				else:
					resoul[1] = 'setRgbw(r='+str(r)+',g='+str(g)+',b='+str(b)+',w='+str(w)+')'
			i = len(save_list_color) - 1
			while i > -1:
				wifiled = led.WifiLedBulb(ip_wifi_led[i])
				if save_list_color[i][4]:
					wifiled.turnOn()
					wifiled.setRgbw(r=save_list_color[i][0],g=save_list_color[i][1],b=save_list_color[i][2],w=save_list_color[i][3])
				else:
					wifiled.turnOff()
				i = i - 1
			return resoul
		except BrokenPipeError:
			self.veil = 0
			print('Failed : "led strip"')
			resoul = ['','']
			resoul[0] = []
			for adress in ip_wifi_led:
				resoul[0].append(adress)
			resoul[1] = 'turnOn()'
			return resoul

	def set_word_aff(self, i):
		lines = str(i).split(" ")
		conta = True
		i = 0
		h = []
		while conta:
			char = ''
			charlen = 0
			conti = True
			while conti:
				if char == '':
					char = char + lines[i]
				else:
					char = char + ' ' + lines[i]
				charlen = charlen + len(lines[i])
				i = i + 1
				if not len(lines)-1 < i:
					if charlen + 1 + len(lines[i]) > 19:
						conti = False
				else:
					conti = False
			h.append(char)
			if len(lines)-1 < i:
				conta = False
		image = Image.new('1', (disp.width,disp.height))
		draw = ImageDraw.Draw(image)
		if len(h) == 1:
			draw.text(((128 - (len(h[0]) * 6)) / 2,26),h[0], font=font, fill=225)
		else:
			jjg = (64 - (len(h) * 12)) / len(h)
			for uut in h:
				draw.text((((128 - (len(uut) * 6)) / 2,jjg)),uut, font=font, fill=225)
				jjg = jjg + 12
		disp.image(image)
		Myassistant.refrech_error()
		self.veil = settings.get("Time stand by")*2+1

if __name__ == '__main__':
	try:
		Myassistant().main()
	except:
		errort = traceback.format_exc().split('\n')
		error = errort[len(errort)-4].replace('  ','') + ': '
		error = 'File ' + error.split('/')[len(error.split('/'))-1].replace('"','')
		error = error + errort[len(errort)-2]
		if 'KeyboardInterrupt' in error:
			exit(0)
		else:
			print(error)
			filerror = open('/home/pi/Google_Assistant/src/ga_error','a')
			filerror.write(time.strftime("%d-%m-%Y %H:%M:%S    ")+str(error)+'\n')
			filerror.close()
			if settings.get("Sense hat"):
				Myassistant.logo_high()
				Myassistant.logo_low()
			if settings.get("Lcd screen"):
				lines = str(error).split(" ")
				conta = True
				i = 0
				h = []
				while conta:
					char = ''
					charlen = 0
					conti = True
					while conti:
						if char == '':
							char = char + lines[i]
						else:
							char = char + ' ' + lines[i]
						charlen = charlen + len(lines[i])
						i = i + 1
						if not len(lines)-1 < i:
							if charlen + 1 + len(lines[i]) > 19:
								conti = False
						else:
							conti = False
					h.append(char)
					if len(lines)-1 < i:
						conta = False
				image = Image.new('1', (disp.width,disp.height))
				draw = ImageDraw.Draw(image)
				if len(h) == 1:
					draw.text(((128 - (len(h) * 6)) / 2,26),h[0], font=font, fill=225)
				else:
					jjg = (64 - (len(h) * 12)) / len(h)
					for uut in h:
						draw.text((((128 - (len(uut) * 6)) / 2,jjg)),uut, font=font, fill=225)
						jjg = jjg + 12
				disp.clear()
				Myassistant.refrech_error()
				disp.image(image)
				Myassistant.refrech_error()
				i = 1000
				while i > 0:
					if GPIO.input(bsquare) == 0 or GPIO.input(bround) == 0 or GPIO.input(brigt) == 0 or GPIO.input(bleft) == 0:
						i = 0
					time.sleep(0.1)
					i = i - 1
				disp.clear()
				Myassistant.refrech_error()
				if i == -1:
					image = Image.new('1', (disp.width,disp.height))
					draw = ImageDraw.Draw(image)
					draw.text((0,0), 'stop Google Assistant', font=font, fill=255)
					draw.text((30,15), 'restart Google A', font=font, fill=255)
					draw.text((55,30), 'shutdown RPI', font=font, fill=255)
					draw.text((85,45), 'nothing', font=font, fill=255)
					draw.line((5,15,5,63), fill=255)
					draw.line((45,30,45,63), fill=255)
					draw.line((80,45,80,63), fill=255)
					draw.line((120,60,120,63), fill=255)
					disp.image(image)
					Myassistant.refrech_error()
					i = 1000
					while i > 0:
						if GPIO.input(bleft) == 0:
							i = -4
							disp.clear()
							Myassistant.refrech_error()
							os.system("sudo systemctl stop Google_Assistant-ok-google.service")
						elif GPIO.input(brigt) == 0:
							i = -4
							disp.clear()
							Myassistant.refrech_error()
							os.system("sudo systemctl restart Google_Assistant-ok-google.service")
						elif GPIO.input(bround) == 0:
							i = -4
							disp.clear()
							Myassistant.refrech_error()
							os.system("sudo halt")
						elif GPIO.input(bsquare) == 0:
							i = -4
						time.sleep(0.1)
						i = i - 1
					if not i == -5:
						disp.clear()
						Myassistant.refrech_error()
						os.system("sudo systemctl stop Google_Assistant-ok-google.service")
				else:
					disp.clear()
					Myassistant.refrech_error()
					os.system("sudo systemctl stop Google_Assistant-ok-google.service")
