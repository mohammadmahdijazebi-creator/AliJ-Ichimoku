from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button


class LoginPanel(BoxLayout):
    def __init__(self, app, auth, on_success, **kwargs):
        super().__init__(
            orientation="vertical", padding=20, spacing=12, **kwargs
        )
        self.app = app
        self.auth = auth
        self.on_success = on_success
        self.registering = not auth.exists()
        self.add_widget(app.make_label("علی جاذبی"))
        title = "ساخت حساب محلی" if self.registering else "ورود"
        self.add_widget(app.make_label(title))
        self.add_widget(app.make_label("نام کاربری"))
        self.username = TextInput(
            multiline=False, size_hint_y=None, height=48
        )
        self.add_widget(self.username)
        self.add_widget(app.make_label("رمز عبور"))
        self.password = TextInput(
            multiline=False, password=True,
            size_hint_y=None, height=48
        )
        self.add_widget(self.password)

        self.confirm = None
        if self.registering:
            self.add_widget(app.make_label("تکرار رمز عبور"))
            self.confirm = TextInput(
                multiline=False, password=True,
                size_hint_y=None, height=48
            )
            self.add_widget(self.confirm)

        self.status = app.make_label("", 72)
        self.add_widget(self.status)
        self.submit_button = Button(
            font_name=self.status.font_name,
            text=self.status.text,
            size_hint_y=None, height=48
        )
        caption = app.make_label(title)
        self.submit_button.text = caption.text
        self.submit_button.bind(on_release=self.submit)
        self.add_widget(self.submit_button)

    def message(self, text):
        self.status.text = self.app.make_label(text).text

    def submit(self, *_):
        from threading import Thread
        if self.submit_button.disabled:
            return
        username = self.username.text.strip()
        password = self.password.text
        if not 3 <= len(username) <= 64:
            self.message("نام کاربری باید ۳ تا ۶۴ نویسه باشد.")
            return
        if not 8 <= len(password) <= 256:
            self.message("رمز باید ۸ تا ۲۵۶ نویسه باشد.")
            return
        if self.registering and password != self.confirm.text:
            self.message("رمز و تکرار آن یکسان نیستند.")
            return
        self.submit_button.disabled = True
        self.username.disabled = True
        self.password.disabled = True
        if self.confirm is not None:
            self.confirm.disabled = True
        self.message("در حال بررسی…")
        Thread(
            target=self._authenticate,
            args=(username, password), daemon=True
        ).start()

    def _authenticate(self, username, password):
        from kivy.clock import Clock
        success = False
        fatal = False
        message = ""
        try:
            if self.registering:
                self.auth.register(username, password)
                success = True
            else:
                success = self.auth.verify(username, password)
                if not success:
                    message = "نام کاربری یا رمز نادرست است."
        except Exception:
            fatal = True
            message = "خطا در فایل حساب؛ ورود متوقف شد."
        finally:
            password = None
        Clock.schedule_once(
            lambda dt: self._finish(success, message, fatal), 0
        )

    def _finish(self, success, message, fatal):
        from kivy.clock import Clock
        self.password.text = ""
        if self.confirm is not None:
            self.confirm.text = ""
        if success:
            self.message("")
            self.on_success()
            return
        self.message(message)
        if fatal:
            return
        self._failures = getattr(self, "_failures", 0) + 1
        delay = min(60, 2 ** min(self._failures, 6))
        Clock.schedule_once(self._enable_retry, delay)

    def _enable_retry(self, dt):
        self.username.disabled = False
        self.password.disabled = False
        if self.confirm is not None:
            self.confirm.disabled = False
        self.submit_button.disabled = False
        self.message("دوباره تلاش کنید.")
