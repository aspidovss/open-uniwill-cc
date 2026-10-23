"""Notification texts and event -> notification mapping shared by the session agents
(bin/uwcc-agent on Linux, the tray app on Windows)."""

TEXT = {
    "en": {"mode0": "Office mode", "mode1": "Gaming mode", "mode2": "Turbo mode", "mode3": "Custom mode · {}",
           "hot_cpu": "CPU at {} °C", "hot_gpu": "GPU at {} °C",
           "hot_body": "It has stayed at or above {} °C for 30 seconds.",
           "hot_body_boost": "It has stayed at or above {} °C for 30 seconds. If it does not cool down within 30 seconds, Fan Boost turns on.",
           "hot_boost": "Fan Boost turned on because of overheating", "hot_boost_body": "Turn it off in Control Center when the load is over.",
           "upd": "open-uniwill-cc {} is available", "upd_body": "Open Control Center → Information to see what's new and update.",
           "upd_err": "Update failed", "upd_ready": "Installing open-uniwill-cc {}",
           "lc_again": "Liquid cooler connected again",
           "lc_guard": "The pump was raised to 11 V and the fan to at least 60 % until the laptop mode changes or you pick a setting.",
           "boost_on": "Fan Boost on", "boost_off": "Fan Boost off",
           "win_locked": "Windows key locked", "win_unlocked": "Windows key unlocked",
           "kb_level": "Keyboard backlight: {}", "touch_on": "Touchpad on", "touch_off": "Touchpad off",
           "reboot": "Restart required", "reboot_body": "The graphics mode change takes effect after a restart",
           "lc_conn": "Liquid cooler connected", "lc_lost": "Liquid cooler disconnected",
           "lc_lost_body": "Bluetooth link lost — reconnecting automatically",
           "lc_flow": "Liquid cooler: no coolant flow!",
           "lc_flow_body": "The pump is running but the flow sensor reports no circulation. "
                           "Check the tubes and the coolant level, or run the filling cycle.",
           "lc_fan_boost": "Cooler fan boost {}", "lc_pump_boost": "Cooler pump boost {}", "on": "on", "off": "off",
           "lc_primed": "Liquid cooler: filling cycle finished"},
    "ru": {"mode0": "Офисный режим", "mode1": "Игровой режим", "mode2": "Турборежим", "mode3": "Пользовательский режим · {}",
           "hot_cpu": "ЦП нагрелся до {} °C", "hot_gpu": "ГП нагрелся до {} °C",
           "hot_body": "Температура держится на уровне {} °C и выше уже 30 секунд.",
           "hot_body_boost": "Температура держится на уровне {} °C и выше уже 30 секунд. Если за 30 секунд не остынет, включится турбовентиляция.",
           "hot_boost": "Турбовентиляция включена из-за перегрева", "hot_boost_body": "Выключите её в Control Center, когда нагрузка закончится.",
           "upd": "Доступна версия open-uniwill-cc {}", "upd_body": "Откройте Control Center → Информация, чтобы посмотреть изменения и обновиться.",
           "upd_err": "Не удалось обновить", "upd_ready": "Установка open-uniwill-cc {}",
           "lc_again": "Система охлаждения снова подключена",
           "lc_guard": "Напряжение помпы поднято до 11 В, вентилятор — не меньше 60 %, пока не сменится режим ноутбука или вы не выберете настройку вручную.",
           "boost_on": "Турбовентиляция включена", "boost_off": "Турбовентиляция выключена",
           "win_locked": "Клавиша Windows заблокирована", "win_unlocked": "Клавиша Windows разблокирована",
           "kb_level": "Подсветка клавиатуры: {}", "touch_on": "Сенсорная панель включена",
           "touch_off": "Сенсорная панель выключена",
           "reboot": "Требуется перезагрузка", "reboot_body": "Изменение режима видеокарты вступит в силу после перезагрузки",
           "lc_conn": "Система охлаждения подключена", "lc_lost": "Система охлаждения отключилась",
           "lc_lost_body": "Связь Bluetooth потеряна — переподключение выполняется автоматически",
           "lc_flow": "Система охлаждения: нет циркуляции!",
           "lc_flow_body": "Помпа работает, но датчик потока не видит циркуляции. "
                           "Проверьте трубки и уровень жидкости или запустите цикл заполнения.",
           "lc_fan_boost": "Усиление вентилятора СО: {}", "lc_pump_boost": "Усиление помпы СО: {}",
           "on": "вкл", "off": "выкл", "lc_primed": "Система охлаждения: цикл заполнения завершён"},
}

