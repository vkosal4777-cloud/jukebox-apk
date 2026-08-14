from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from kivy.uix.popup import Popup

from jnius import autoclass, PythonJavaClass, java_method
from kivy.core.image import Image as CoreImage

import os
import json
import random
import re
import threading


# =========================================================
# ANDROID MEDIA PLAYER
# =========================================================

MediaPlayer = autoclass("android.media.MediaPlayer")
MediaMetadataRetriever = autoclass("android.media.MediaMetadataRetriever")

try:
    AndroidEqualizer = autoclass("android.media.audiofx.Equalizer")
except:
    AndroidEqualizer = None


class CompletionListener(PythonJavaClass):

    __javainterfaces__ = [
        "android/media/MediaPlayer$OnCompletionListener"
    ]

    def __init__(self, app):
        super().__init__()
        self.app = app

    @java_method("(Landroid/media/MediaPlayer;)V")
    def onCompletion(self, mp):
        Clock.schedule_once(
            lambda dt: self.app.song_finished(),
            0
        )


# =========================================================
# JUKE BOX
# =========================================================

class JukeBoxApp(App):

    def build(self):

        self.player = None
        self.equalizer = None
        self.eq_session_id = None

        self.completion_listener = CompletionListener(self)

        self.playing = False
        self.current_song = 0

        self.phone_scan_running = False
        self.phone_scan_paths = []
        self.phone_scan_displayed = 0

        self.shuffle = False
        self.repeat = False

        self.current_category = "90s songs"

        self.paused_position = 0
        self.dragging_progress = False

        self.bass_value = 0
        self.treble_value = 0

        # -------------------------------------------------
        # FOLDERS
        # -------------------------------------------------

        self.base_folder = os.path.dirname(
            os.path.abspath(__file__)
        )

        self.song_folder = os.path.join(
            self.base_folder,
            "songs"
        )

        self.favorite_file = os.path.join(
            self.base_folder,
            "favorites.json"
        )

        self.recent_file = os.path.join(
            self.base_folder,
            "recent.json"
        )

        self.playlist_file = os.path.join(
            self.base_folder,
            "playlists.json"
        )

        self.songs = []
        self.favorites = []
        self.recent_songs = []
        self.playlists = {}

        self.load_favorites()
        self.load_recent()
        self.load_playlists()

        # -------------------------------------------------
        # MAIN LAYOUT
        # -------------------------------------------------

        main = BoxLayout(
            orientation="vertical",
            padding=10,
            spacing=6
        )

        title = Label(
            text="JUKE BOX",
            font_size=30,
            bold=True,
            size_hint_y=None,
            height=45
        )

        main.add_widget(title)

        # -------------------------------------------------
        # SEARCH
        # -------------------------------------------------

        self.search = TextInput(
            hint_text="SEARCH SONG",
            multiline=False,
            size_hint_y=None,
            height=44
        )

        self.search.bind(
            text=self.search_song
        )

        main.add_widget(self.search)

        # -------------------------------------------------
        # CATEGORIES
        # -------------------------------------------------

        categories = GridLayout(
            cols=3,
            spacing=4,
            size_hint_y=None,
            height=48
        )

        b1 = Button(
            text="90S SONGS",
            font_size=10
        )

        b2 = Button(
            text="2000 - 2015 SONGS",
            font_size=9
        )

        b3 = Button(
            text="POPULAR AFTER 2015",
            font_size=9
        )

        b1.bind(
            on_press=lambda x:
            self.load_category("90s songs")
        )

        b2.bind(
            on_press=lambda x:
            self.load_category("2000 - 2015 songs")
        )

        b3.bind(
            on_press=lambda x:
            self.load_category("popular after 2015")
        )

        categories.add_widget(b1)
        categories.add_widget(b2)
        categories.add_widget(b3)

        main.add_widget(categories)

        # -------------------------------------------------
        # SONG PHOTO
        # -------------------------------------------------

        self.song_image = Image(
            source="",
            size_hint_y=None,
            height=160,
            allow_stretch=True,
            keep_ratio=True
        )

        main.add_widget(self.song_image)

        # -------------------------------------------------
        # SONG NAME
        # -------------------------------------------------

        self.song_name = Label(
            text="NO SONG",
            font_size=20,
            bold=True,
            size_hint_y=None,
            height=35
        )

        main.add_widget(self.song_name)

        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        self.status = Label(
            text="READY",
            font_size=12,
            size_hint_y=None,
            height=22
        )

        main.add_widget(self.status)

        # -------------------------------------------------
        # PROGRESS
        # -------------------------------------------------

        self.progress = Slider(
            min=0,
            max=100,
            value=0,
            size_hint_y=None,
            height=35
        )

        main.add_widget(self.progress)

        self.progress.bind(
            on_touch_down=self.progress_touch_down
        )

        self.progress.bind(
            on_touch_up=self.progress_touch_up
        )

        # -------------------------------------------------
        # TIME
        # -------------------------------------------------

        self.time_label = Label(
            text="00:00 / 00:00",
            font_size=11,
            size_hint_y=None,
            height=20
        )

        main.add_widget(self.time_label)

        # -------------------------------------------------
        # CONTROLS
        # -------------------------------------------------

        controls = GridLayout(
            cols=5,
            spacing=4,
            size_hint_y=None,
            height=52
        )

        back10 = Button(
            text="-10 SEC",
            font_size=10
        )

        back = Button(
            text="BACK",
            font_size=10
        )

        self.play_button = Button(
            text="PLAY",
            font_size=15,
            bold=True
        )

        forward = Button(
            text="FORWARD",
            font_size=10
        )

        forward10 = Button(
            text="+10 SEC",
            font_size=10
        )

        back10.bind(
            on_press=self.backward_10
        )

        back.bind(
            on_press=self.previous_song
        )

        self.play_button.bind(
            on_press=self.play_pause
        )

        forward.bind(
            on_press=self.next_song
        )

        forward10.bind(
            on_press=self.forward_10
        )

        controls.add_widget(back10)
        controls.add_widget(back)
        controls.add_widget(self.play_button)
        controls.add_widget(forward)
        controls.add_widget(forward10)

        main.add_widget(controls)

        # -------------------------------------------------
        # SHUFFLE / REPEAT / FAVORITE
        # -------------------------------------------------

        extra = GridLayout(
            cols=3,
            spacing=5,
            size_hint_y=None,
            height=45
        )

        self.shuffle_button = Button(
            text="SHUFFLE OFF",
            font_size=10
        )

        self.repeat_button = Button(
            text="REPEAT OFF",
            font_size=10
        )

        self.favorite_button = Button(
            text="FAVORITE",
            font_size=10
        )

        self.shuffle_button.bind(
            on_press=self.toggle_shuffle
        )

        self.repeat_button.bind(
            on_press=self.toggle_repeat
        )

        self.favorite_button.bind(
            on_press=self.toggle_favorite
        )

        extra.add_widget(self.shuffle_button)
        extra.add_widget(self.repeat_button)
        extra.add_widget(self.favorite_button)

        main.add_widget(extra)

        # -------------------------------------------------
        # VOLUME
        # -------------------------------------------------

        volume_label = Label(
            text="VOLUME",
            font_size=11,
            size_hint_y=None,
            height=18
        )

        main.add_widget(volume_label)

        self.volume = Slider(
            min=0,
            max=1,
            value=1,
            size_hint_y=None,
            height=25
        )

        self.volume.bind(
            value=self.change_volume
        )

        main.add_widget(self.volume)

        # -------------------------------------------------
        # EQUALIZER
        # -------------------------------------------------

        eq_title = Label(
            text="EQUALIZER",
            font_size=15,
            bold=True,
            size_hint_y=None,
            height=25
        )

        main.add_widget(eq_title)

        # BASS

        bass_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=35,
            spacing=5
        )

        bass_label = Label(
            text="BASS",
            size_hint_x=None,
            width=60,
            font_size=11
        )

        self.bass_slider = Slider(
            min=-10,
            max=10,
            value=0,
            step=1
        )

        self.bass_value_label = Label(
            text="0",
            size_hint_x=None,
            width=35,
            font_size=11
        )

        self.bass_slider.bind(
            value=self.change_bass
        )

        bass_box.add_widget(bass_label)
        bass_box.add_widget(self.bass_slider)
        bass_box.add_widget(self.bass_value_label)

        main.add_widget(bass_box)

        # TREBLE

        treble_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=35,
            spacing=5
        )

        treble_label = Label(
            text="TREBLE",
            size_hint_x=None,
            width=60,
            font_size=11
        )

        self.treble_slider = Slider(
            min=-10,
            max=10,
            value=0,
            step=1
        )

        self.treble_value_label = Label(
            text="0",
            size_hint_x=None,
            width=35,
            font_size=11
        )

        self.treble_slider.bind(
            value=self.change_treble
        )

        treble_box.add_widget(treble_label)
        treble_box.add_widget(self.treble_slider)
        treble_box.add_widget(self.treble_value_label)

        main.add_widget(treble_box)

        reset_eq = Button(
            text="RESET EQUALIZER",
            size_hint_y=None,
            height=38,
            font_size=10
        )

        reset_eq.bind(
            on_press=self.reset_equalizer
        )

        main.add_widget(reset_eq)

        # -------------------------------------------------
        # SONG LIST
        # -------------------------------------------------

        self.list_title = Label(
            text="SONGS",
            font_size=15,
            bold=True,
            size_hint_y=None,
            height=28
        )

        main.add_widget(self.list_title)

        self.scroll = ScrollView()

        self.song_list = GridLayout(
            cols=1,
            spacing=4,
            size_hint_y=None
        )

        self.song_list.bind(
            minimum_height=
            self.song_list.setter("height")
        )

        self.scroll.add_widget(
            self.song_list
        )

        main.add_widget(
            self.scroll
        )

        # -------------------------------------------------
        # FAVORITES
        # -------------------------------------------------

        favorites = Button(
            text="FAVORITES",
            size_hint_y=None,
            height=42
        )

        favorites.bind(
            on_press=self.show_favorites
        )

        main.add_widget(favorites)

        # -------------------------------------------------
        # ADD TO PLAYLIST
        # -------------------------------------------------

        add_playlist = Button(
            text="ADD TO PLAYLIST",
            size_hint_y=None,
            height=42
        )

        add_playlist.bind(
            on_press=self.open_add_to_playlist
        )

        main.add_widget(add_playlist)

        # -------------------------------------------------
        # PLAYLISTS
        # -------------------------------------------------

        playlists_button = Button(
            text="PLAYLISTS",
            size_hint_y=None,
            height=42
        )

        playlists_button.bind(
            on_press=self.show_playlists
        )

        main.add_widget(playlists_button)

        # -------------------------------------------------
        # PLAYLIST MANAGEMENT
        # -------------------------------------------------

        manage_playlists = Button(
            text="MANAGE PLAYLISTS",
            size_hint_y=None,
            height=42
        )

        manage_playlists.bind(
            on_press=self.manage_playlists
        )

        main.add_widget(manage_playlists)

        # -------------------------------------------------
        # PHONE SONG SCAN
        # -------------------------------------------------

        scan_phone = Button(
            text="SCAN PHONE SONGS",
            size_hint_y=None,
            height=42
        )

        scan_phone.bind(
            on_press=self.scan_phone_songs
        )

        main.add_widget(scan_phone)

        # -------------------------------------------------
        # RECENT
        # -------------------------------------------------

        recent = Button(
            text="RECENTLY PLAYED",
            size_hint_y=None,
            height=42
        )

        recent.bind(
            on_press=self.show_recent
        )

        main.add_widget(recent)

        # -------------------------------------------------
        # START
        # -------------------------------------------------

        self.load_category("90s songs")

        Clock.schedule_interval(
            self.update_progress,
            0.2
        )

        return main

    # =====================================================
    # FIND CATEGORY
    # =====================================================

    def find_category_folder(self, category):

        if not os.path.isdir(
            self.song_folder
        ):
            return None

        wanted = category.lower().strip()

        for folder in os.listdir(
            self.song_folder
        ):

            path = os.path.join(
                self.song_folder,
                folder
            )

            if os.path.isdir(path):

                if folder.lower().strip() == wanted:
                    return path

        return None

    # =====================================================
    # LOAD CATEGORY
    # =====================================================

    def load_category(self, category):

        self.stop_player()

        self.current_category = category
        self.current_song = 0
        self.songs = []

        self.search.text = ""
        self.list_title.text = "SONGS"

        folder = self.find_category_folder(
            category
        )

        if folder is None:

            self.status.text = "FOLDER NOT FOUND"
            self.song_name.text = "NO SONG"
            self.song_image.source = ""

            self.update_song_list()

            return

        for filename in os.listdir(folder):

            path = os.path.join(
                folder,
                filename
            )

            if os.path.isfile(path):

                if filename.lower().endswith(
                    (".mp3", ".wav", ".m4a")
                ):

                    self.songs.append(filename)

        self.songs.sort(
            key=lambda x: x.lower()
        )

        self.progress.value = 0

        self.update_song_name()
        self.update_song_list()

        self.status.text = (
            category.upper()
            + " : "
            + str(len(self.songs))
            + " SONGS"
        )

    # =====================================================
    # UPDATE SONG NAME + PHOTO
    # =====================================================

    def update_song_name(self):

        if not self.songs:

            self.song_name.text = "NO SONG"
            self.song_image.source = ""
            return

        if self.current_song >= len(self.songs):
            self.current_song = 0

        song = self.songs[
            self.current_song
        ]

        self.song_name.text = (
            os.path.splitext(song)[0].upper()
        )

        self.update_song_photo()

        self.update_favorite_button()

    # =====================================================
    # SONG PHOTO
    # =====================================================

    def update_song_photo(self):

        if not self.songs:
            self.song_image.source = ""
            return

        song = self.songs[self.current_song]
        folder = self.find_category_folder(self.current_category)
        if folder is None:
            self.song_image.source = ""
            return

        path = os.path.join(folder, song)
        if self.set_embedded_album_art(path):
            return

        # Fallback: if an external cover exists, use it.
        def clean_name(value):
            return re.sub(r"[^a-z0-9]", "", value.lower())

        wanted_name = clean_name(os.path.splitext(song)[0])
        image_path = None
        try:
            for filename in os.listdir(folder):
                full_path = os.path.join(folder, filename)
                if not os.path.isfile(full_path):
                    continue
                file_name, file_ext = os.path.splitext(filename)
                if file_ext.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                    continue
                if clean_name(file_name) == wanted_name:
                    image_path = full_path
                    break
        except Exception as e:
            print("PHOTO SEARCH ERROR:", e)

        if image_path:
            self.song_image.source = image_path
            self.song_image.reload()
        else:
            self.song_image.source = ""

    def set_embedded_album_art(self, path):
        """Extract the cover stored INSIDE the audio file."""
        try:
            retriever = MediaMetadataRetriever()
            retriever.setDataSource(path)
            picture = retriever.getEmbeddedPicture()
            if picture is None:
                retriever.release()
                return False

            data = bytes(picture)
            if not data:
                retriever.release()
                return False

            cache_dir = os.path.join(self.base_folder, ".album_art_cache")
            os.makedirs(cache_dir, exist_ok=True)
            safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", os.path.abspath(path))
            cache_path = os.path.join(cache_dir, safe + ".jpg")
            with open(cache_path, "wb") as f:
                f.write(data)

            retriever.release()
            self.song_image.source = cache_path
            self.song_image.reload()
            return True
        except Exception as e:
            print("EMBEDDED ART ERROR:", e)
            try:
                retriever.release()
            except:
                pass
            return False

    # =====================================================
    # SONG LIST
    # =====================================================

    def update_song_list(self):

        self.song_list.clear_widgets()

        for index, song in enumerate(
            self.songs
        ):

            text = os.path.splitext(
                song
            )[0].upper()

            button = Button(
                text=text,
                size_hint_y=None,
                height=44,
                font_size=12
            )

            button.bind(
                on_press=
                lambda instance,
                i=index:
                self.select_song(i)
            )

            self.song_list.add_widget(
                button
            )

    # =====================================================
    # SELECT SONG
    # =====================================================

    def select_song(self, index):

        if not self.songs:
            return

        if index < 0 or index >= len(self.songs):
            return

        self.current_song = index

        self.update_song_name()

        self.play_current_song()

    # =====================================================
    # PLAY CURRENT SONG
    # =====================================================

    def play_current_song(self):

        if not self.songs:
            self.status.text = "NO SONG"
            return

        folder = self.find_category_folder(
            self.current_category
        )

        if folder is None:
            self.status.text = "FOLDER NOT FOUND"
            return

        song = self.songs[
            self.current_song
        ]

        path = os.path.join(
            folder,
            song
        )

        self.stop_player()

        try:

            self.player = MediaPlayer()

            self.player.setDataSource(
                path
            )

            self.player.setOnCompletionListener(
                self.completion_listener
            )

            self.player.prepare()

            self.player.setVolume(
                self.volume.value,
                self.volume.value
            )

            self.player.start()
            self.apply_equalizer()

            self.playing = True

            self.play_button.text = "PAUSE"

            self.progress.value = 0

            self.add_recent(
                self.current_category,
                song
            )

            self.update_song_name()
            self.set_embedded_album_art(path)

            self.status.text = "PLAYING"

        except Exception as e:

            self.player = None
            self.playing = False
            self.play_button.text = "PLAY"
            self.status.text = "PLAY ERROR"

            print("PLAY ERROR:", e)

    # =====================================================
    # PLAY / PAUSE
    # =====================================================

    def play_pause(self, instance):

        if not self.songs:
            return

        if self.player is None:

            self.play_current_song()
            return

        try:

            if self.playing:

                self.player.pause()

                self.playing = False

                self.play_button.text = "PLAY"
                self.status.text = "PAUSED"

            else:

                self.player.start()

                self.playing = True

                self.play_button.text = "PAUSE"
                self.status.text = "PLAYING"

        except:

            self.play_current_song()

    # =====================================================
    # STOP PLAYER
    # =====================================================

    def stop_player(self):

        if self.player is not None:

            try:
                self.player.stop()
            except:
                pass

            try:
                self.player.release()
            except:
                pass

        if self.equalizer is not None:
            try:
                self.equalizer.setEnabled(False)
            except:
                pass
            try:
                self.equalizer.release()
            except:
                pass

        self.equalizer = None
        self.eq_session_id = None
        self.player = None
        self.playing = False

        if hasattr(self, "play_button"):
            self.play_button.text = "PLAY"

    # =====================================================
    # NEXT
    # =====================================================

    def next_song(self, instance=None):

        if not self.songs:
            return

        if self.shuffle:

            if len(self.songs) > 1:

                choices = [
                    i for i in range(
                        len(self.songs)
                    )
                    if i != self.current_song
                ]

                self.current_song = random.choice(
                    choices
                )

        else:

            self.current_song += 1

            if self.current_song >= len(
                self.songs
            ):

                self.current_song = 0

        self.play_current_song()

    # =====================================================
    # PREVIOUS
    # =====================================================

    def previous_song(self, instance=None):

        if not self.songs:
            return

        self.current_song -= 1

        if self.current_song < 0:
            self.current_song = (
                len(self.songs) - 1
            )

        self.play_current_song()

    # =====================================================
    # +10 SEC
    # =====================================================

    def forward_10(self, instance=None):

        if self.player is None:
            return

        try:

            current = self.player.getCurrentPosition()
            duration = self.player.getDuration()

            new_position = min(
                current + 10000,
                duration
            )

            self.player.seekTo(
                new_position
            )

        except:
            pass

    # =====================================================
    # -10 SEC
    # =====================================================

    def backward_10(self, instance=None):

        if self.player is None:
            return

        try:

            current = self.player.getCurrentPosition()

            new_position = max(
                current - 10000,
                0
            )

            self.player.seekTo(
                new_position
            )

        except:
            pass

    # =====================================================
    # PROGRESS TOUCH
    # =====================================================

    def progress_touch_down(
        self,
        slider,
        touch
    ):

        if slider.collide_point(
            *touch.pos
        ):

            self.dragging_progress = True

            return False

        return False

    def progress_touch_up(
        self,
        slider,
        touch
    ):

        if self.dragging_progress:

            self.dragging_progress = False

            if self.player is not None:

                try:

                    duration = self.player.getDuration()

                    position = int(
                        duration *
                        slider.value /
                        100
                    )

                    self.player.seekTo(
                        position
                    )

                except:
                    pass

        return False

    # =====================================================
    # UPDATE PROGRESS
    # =====================================================

    def update_progress(self, dt):

        if self.player is None:
            return

        try:

            duration = self.player.getDuration()
            current = self.player.getCurrentPosition()

            if duration <= 0:
                return

            if not self.dragging_progress:

                self.progress.value = (
                    current / duration
                ) * 100

            current_sec = int(
                current / 1000
            )

            duration_sec = int(
                duration / 1000
            )

            self.time_label.text = (
                self.format_time(current_sec)
                + " / "
                + self.format_time(duration_sec)
            )

        except:
            pass

    # =====================================================
    # FORMAT TIME
    # =====================================================

    def format_time(self, seconds):

        minutes = int(seconds // 60)
        seconds = int(seconds % 60)

        return f"{minutes:02d}:{seconds:02d}"

    # =====================================================
    # SONG FINISHED
    # =====================================================

    def song_finished(self):

        if not self.songs:
            return

        if self.repeat:

            self.play_current_song()

        else:

            self.next_song()

    # =====================================================
    # VOLUME
    # =====================================================

    def change_volume(
        self,
        slider,
        value
    ):

        if self.player is not None:

            try:

                self.player.setVolume(
                    value,
                    value
                )

            except:
                pass

    # =====================================================
    # SHUFFLE
    # =====================================================

    def toggle_shuffle(self, instance):

        self.shuffle = not self.shuffle

        if self.shuffle:

            self.shuffle_button.text = "SHUFFLE ON"

        else:

            self.shuffle_button.text = "SHUFFLE OFF"

    # =====================================================
    # REPEAT
    # =====================================================

    def toggle_repeat(self, instance):

        self.repeat = not self.repeat

        if self.repeat:

            self.repeat_button.text = "REPEAT ON"

        else:

            self.repeat_button.text = "REPEAT OFF"

    # =====================================================
    # FAVORITE
    # =====================================================

    def toggle_favorite(self, instance):

        if not self.songs:
            return

        song = self.songs[
            self.current_song
        ]

        key = (
            self.current_category
            + "|"
            + song
        )

        if key in self.favorites:

            self.favorites.remove(key)

            self.status.text = "REMOVED FROM FAVORITES"

        else:

            self.favorites.append(key)

            self.status.text = "ADDED TO FAVORITES"

        self.save_favorites()

        self.update_favorite_button()

    # =====================================================
    # FAVORITE BUTTON TEXT
    # =====================================================

    def update_favorite_button(self):

        if not hasattr(
            self,
            "favorite_button"
        ):
            return

        if not self.songs:
            self.favorite_button.text = "FAVORITE"
            return

        song = self.songs[
            self.current_song
        ]

        key = (
            self.current_category
            + "|"
            + song
        )

        if key in self.favorites:

            self.favorite_button.text = "FAVORITED"

        else:

            self.favorite_button.text = "FAVORITE"

    # =====================================================
    # LOAD FAVORITES
    # =====================================================

    def load_favorites(self):

        self.favorites = []

        if os.path.exists(
            self.favorite_file
        ):

            try:

                with open(
                    self.favorite_file,
                    "r"
                ) as f:

                    data = json.load(f)

                    if isinstance(
                        data,
                        list
                    ):

                        self.favorites = data

            except:

                self.favorites = []

    # =====================================================
    # SAVE FAVORITES
    # =====================================================

    def save_favorites(self):

        try:

            with open(
                self.favorite_file,
                "w"
            ) as f:

                json.dump(
                    self.favorites,
                    f
                )

        except:
            pass

    # =====================================================
    # SHOW FAVORITES
    # =====================================================

    def show_favorites(self, instance):

        self.song_list.clear_widgets()

        self.list_title.text = "FAVORITES"

        if not self.favorites:

            self.song_list.add_widget(
                Label(
                    text="NO FAVORITES",
                    size_hint_y=None,
                    height=40
                )
            )

            return

        for key in self.favorites:

            try:

                category, song = key.split(
                    "|",
                    1
                )

            except:

                continue

            button = Button(
                text=os.path.splitext(
                    song
                )[0].upper(),
                size_hint_y=None,
                height=42,
                font_size=12
            )

            button.bind(
                on_press=
                lambda instance,
                s=song,
                c=category:
                self.play_favorite(
                    s,
                    c
                )
            )

            self.song_list.add_widget(
                button
            )

    # =====================================================
    # PLAY FAVORITE
    # =====================================================

    def play_favorite(
        self,
        song,
        category
    ):

        folder = self.find_category_folder(
            category
        )

        if folder is None:
            return

        if song not in self.songs or (
            self.current_category != category
        ):

            self.current_category = category

            self.songs = []

            for filename in os.listdir(
                folder
            ):

                path = os.path.join(
                    folder,
                    filename
                )

                if os.path.isfile(path):

                    if filename.lower().endswith(
                        (".mp3", ".wav", ".m4a")
                    ):

                        self.songs.append(
                            filename
                        )

            self.songs.sort(
                key=lambda x: x.lower()
            )

        if song in self.songs:

            self.current_song = self.songs.index(
                song
            )

            self.update_song_name()
            self.update_song_list()
            self.play_current_song()

    # =====================================================
    # RECENT
    # =====================================================

    def load_recent(self):

        self.recent_songs = []

        if not os.path.exists(
            self.recent_file
        ):
            return

        try:

            with open(
                self.recent_file,
                "r"
            ) as f:

                data = json.load(f)

                if isinstance(
                    data,
                    list
                ):

                    self.recent_songs = data

        except:

            self.recent_songs = []

    # =====================================================
    # SAVE RECENT
    # =====================================================

    def save_recent(self):

        try:

            with open(
                self.recent_file,
                "w"
            ) as f:

                json.dump(
                    self.recent_songs,
                    f
                )

        except:
            pass

    # =====================================================
    # ADD RECENT
    # =====================================================

    def add_recent(
        self,
        category,
        song
    ):

        item = {
            "category": category,
            "song": song
        }

        self.recent_songs = [
            x for x in self.recent_songs
            if not (
                isinstance(x, dict)
                and x.get("category") == category
                and x.get("song") == song
            )
        ]

        self.recent_songs.insert(
            0,
            item
        )

        self.recent_songs = (
            self.recent_songs[:20]
        )

        self.save_recent()

    # =====================================================
    # SHOW RECENT
    # =====================================================

    def show_recent(self, instance):

        self.song_list.clear_widgets()

        self.list_title.text = (
            "RECENTLY PLAYED"
        )

        if not self.recent_songs:

            self.song_list.add_widget(
                Label(
                    text="NO RECENT SONGS",
                    size_hint_y=None,
                    height=40
                )
            )

            return

        for item in self.recent_songs:

            if isinstance(item, dict):

                song = item.get(
                    "song",
                    ""
                )

                category = item.get(
                    "category",
                    ""
                )

            else:

                song = str(item)
                category = ""

            if not song:
                continue

            button = Button(
                text=os.path.splitext(
                    song
                )[0].upper(),
                size_hint_y=None,
                height=42,
                font_size=12
            )

            button.bind(
                on_press=
                lambda instance,
                s=song,
                c=category:
                self.play_recent(
                    s,
                    c
                )
            )

            self.song_list.add_widget(
                button
            )

    # =====================================================
    # PLAY RECENT
    # =====================================================

    def play_recent(
        self,
        song,
        category
    ):

        if not category:
            return

        folder = self.find_category_folder(
            category
        )

        if folder is None:
            return

        self.current_category = category

        self.songs = []

        for filename in os.listdir(
            folder
        ):

            path = os.path.join(
                folder,
                filename
            )

            if os.path.isfile(path):

                if filename.lower().endswith(
                    (".mp3", ".wav", ".m4a")
                ):

                    self.songs.append(
                        filename
                    )

        self.songs.sort(
            key=lambda x: x.lower()
        )

        if song not in self.songs:
            return

        self.current_song = self.songs.index(
            song
        )

        self.update_song_name()
        self.update_song_list()
        self.play_current_song()

    # =====================================================
    # SEARCH
    # =====================================================

    def search_song(
        self,
        instance,
        text
    ):

        query = text.lower().strip()

        if not query:

            self.list_title.text = "SONGS"
            self.update_song_list()
            return

        self.song_list.clear_widgets()

        self.list_title.text = "SEARCH RESULTS"

        for index, song in enumerate(
            self.songs
        ):

            name = os.path.splitext(
                song
            )[0]

            if query in name.lower():

                button = Button(
                    text=name.upper(),
                    size_hint_y=None,
                    height=44,
                    font_size=12
                )

                button.bind(
                    on_press=
                    lambda instance,
                    i=index:
                    self.select_song(i)
                )

                self.song_list.add_widget(
                    button
                )

    # =====================================================
    # PLAYLISTS
    # =====================================================

    def load_playlists(self):

        self.playlists = {}

        if not os.path.exists(
            self.playlist_file
        ):
            return

        try:

            with open(
                self.playlist_file,
                "r"
            ) as f:

                data = json.load(f)

                if isinstance(data, dict):
                    self.playlists = data

        except:
            self.playlists = {}

    def save_playlists(self):

        try:

            with open(
                self.playlist_file,
                "w"
            ) as f:

                json.dump(
                    self.playlists,
                    f,
                    indent=2
                )

        except:
            pass

    def open_add_to_playlist(self, instance):

        if not self.songs:
            self.status.text = "NO SONG"
            return

        box = BoxLayout(
            orientation="vertical",
            padding=10,
            spacing=8
        )

        title = Label(
            text="SELECT PLAYLIST",
            size_hint_y=None,
            height=35
        )

        box.add_widget(title)

        scroll = ScrollView()

        playlist_list = GridLayout(
            cols=1,
            spacing=5,
            size_hint_y=None
        )

        playlist_list.bind(
            minimum_height=playlist_list.setter("height")
        )

        if self.playlists:

            for name in sorted(
                self.playlists.keys(),
                key=lambda x: x.lower()
            ):

                button = Button(
                    text=name.upper(),
                    size_hint_y=None,
                    height=42
                )

                button.bind(
                    on_press=lambda btn,
                    n=name:
                    self.add_current_song_to_playlist(
                        n,
                        popup
                    )
                )

                playlist_list.add_widget(button)

        else:

            playlist_list.add_widget(
                Label(
                    text="NO PLAYLISTS YET",
                    size_hint_y=None,
                    height=40
                )
            )

        scroll.add_widget(playlist_list)
        box.add_widget(scroll)

        create = Button(
            text="CREATE NEW PLAYLIST",
            size_hint_y=None,
            height=42
        )

        create.bind(
            on_press=lambda instance:
            self.create_playlist_from_popup(popup)
        )

        box.add_widget(create)

        close = Button(
            text="CLOSE",
            size_hint_y=None,
            height=42
        )

        close.bind(
            on_press=lambda instance:
            popup.dismiss()
        )

        box.add_widget(close)

        popup = Popup(
            title="ADD TO PLAYLIST",
            content=box,
            size_hint=(0.88, 0.80),
            auto_dismiss=False
        )

        popup.open()

    def create_playlist_from_popup(self, parent_popup):

        box = BoxLayout(
            orientation="vertical",
            padding=10,
            spacing=8
        )

        name_input = TextInput(
            hint_text="PLAYLIST NAME",
            multiline=False,
            size_hint_y=None,
            height=45
        )

        box.add_widget(name_input)

        create = Button(
            text="CREATE",
            size_hint_y=None,
            height=42
        )

        def create_now(instance):

            name = name_input.text.strip()

            if not name:
                return

            if name not in self.playlists:
                self.playlists[name] = []

                self.save_playlists()

                parent_popup.dismiss()

                self.status.text = (
                    "PLAYLIST CREATED: "
                    + name.upper()
                )

                self.add_current_song_to_playlist(
                    name
                )

        create.bind(
            on_press=create_now
        )

        box.add_widget(create)

        cancel = Button(
            text="CANCEL",
            size_hint_y=None,
            height=42
        )

        box.add_widget(cancel)

        popup = Popup(
            title="CREATE PLAYLIST",
            content=box,
            size_hint=(0.85, 0.45)
        )

        cancel.bind(
            on_press=lambda instance:
            popup.dismiss()
        )

        popup.open()

    def add_current_song_to_playlist(
        self,
        playlist_name,
        popup=None
    ):

        if not self.songs:
            return

        song = self.songs[
            self.current_song
        ]

        item = {
            "category": self.current_category,
            "song": song
        }

        if playlist_name not in self.playlists:
            self.playlists[playlist_name] = []

        exists = any(
            isinstance(x, dict)
            and x.get("category") == self.current_category
            and x.get("song") == song
            for x in self.playlists[playlist_name]
        )

        if not exists:

            self.playlists[playlist_name].append(
                item
            )

            self.save_playlists()

            self.status.text = (
                "ADDED TO "
                + playlist_name.upper()
            )

        else:

            self.status.text = "ALREADY IN PLAYLIST"

        if popup is not None:
            popup.dismiss()

    def show_playlists(self, instance):

        self.song_list.clear_widgets()

        self.list_title.text = "PLAYLISTS"

        if not self.playlists:

            self.song_list.add_widget(
                Label(
                    text="NO PLAYLISTS",
                    size_hint_y=None,
                    height=40
                )
            )

            return

        for name in sorted(
            self.playlists.keys(),
            key=lambda x: x.lower()
        ):

            count = len(
                self.playlists.get(name, [])
            )

            button = Button(
                text=name.upper()
                + " ("
                + str(count)
                + ")",
                size_hint_y=None,
                height=44,
                font_size=12
            )

            button.bind(
                on_press=lambda btn,
                n=name:
                self.show_playlist_songs(n)
            )

            self.song_list.add_widget(button)

    def show_playlist_songs(self, playlist_name):

        self.song_list.clear_widgets()

        self.list_title.text = (
            playlist_name.upper()
        )

        items = self.playlists.get(
            playlist_name,
            []
        )

        back = Button(
            text="BACK TO PLAYLISTS",
            size_hint_y=None,
            height=42
        )

        back.bind(
            on_press=self.show_playlists
        )

        self.song_list.add_widget(back)

        if not items:

            self.song_list.add_widget(
                Label(
                    text="PLAYLIST IS EMPTY",
                    size_hint_y=None,
                    height=40
                )
            )

            return

        for index, item in enumerate(items):

            if not isinstance(item, dict):
                continue

            song = item.get(
                "song",
                ""
            )

            category = item.get(
                "category",
                ""
            )

            if not song:
                continue

            button = Button(
                text=os.path.splitext(
                    song
                )[0].upper(),
                size_hint_y=None,
                height=44,
                font_size=12
            )

            button.bind(
                on_press=lambda btn,
                i=index,
                n=playlist_name:
                self.play_playlist_song(n, i)
            )

            remove_button = Button(
                text="REMOVE",
                size_hint_y=None,
                height=36,
                font_size=11
            )

            remove_button.bind(
                on_press=lambda btn,
                i=index,
                n=playlist_name:
                self.remove_playlist_item(n, i)
            )

            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=44,
                spacing=4
            )

            row.add_widget(button)
            row.add_widget(remove_button)

            self.song_list.add_widget(
                row
            )

    def remove_playlist_item(
        self,
        playlist_name,
        index
    ):

        items = self.playlists.get(
            playlist_name,
            []
        )

        if index < 0 or index >= len(items):
            return

        items.pop(index)

        if not items:
            self.playlists.pop(
                playlist_name,
                None
            )
            self.save_playlists()
            self.status.text = "PLAYLIST EMPTY"
            self.show_playlists(None)
            return

        self.save_playlists()

        self.status.text = (
            "SONG REMOVED FROM PLAYLIST"
        )

        self.show_playlist_songs(
            playlist_name
        )

    def play_playlist_song(
        self,
        playlist_name,
        index
    ):

        items = self.playlists.get(
            playlist_name,
            []
        )

        if index < 0 or index >= len(items):
            return

        item = items[index]

        if not isinstance(item, dict):
            return

        category = item.get(
            "category",
            ""
        )

        song = item.get(
            "song",
            ""
        )

        if not category or not song:
            return

        self.load_category(category)

        if song in self.songs:

            self.current_song = (
                self.songs.index(song)
            )

            self.update_song_name()
            self.play_current_song()

            self.status.text = (
                playlist_name.upper()
                + " : "
                + os.path.splitext(song)[0].upper()
            )

    def scan_phone_songs(self, instance):

        # Prevent starting multiple scans at once.
        if getattr(self, "phone_scan_running", False):
            self.status.text = "SCAN ALREADY RUNNING"
            return

        self.phone_scan_running = True
        self.phone_scan_paths = []
        self.phone_scan_displayed = 0

        self.song_list.clear_widgets()
        self.list_title.text = "PHONE SONGS"

        self.song_list.add_widget(
            Label(
                text="SCANNING PHONE...\nPLEASE WAIT",
                size_hint_y=None,
                height=70
            )
        )

        self.status.text = "SCANNING PHONE..."

        # Run filesystem scan away from the Kivy UI thread.
        threading.Thread(
            target=self._scan_phone_worker,
            daemon=True
        ).start()

    def _scan_phone_worker(self):

        roots = [
            "/storage/emulated/0",
            "/sdcard"
        ]

        found = []
        seen = set()

        skip_names = {
            "android",
            ".android",
            "lost+found",
            ".thumbnails",
            ".trash"
        }

        for root in roots:

            if not os.path.isdir(root):
                continue

            try:

                for folder, dirs, files in os.walk(root):

                    dirs[:] = [
                        d for d in dirs
                        if d.lower() not in skip_names
                        and not d.startswith(".")
                    ]

                    for filename in files:

                        if not filename.lower().endswith(
                            (
                                ".mp3",
                                ".m4a",
                                ".wav",
                                ".ogg",
                                ".aac",
                                ".flac",
                                ".opus",
                                ".amr"
                            )
                        ):
                            continue

                        path = os.path.join(
                            folder,
                            filename
                        )

                        try:
                            key = os.path.realpath(
                                path
                            ).lower()
                        except:
                            key = path.lower()

                        if key in seen:
                            continue

                        seen.add(key)
                        found.append(path)

            except Exception as e:
                print(
                    "PHONE FULL SCAN ERROR:",
                    root,
                    e
                )

        found.sort(
            key=lambda p:
            os.path.basename(p).lower()
        )

        # Send only the result back to the UI thread.
        Clock.schedule_once(
            lambda dt, result=found:
            self.finish_phone_scan(result),
            0
        )

    def finish_phone_scan(self, paths):

        self.phone_scan_running = False
        self.phone_scan_paths = paths
        self.phone_scan_displayed = 0

        self.song_list.clear_widgets()

        self.list_title.text = "PHONE SONGS"

        if not paths:

            self.status.text = "NO PHONE SONGS FOUND"

            self.song_list.add_widget(
                Label(
                    text="NO SONGS FOUND",
                    size_hint_y=None,
                    height=45
                )
            )

            return

        self.status.text = (
            str(len(paths))
            + " PHONE SONGS FOUND"
        )

        self.song_list.add_widget(
            Label(
                text=(
                    str(len(paths))
                    + " SONGS FOUND"
                    + "\\nLOADING LIST..."
                ),
                size_hint_y=None,
                height=55
            )
        )

        # Add buttons in small batches so the app does not freeze.
        Clock.schedule_once(
            self.add_phone_song_batch,
            0.05
        )

    def add_phone_song_batch(self, dt):

        paths = getattr(
            self,
            "phone_scan_paths",
            []
        )

        start = getattr(
            self,
            "phone_scan_displayed",
            0
        )

        batch_size = 25
        end = min(
            start + batch_size,
            len(paths)
        )

        # Replace the loading label on first batch.
        if start == 0:
            self.song_list.clear_widgets()

            self.song_list.add_widget(
                Label(
                    text=(
                        str(len(paths))
                        + " SONGS FOUND"
                    ),
                    size_hint_y=None,
                    height=42
                )
            )

        for path in paths[start:end]:

            filename = os.path.basename(path)

            button = Button(
                text=os.path.splitext(
                    filename
                )[0].upper(),
                size_hint_y=None,
                height=44,
                font_size=12
            )

            button.bind(
                on_press=lambda btn,
                p=path:
                self.play_phone_song(p)
            )

            self.song_list.add_widget(
                button
            )

        self.phone_scan_displayed = end

        if end < len(paths):

            self.status.text = (
                "LOADING "
                + str(end)
                + "/"
                + str(len(paths))
            )

            Clock.schedule_once(
                self.add_phone_song_batch,
                0.01
            )

        else:

            self.status.text = (
                str(len(paths))
                + " PHONE SONGS READY"
            )


    def play_phone_song(self, path):

        try:

            if self.player:

                try:
                    self.player.stop()
                except:
                    pass

                try:
                    self.player.release()
                except:
                    pass

                self.player = None

            self.player = MediaPlayer()

            self.player.setDataSource(
                path
            )

            self.player.prepare()

            # Phone songs are independent from the category queue.
            # Do not attach the normal queue completion listener here.
            self.player.start()
            self.apply_equalizer()

            self.playing = True
            self.paused_position = 0

            self.status.text = (
                os.path.splitext(
                    os.path.basename(path)
                )[0].upper()
            )

            # Phone songs are scanned/playable without
            # copying or moving the original file.
            self.set_embedded_album_art(path)

        except Exception as e:

            self.playing = False

            self.status.text = (
                "PHONE SONG PLAY ERROR"
            )

            print(
                "PHONE SONG PLAY ERROR:",
                e
            )

    def manage_playlists(self, instance):

        box = BoxLayout(
            orientation="vertical",
            padding=10,
            spacing=8
        )

        scroll = ScrollView()

        playlist_list = GridLayout(
            cols=1,
            spacing=6,
            size_hint_y=None
        )

        playlist_list.bind(
            minimum_height=playlist_list.setter("height")
        )

        if not self.playlists:

            playlist_list.add_widget(
                Label(
                    text="NO PLAYLISTS",
                    size_hint_y=None,
                    height=40
                )
            )

        else:

            for name in sorted(
                self.playlists.keys(),
                key=lambda x: x.lower()
            ):

                row = BoxLayout(
                    orientation="horizontal",
                    size_hint_y=None,
                    height=44,
                    spacing=4
                )

                rename_button = Button(
                    text="RENAME",
                    size_hint_x=0.28,
                    font_size=11
                )

                name_button = Button(
                    text=name.upper(),
                    font_size=11
                )

                delete_button = Button(
                    text="DELETE",
                    size_hint_x=0.28,
                    font_size=11
                )

                rename_button.bind(
                    on_press=lambda btn,
                    n=name:
                    self.rename_playlist(n, popup)
                )

                name_button.bind(
                    on_press=lambda btn,
                    n=name:
                    self.show_playlist_songs(n)
                )

                delete_button.bind(
                    on_press=lambda btn,
                    n=name:
                    self.delete_playlist(n, popup)
                )

                row.add_widget(rename_button)
                row.add_widget(name_button)
                row.add_widget(delete_button)

                playlist_list.add_widget(row)

        scroll.add_widget(playlist_list)
        box.add_widget(scroll)

        close = Button(
            text="CLOSE",
            size_hint_y=None,
            height=42
        )

        box.add_widget(close)

        popup = Popup(
            title="MANAGE PLAYLISTS",
            content=box,
            size_hint=(0.95, 0.80),
            auto_dismiss=False
        )

        close.bind(
            on_press=lambda instance:
            popup.dismiss()
        )

        popup.open()

    def rename_playlist(
        self,
        old_name,
        manage_popup=None
    ):

        box = BoxLayout(
            orientation="vertical",
            padding=10,
            spacing=8
        )

        name_input = TextInput(
            text=old_name,
            multiline=False,
            size_hint_y=None,
            height=45
        )

        box.add_widget(name_input)

        save = Button(
            text="SAVE",
            size_hint_y=None,
            height=42
        )

        cancel = Button(
            text="CANCEL",
            size_hint_y=None,
            height=42
        )

        box.add_widget(save)
        box.add_widget(cancel)

        popup = Popup(
            title="RENAME PLAYLIST",
            content=box,
            size_hint=(0.85, 0.48)
        )

        def save_name(instance):

            new_name = name_input.text.strip()

            if not new_name:
                return

            if (
                new_name != old_name
                and new_name in self.playlists
            ):
                self.status.text = "PLAYLIST NAME ALREADY EXISTS"
                return

            self.playlists[new_name] = (
                self.playlists.pop(old_name)
            )

            self.save_playlists()

            popup.dismiss()

            if manage_popup is not None:
                manage_popup.dismiss()

            self.status.text = (
                "PLAYLIST RENAMED TO "
                + new_name.upper()
            )

            self.show_playlists(None)

        save.bind(on_press=save_name)
        cancel.bind(
            on_press=lambda instance:
            popup.dismiss()
        )

        popup.open()

    def delete_playlist(
        self,
        playlist_name,
        manage_popup=None
    ):

        box = BoxLayout(
            orientation="vertical",
            padding=10,
            spacing=8
        )

        message = Label(
            text=(
                "DELETE PLAYLIST?\n\n"
                + playlist_name.upper()
            )
        )

        box.add_widget(message)

        yes = Button(
            text="DELETE",
            size_hint_y=None,
            height=42
        )

        no = Button(
            text="CANCEL",
            size_hint_y=None,
            height=42
        )

        box.add_widget(yes)
        box.add_widget(no)

        popup = Popup(
            title="CONFIRM DELETE",
            content=box,
            size_hint=(0.85, 0.50)
        )

        def delete_now(instance):

            if playlist_name in self.playlists:
                del self.playlists[
                    playlist_name
                ]

                self.save_playlists()

            popup.dismiss()

            if manage_popup is not None:
                manage_popup.dismiss()

            self.status.text = (
                "PLAYLIST DELETED"
            )

            self.show_playlists(None)

        yes.bind(on_press=delete_now)
        no.bind(
            on_press=lambda instance:
            popup.dismiss()
        )

        popup.open()

    def remove_current_song_from_playlist(
        self,
        playlist_name,
        song,
        category
    ):

        if playlist_name not in self.playlists:
            return

        self.playlists[playlist_name] = [
            item
            for item in self.playlists[playlist_name]
            if not (
                isinstance(item, dict)
                and item.get("song") == song
                and item.get("category") == category
            )
        ]

        self.save_playlists()

    # =====================================================
    # BASS
    # =====================================================

    def change_bass(
        self,
        slider,
        value
    ):

        self.bass_value = int(value)

        self.bass_value_label.text = str(
            self.bass_value
        )

        self.apply_equalizer()

    # =====================================================
    # TREBLE
    # =====================================================

    def change_treble(
        self,
        slider,
        value
    ):

        self.treble_value = int(value)

        self.treble_value_label.text = str(
            self.treble_value
        )

        self.apply_equalizer()

    # =====================================================
    # EQUALIZER
    # =====================================================

    def apply_equalizer(self):

        # Apply the BASS/TREBLE sliders to the Android audio session.
        # Android Equalizer uses millibels (mB), so +10 / -10 on our
        # sliders becomes approximately +1000 / -1000 mB.

        if AndroidEqualizer is None or self.player is None:
            return

        try:
            session_id = int(self.player.getAudioSessionId())
            if session_id <= 0:
                return

            # Re-create the effect if the song/player has changed.
            if (self.equalizer is None or
                    self.eq_session_id != session_id):

                if self.equalizer is not None:
                    try:
                        self.equalizer.setEnabled(False)
                    except:
                        pass
                    try:
                        self.equalizer.release()
                    except:
                        pass

                self.equalizer = AndroidEqualizer(0, session_id)
                self.eq_session_id = session_id
                self.equalizer.setEnabled(True)

            bands = int(self.equalizer.getNumberOfBands())
            if bands <= 0:
                return

            # Use the device's real supported EQ range.
            level_range = self.equalizer.getBandLevelRange()
            min_level = int(level_range[0])
            max_level = int(level_range[1])

            bass_gain = int(self.bass_value * 100)
            treble_gain = int(self.treble_value * 100)

            for band in range(bands):
                try:
                    center_hz = int(self.equalizer.getCenterFreq(band)) // 1000
                except:
                    center_hz = 0

                # Bass: strongest below 250 Hz, fades out by 1000 Hz.
                if center_hz <= 250:
                    gain = bass_gain
                elif center_hz < 1000:
                    ratio = (center_hz - 250) / 750.0
                    gain = int(bass_gain * (1.0 - ratio))
                # Treble: starts around 2 kHz and reaches full effect at 8 kHz+.
                elif center_hz < 2000:
                    gain = 0
                elif center_hz < 8000:
                    ratio = (center_hz - 2000) / 6000.0
                    gain = int(treble_gain * ratio)
                else:
                    gain = treble_gain

                gain = max(min_level, min(max_level, gain))
                self.equalizer.setBandLevel(band, gain)

            self.equalizer.setEnabled(True)

        except Exception as e:
            print("EQUALIZER ERROR:", e)

    # =====================================================
    # RESET EQUALIZER
    # =====================================================

    def reset_equalizer(self, instance):

        self.bass_value = 0
        self.treble_value = 0

        self.bass_slider.value = 0
        self.treble_slider.value = 0

        self.bass_value_label.text = "0"
        self.treble_value_label.text = "0"

        self.status.text = "EQUALIZER RESET"

        self.apply_equalizer()

    # =====================================================
    # APP STOP
    # =====================================================

    def on_stop(self):

        self.stop_player()


# =========================================================
# START APP
# =========================================================

if __name__ == "__main__":
    JukeBoxApp().run()