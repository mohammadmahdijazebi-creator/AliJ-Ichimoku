from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button


class LoginPanel(BoxLayout):
    def __init__(self, app, auth, on_success, **kwargs):
        super().__init__(
            orientation="vertical", padding=[10, 20, 10, 20], spacing=12, **kwargs
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

        if not self.registering:
            recovery = Button(
                text=app.make_label("فراموشی رمز").text,
                font_name=self.status.font_name,
                size_hint_y=None, height=48
            )
            recovery.bind(on_release=self.show_recovery)
            self.add_widget(recovery)

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

    def show_recovery(self, *_):
        from kivy.uix.popup import Popup
        from kivy.metrics import dp
        from kivy.clock import Clock
        from threading import Thread

        box = BoxLayout(
            orientation="vertical", padding=dp(12), spacing=dp(8)
        )
        status = self.app.make_label(
            "کد بازیابی را وارد کنید.\n"
            "پس از استفاده، کد باطل می‌شود.", 80
        )
        code = TextInput(
            multiline=False, password=True,
            size_hint_y=None, height=dp(48)
        )
        new_password = TextInput(
            multiline=False, password=True,
            size_hint_y=None, height=dp(48)
        )
        confirm = TextInput(
            multiline=False, password=True,
            size_hint_y=None, height=dp(48)
        )
        submit = Button(
            text=self.app.make_label("تغییر رمز").text,
            font_name=self.status.font_name,
            size_hint_y=None, height=dp(48)
        )
        close = Button(
            text=self.app.make_label("بستن").text,
            font_name=self.status.font_name,
            size_hint_y=None, height=dp(48)
        )
        for widget in (
            status, self.app.make_label("کد بازیابی", 30), code,
            self.app.make_label("رمز جدید", 30), new_password,
            self.app.make_label("تکرار رمز جدید", 30), confirm,
            submit, close
        ):
            box.add_widget(widget)

        from kivy.uix.scrollview import ScrollView
        box.size_hint_y = None
        box.bind(minimum_height=box.setter("height"))
        scroll = ScrollView()
        scroll.add_widget(box)
        popup = Popup(
            title=self.app.make_label("بازیابی حساب").text,
            title_font=self.status.font_name,
            content=scroll, size_hint=(0.96, 0.92)
        )

        def clear(*_):
            code.text = ""
            new_password.text = ""
            confirm.text = ""

        popup.bind(on_dismiss=clear)
        close.bind(on_release=popup.dismiss)

        def message(text):
            status.text = self.app.make_label(text).text

        def finish(success, error):
            if popup.parent is None:
                return
            if success:
                clear()
                message(
                    "رمز تغییر کرد؛ پنجره را ببندید و وارد شوید.\n"
                    "پس از ورود، کد بازیابی جدید بسازید."
                )
            else:
                message(error)
                # Reopen the dialog to retry.

        def worker(recovery_code, password):
            success = False
            error = ""
            try:
                success = self.auth.reset_password(
                    recovery_code, password
                )
                if not success:
                    error = "کد نامعتبر یا قبلاً استفاده شده است."
            except Exception:
                error = "بازیابی انجام نشد؛ فایل حساب بررسی شود."
            finally:
                recovery_code = None
                password = None
            Clock.schedule_once(
                lambda dt: finish(success, error), 0
            )

        def reset(*_):
            if submit.disabled:
                return
            password = new_password.text
            if not 8 <= len(password) <= 256:
                message("رمز باید ۸ تا ۲۵۶ نویسه باشد.")
                return
            if password != confirm.text:
                message("رمز و تکرار آن یکسان نیستند.")
                return
            recovery_code = code.text
            submit.disabled = True
            for field in (code, new_password, confirm):
                field.disabled = True
            clear()
            message("در حال تغییر رمز…")
            Thread(
                target=worker,
                args=(recovery_code, password), daemon=True
            ).start()

        submit.bind(on_release=reset)
        popup.open()
