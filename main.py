from kivy.lang import Builder
from kivy.clock import Clock
from kivy.storage.jsonstore import JsonStore
from kivymd.app import MDApp
from kivymd.uix.label import MDLabel
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton, MDRaisedButton
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.textfield import MDTextField
from kivymd.uix.responsivelayout import MDResponsiveLayout
from kivymd.uix.screen import MDScreen
from datetime import datetime, timedelta
from kivy.config import Config
import sqlite3

Config.set('kivy', 'log_level', 'debug')

KV = """
<CommonComponentLabel>
    halign: "center"


<MobileView>
    CommonComponentLabel:
        text: "Mobile"

<TabletView>
    CommonComponentLabel:
        text: "Table"

<DesktopView>
    CommonComponentLabel:
        text: "Desktop"

ScreenManager:
    id: screen_manager
    Screen:
        name: "main"
        BoxLayout:
            orientation: 'vertical'
            MDTopAppBar:
                title: "TimeCheck!"
                left_action_items: [['menu', lambda x: app.show_menu(x)]]

            MDLabel:
                id: overall_time
                adaptive_size: True
                text: "00:00:00:000"
                pos_hint: {"center_x": .5, "center_y": .005}
                padding: "8dp", "50dp"
                halign: 'center'
                font_style: 'H1'
                theme_text_color: "Primary"

            MDLabel:
                id: segment_time
                text: "00:00:00:000"
                pos_hint: {"center_x": .5, "center_y": .75}
                halign: 'center'
                font_style: 'H3'
                theme_text_color: "Primary"

            MDLabel:
                id: segment_count
                text: "Segments: 0"
                halign: 'center'
                font_style: 'H4'
                theme_text_color: "Secondary"

            MDFloatLayout:
                MDRaisedButton:
                    id:  start_stopwatch
                    text: "Play/Pause"
                    pos_hint: {"center_x": 0.2, "center_y": 0.6}
                    font_size: "20sp"
                    size_hint_x: .17
                    on_release: app.start_stopwatch()

                MDRaisedButton:
                    id: record_segment
                    text: "Segment"
                    pos_hint: {"center_x": 0.4, "center_y": 0.6}
                    font_size: "20sp"
                    size_hint_x: .17
                    on_release: app.record_segment()

                MDRaisedButton:
                    id: stop_stopwatch
                    text: "Stop"
                    pos_hint: {"center_x": 0.6, "center_y": 0.6}
                    font_size: "20sp"
                    size_hint_x: .17
                    on_release: app.stop_stopwatch()

                MDRaisedButton:
                    id: reset_stopwatch
                    text: "Reset"
                    pos_hint: {"center_x": 0.8, "center_y": 0.6}
                    font_size: "20sp"
                    size_hint_x: .17
                    on_release: app.reset_stopwatch()
"""

class CommonComponentLabel(MDLabel):
    pass

class MobileView(MDScreen):
    pass

class TabletView(MDScreen):
    pass

class DesktopView(MDScreen):
    pass

