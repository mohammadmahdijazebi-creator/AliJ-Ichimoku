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

    def show_status(self, title):
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

    def build(self):
        self.title = "AliJ-Ichimoku"
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

        root.add_widget(self.make_label("ایچیموکو | علی‌جی"))
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

        root.add_widget(self.make_label(
            "امکانات تحلیلی هنوز متصل نیستند.", 44
        ))
        scroll.add_widget(root)
        return scroll


if __name__ == "__main__":
    AliJApp().run()
