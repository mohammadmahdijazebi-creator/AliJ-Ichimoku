"""Android document picker; callbacks run on the Kivy thread."""
from threading import Thread
from kivy.clock import Clock

REQUEST_CODE = 4812
_active = None


def choose_text_file(on_success, on_error):
    global _active
    if _active is not None:
        on_error("انتخاب فایل دیگری در حال انجام است.")
        return

    from kivy.utils import platform
    if platform != "android":
        on_error("این فایل‌گزین مخصوص اندروید است.")
        return

    from android import activity
    from android.runnable import run_on_ui_thread
    from jnius import autoclass

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")

    def finish(text=None, error=None):
        global _active
        _active = None
        if error is not None:
            on_error(error)
        else:
            on_success(text)

    def read_document(uri):
        stream = None
        reader = None
        text = None
        error = None
        try:
            resolver = PythonActivity.mActivity.getContentResolver()
            stream = resolver.openInputStream(uri)
            if stream is None:
                raise ValueError("فایل قابل خواندن نیست.")
            InputStreamReader = autoclass("java.io.InputStreamReader")
            BufferedReader = autoclass("java.io.BufferedReader")
            reader = BufferedReader(InputStreamReader(stream, "UTF-8"))
            parts = []
            size = 0
            while True:
                line = reader.readLine()
                if line is None:
                    break
                line = str(line)
                size += len(line) + 1
                if size > 10_000_000:
                    raise ValueError("فایل بیش از حد بزرگ است.")
                parts.append(line)
            text = "\n".join(parts)
            if not text.strip():
                raise ValueError("فایل خالی است.")
        except ValueError as exc:
            error = str(exc)
        except Exception:
            from kivy.logger import Logger
            Logger.exception("Document reading failed")
            error = "خواندن فایل ناموفق بود."
        finally:
            try:
                if reader is not None:
                    reader.close()
                elif stream is not None:
                    stream.close()
            except Exception:
                pass
        Clock.schedule_once(lambda dt: finish(text, error), 0)

    def result(request_code, result_code, intent):
        if request_code != REQUEST_CODE:
            return
        activity.unbind(on_activity_result=result)
        if result_code != -1 or intent is None:
            Clock.schedule_once(
                lambda dt: finish(error="انتخاب فایل لغو شد."), 0
            )
            return
        uri = intent.getData()
        if uri is None:
            Clock.schedule_once(
                lambda dt: finish(error="نشانی فایل دریافت نشد."), 0
            )
            return
        Thread(target=read_document, args=(uri,), daemon=True).start()

    def launch_failed():
        activity.unbind(on_activity_result=result)
        finish(error="باز کردن فایل‌گزین اندروید ناموفق بود.")

    @run_on_ui_thread
    def launch():
        try:
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType("*/*")
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            PythonActivity.mActivity.startActivityForResult(
                intent, REQUEST_CODE
            )
        except Exception:
            Clock.schedule_once(lambda dt: launch_failed(), 0)

    _active = result
    try:
        activity.bind(on_activity_result=result)
        launch()
    except Exception:
        launch_failed()
