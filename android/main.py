from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from kivy.app import App
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView


BASE = Path(__file__).resolve().parent
FONT = str(BASE / "fonts" / "Vazir.ttf")


def fa(text):
    return "\n".join(
        get_display(arabic_reshaper.reshape(line))
        for line in text.split("\n")
    )


class AliJApp(App):
    def make_label(self, text, height=48):
        return Label(
            text=fa(text), font_name=FONT, font_size="18sp",
            halign="center", size_hint_y=None, height=dp(height),
        )

    def show_archive(self):
        from market_archive import connect

        folder = Path(self.user_data_dir) / "all_market"
        db = None
        try:
            db = connect(folder)
            symbols = db.execute(
                "SELECT COUNT(DISTINCT symbol) FROM candles"
            ).fetchone()[0]
            candles = db.execute(
                "SELECT COUNT(*) FROM candles"
            ).fetchone()[0]
            message = (
                f"تعداد نمادها: {symbols}\n"
                f"تعداد کندل‌ها: {candles}\n"
                + ("آرشیو هنوز خالی است."
                   if candles == 0 else "آرشیو محلی آماده است.")
            )
        except Exception:
            from kivy.logger import Logger
            Logger.exception("Archive: opening database failed")
            message = "باز کردن آرشیو ناموفق بود."
        finally:
            if db is not None:
                db.close()

        content = BoxLayout(
            orientation="vertical", padding=dp(12), spacing=dp(12)
        )
        content.add_widget(self.make_label(message, 120))
        close = Button(
            text=fa("بستن"), font_name=FONT,
            size_hint_y=None, height=dp(48),
        )
        content.add_widget(close)
        popup = Popup(
            title=fa("آرشیو بازار"), title_font=FONT,
            content=content, size_hint=(0.92, None),
            height=dp(290),
        )
        close.bind(on_release=popup.dismiss)
        popup.open()

    def show_status(self, title):
        if title == "تحلیل ایچیموکو":
            self.show_cross_scan()
            return
        if title == "آرشیو بازار":
            self.show_archive()
            return

        content = BoxLayout(
            orientation="vertical", padding=dp(12), spacing=dp(12)
        )
        content.add_widget(self.make_label(
            "این بخش هنوز فعال نیست.\n"
            "اتصال به امکانات برنامه\n"
            "در مراحل بعد انجام می‌شود.", 120
        ))
        close = Button(
            text=fa("بستن"), font_name=FONT,
            size_hint_y=None, height=dp(48),
        )
        content.add_widget(close)
        popup = Popup(
            title=fa(title), title_font=FONT,
            content=content, size_hint=(0.92, None),
            height=dp(290),
        )
        close.bind(on_release=popup.dismiss)
        popup.open()


    def show_cross_scan(self):
        from threading import Thread
        from kivy.clock import Clock
        from kivy.uix.textinput import TextInput

        box = BoxLayout(
            orientation="vertical", padding=dp(12), spacing=dp(10)
        )
        box.add_widget(self.make_label(
            "تقاطع خطوط میانی بدون جابه‌جایی\n"
            "در پنج کندل آخر هر نماد؛ نه الزاماً پنج روز اخیر", 80
        ))
        output = TextInput(
            text=fa("نوع تقاطع را انتخاب کنید."),
            readonly=True, font_name=FONT, font_size="16sp"
        )
        buttons = []
        busy = [False]

        def finish(text):
            busy[0] = False
            for button in buttons:
                button.disabled = False
            if popup.parent is not None:
                output.text = fa(text)

        def worker(kind):
            db = None
            try:
                from market_archive import connect, recent_search
                db = connect(Path(self.user_data_dir) / "all_market")
                count = db.execute(
                    "SELECT COUNT(DISTINCT symbol) FROM candles"
                ).fetchone()[0]
                db.close()
                db = None
                if not count:
                    text = "آرشیو خالی است؛ ابتدا داده وارد کنید."
                else:
                    results = recent_search(
                        self.user_data_dir, kind, last_n=5
                    )
                    lines = [
                        "نمادهای آرشیو: " + str(count),
                        "تعداد نتایج: " + str(len(results)),
                        "این خروجی به‌تنهایی توصیهٔ خرید یا فروش نیست.",
                    ]
                    if not results:
                        lines.append("تقاطع مطابق شرط پیدا نشد.")
                    for symbol, date, direction in results[:200]:
                        lines.append(
                            str(symbol) + " | " + str(date)
                            + " | " + direction
                        )
                    if len(results) > 200:
                        lines.append("نمایش محدود به ۲۰۰ نتیجه است.")
                    text = "\n".join(lines)
            except Exception:
                from kivy.logger import Logger
                Logger.exception("Archive scan failed")
                text = "اسکن ناموفق بود؛ گزارش خطا بررسی شود."
            finally:
                if db is not None:
                    db.close()
            Clock.schedule_once(lambda dt: finish(text), 0)

        def start(kind):
            if busy[0]:
                return
            busy[0] = True
            for button in buttons:
                button.disabled = True
            output.text = fa("در حال بررسی آرشیو…")
            Thread(target=worker, args=(kind,), daemon=True).start()

        for caption, kind in (
            ("تقاطع ۹ و ۲۶", "sub"),
            ("تقاطع ۲۶ و ۵۲", "main"),
        ):
            button = Button(
                text=fa(caption), font_name=FONT,
                size_hint_y=None, height=dp(48)
            )
            button.bind(
                on_release=lambda instance, k=kind: start(k)
            )
            buttons.append(button)
            box.add_widget(button)

        box.add_widget(output)
        close = Button(
            text=fa("بستن"), font_name=FONT,
            size_hint_y=None, height=dp(48)
        )
        box.add_widget(close)
        popup = Popup(
            title=fa("اسکن آرشیو ایچیموکو"), title_font=FONT,
            content=box, size_hint=(0.96, 0.92)
        )
        close.bind(on_release=popup.dismiss)
        popup.open()

    def build(self):
        from local_auth import LocalAuth
        self.title = "ALI JAZEBI"
        Window.clearcolor = (0.06, 0.09, 0.14, 1)
        self.auth = LocalAuth(self.user_data_dir)
        self.container = BoxLayout(orientation="vertical")
        self._background = False
        self._login_generation = 0
        self._signed_in = self.session_valid()
        if self._signed_in:
            self.open_menu()
        else:
            self.show_login()
        return self.container

    def show_login(self):
        from auth_ui import LoginPanel
        self.container.clear_widgets()
        scroll = ScrollView()
        self._login_generation = getattr(
            self, "_login_generation", 0
        ) + 1
        generation = self._login_generation
        panel = LoginPanel(
            self, self.auth,
            lambda: self.accept_login(generation),
            size_hint_y=None
        )
        panel.bind(minimum_height=panel.setter("height"))
        scroll.add_widget(panel)
        self.container.add_widget(scroll)

    def accept_login(self, generation):
        if generation != self._login_generation:
            return
        if getattr(self, "_background", False):
            return
        try:
            self.save_session()
        except OSError:
            self.show_login()
            return
        self._signed_in = True
        self.open_menu()

    def session_path(self):
        return Path(self.user_data_dir) / "login_session"

    def account_stamp(self):
        import hashlib
        self.auth._load()
        return hashlib.sha256(self.auth.path.read_bytes()).hexdigest()

    def session_valid(self):
        import hmac
        try:
            return hmac.compare_digest(
                self.session_path().read_text(encoding="ascii"),
                self.account_stamp()
            )
        except Exception:
            return False

    def save_session(self):
        import os
        import tempfile
        stamp = self.account_stamp()
        fd, name = tempfile.mkstemp(
            prefix=".session-", dir=self.user_data_dir
        )
        try:
            with os.fdopen(fd, "w", encoding="ascii") as f:
                f.write(stamp)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.session_path())
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def logout(self, *_):
        try:
            self.session_path().unlink(missing_ok=True)
        except OSError:
            from kivy.logger import Logger
            Logger.exception("Auth: could not remove saved session")
            popup = Popup(
                title=fa("خطا"), title_font=FONT,
                content=self.make_label(
                    "خروج انجام نشد؛ دوباره تلاش کنید.", 90
                ),
                size_hint=(0.95, None), height=dp(180)
            )
            popup.open()
            return
        self._signed_in = False
        self.show_login()

    def on_pause(self):
        self._background = True
        self._login_generation += 1
        for widget in list(Window.children):
            if isinstance(widget, Popup):
                widget.dismiss(animation=False)
        self.container.clear_widgets()
        return True

    def on_resume(self):
        self._background = False
        self._signed_in = self.session_valid()
        if self._signed_in:
            self.open_menu()
        else:
            self.show_login()

    def open_menu(self):
        self.container.clear_widgets()
        self.container.add_widget(self.build_menu())
        from kivy.clock import Clock
        Clock.schedule_once(self.deliver_import_notice, 0.2)


    def setup_recovery(self, *_):
        from kivy.uix.textinput import TextInput
        from kivy.clock import Clock
        from threading import Thread

        generation = self._login_generation
        box = BoxLayout(
            orientation="vertical", padding=dp(12), spacing=dp(10)
        )
        note = self.make_label(
            "رمز فعلی را وارد کنید.\n"
            "ساخت کد جدید، کد قبلی را باطل می‌کند.", 80
        )
        password = TextInput(
            multiline=False, password=True,
            size_hint_y=None, height=dp(48)
        )
        button = Button(
            text=fa("ساخت کد بازیابی"), font_name=FONT,
            size_hint_y=None, height=dp(48)
        )
        close = Button(
            text=fa("بستن"), font_name=FONT,
            size_hint_y=None, height=dp(48)
        )
        for widget in (note, password, button, close):
            box.add_widget(widget)
        popup = Popup(
            title=fa("کد بازیابی"), title_font=FONT,
            content=box, size_hint=(0.96, None), height=dp(430)
        )
        popup.bind(on_dismiss=lambda *_: setattr(password, "text", ""))
        close.bind(on_release=popup.dismiss)

        def finish(code, error):
            if (
                generation != self._login_generation
                or self._background
                or popup.parent is None
            ):
                return
            password.text = ""
            if error:
                note.text = fa(error)
                # Close and reopen to retry; do not allow rapid submissions.
                return
            box.clear_widgets()
            box.add_widget(self.make_label(
                "این کد را در جای امن نگه دارید.\n"
                "بعد از بستن، دوباره نمایش داده نمی‌شود.", 80
            ))
            code_field = TextInput(
                text=code, readonly=True, multiline=True,
                font_size="16sp"
            )
            box.add_widget(code_field)
            popup.bind(
                on_dismiss=lambda *_: setattr(code_field, "text", "")
            )
            box.add_widget(close)

        def worker(value):
            code = None
            error = ""
            try:
                username = self.auth._load()["username"]
                code = self.auth.create_recovery_code(username, value)
            except PermissionError:
                error = "رمز نادرست است؛ پنجره را ببندید."
            except Exception:
                error = "ساخت کد انجام نشد؛ دوباره تلاش کنید."
            finally:
                value = None
            Clock.schedule_once(
                lambda dt: complete(code, error), 0
            )

        def complete(code, error):
            if (
                code is not None
                and generation == self._login_generation
                and self._signed_in
            ):
                try:
                    self.save_session()
                except OSError:
                    # The code is still valid; next launch may require login.
                    pass
            finish(code, error)

        def submit(*_):
            if button.disabled:
                return
            value = password.text
            if not 8 <= len(value) <= 256:
                note.text = fa("رمز باید ۸ تا ۲۵۶ نویسه باشد.")
                return
            button.disabled = True
            password.text = ""
            password.disabled = True
            note.text = fa("در حال بررسی…")
            Thread(target=worker, args=(value,), daemon=True).start()

        button.bind(on_release=submit)
        popup.open()


    def show_file_import(self, *_):
        from kivy.uix.textinput import TextInput
        from kivy.clock import Clock
        from threading import Thread

        if getattr(self, "_import_busy", False):
            return

        box = BoxLayout(
            orientation="vertical", padding=dp(12), spacing=dp(10)
        )
        box.add_widget(self.make_label(
            "نام نماد را وارد کنید؛ سپس فایل روزانه را انتخاب کنید.\n"
            "تاریخ‌های مشترک همان نماد جایگزین می‌شوند.\n"
            "داده‌های تعدیل‌شده و تعدیل‌نشده را مخلوط نکنید.", 120
        ))
        symbol_input = TextInput(
            multiline=False, size_hint_y=None, height=dp(48)
        )
        box.add_widget(symbol_input)
        status = self.make_label("", 60)
        box.add_widget(status)
        choose = Button(
            text=fa("انتخاب CSV یا TXT"), font_name=FONT,
            size_hint_y=None, height=dp(48)
        )
        box.add_widget(choose)
        close = Button(
            text=fa("بستن"), font_name=FONT,
            size_hint_y=None, height=dp(48)
        )
        box.add_widget(close)
        popup = Popup(
            title=fa("ورود داده به آرشیو"), title_font=FONT,
            content=box, size_hint=(0.96, None), height=dp(420)
        )
        close.bind(on_release=popup.dismiss)

        def report(message):
            self._import_busy = False
            self._import_notice = message
            self.deliver_import_notice()

        def save(symbol, text):
            try:
                from file_import import import_text
                count, total, missing_volume = import_text(
                    Path(self.user_data_dir) / "all_market",
                    symbol, text
                )
                message = (
                    f"نماد: {symbol}\n"
                    f"کندل‌های ورودی: {count}\n"
                    f"کل کندل‌های نماد: {total}"
                )
                if missing_volume:
                    message += "\nحجم در فایل نبود؛ صفر ذخیره شد."
                if total < 53:
                    message += "\nبرای بررسی تقاطع ۲۶/۵۲ حداقل ۵۳ کندل لازم است."
                message += "\nاکنون اسکن آرشیو را اجرا کنید."
            except ValueError as exc:
                message = "ورود فایل رد شد:\n" + str(exc)
            except Exception:
                from kivy.logger import Logger
                Logger.exception("File import failed")
                message = "ذخیره فایل ناموفق بود؛ گزارش خطا بررسی شود."
            Clock.schedule_once(lambda dt: report(message), 0)

        def selected(symbol, text):
            if not getattr(self, "_signed_in", False):
                report("ورود فایل به دلیل خروج از حساب لغو شد.")
                return
            Thread(
                target=save, args=(symbol, text), daemon=True
            ).start()

        def start(*_):
            symbol = symbol_input.text.strip()
            if not symbol or len(symbol) > 100:
                status.text = fa("نام نماد معتبر وارد کنید.")
                return
            if getattr(self, "_import_busy", False):
                return
            self._import_busy = True
            popup.dismiss()
            try:
                from android_file_picker import choose_text_file
                choose_text_file(
                    lambda text: selected(symbol, text), report
                )
            except Exception:
                from kivy.logger import Logger
                Logger.exception("File picker failed")
                report("راه‌اندازی فایل‌گزین ناموفق بود.")

        choose.bind(on_release=start)
        popup.open()

    def deliver_import_notice(self, *_):
        message = getattr(self, "_import_notice", None)
        if (
            not message
            or getattr(self, "_background", False)
            or not getattr(self, "_signed_in", False)
        ):
            return
        self._import_notice = None
        box = BoxLayout(
            orientation="vertical", padding=dp(12), spacing=dp(10)
        )
        from kivy.uix.textinput import TextInput
        box.add_widget(TextInput(
            text=fa(message), readonly=True,
            font_name=FONT, font_size="16sp"
        ))
        close = Button(
            text=fa("بستن"), font_name=FONT,
            size_hint_y=None, height=dp(48)
        )
        box.add_widget(close)
        popup = Popup(
            title=fa("نتیجه ورود فایل"), title_font=FONT,
            content=box, size_hint=(0.96, 0.65)
        )
        close.bind(on_release=popup.dismiss)
        popup.open()

    def build_menu(self):
        self.title = "ALI JAZEBI"
        Window.clearcolor = (0.06, 0.09, 0.14, 1)

        scroll = ScrollView()
        root = BoxLayout(
            orientation="vertical", padding=dp(20),
            spacing=dp(12), size_hint_y=None,
        )
        root.bind(minimum_height=root.setter("height"))

        logo = BASE / "branding" / "AliJ.png"
        if logo.is_file():
            root.add_widget(Image(
                source=str(logo), size_hint_y=None, height=dp(180)
            ))

        root.add_widget(self.make_label("ایچیموکو | علی جاذبی"))
        root.add_widget(self.make_label(
            "نسخه آزمایشی رابط اندروید", 36
        ))

        for title in (
            "آرشیو بازار",
            "تحلیل ایچیموکو",
            "راهنمای سیگنال‌ها",
        ):
            button = Button(
                text=fa(title), font_name=FONT, font_size="20sp",
                size_hint_y=None, height=dp(56),
                background_normal="",
                background_color=(0.10, 0.36, 0.43, 1),
            )
            button.bind(
                on_release=lambda instance, name=title:
                self.show_status(name)
            )
            root.add_widget(button)

        import_button = Button(
            text=fa("ورود فایل به آرشیو"), font_name=FONT,
            size_hint_y=None, height=dp(56),
        )
        import_button.bind(on_release=self.show_file_import)
        root.add_widget(import_button)

        recovery_button = Button(
            text=fa("ساخت کد بازیابی"), font_name=FONT,
            size_hint_y=None, height=dp(56),
        )
        recovery_button.bind(on_release=self.setup_recovery)
        root.add_widget(recovery_button)

        logout_button = Button(
            text=fa("خروج از حساب"), font_name=FONT,
            size_hint_y=None, height=dp(56),
        )
        logout_button.bind(on_release=self.logout)
        root.add_widget(logout_button)

        root.add_widget(self.make_label(
            "اسکن آرشیو متصل شد؛ دریافت آنلاین هنوز فعال نیست.", 44
        ))
        scroll.add_widget(root)
        return scroll


if __name__ == "__main__":
    AliJApp().run()