TRAY = {
    "en": {"open": "Open Control Center", "mode": "Mode", "boost": "Fan Boost", "kb": "Keyboard backlight",
           "lc": "Liquid cooler", "lc_auto": "Automatic", "lc_laptop": "Follow the laptop", "lc_low": "Low",
           "lc_medium": "Medium", "lc_high": "High", "lc_off": "Off", "lc_connect": "Connect", "lc_disconnect": "Disconnect",
           "lang": "Language", "autostart": "Start with Windows", "exit": "Exit", "offline": "no connection to the service",
           "custom": "Custom", "office": "Office", "gaming": "Gaming", "turbo": "Turbo",
           "not_connected": "not connected", "svc_down": "The Control Center service is not running",
           "svc_down_body": "Start it in Services (uwccd) or reinstall Control Center.",
           "upd_check": "Check for updates", "upd_install": "Install update {}", "github": "Project on GitHub",
           "upd_latest": "You have the latest version ({})", "upd_failed": "Update check failed"},
    "ru": {"open": "Открыть Control Center", "mode": "Режим", "boost": "Турбовентиляция", "kb": "Подсветка клавиатуры",
           "lc": "Система охлаждения", "lc_auto": "Автоматический", "lc_laptop": "Как у ноутбука", "lc_low": "Низкий",
           "lc_medium": "Средний", "lc_high": "Высокий", "lc_off": "Выкл", "lc_connect": "Подключить",
           "lc_disconnect": "Отключить", "lang": "Язык", "autostart": "Запускать вместе с Windows", "exit": "Выход",
           "offline": "нет связи со службой", "custom": "Пользовательский", "office": "Офисный", "gaming": "Игровой",
           "turbo": "Турбо", "not_connected": "не подключена", "svc_down": "Служба Control Center не запущена",
           "svc_down_body": "Запустите её в «Службах» (uwccd) или переустановите Control Center.",
           "upd_check": "Проверить обновления", "upd_install": "Установить обновление {}", "github": "Проект на GitHub",
           "upd_latest": "У вас последняя версия ({})", "upd_failed": "Не удалось проверить обновления"},
}


def T(lang, key, *a):
    s = TEXT.get(lang, TEXT["en"]).get(key) or TEXT["en"].get(key) or TRAY.get(lang, TRAY["en"]).get(key) \
        or TRAY["en"].get(key, key)
    return s.format(*a) if a else s


def describe(ev, osd_enabled, lang):
    """-> list of (title, body, critical) notifications for one service event."""
    t, d = ev.get("type"), ev.get("data") or {}
    out = []

    def n(title, body="", critical=False):
        out.append((title, body, critical))

    if t == "touchpad":
        if osd_enabled:
            n(T(lang, "touch_on") if d.get("enabled") else T(lang, "touch_off"))
    elif t == "lc":
        e = d.get("event")
        if e == "flow_fault":
            n(T(lang, "lc_flow"), T(lang, "lc_flow_body") + "\n" + T(lang, "lc_guard"), True)
        elif e == "disconnected" and d.get("unexpected"):
            n(T(lang, "lc_lost"), T(lang, "lc_lost_body"))
        elif not osd_enabled:
            pass
        elif e == "connected":
            n(T(lang, "lc_again") if d.get("again") else T(lang, "lc_conn"), d.get("name", ""))
        elif e == "boost":
            n(T(lang, "lc_fan_boost" if d.get("which") == "fan" else "lc_pump_boost", T(lang, "on" if d.get("on") else "off")))
        elif e == "prime_done":
            n(T(lang, "lc_primed"))
    elif t == "overheat":
        n(T(lang, "hot_" + d.get("sensor", "cpu"), d.get("temp")),
          T(lang, "hot_body_boost" if d.get("boost") else "hot_body", d.get("limit")), True)
    elif t == "overheat_boost":
        n(T(lang, "hot_boost"), T(lang, "hot_boost_body"), True)
    elif t == "update":
        n(T(lang, "upd", d.get("version", "")), T(lang, "upd_body"))
    elif t == "update_error":
        n(T(lang, "upd_err"), str(d.get("error", "")))
    elif not osd_enabled:
        pass
    elif t == "mode" and d.get("osd"):
        m = d.get("mode")
        n(T(lang, "mode3", (d.get("slot") or 0) + 1) if m == 3 else (T(lang, f"mode{m}") if m in (0, 1, 2) else ""))
    elif t == "fanboost" and d.get("osd"):
        n(T(lang, "boost_on" if d.get("on") else "boost_off"))
    elif t == "setting" and d.get("osd"):
        if "winkey_lock" in d:
            n(T(lang, "win_locked" if d["winkey_lock"] else "win_unlocked"))
        if "fn_lock" in d:
            n("Fn Lock" if d["fn_lock"] else "Fn UnLock")
    elif t == "kb_level" and d.get("osd"):
        n(T(lang, "kb_level", d.get("level", 0)))
    elif t == "reboot_required":
        n(T(lang, "reboot"), T(lang, "reboot_body"))
    return out
