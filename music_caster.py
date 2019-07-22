from bs4 import BeautifulSoup
from contextlib import suppress
import ctypes
import getpass
from glob import glob
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
from mutagen.easyid3 import EasyID3
import os
from pathlib import Path
import pychromecast.controllers.media
from pychromecast.error import UnsupportedNamespace
import pychromecast
from pydub.utils import mediainfo
from pygame import mixer as local_music_player  # https://www.pygame.org/docs/ref/music.html
from pynput.keyboard import Listener
import socket
# import PySimpleGUIQt as sg
import PySimpleGUI as Sg
# noinspection PyPep8Naming
import PySimpleGUIWx as sg
import wx
from random import shuffle
import requests
from subprocess import Popen
from time import time
import threading
import win32api
import win32com.client
import win32event
from winerror import ERROR_ALREADY_EXISTS
import sys

mutex = win32event.CreateMutex(None, False, 'name')
last_error = win32api.GetLastError()
if last_error == ERROR_ALREADY_EXISTS: sys.exit()  # one instance

CURRENT_VERSION = '4.3.0'
starting_dir = os.path.dirname(os.path.realpath(__file__))
os.chdir('C:/')
PORT = 2001
while True:
    try:
        httpd = HTTPServer(('0.0.0.0', PORT), SimpleHTTPRequestHandler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()  # TODO: multiprocess
        # print('Running server')
        break
    except OSError:
        PORT += 1

user32 = ctypes.windll.user32
# SCREEN_WIDTH, SCREEN_HEIGHT = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
home_music_dir = str(Path.home()).replace('\\', '/') + '/Music'

settings = {  # default settings
    'previous device': None,
    'comments': ['Edit only the variables below', 'Restart the program after editing this file!'],
    'auto update': True,
    'run on startup': True,
    'notifications': True,
    'volume': 100,
    'local volume': 100,
    'music directories': [home_music_dir],
    'sample music directories': [
        'C:/Users/maste/Documents/MEGAsync/Music',
        'Put in a valid path',
        'First path is the default directory when selecting a file to play. FOR NOW'
    ],
    'playlists': {},
    'playlists_example': {'NAME': ['PATHS']}
}
settings_file = f'{starting_dir}/settings.json'


def save_json():
    with open(settings_file, 'w') as outfile:
        json.dump(settings, outfile, indent=4)


# check if settings file is valid
try:
    with open(settings_file) as json_file:
        loaded_settings = json.load(json_file)
        save_settings = False
        for k, v in settings.items():
            if k not in loaded_settings:
                loaded_settings[k] = v
                save_settings = True
        settings = loaded_settings
    if save_settings: save_json()
except FileNotFoundError:
    save_json()


if settings['auto update']:
    github_url = 'https://github.com/elibroftw/music-caster/releases'
    try:
        html_doc = requests.get(github_url).text
        soup = BeautifulSoup(html_doc, features='html.parser')
        release_entry = soup.find('div', class_='release-entry')
        latest_version = release_entry.find('a', class_='muted-link css-truncate')['title'][1:]
        major, minor, patch = (int(x) for x in CURRENT_VERSION.split('.'))
        lt_major, lt_minor, lt_patch = (int(x) for x in latest_version.split('.'))
        if (lt_major > major or lt_major == major and lt_minor > minor
                or lt_major == major and lt_minor == minor and lt_patch > patch):
            os.chdir(starting_dir)
            if settings.get('DEBUG') or os.path.exists('updater.py'):
                Popen('python updater.py')
            elif os.path.exists('Updater.exe'):
                os.startfile('Updater.exe')
            elif os.path.exists('updater.pyw'):
                Popen('pythonw updater.pyw')
            sys.exit()
    except requests.ConnectionError:  # Should handle more errors?
        pass
        # start a thread to check every 20 seconds


USER_NAME = getpass.getuser()
shortcut_path = f'C:/Users/{USER_NAME}/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Music Caster.lnk'


def startup_setting():
    run_on_startup = settings['run on startup']
    shortcut_exists = os.path.exists(shortcut_path)
    if run_on_startup and not shortcut_exists and not settings.get('DEBUG'):
        shell = win32com.client.Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        if getattr(sys, 'frozen', False):  # Running in a bundle
            # C:\Users\maste\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
            target = f'{starting_dir}\\Music Caster.exe'
        else:  # set shortcut to python script; __file__
            bat_file = f'{starting_dir}\\music_caster.bat'
            if os.path.exists(bat_file):
                with open('music_caster.bat', 'w') as f:
                    f.write(f'pythonw {os.path.basename(__file__)}')
            target = bat_file
            shortcut.IconLocation = f'{starting_dir}\\icon.ico'
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = starting_dir
        shortcut.WindowStyle = 1  # 7 - Minimized, 3 - Maximized, 1 - Normal
        shortcut.save()
    elif not run_on_startup and shortcut_exists:
        os.remove(shortcut_path)


startup_setting()

update_devices = False
chromecasts = []
device_names = ['1. Local Device']
cast = None


def chromecast_callback(chromecast):
    global update_devices, cast
    previous_device = settings['previous device']
    if str(chromecast.device.uuid) == previous_device and cast != chromecast:
        cast = chromecast
        cast.wait()
    chromecasts.append(chromecast)
    devices = len(device_names)
    device_names.append(f'{devices + 1}. {chromecast.device.friendly_name}')
    update_devices = True


local_music_player.init(44100, -16, 2, 2048)
# volume = settings['volume']/100
# print('Retrieving chromecasts...')
# chromecasts = pychromecast.get_chromecasts()
stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
menu_def_1 = ['', ['Refresh Devices', 'Select &Device', device_names, 'Settings', 'Play &File', 'Play All', 'E&xit']]

menu_def_2 = ['', ['Refresh Devices', 'Select &Device', device_names, 'Settings', 'Play &File', 'Play All',
                   'Next Song', 'Previous Song', 'Pause', 'E&xit']]

menu_def_3 = ['', ['Refresh Devices', 'Select &Device', device_names, 'Settings', 'Play &File', 'Play All',
                   'Next Song', 'Previous Song', 'Resume', 'E&xit']]

unfilled_logo_data = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACWElEQVRo3u2ZsUsbURzHo2Bc0kkMDoYirRkcpEu7NtAubo7ZPXDo6qaL\nkyUIQtshkE6CkA79C4SqWIiLi5N2iBQ7WgRvUNvGj0OG/n737kLt9d476PuOvx9JPnn3e9/v3b1C\nwcvLy8srSQwR0CHEpi7pEDAUhzPBNq60zYS5Ou5w+kh6lQhwrUADHTgH6mig0DlQqIGErO7spN/1\nQB7IA3kg10DObnk8kAf6b4C44ZxTDmmzSp3JXPkQAF9o8oLh/AD1dcYalTwBAdzQ4lGegAB+sk4p\nT0AA35i3CVRkjClqLPKGI24ToN4x6sSHGGeB3Visw3875PcyRqb5EAN1xoxDp+Ypnwyk7zxzGh3M\n0TWQZhwCFQqMsWtcuEq2uyzkhB22WGE29oMjNI3xHrXlQ1024rB4xS9tAjaNsccmD2OQtObtOvU1\nDYqRL2hG3LtkEwjgM+XILOnxXrefZV95EtlxXRW7j7MBKlGlxhL79Mx3WxGkOdV9n7EPUabBlbFK\n+sJJ9/6RxpH+NFwrfDRmqagCRWbcaytOzXIkWBuq21auPWwlOqgrpGvpS0yr3ktLWcayWqNN1ZPb\nv5lFlh3TMv+pmqWeDBQW5ENTdj60RzUy3nLHbai7SnnRJrMzxgueq05Dxq7qHIlOPUunvpCrRFlZ\npbxob0V99Z7PMDEnZ4OiY0/19kVnRdQXRb2dGqgzOMvEeLMk6luiXpO3a6mBgsFArYQf3hH1KVE/\nTQlkHOBFdSx6VVE/Ubn/W+epgGKOOAecXvEgoV6UryT+EihMPAT28vLy8urrDgm99Mb0O5qlAAAA\nJXRFWHRkYXRlOmNyZWF0ZQAyMDE5LTA3LTE0VDAwOjQ2OjMyKzAwOjAwaWwEjwAAACV0RVh0ZGF0\nZTptb2RpZnkAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMBgxvDMAAAAASUVORK5CYII=\n'
filled_logo_data = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAQAAAD/5HvMAAAABGdBTUEAALGPC/xhBQAAACBjSFJN\nAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAAAmJLR0QA/4ePzL8AAAAHdElN\nRQfjBw4ALiA+kkFLAAACxUlEQVRo3u2ZT0hUURSHn0bjxtpIYqCElLNwEW1yWYO1yF3L2fvARVs3\nqRtX2SAIJTFgK0HQRdJeaBSDaePGlYaoYUtD8C3ScvpaKHTOfe8NOu/fQPe3PGec+bz3nN+57z7H\nsbKysrIKEy24VPFIU8dUcWkJwulihay0Qpd/dbLDOUfSq4RL1nI10JfMgaoayMscyNNAQql2dtjv\nWiAL9N8AJdHfFigWoMvscXMAnTUb0G3G2GkioIuz0iDLTQR08acDVJoKyHEch2dsptX2pxyyxwaL\nTFKkOxQpx2tqKfsQAF8p84TWQKhH7KcPdK4DXtETgHSTj9kAAZwyx10fUivvsgIC+M007T6oseyA\nAL7z3IfkJgeUo4NeCozwhk3+hHzXLG3RV6kBH+IWw6wGYm2YRX71WmrYGOljKQDqgH71qWtX7bho\nw/Uhn3zf+IMBwwT2Ux0dDLHrQ+o3rLKW6iyjg1XfxqlaYiruLvPYpsICE9wPRLpO2VfebapLN5Pz\noV1mgrB4YZwfZ42TQKLGWGOeOwFIWsoqL3teatypTyiRM5DKhnu3qyNcCqPjM51GLenynlbZ5TRm\n2TceGB23q8buPZEbjA+onTwFRlkPcBTPQBpS2ffqcWAndh+ikxI/faukN0669y/pSLxMZrj28MFX\nSzk1UOSMm1LPcWcJOTXjxmAtqeyicu3W2K9jAj9cVEgn0pfoU7mnqQA5DuNqjeZVTrZ/Of4LK48t\n5vz/qaqlmhwoDMuHpuRu0NbIG+UtO25GnSrlpnUnd6V3xGOVKcmxqzJyvhcTvGPkSK4Sncoq5aa9\nFfHJyNdcx/VGx5rKrYvMhIiPiPhiZKBq/VkmyptREV8Q8YI8rkUGcusDzYX8cEXEe0V8LyKQ7wWe\nqS2Ry4v4tpr7/3QYCSjgFWedt1fcCInn5JVEg0Be6EtgKysrK6tz/QVPmZ3Bw5RmTgAAACV0RVh0\nZGF0ZTpjcmVhdGUAMjAxOS0wNy0xNFQwMDo0NjozMiswMDowMGlsBI8AAAAldEVYdGRhdGU6bW9k\naWZ5ADIwMTktMDctMTRUMDA6NDY6MzIrMDA6MDAYMbwzAAAAAElFTkSuQmCC\n'
window_icon = b'iVBORw0KGgoAAAANSUhEUgAAAEgAAABICAYAAABV7bNHAAAAAXNSR0IArs4c6QAABV9JREFUeAHt\nWUtsVUUYvhQsG0qMDaQQTUPwEVkQN7gsTXGhG+JO9zRhwZaN1o1xISEkJmIISWVDQoILG1iXtNfY\nUBe6MRrAR1OjK+MjqSaK2ML3lU47d/J/M+fce8+B9s6ffDlzvvlf83fOPG4bjSy5ArkCuQK5ArkC\nuQK5ArkCuQIlKrANuuPAPPAXcH+LYmltjBwrx1xIhqA1DWzVoqhxccwce1RYxV4sjisaxx6dSZxq\nTrlXn6yBlC/Q06uFcePmursu4XTigrxrvbc3G39j2ANu6GGBWEVLQj1LZzNyyfH2bcZR1ZlzLlCi\n2rlAuUCJCiS68wxKFGhHoj/VrXaBlF3d/W3vwnkGJf5UuUCJAoWfWNtTMRFn03Z3OoOWN+3ICybe\naYGeQZwJ4MeC8XpWjZ/mGDAFuFvx4/RUfxiVo9LvCv8yvMwCKvij4NXAVC5Kv6v8q/D2NaCSqJNX\nA1M5rOuHu9Zd9PA3IeIP4HvgDnALmAN+AcpIP5TfA04Dna53ZeKGuuE4XT8LZInST/61v4O3i8Ax\noMyAR6C/CKi/WNU8Qpui4prKJJWBxf8M/fcB7mRFZDeUrgGWr6o5lZ+Kq/TbSp6f5SRwUHrd6OCs\nuwCoxKriNzJobal4rVremzIowt+Dn3NAkd+034ZeEZ/d0vGG2NJU/luU/BdlUIbnQv6671S0x8GX\n8duJrkhBxlf6De46g8ABYBQ4CXwIcLteAcok+RH0dwIxqWsmqRzUeJR+lN+D3hNAEyharK+gm1rE\n61iTkIYpXS2QH+E5vHwCFCkUd7tDvnHQ3o73qne3IOT6a2UFchGOoDEDqECO/x06vIIo4RFgEXD6\n3X6quCqO0m+bfw2WC4AKSJ5Fis2kEfQvJ3zE/Mf64NYUZWMqd0pycW8CKih5fm6xNelMwj7mO9YH\nt6YoG1OZJO9gvHvNAleAd4DDQFF5Aoq8iqjA5Llwq92Nu2gVF1y4NUXlaSqTVAb8fD4AihbrFHT/\nj/jjEUAJfwVQebTLq1jKn9JPJsY14jIwLD1sdLBIKgHyscPkbMI25tfq28iqtWXpkpOiDEL+X3g4\nC/CTiEnsc+OJW11LuOOFMTt5Vzkqn0q/dFJz8LRXems0uCY1AZUI725KptCh7MryKobyo/TbSugn\neHtJenx4dVFHAF5wnxW2Y+DVAMryIoT0r/RXp/zz6B0F+Cvg50CRswl3v1iReE5Sg/oYfZbwV70f\nAGVXhrf8k1M+lL7J8xPievMPoByS50yKfW4zwv4/8Ops9JawieVh9cGNKZYuubaEg/gUUE7Jc01S\nCzevJSvCngdES/aBjB0XYrn4fZZvcr6O31b6hfgJaKmBMghnm5Kr6PATcW2esPuUUYW8ix8+Ow75\nJjyoIvEIMCwi8FcAZfeKsKmSDgvj3rsSkzPJOQyfPEwqaaIj1Oc7z0x1i5UHOSncjW4Dk0CRv6ha\nk7jzqWvJCfRZifFfSnWLlUe0QKHBZ8iY274SLtxqd+PdzRL+Mqk+s6ctgwq5cLzuXYZ0Cv7zT2gf\nlRYPF2Vf37UXIjbqxs61rU5xuYZPmUOo6N5ZJDWTePbhJ+V0/af6zM4L/XfBK/H9Vtle8hMourU+\nCSOuS5b8CvKm1QHuuOC/EfwLgq+T/tYPVrRAtBkB1MJ93XfqtV/02n6TP8pZwmPAo5ZLfgJlCkS7\nN3xjr/2l1/ab+/0Xr81riSVPWWSN3A3EailQGDv1bfMIYAnXJ8tWzZRBof+b5XyNs/x3k5tGnKFI\n/NWuVECekywZAGnZKv1+oX/Xcr7GWf475ZjfPDAObFuLkx+5ArkCuQK5ArkCuQK5ArkCuQLpCjwA\nMCQ8Gt1a8k0AAAAASUVORK5CYII=\n'

tray = sg.SystemTray(menu=menu_def_1, data_base64=unfilled_logo_data, tooltip='Music Caster')
notifications_enabled = settings['notifications']
if notifications_enabled: tray.ShowMessage('Music Caster', 'Music Caster is running in the tray', time=500)
music_directories = settings['music directories']
if not music_directories:
    music_directories = settings['music directories'] = [home_music_dir]
    save_json()
DEFAULT_DIR = music_directories[0]

music_queue = []
done_queue = []
# noinspection PyTypeChecker
mc: pychromecast.controllers.media.MediaController = None
song_end = song_length = song_position = song_start = 0
playing_status = 'NOT PLAYING'


# Styling
fg = '#aaaaaa'
bg = '#121212'
font_family = 'SourceSans', 11
button_color = ('black', '#4285f4')


def play_file(filename, position=0):
    global mc, song_start, song_end, playing_status, song_length, song_position, volume
    hostname = socket.gethostname()    
    ipv4_address = socket.gethostbyname(hostname)
    song_position = position
    media_info = mediainfo(filename)
    song_length = float(media_info['duration'])
    # tags = media_info['TAG']
    # title = tags['title']
    # artist = tags['artist']
    # album = tags['album']
    # noinspection PyUnusedLocal
    title = artist = album = 'Unknown'
    # song_length = MP3(filename).info.length
    volume = settings['volume']/100
    with suppress(Exception):
        title = EasyID3(filename)['title'][0]
        artist = EasyID3(filename)['artist']
        artist = ', '.join(artist)
        album = EasyID3(filename)['album']
    if cast is None:
        mc = None
        sampling_rate = int(media_info['sample_rate'])
        local_music_player.quit()
        local_music_player.init(sampling_rate, -16, 2, 2048)
        local_music_player.music.load(filename)
        local_music_player.music.set_volume(volume)
        local_music_player.music.play(start=position)
        song_start = time()
        song_end = song_start + song_length - position
        playing_status = 'PLAYING'
    else:
        uri_safe = Path(filename).as_uri()[11:]
        url = f'http://{ipv4_address}:{PORT}/{uri_safe}'
        cast.wait()
        cast.set_volume(volume)
        mc = cast.media_controller
        if mc.is_playing or mc.is_paused:
            mc.stop()
            mc.block_until_active(5)
        music_metadata = {'metadataType': 3, 'albumName': album, 'title': title, 'artist': artist}
        mc.play_media(url, 'audio/mp3', current_time=position, metadata=music_metadata)
        # mc.play_media(url, 'audio/mp3', current_time=position, metadata=music_metadata, thumb=url)
        # TODO: not sure if thumb actually works, test on my Chromecast!
        # Otherwise, you could extract image and upload it / store it in a directory
        mc.block_until_active()
        if position > 0:
            mc.seek(position)
        song_start = time()
        song_end = song_start + song_length - position
        playing_status = 'PLAYING'
    if notifications_enabled: tray.ShowMessage('Music Caster', f"Playing: {artist.split(', ')[0]} - {title}", time=500)


def pause():
    global tray, playing_status, song_position
    if playing_status == 'PLAYING':
        tray.Update(menu=menu_def_3, data_base64=unfilled_logo_data)
        # tray: sg.SystemTray
        try:
            if mc is not None:
                mc.update_status()
                mc.pause()
                song_position = mc.status.adjusted_current_time
            else:
                song_position += local_music_player.music.get_pos()/1000
                local_music_player.music.pause()
            playing_status = 'PAUSED'
        except UnsupportedNamespace:
            song_position = 0
            playing_status = 'NOT PLAYING'


def resume():
    global tray, playing_status, song_end, song_position
    if playing_status == 'PAUSED':
        tray.Update(menu=menu_def_2, data_base64=filled_logo_data)
        try:
            if mc is not None:
                mc.update_status()
                mc.play()
                mc.block_until_active()
            else:
                local_music_player.music.unpause()
            song_end = time() + song_length - song_position
            playing_status = 'PLAYING'
        except UnsupportedNamespace:
            play_file(music_queue[0], position=song_position)


def next_song():
    global playing_status
    if music_queue:
        playing_status = 'NOT PLAYING'
        song = music_queue.pop(0)
        done_queue.append(song)
        if music_queue:
            play_file(music_queue[0])


def previous():
    global playing_status
    # NOTE: restart song if current_time > 5?
    if done_queue:
        playing_status = 'NOT PLAYING'
        song = done_queue.pop()
        music_queue.insert(0, song)
        play_file(song)


def on_press(key):
    global keyboard_command
    if str(key) == '<179>':
        if playing_status == 'PLAYING':
            keyboard_command = 'Pause'
            # pause()
        elif playing_status == 'PAUSED':
            keyboard_command = 'Resume'
            # resume()
    elif str(key) == '<176>':
        keyboard_command = 'Next Song'
        # next_song()
    elif str(key) == '<177>':
        keyboard_command = 'Previous Song'
        # previous()


keyboard_command = None
settings_window = None
settings_active = False
listener_thread = Listener(on_press=on_press)
listener_thread.start()

while True:
    menu_item = tray.Read(timeout=0)
    # if menu_item != '__TIMEOUT__':
    #     print(menu_item)
    if menu_item == 'Refresh Devices':
        update_devices = True
        stop_discovery()
        chromecasts.clear()
        device_names.clear()
        device_names.append('1. Local Device')
        stop_discovery = pychromecast.get_chromecasts(blocking=False, callback=chromecast_callback)
    if update_devices:
        update_devices = False
        if playing_status == 'PLAYING': tray.Update(menu=menu_def_2)
        elif playing_status == 'PAUSED': tray.Update(menu=menu_def_3)
        else: tray.Update(menu=menu_def_1)
    elif menu_item.split('.')[0].isdigit():  # if user selected a device
        device = ' '.join(menu_item.split('.')[1:])[1:]
        try:
            new_cast = next(cc for cc in chromecasts if cc.device.friendly_name == device)
        except StopIteration:
            new_cast = None
        if cast != new_cast:
            cast = new_cast
            if cast is None:
                settings['previous device'] = None
            else:
                settings['previous device'] = str(cast.uuid)
                cast.wait()
                cast.set_volume(settings['volume']/100)
            save_json()
            current_pos = 0
            
            if local_music_player.music.get_busy():
                current_pos = song_position + local_music_player.music.get_pos()/1000
                local_music_player.music.stop()
            elif mc is not None:
                mc.update_status()  # Switch device without playback loss
                current_pos = mc.status.adjusted_current_time
                mc.stop()
            
            if playing_status == 'PLAYING':
                play_file(music_queue[0], position=current_pos)
    elif menu_item == 'Settings' and not settings_active:
        settings_active = True
        # RELIEFS: RELIEF_RAISED RELIEF_SUNKEN RELIEF_FLAT RELIEF_RIDGE RELIEF_GROOVE RELIEF_SOLID
        settings_layout = [
            [Sg.Text(f'Music Caster Version {CURRENT_VERSION} by Elijah Lopez', text_color=fg, background_color=bg, font=font_family)],
            [Sg.Checkbox('Auto Update', default=settings['auto update'], key='auto update', text_color=fg,  background_color=bg, font=font_family, enable_events=True)],
            [Sg.Checkbox('Run on Startup', default=settings['run on startup'], key='run on startup', text_color=fg, background_color=bg, font=font_family, enable_events=True)],
            [Sg.Checkbox('Enable Notifications', default=settings['notifications'], key='notifications', text_color=fg, background_color=bg, font=font_family, enable_events=True)],
            [Sg.Slider((0, 100), default_value=settings['volume'], orientation='horizontal', key='volume', tick_interval=5, enable_events=True, background_color='#4285f4', text_color='black', size=(50, 15))],
            [Sg.Listbox(music_directories, size=(41, 5), select_mode=Sg.SELECT_MODE_SINGLE , text_color=fg, key='music_dirs', background_color=bg, font=font_family, enable_events=True),
             Sg.Frame('', [
                    [Sg.Button(button_text='Remove Selected Folder', button_color=button_color, key='Remove Folder', enable_events=True, font=font_family)],
                    [Sg.FolderBrowse('Add Folder', button_color=button_color, font=font_family, enable_events=True)],
                    [Sg.Button('Open Settings File', key='Open Settings', button_color=button_color, font=font_family, enable_events=True)]], background_color=bg, border_width=0)]
            ]
        settings_window = Sg.Window('Music Caster Settings', settings_layout, background_color=bg, icon=window_icon, return_keyboard_events=True, use_default_focus=False)
        settings_window.BringToFront()
        settings_window.Finalize()
        settings_window.TKroot.attributes('-topmost', 1)
        settings_window.TKroot.attributes('-topmost', 0)
        # settings_window.GrabAnyWhereOn()
    elif menu_item == 'Play File':
        # maybe add *flac compatibility https://mutagen.readthedocs.io/en/latest/api/flac.html
        # path_to_file = sg.PopupGetFile('', title='Select Music File', file_types=(('Audio', '*mp3'),),
        #                                initial_folder=DEFAULT_DIR, no_window=True)
        if music_directories: DEFAULT_DIR = music_directories[0]
        fd = wx.FileDialog(None, 'Select Music File', defaultDir=DEFAULT_DIR, wildcard='Audio File (*.mp3)|*mp3',
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if fd.ShowModal() != wx.ID_CANCEL:
            path_to_file = fd.GetPath()
        # if os.path.exists(path_to_file):
            play_file(path_to_file)
            music_queue.clear()
            done_queue.clear()
            for directory in music_directories:
                music_queue.extend([file for file in glob(f'{directory}/*.mp3') if file != path_to_file])
            shuffle(music_queue)
            music_queue.insert(0, path_to_file)
            tray.Update(menu=menu_def_2, data_base64=filled_logo_data)
    elif menu_item == 'Play All':
        music_queue.clear()
        for directory in music_directories:
            music_queue.extend(file for file in glob(f'{directory}/*.mp3'))
        if music_queue:
            shuffle(music_queue)
            done_queue.clear()
            play_file(music_queue[0])
            tray.Update(menu=menu_def_2, data_base64=filled_logo_data)
    elif menu_item == 'Stop':
        if playing_status in ('PLAYING', 'PAUSED'):
            if mc is not None:
                mc.stop()
            elif local_music_player.music.get_busy():
                local_music_player.music.stop()
            playing_status = 'STOPPED'
    elif 'Next Song' in (menu_item, keyboard_command) or playing_status == 'PLAYING' and time() > song_end: next_song()
    elif 'Previous Song' in (menu_item, keyboard_command): previous()
    elif 'Resume' in (menu_item, keyboard_command): resume()
    elif 'Pause' in (menu_item, keyboard_command): pause()
    elif menu_item == 'Exit':
        tray.Hide()
        if cast is not None and cast.app_id == 'CC1AD845':
            cast.quit_app()
            # TODO: implement fadeout?
        elif local_music_player.music.get_busy():
            # local_music_player.music.fadeout(3)  # needs to be threaded
            local_music_player.music.stop()
        break

    # SETTINGS WINDOW
    if settings_active:
        settings_event, settings_values = settings_window.Read(timeout=0)
        if settings_event is None:
            settings_active = False
            continue
        settings_value = settings_values.get(settings_event)            
        # if settings_event != '__TIMEOUT__':
        #     print(settings_event)
        if settings_event in ('auto update', 'run on startup', 'notifications'):
            settings[settings_event] = settings_value
            save_json()
            if settings_event == 'run on startup':
                startup_setting()
            elif settings_event == 'notifications':
                notifications_enabled = settings_value
                if settings_value: tray.ShowMessage('Music Caster', 'Notifications have been enabled', time=500)
        elif settings_event in ('volume', 'a', 'd') or settings_event.isdigit():
            update_slider = False
            delta = 0
            if settings_event.isdigit():
                update_slider = True
                new_volume = int(settings_event) * 10
            else:
                if settings_event == 'a': delta = -5
                elif settings_event == 'd': delta = 5
                new_volume = settings_values['volume'] + delta
            settings['volume'] = new_volume
            save_json()
            volume = new_volume/100
            if update_slider or delta != 0: settings_window.Element('volume').Update(value=new_volume)
            if cast is None: local_music_player.music.set_volume(volume)
            else: cast.set_volume(volume)
        elif settings_event == 'Remove Folder' and settings_values['music_dirs']:
            selected_item = settings_values['music_dirs'][0]
            if selected_item in music_directories:
                music_directories.remove(selected_item)
                save_json()
                settings_window.Element('music_dirs').Update(music_directories)
        elif settings_event == 'Add Folder':
            if settings_value not in music_directories and os.path.exists(settings_value):
                music_directories.append(settings_value)
                save_json()
                settings_window.Element('music_dirs').Update(music_directories)
        elif settings_event == 'Open Settings':
            os.startfile(settings_file)

    if keyboard_command is not None: keyboard_command = None
