# Инструменты анализа (для повторной генерации)

Использовались для восстановления протокола из Windows-пакета Control Center.

1. `innoextract -e ControlCenter_*.exe` — распаковать установщик (Inno Setup 6).
2. `python3 ildump.py GCUService.exe out.il` — IL-листинг с разрешёнными токенами.
3. `python3 lift.py GCUService.exe 'Регулярка::Метод'` — псевдокод C# (стековая машина → выражения).
4. `python3 enums.py GCUService.exe ProjectID RGBKB_Effect` — значения перечислений.
5. `python3 structdump.py GCUService.exe NVRAM_STRUCT` — раскладка структур.
6. `pyport.py` / `apport.py` — генерация `uwccd/lighting/oem/wkdcolor.py` и `oem/apfx.py`
   из псевдокода (пути к входным файлам заданы в начале скриптов).

Зависимости: `pip install dnfile dncil "pefile==2023.2.7"`.
