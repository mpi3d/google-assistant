import vlc
import os
import random

class vlcplayer():

    def __init__(self):
        self.playback = [False,'']
        Instance=vlc.Instance()
        self.player = Instance.media_player_new()

    def play_audio_file(self,fname):
        print('Vlc play ' + str(fname))
        if vlcplayer.is_vlc_playing(self):
            vlcplayer.stop_vlc(self)
        self.playback = ['file',str(fname.split("/")[len(fname.split("/")) - 1])]
        Instance=vlc.Instance()
        self.player=Instance.media_player_new()
        self.player.set_mrl(fname)
        self.player.play()

    def play_audio_folder(self,folder):
        print('Vlc play ' + str(folder))
        if vlcplayer.is_vlc_playing(self):
            vlcplayer.stop_vlc(self)
        self.playback = ['list',str(folder.split("/")[len(folder.split("/")) - 1])]
        files = []
        for path, dirs, file in os.walk(folder):
            for filename in file:
                files.append(path + '/' + filename)
        i = len(files) - 1
        while i > -1 :
            if not ".mp3" in str(files[i]) :
                del files[i]
            i = i - 1
        if not len(files) == 0 :
            sefulfiles = []
            while len(files) > 0:
                u = random.randint(0,len(files)-1)
                sefulfiles.append(files[u])
                del files[u]
            instance = vlc.Instance()
            self.player = instance.media_list_player_new()
            media_list = instance.media_list_new(sefulfiles)
            self.player.set_media_list(media_list)
            self.player.set_playback_mode(vlc.PlaybackMode.loop)
            self.player.play()

    def stop_vlc(self):
        if vlcplayer.is_vlc_playing(self):
            self.player.stop()
            self.playback = [False,'']

    def next_vlc(self):
        if self.playback[0] == 'list':
            self.player.next()

    def previous_vlc(self):
        if self.playback[0] == 'list':
            self.player.previous()

    def pause_vlc(self):
        if vlcplayer.is_vlc_playing(self):
            if not self.player.get_state()==vlc.State.Paused:
                self.player.pause()

    def resume_vlc(self):
        if vlcplayer.is_vlc_playing(self):
            if self.player.get_state()==vlc.State.Paused:
                self.player.pause()

    def get_title(self):
        return self.playback[1]

    def is_pause(self):
        if vlcplayer.is_vlc_playing(self):
            if self.player.get_state()==vlc.State.Paused:
                return True
            else :
                return False
        else:
            return True

    def is_vlc_playing(self):
        if self.player.get_state()==vlc.State.Playing:
            return True
        else:
            if self.player.get_state()==vlc.State.Paused:
                return True
            else:
                return False