class ResponsiveView(MDResponsiveLayout, MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.mobile_view = MobileView()
        self.tablet_view = TabletView()
        self.desktop_view = DesktopView()


class Test(MDApp):
    def build(self):
        return Builder.load_string(KV)


class StopwatchApp(MDApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.running = False
        self.paused = False
        self.start_time = None
        self.pause_time = None
        self.segment_start = None
        self.segments = []
        self.session_start = None
        self.total_elapsed = timedelta(0)
        self.sessions = []
        self.current_session = None
        self.session_count = 1
        self.records_dialog = None

        self.conn = sqlite3.connect('stopwatch.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()

        self.cursor.execute('CREATE TABLE IF NOT EXISTS settings (theme TEXT)')
        self.conn.commit()
        self.cursor.execute('SELECT theme FROM settings')
        theme = self.cursor.fetchone()
        self.theme_cls.theme_style = theme[0] if theme else "Light"

    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT,
                total_duration TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS segments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                segment_number INTEGER,
                time TEXT,
                timestamp TEXT,
                note TEXT,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
        ''')
        self.conn.commit()

    def build(self):
        self.root = Builder.load_string(KV)
        Clock.schedule_once(self.initialize_ui, 0.3)
        return self.root

    def theme(self):
        if self.store.exists("settings"):
            self.theme_cls.theme_style = self.store.get("settings")["theme"]
        else:
            self.theme_cls.theme_style = "Light"
        self.root = Builder.load_string(KV)
        Clock.schedule_once(self.initialize_ui, 0.3)
        return self.root

    def toggle_dark_mode(self):
        self.theme_cls.theme_style = "Dark" if self.theme_cls.theme_style == "Light" else "Light"
        self.cursor.execute('DELETE FROM settings')
        self.cursor.execute('INSERT INTO settings (theme) VALUES (?)', (self.theme_cls.theme_style,))
        self.conn.commit()

    def initialize_ui(self, dt=None):
        try:
            self.load_records()
            self.update_display()
        except Exception as e:
            print(f"Initialization error: {str(e)}")

    def safe_widget_access(self, widget_id, default=""):
        try:
            screen = self.root.get_screen('main')
            if screen and widget_id in screen.ids:
                return screen.ids[widget_id]
        except Exception as e:
            print(f"Widget access error: {str(e)}")
        return None

    def update_display(self):
        try:
            overall_label = self.safe_widget_access('overall_time')
            if overall_label:
                overall_label.text = self.format_time(self.total_elapsed)

            segment_count = self.safe_widget_access('segment_count')
            if segment_count:
                segment_count.text = f"Segments: {len(self.segments)}"
        except Exception as e:
            print(f"Display update error: {str(e)}")

    def load_records(self):
        try:
            self.sessions = []

            self.cursor.execute('SELECT id, start_time, total_duration FROM sessions')
            sessions = self.cursor.fetchall()

            for session in sessions:
                session_id, start_time, total_duration = session

                self.cursor.execute('''
                    SELECT segment_number, time, timestamp, note FROM segments 
                    WHERE session_id = ?
                ''', (session_id,))
                segments = self.cursor.fetchall()

                formatted_segments = []
                for segment in segments:
                    segment_number, time, timestamp, note = segment
                    formatted_segments.append({
                        'segment': segment_number,
                        'time': time,
                        'timestamp': timestamp,
                        'note': note if note else ""
                    })

                self.sessions.append({
                    'session_count': session_id,
                    'start_time': start_time,
                    'total_duration': timedelta(seconds=float(total_duration)),
                    'segments': formatted_segments
                })
        except Exception as e:
            print(f"Load records error: {str(e)}")

    def show_menu(self, button):
        if not self.running:
            menu_items = [
                {"text": "View & Edit Records", "on_release": self.view_records},
                {"text": "Toggle Dark Mode", "on_release": self.toggle_dark_mode},
                {"text": "Clear Records", "on_release": self.confirm_clear_records},
                {"text": "Credits", "on_release": self.show_credits}
            ]
            MDDropdownMenu(caller=button, items=menu_items, width_mult=4).open()

    def start_stopwatch(self):
        if not self.running:
            self.running = True
            now = datetime.now()

            if not self.session_start:
                self.session_start = now
                self.session_count += 1
                self.current_session = {
                    'session_count': self.session_count,
                    'start_time': self.session_start.strftime('%Y/%m/%d | %I:%M.%S %p'),
                    'total_duration': timedelta(0),
                    'segments': []
                }

            if not self.start_time:
                self.start_time = now
                self.segment_start = self.start_time

            if self.paused:
                pause_duration = now - self.pause_time
                self.start_time += pause_duration
                self.segment_start += pause_duration
                self.session_start += pause_duration
                self.paused = False

            Clock.schedule_interval(self.update_time, 0.01)

    def update_time(self, dt):
        if self.running:
            now = datetime.now()
            segment_elapsed = now - self.segment_start
            session_elapsed = now - self.session_start if self.session_start else timedelta(0)

            self.root.ids.segment_time.text = self.format_time(segment_elapsed)
            self.root.ids.overall_time.text = self.format_time(session_elapsed)

    def record_segment(self):
        if self.running:
            now = datetime.now()
            elapsed = now - self.segment_start
            self.segment_start = now
            segment_data = {
                "segment": len(self.current_session['segments']) + 1,
                "time": self.format_time(elapsed),
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "note": ""
            }
            self.current_session['segments'].append(segment_data)
            self.root.ids.segment_count.text = f"Segments: {len(self.current_session['segments'])}"

    def stop_stopwatch(self):
        if self.running:
            self.running = False
            self.paused = True
            now = datetime.now()

            if self.segment_start:
                elapsed = now - self.segment_start
                segment_data = {
                    "segment": len(self.current_session['segments']) + 1,
                    "time": self.format_time(elapsed),
                    "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "note": ""
                }
                self.current_session['segments'].append(segment_data)
                self.root.ids.segment_count.text = f"Segments: {len(self.current_session['segments'])}"

            self.current_session['total_duration'] = now - self.session_start

            Clock.unschedule(self.update_time)

            self.save_records()

            self.root.ids.start_stopwatch.disabled = True

    def reset_stopwatch(self):
        self.running = False
        self.paused = False
        Clock.unschedule(self.update_time)

        self.start_time = None
        self.pause_time = None
        self.segment_start = None
        self.session_start = None
        self.total_elapsed = timedelta(0)
        self.segments = []
        self.current_session = None

        self.root.ids.start_stopwatch.opacity = 1
        self.root.ids.start_stopwatch.disabled = False
        self.root.ids.segment_time.text = "00:00:00:000"
        self.root.ids.overall_time.text = "00:00:00:000"
        self.root.ids.segment_count.text = f"Segments: 0"

    def format_time(self, time_delta):
        total_seconds = int(time_delta.total_seconds())
        milliseconds = int(time_delta.microseconds / 1000)
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}:{milliseconds:03}"

    def copy_to_clipboard(self, pyperclip=None):
        pyperclip.copy(str(self.segments))

    def save_records(self):
        if self.current_session:

            self.cursor.execute('''
                INSERT INTO sessions (start_time, total_duration)
                VALUES (?, ?)
            ''', (
                self.current_session['start_time'],
                self.current_session['total_duration'].total_seconds()
            ))
            session_id = self.cursor.lastrowid

            for segment in self.current_session['segments']:
                self.cursor.execute('''
                    INSERT INTO segments (session_id, segment_number, time, timestamp, note)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    session_id,
                    segment['segment'],
                    segment['time'],
                    segment['timestamp'],
                    segment['note']
                ))
            self.conn.commit()

    def save_note(self, session_id, segment_number, note):
        try:
            self.cursor.execute('''
                UPDATE segments
                SET note = ?
                WHERE session_id = ? AND segment_number = ?
            ''', (note, session_id, segment_number))
            self.conn.commit()
        except Exception as e:
            print(f"Error saving note: {str(e)}")

    def view_records(self):
        try:
            self.load_records()

            content = MDBoxLayout(orientation="vertical", size_hint_y=None, adaptive_height=True, spacing="20dp",
                                  padding="10dp")
            content.bind(minimum_height=content.setter("height"))

            for session in self.sessions:
                session_item = MDBoxLayout(adaptive_height=True, spacing="10dp")
                session_label = MDLabel(
                    text=f"[color=FF0000]Session {session['start_time']} | Duration: {self.format_time(session['total_duration'])}[/color]",
                    markup=True,
                    halign="left",
                    theme_text_color="Primary"
                )
                session_item.add_widget(session_label)
                content.add_widget(session_item)

                for segment in session["segments"]:
                    segment_item = MDBoxLayout(adaptive_height=True, spacing="10dp", padding=(20, 0, 0, 0))
                    segment_label = MDLabel(
                        text=f"Segment {segment['segment']} | {segment['time']} | Note: {segment['note']}",
                        halign="left",
                        theme_text_color="Secondary"
                    )
                    segment_item.add_widget(segment_label)

                    edit_btn = MDRaisedButton(
                        text="Edit Note",
                        size_hint=(None, None),
                        size=("100dp", "40dp"),
                        on_release=lambda x, s=session, seg=segment: self.edit_note(s, seg)
                    )
                    segment_item.add_widget(edit_btn)
                    content.add_widget(segment_item)

            if self.records_dialog:
                self.records_dialog.dismiss()
                self.records_dialog = None

            self.records_dialog = MDDialog(
                title="Recorded Sessions",
                type="custom",
                content_cls=MDScrollView(
                    MDBoxLayout(
                        content,
                        orientation="vertical",
                        size_hint_y=None,
                        adaptive_height=True
                    ),
                    size_hint=(1, None),
                    size=("400dp", "400dp")
                ),
                buttons=[MDFlatButton(text="Close", on_release=lambda x: self.records_dialog.dismiss())]
            )
            self.records_dialog.open()
        except Exception as e:
            print(f"View records error: {str(e)}")

    def edit_note(self, session, segment):
        def save_and_refresh(dialog, note_input):
            self.save_note(session['session_count'], segment['segment'], note_input.text)

            segment['note'] = note_input.text

            dialog.dismiss()
            self.records_dialog.dismiss()
            self.view_records()

        note_input = MDTextField(
            text=segment.get('note', ''),
            hint_text="Enter a new note",
            size_hint=(1, None),
            height="40dp"
        )

        edit_dialog = MDDialog(
            title=f"Edit Note for Segment {segment['segment']}",
            type="custom",
            content_cls=note_input,
            buttons=[
                MDFlatButton(text="Cancel", on_release=lambda x: edit_dialog.dismiss()),
                MDFlatButton(text="Save", on_release=lambda x: save_and_refresh(edit_dialog, note_input)),
            ]
        )
        edit_dialog.open()

    def clear_records(self):
        try:
            self.cursor.execute('DELETE FROM sessions')
            self.cursor.execute('DELETE FROM segments')
            self.conn.commit()

            self.sessions.clear()
            self.total_elapsed = timedelta(0)
            self.session_start = None
            self.current_session = None
            self.session_count = 1

            self.root.ids.segment_time.text = "00:00:00:000"
            self.root.ids.overall_time.text = "00:00:00:000"
            self.root.ids.segment_count.text = f"Segments: 0"

            if self.records_dialog:
                self.records_dialog.dismiss()
                self.records_dialog = None

            success_dialog = MDDialog(
                title="Success!",
                text="All records have been cleared!",
                buttons=[MDFlatButton(text="OK", on_release=lambda x: success_dialog.dismiss())]
            )
            success_dialog.open()
        except Exception as e:
            error_dialog = MDDialog(
                title="Error",
                text=f"Failed to clear records: {str(e)}",
                buttons=[MDFlatButton(text="OK", on_release=lambda x: error_dialog.dismiss())]
            )
            error_dialog.open()

    def confirm_clear_records(self):
        def clear_and_close_dialog(dialog):
            self.clear_records()
            dialog.dismiss()

        clear_records_dialog = MDDialog(
            title="Clear Records",
            text="Are you sure you want to clear all records?",
            buttons=[
                MDFlatButton(text="Cancel", on_release=lambda x: clear_records_dialog.dismiss()),
                MDFlatButton(text="Clear", on_release=lambda x: clear_and_close_dialog(clear_records_dialog))
            ]
        )
        clear_records_dialog.open()

    def show_credits(self):
        credits_text = (
            "TimeCheck App v1.0\n"
            "Developed and Designed by:\n"
            "Elijah Damasin, Ezekiel Kwan, Jude Obiasca, and Ulysses Porte [BSCPE 1-2]\n"
            "Powered by Kivy & KivyMD\n"
            "© 2025 All Rights Reserved"
        )

        credits_dialog = MDDialog(
            title="Credits",
            text=credits_text,
            buttons=[MDFlatButton(text="OK", on_release=lambda x: credits_dialog.dismiss())]
        )
        credits_dialog.open()

    def on_stop(self):
        self.conn.close()

if __name__ == "__main__":
    StopwatchApp().run()