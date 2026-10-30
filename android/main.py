from pathlib import Path

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.core.window import Window


class AliJApp(App):
    def build(self):
        self.title = "AliJ-Ichimoku"
        Window.clearcolor = (0.06, 0.09, 0.14, 1)
        root = BoxLayout(
            orientation="vertical", padding=24, spacing=16
        )
        logo = Path(__file__).resolve().parent / "branding" / "AliJ.png"
        if logo.is_file():
            root.add_widget(Image(source=str(logo)))
        root.add_widget(Label(
            text="ALI.J\nIchimoku",
            halign="center",
            font_size="28sp",
            size_hint_y=0.3,
        ))
        return root


if __name__ == "__main__":
    AliJApp().run()
